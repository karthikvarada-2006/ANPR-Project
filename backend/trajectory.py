"""Module 5: Multi-Camera ANPR Trajectory Reconstruction Engine.

Reconstructs continuous vehicle trips from discrete camera sightings,
applies precomputed OpenStreetMap shortest-path routing, performs speed feasibility validation,
detects cloned plates / impossible hops, and supports fuzzy plate queries.
"""

from __future__ import annotations

import datetime
import math
import pickle
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import networkx as nx
import osmnx as ox
import pandas as pd
from sqlalchemy.orm import Session

# Ensure project root is in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.db import SessionLocal
from backend.models import Camera, Event
from backend.plate_utils import find_similar_plates, heading_to_compass, normalize_plate
from simulator.config import CAMERAS_PATH, DATA_SIM_DIR, GRAPH_PATH

# Configuration constants
MAX_IMPOSSIBLE_SPEED_KMH = 120.0  # Urban impossible speed threshold (cloned plate flag)
SAME_CAMERA_DEDUP_SECONDS = 60.0  # Drop duplicate reads at same camera within 60s
TRIP_INACTIVITY_THRESHOLD_SECONDS = 1800.0  # 30 minutes inactivity splits trips
CAMERA_PATHS_PATH = DATA_SIM_DIR / "camera_paths.pkl"

# Singleton caches
_ROAD_GRAPH: Optional[nx.MultiDiGraph] = None
_CAMERAS_INFO: Optional[Dict[str, Dict[str, Any]]] = None
_CAMERA_PATHS_CACHE: Optional[Dict[Tuple[str, str], Tuple[float, float, List[List[float]]]]] = None


def get_road_graph() -> nx.MultiDiGraph:
    """Load and cache the OpenStreetMap road graph."""
    global _ROAD_GRAPH
    if _ROAD_GRAPH is None:
        if not GRAPH_PATH.exists():
            raise FileNotFoundError(f"Road network graph not found at {GRAPH_PATH}")
        _ROAD_GRAPH = ox.load_graphml(GRAPH_PATH)
    return _ROAD_GRAPH


def get_cameras_info(db: Optional[Session] = None) -> Dict[str, Dict[str, Any]]:
    """Load and cache camera metadata (coordinates, OSM node_id, name)."""
    global _CAMERAS_INFO
    if _CAMERAS_INFO is not None:
        return _CAMERAS_INFO

    cams: Dict[str, Dict[str, Any]] = {}

    # Try loading from database first
    close_session = False
    if db is None:
        db = SessionLocal()
        close_session = True

    try:
        db_cams = db.query(Camera).all()
        if db_cams:
            for c in db_cams:
                cams[c.camera_id] = {
                    "camera_id": c.camera_id,
                    "name": c.name,
                    "lat": float(c.lat),
                    "lon": float(c.lon),
                    "node_id": int(c.node_id) if c.node_id is not None else None,
                }
    finally:
        if close_session:
            db.close()

    # Fallback / supplement from cameras.csv if needed
    if not cams and CAMERAS_PATH.exists():
        df = pd.read_csv(CAMERAS_PATH)
        for _, row in df.iterrows():
            cid = str(row["camera_id"])
            cams[cid] = {
                "camera_id": cid,
                "name": str(row["name"]),
                "lat": float(row["lat"]),
                "lon": float(row["lon"]),
                "node_id": int(row["node_id"]),
            }

    _CAMERAS_INFO = cams
    return _CAMERAS_INFO


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Compute great-circle distance between two GPS coordinates in kilometers."""
    R = 6371.0  # Earth radius in kilometers
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2.0) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(max(0.0, 1.0 - a)))
    return R * c


def precompute_camera_paths() -> Dict[Tuple[str, str], Tuple[float, float, List[List[float]]]]:
    """Precompute shortest-path distance, travel time, and route geometry between every camera pair.

    Saves results to data/sim/camera_paths.pkl for instant retrieval.
    """
    cams = get_cameras_info()
    G = get_road_graph()

    cam_nodes = {cid: c["node_id"] for cid, c in cams.items() if c.get("node_id") is not None}
    cam_coords = {cid: (c["lat"], c["lon"]) for cid, c in cams.items()}

    camera_paths: Dict[Tuple[str, str], Tuple[float, float, List[List[float]]]] = {}

    for c1, u in cam_nodes.items():
        lengths, paths = nx.single_source_dijkstra(G, u, weight="travel_time")
        lat1, lon1 = cam_coords[c1]

        for c2, v in cam_nodes.items():
            lat2, lon2 = cam_coords[c2]

            if c1 == c2:
                camera_paths[(c1, c2)] = (0.0, 0.0, [[round(lat1, 6), round(lon1, 6)]])
                continue

            if v in paths:
                path_nodes = paths[v]
                total_dist_m = 0.0
                total_time_s = lengths[v]
                coords: List[List[float]] = []

                for i in range(len(path_nodes) - 1):
                    nu, nv = path_nodes[i], path_nodes[i + 1]
                    edge_dict = G.get_edge_data(nu, nv)
                    if not edge_dict:
                        continue
                    best_edge = min(
                        edge_dict.values(),
                        key=lambda e: float(e.get("travel_time", e.get("length", 40.0))),
                    )
                    total_dist_m += float(best_edge.get("length", 40.0))
                    if "geometry" in best_edge:
                        for x, y in best_edge["geometry"].coords:
                            coords.append([round(y, 6), round(x, 6)])
                    else:
                        coords.append([round(G.nodes[nu]["y"], 6), round(G.nodes[nu]["x"], 6)])

                last_node = path_nodes[-1]
                coords.append([round(G.nodes[last_node]["y"], 6), round(G.nodes[last_node]["x"], 6)])

                dedup_coords: List[List[float]] = []
                for pt in coords:
                    if not dedup_coords or dedup_coords[-1] != pt:
                        dedup_coords.append(pt)

                dist_km = round(total_dist_m / 1000.0, 3)
                camera_paths[(c1, c2)] = (dist_km, round(total_time_s, 1), dedup_coords)
            else:
                # Fallback to straight line
                d = round(haversine_km(lat1, lon1, lat2, lon2), 3)
                time_s = round((d / 30.0) * 3600.0, 1)
                camera_paths[(c1, c2)] = (
                    d,
                    time_s,
                    [[round(lat1, 6), round(lon1, 6)], [round(lat2, 6), round(lon2, 6)]],
                )

    DATA_SIM_DIR.mkdir(parents=True, exist_ok=True)
    with open(CAMERA_PATHS_PATH, "wb") as f:
        pickle.dump(camera_paths, f, protocol=pickle.HIGHEST_PROTOCOL)

    return camera_paths


def get_camera_paths(force_rebuild: bool = False) -> Dict[Tuple[str, str], Tuple[float, float, List[List[float]]]]:
    """Load precomputed camera paths from data/sim/camera_paths.pkl.

    Automatically rebuilds if the file is missing or if city.graphml is newer.
    """
    global _CAMERA_PATHS_CACHE
    if _CAMERA_PATHS_CACHE is not None and not force_rebuild:
        return _CAMERA_PATHS_CACHE

    rebuild_needed = force_rebuild or (not CAMERA_PATHS_PATH.exists())
    if not rebuild_needed and GRAPH_PATH.exists():
        if GRAPH_PATH.stat().st_mtime > CAMERA_PATHS_PATH.stat().st_mtime:
            rebuild_needed = True

    if rebuild_needed:
        _CAMERA_PATHS_CACHE = precompute_camera_paths()
        return _CAMERA_PATHS_CACHE

    try:
        with open(CAMERA_PATHS_PATH, "rb") as f:
            _CAMERA_PATHS_CACHE = pickle.load(f)
        return _CAMERA_PATHS_CACHE
    except Exception:
        _CAMERA_PATHS_CACHE = precompute_camera_paths()
        return _CAMERA_PATHS_CACHE


def get_hop_route(
    c1_id: str,
    c2_id: str,
    c1_info: Dict[str, Any],
    c2_info: Dict[str, Any],
) -> Tuple[float, List[List[float]]]:
    """Retrieve precomputed shortest path distance in km and route geometry coordinates."""
    paths = get_camera_paths()
    if (c1_id, c2_id) in paths:
        dist_km, _, coords = paths[(c1_id, c2_id)]
        return dist_km, coords

    # Fallback to straight-line great-circle distance
    lat1, lon1 = c1_info["lat"], c1_info["lon"]
    lat2, lon2 = c2_info["lat"], c2_info["lon"]
    dist_km = haversine_km(lat1, lon1, lat2, lon2)
    coords = [[round(lat1, 6), round(lon1, 6)], [round(lat2, 6), round(lon2, 6)]]
    return dist_km, coords


def get_trajectory(
    plate: str,
    start: Optional[Union[str, datetime.datetime]] = None,
    end: Optional[Union[str, datetime.datetime]] = None,
    fuzzy: bool = True,
    db: Optional[Session] = None,
    source: Optional[str] = "sim",
) -> Dict[str, Any]:
    """Retrieve and reconstruct the trajectory of a vehicle across all cameras.

    Args:
        plate: Target license plate query (e.g. 'KA01AB1234').
        start: Optional start timestamp filter.
        end: Optional end timestamp filter.
        fuzzy: If True, search visually confusable plate variants (O/0, B/8, etc.).
        db: Optional database session scope.
        source: Optional source filter ('sim', 'video', 'image', or None for all). Default is 'sim'.

    Returns:
        Dictionary containing trips, points, route geometry, distance, duration,
        and flagged impossible/cloned plate hops.
    """
    norm_plate = normalize_plate(plate)
    if not norm_plate:
        return {
            "plate": "",
            "matched_plates": [],
            "total_trips": 0,
            "trips": [],
            "flagged_hops": [],
        }

    close_session = False
    if db is None:
        db = SessionLocal()
        close_session = True

    try:
        cams_info = get_cameras_info(db=db)

        # 1. Gather candidate plate variants
        matched_plates: List[str] = []
        if fuzzy:
            similar = find_similar_plates(norm_plate, max_distance=1.0, db=db, source=source)
            matched_plates = [m.plate for m in similar]
            if norm_plate not in matched_plates:
                matched_plates.insert(0, norm_plate)
        else:
            matched_plates = [norm_plate]

        # 2. Query events from database
        query = (
            db.query(Event)
            .filter(Event.plate.in_(matched_plates))
        )
        if source is not None:
            query = query.filter(Event.source == source)

        if start is not None:
            if isinstance(start, str):
                start = pd.to_datetime(start).to_pydatetime()
            query = query.filter(Event.timestamp >= start)

        if end is not None:
            if isinstance(end, str):
                end = pd.to_datetime(end).to_pydatetime()
            query = query.filter(Event.timestamp <= end)

        # Order chronologically
        events = query.order_by(Event.timestamp.asc(), Event.id.asc()).all()

        if not events:
            return {
                "plate": norm_plate,
                "matched_plates": matched_plates,
                "total_trips": 0,
                "trips": [],
                "flagged_hops": [],
            }

        # 3. Drop duplicate reads at the same camera within 60 seconds
        dedup_events: List[Event] = []
        for ev in events:
            if not dedup_events:
                dedup_events.append(ev)
                continue
            prev_ev = dedup_events[-1]
            dt = (ev.timestamp - prev_ev.timestamp).total_seconds()
            if ev.camera_id == prev_ev.camera_id and dt <= SAME_CAMERA_DEDUP_SECONDS:
                continue
            dedup_events.append(ev)

        if not dedup_events:
            return {
                "plate": norm_plate,
                "matched_plates": matched_plates,
                "total_trips": 0,
                "trips": [],
                "flagged_hops": [],
            }

        # 4. Split trips on inactivity (> 30 min) or impossible hops (> 120 km/h or dt <= 0)
        trips_data: List[Dict[str, Any]] = []
        all_flagged_hops: List[Dict[str, Any]] = []

        current_points: List[Dict[str, Any]] = []
        current_hops: List[Tuple[float, List[List[float]]]] = []
        current_trip_flagged: List[Dict[str, Any]] = []

        def make_point_dict(ev: Event) -> Dict[str, Any]:
            c_info = cams_info.get(ev.camera_id, {})
            hdg = float(ev.heading_degrees) if ev.heading_degrees is not None else 0.0
            spd = float(ev.speed_kmh) if ev.speed_kmh is not None else 0.0
            cnf = float(ev.ocr_confidence) if ev.ocr_confidence is not None else 1.0
            return {
                "timestamp": ev.timestamp,
                "camera_id": ev.camera_id,
                "name": c_info.get("name", f"Camera {ev.camera_id}"),
                "lat": float(c_info.get("lat", 0.0)),
                "lon": float(c_info.get("lon", 0.0)),
                "heading": round(hdg, 1),
                "compass": heading_to_compass(hdg),
                "speed_kmh": round(spd, 1),
                "confidence": round(cnf, 3),
                "plate_read": ev.plate,
            }

        def finalize_trip():
            nonlocal current_points, current_hops, current_trip_flagged
            if not current_points:
                return

            # Ensure strict point deduplication within trip
            dedup_trip_points: List[Dict[str, Any]] = []
            seen_pts = set()
            for p in current_points:
                pt_key = (p["camera_id"], str(p["timestamp"]))
                if pt_key not in seen_pts:
                    seen_pts.add(pt_key)
                    dedup_trip_points.append(p)

            if not dedup_trip_points:
                current_points = []
                current_hops = []
                current_trip_flagged = []
                return

            t_start = dedup_trip_points[0]["timestamp"]
            t_end = dedup_trip_points[-1]["timestamp"]
            duration = max(0.0, (t_end - t_start).total_seconds())

            trip_distance_km = sum(h[0] for h in current_hops)

            # Build concatenated route geometry
            full_geom: List[List[float]] = []
            if current_hops:
                for _, hop_coords in current_hops:
                    for pt in hop_coords:
                        if not full_geom or full_geom[-1] != pt:
                            full_geom.append(pt)
            else:
                full_geom = [[dedup_trip_points[0]["lat"], dedup_trip_points[0]["lon"]]]

            avg_speed = (
                (trip_distance_km / (duration / 3600.0))
                if duration > 0 and trip_distance_km > 0
                else 0.0
            )

            trips_data.append({
                "trip_id": len(trips_data) + 1,
                "start_time": t_start.isoformat() if hasattr(t_start, "isoformat") else str(t_start),
                "end_time": t_end.isoformat() if hasattr(t_end, "isoformat") else str(t_end),
                "duration_seconds": round(duration, 1),
                "total_distance_km": round(trip_distance_km, 3),
                "avg_speed_kmh": round(avg_speed, 1),
                "num_sightings": len(dedup_trip_points),
                "points": dedup_trip_points,
                "route_geometry": full_geom,
                "flagged_hops": current_trip_flagged,
            })

            current_points = []
            current_hops = []
            current_trip_flagged = []

        # Initialize with first event
        current_points.append(make_point_dict(dedup_events[0]))

        for i in range(1, len(dedup_events)):
            prev_pt = current_points[-1]
            curr_ev = dedup_events[i]
            curr_pt = make_point_dict(curr_ev)

            # Guard against appending duplicate sighting
            if (
                curr_pt["camera_id"] == prev_pt["camera_id"]
                and curr_pt["timestamp"] == prev_pt["timestamp"]
            ):
                continue

            dt = (curr_pt["timestamp"] - prev_pt["timestamp"]).total_seconds()

            # Rule A: Inactivity gap > 30 minutes -> split into new trip
            if dt > TRIP_INACTIVITY_THRESHOLD_SECONDS:
                finalize_trip()
                current_points.append(curr_pt)
                continue

            # Rule B: Compute shortest road path and implied speed between sightings
            c1_info = cams_info.get(
                prev_pt["camera_id"],
                {"lat": prev_pt["lat"], "lon": prev_pt["lon"], "node_id": None},
            )
            c2_info = cams_info.get(
                curr_pt["camera_id"],
                {"lat": curr_pt["lat"], "lon": curr_pt["lon"], "node_id": None},
            )

            hop_dist_km, hop_coords = get_hop_route(
                prev_pt["camera_id"],
                curr_pt["camera_id"],
                c1_info,
                c2_info,
            )

            # Implied speed check
            if dt <= 0:
                implied_speed = float("inf")
                is_impossible = True
            else:
                implied_speed = hop_dist_km / (dt / 3600.0)
                is_impossible = (implied_speed > MAX_IMPOSSIBLE_SPEED_KMH)

            if is_impossible:
                flagged_hop = {
                    "from_camera": prev_pt["camera_id"],
                    "to_camera": curr_pt["camera_id"],
                    "from_camera_name": prev_pt["name"],
                    "to_camera_name": curr_pt["name"],
                    "from_timestamp": prev_pt["timestamp"].isoformat() if hasattr(prev_pt["timestamp"], "isoformat") else str(prev_pt["timestamp"]),
                    "to_timestamp": curr_pt["timestamp"].isoformat() if hasattr(curr_pt["timestamp"], "isoformat") else str(curr_pt["timestamp"]),
                    "time_delta_seconds": round(dt, 1),
                    "distance_km": round(hop_dist_km, 3),
                    "implied_speed_kmh": round(implied_speed, 1) if dt > 0 else 999.0,
                    "reason": "IMPOSSIBLE",
                }
                all_flagged_hops.append(flagged_hop)
                current_trip_flagged.append(flagged_hop)

                # Hop is impossible -> finish current trip and start new segment (protects against cloned plates)
                finalize_trip()
                current_points.append(curr_pt)
            else:
                # Valid hop
                current_points.append(curr_pt)
                current_hops.append((hop_dist_km, hop_coords))

        finalize_trip()

        return {
            "plate": norm_plate,
            "matched_plates": matched_plates,
            "total_trips": len(trips_data),
            "trips": trips_data,
            "flagged_hops": all_flagged_hops,
        }
    finally:
        if close_session:
            db.close()
