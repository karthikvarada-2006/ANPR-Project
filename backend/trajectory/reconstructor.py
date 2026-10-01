"""Module 5: Multi-Camera ANPR Trajectory Reconstruction Engine.

This module connects discrete, disjoint camera sightings into continuous,
topologically valid vehicle travel trajectories along the urban road network.
"""

from __future__ import annotations

import datetime
import json
import math
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import networkx as nx
import osmnx as ox
import pandas as pd
from geoalchemy2.elements import WKTElement
from shapely.geometry import LineString, mapping
from tqdm import tqdm

# Ensure project root is in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.db import SessionLocal, engine
from backend.models import Camera, Event, Trajectory
from simulator.config import CAMERAS_PATH, GRAPH_PATH

# Maximum inactive duration (in seconds) before splitting into a new trip
TRIP_INACTIVITY_THRESHOLD_SECONDS = 1800.0  # 30 minutes
SPEED_LIMIT_KMH = 60.0
MAX_REALISTIC_SPEED_KMH = 160.0


class TrajectoryReconstructor:
    """Reconstructs continuous vehicle paths from discrete ANPR camera observations."""

    def __init__(self, graph_path: Path = GRAPH_PATH, cameras_path: Path = CAMERAS_PATH):
        self.graph_path = graph_path
        self.cameras_path = cameras_path
        self.G: Optional[nx.MultiDiGraph] = None
        self.camera_node_map: Dict[str, int] = {}
        self.camera_coord_map: Dict[str, Tuple[float, float]] = {}

        self._load_network_and_cameras()

    def _load_network_and_cameras(self) -> None:
        """Load OpenStreetMap road graph and camera metadata."""
        if not self.graph_path.exists():
            raise FileNotFoundError(f"Road network graph not found at {self.graph_path}")

        print(f"Loading road network from: {self.graph_path} ...")
        self.G = ox.load_graphml(self.graph_path)

        if not self.cameras_path.exists():
            raise FileNotFoundError(f"Cameras registry not found at {self.cameras_path}")

        cams_df = pd.read_csv(self.cameras_path)
        for _, row in cams_df.iterrows():
            cid = str(row["camera_id"])
            nid = int(row["node_id"])
            lat = float(row["lat"])
            lon = float(row["lon"])
            self.camera_node_map[cid] = nid
            self.camera_coord_map[cid] = (lat, lon)

        print(f"Initialized reconstructor with {len(self.G)} road nodes and {len(self.camera_node_map)} cameras.")

    def reconstruct_vehicle_trips(
        self, sightings: List[Dict]
    ) -> List[Dict]:
        """Group sequential sightings into trips and reconstruct continuous road paths.

        Each sighting dict must have: 'camera_id', 'timestamp', 'speed_kmh'.
        """
        if len(sightings) < 2:
            return []

        # Sort chronologically
        sorted_sightings = sorted(
            sightings, key=lambda s: s["timestamp"] if isinstance(s["timestamp"], datetime.datetime) else pd.to_datetime(s["timestamp"])
        )

        # 1. Split into distinct trips if time gap between sightings > threshold
        trips = []
        current_trip = [sorted_sightings[0]]

        for i in range(1, len(sorted_sightings)):
            prev_t = sorted_sightings[i - 1]["timestamp"]
            curr_t = sorted_sightings[i]["timestamp"]
            if isinstance(prev_t, str):
                prev_t = pd.to_datetime(prev_t).to_pydatetime()
            if isinstance(curr_t, str):
                curr_t = pd.to_datetime(curr_t).to_pydatetime()

            delta = (curr_t - prev_t).total_seconds()
            if delta > TRIP_INACTIVITY_THRESHOLD_SECONDS:
                if len(current_trip) >= 2:
                    trips.append(current_trip)
                current_trip = [sorted_sightings[i]]
            else:
                current_trip.append(sorted_sightings[i])

        if len(current_trip) >= 2:
            trips.append(current_trip)

        # 2. Reconstruct graph path for each trip
        reconstructed_trajectories = []

        for trip in trips:
            start_t = trip[0]["timestamp"]
            end_t = trip[-1]["timestamp"]
            if isinstance(start_t, str):
                start_t = pd.to_datetime(start_t).to_pydatetime()
            if isinstance(end_t, str):
                end_t = pd.to_datetime(end_t).to_pydatetime()

            total_duration = (end_t - start_t).total_seconds()
            if total_duration <= 0:
                continue

            full_coords: List[Tuple[float, float]] = []  # (lon, lat)
            total_distance_m = 0.0
            camera_sequence = []
            segment_anomalies = []

            for i in range(len(trip) - 1):
                s1 = trip[i]
                s2 = trip[i + 1]

                c1, c2 = s1["camera_id"], s2["camera_id"]
                camera_sequence.append(c1)

                t1 = s1["timestamp"] if isinstance(s1["timestamp"], datetime.datetime) else pd.to_datetime(s1["timestamp"]).to_pydatetime()
                t2 = s2["timestamp"] if isinstance(s2["timestamp"], datetime.datetime) else pd.to_datetime(s2["timestamp"]).to_pydatetime()
                delta_sec = max(1.0, (t2 - t1).total_seconds())

                u1 = self.camera_node_map.get(c1)
                u2 = self.camera_node_map.get(c2)

                if u1 is None or u2 is None:
                    continue

                # Shortest road path between camera nodes
                try:
                    path_nodes = nx.shortest_path(self.G, u1, u2, weight="travel_time")
                except (nx.NetworkXNoPath, nx.NodeNotFound):
                    # Fallback straight-line segment
                    lat1, lon1 = self.camera_coord_map[c1]
                    lat2, lon2 = self.camera_coord_map[c2]
                    dist_est = ox.distance.great_circle(lat1, lon1, lat2, lon2)
                    total_distance_m += dist_est
                    full_coords.extend([(lon1, lat1), (lon2, lat2)])
                    continue

                # Collect edge coordinates and distance
                seg_dist = 0.0
                seg_coords = []
                for k in range(len(path_nodes) - 1):
                    nu = path_nodes[k]
                    nv = path_nodes[k + 1]
                    edge_dict = self.G.get_edge_data(nu, nv)
                    if edge_dict:
                        edge_data = next(iter(edge_dict.values()))
                        seg_dist += float(edge_data.get("length", 40.0))

                        if "geometry" in edge_data:
                            for x, y in edge_data["geometry"].coords:
                                seg_coords.append((x, y))
                        else:
                            seg_coords.append((self.G.nodes[nu]["x"], self.G.nodes[nu]["y"]))

                # Add final node coord
                last_node = path_nodes[-1]
                seg_coords.append((self.G.nodes[last_node]["x"], self.G.nodes[last_node]["y"]))

                total_distance_m += seg_dist
                full_coords.extend(seg_coords)

                # Segment speed check
                speed_mps = seg_dist / delta_sec
                seg_speed_kmh = (speed_mps * 3600.0) / 1000.0

                if seg_speed_kmh > MAX_REALISTIC_SPEED_KMH:
                    segment_anomalies.append(
                        {
                            "type": "IMPOSSIBLE_SPEED",
                            "camera_1": c1,
                            "camera_2": c2,
                            "speed_kmh": round(seg_speed_kmh, 1),
                            "time_delta_sec": delta_sec,
                        }
                    )
                elif seg_speed_kmh > SPEED_LIMIT_KMH:
                    segment_anomalies.append(
                        {
                            "type": "SECTION_SPEEDING",
                            "camera_1": c1,
                            "camera_2": c2,
                            "speed_kmh": round(seg_speed_kmh, 1),
                        }
                    )

            camera_sequence.append(trip[-1]["camera_id"])

            # Remove consecutive duplicate coordinates
            dedup_coords = []
            for pt in full_coords:
                if not dedup_coords or dedup_coords[-1] != pt:
                    dedup_coords.append(pt)

            if len(dedup_coords) < 2:
                continue

            overall_speed_kmh = (
                ((total_distance_m / total_duration) * 3600.0) / 1000.0
                if total_duration > 0
                else 0.0
            )

            # Create Shapely LineString geometry
            line_geom = LineString(dedup_coords)

            reconstructed_trajectories.append(
                {
                    "start_time": start_t,
                    "end_time": end_t,
                    "duration_seconds": round(total_duration, 1),
                    "total_distance_meters": round(total_distance_m, 1),
                    "avg_speed_kmh": round(overall_speed_kmh, 1),
                    "num_sightings": len(trip),
                    "camera_sequence": camera_sequence,
                    "coordinates": dedup_coords,
                    "line_geom": line_geom,
                    "anomalies": segment_anomalies,
                }
            )

        return reconstructed_trajectories

    def reconstruct_from_dataframe(
        self, events_df: pd.DataFrame, max_vehicles: Optional[int] = None
    ) -> List[Dict]:
        """Reconstruct trajectories for all or top active vehicles in an events DataFrame."""
        plate_groups = events_df.groupby("plate")
        # Rank by activity
        active_plates = plate_groups.size().sort_values(ascending=False)
        if max_vehicles:
            active_plates = active_plates.head(max_vehicles)

        print(f"Reconstructing paths for {len(active_plates)} active vehicles...")

        results = []
        for plate in tqdm(active_plates.index, desc="Reconstructing trajectories"):
            sub_df = plate_groups.get_group(plate)
            sightings = sub_df.to_dict("records")
            trajs = self.reconstruct_vehicle_trips(sightings)
            for t in trajs:
                t["plate"] = plate
                results.append(t)

        print(f"Successfully reconstructed {len(results):,} complete journey trajectories.")
        return results

    def save_trajectories_to_db(self, trajectories: List[Dict]) -> int:
        """Persist reconstructed trajectories to the PostgreSQL/PostGIS database."""
        session = SessionLocal()
        saved = 0
        try:
            for t in trajectories:
                wkt_str = t["line_geom"].wkt
                traj_orm = Trajectory(
                    plate=t["plate"],
                    start_time=t["start_time"],
                    end_time=t["end_time"],
                    duration_seconds=t["duration_seconds"],
                    total_distance_meters=t["total_distance_meters"],
                    avg_speed_kmh=t["avg_speed_kmh"],
                    num_sightings=t["num_sightings"],
                    camera_sequence=t["camera_sequence"],
                    geom=WKTElement(wkt_str, srid=4326),
                )
                session.add(traj_orm)
                saved += 1
            session.commit()
            print(f"Persisted {saved} trajectories to PostGIS 'trajectories' table.")
        except Exception as exc:
            session.rollback()
            print(f"[NOTE] Database persistence skipped or failed: {exc}")
        finally:
            session.close()
        return saved

    def export_geojson(self, trajectories: List[Dict], output_path: Path) -> Path:
        """Export trajectories as standard GeoJSON FeatureCollection."""
        features = []
        for idx, t in enumerate(trajectories):
            feature = {
                "type": "Feature",
                "id": idx + 1,
                "geometry": mapping(t["line_geom"]),
                "properties": {
                    "plate": t["plate"],
                    "start_time": t["start_time"].isoformat(),
                    "end_time": t["end_time"].isoformat(),
                    "duration_seconds": t["duration_seconds"],
                    "total_distance_meters": t["total_distance_meters"],
                    "avg_speed_kmh": t["avg_speed_kmh"],
                    "num_sightings": t["num_sightings"],
                    "camera_sequence": t["camera_sequence"],
                    "anomalies": t.get("anomalies", []),
                },
            }
            features.append(feature)

        geojson_data = {
            "type": "FeatureCollection",
            "features": features,
        }

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(geojson_data, f, indent=2)

        print(f"Exported {len(features)} trajectories to GeoJSON: {output_path}")
        return output_path


def main() -> int:
    events_csv = ROOT_DIR / "data" / "sim" / "events.csv"
    if not events_csv.exists():
        print(f"[ERROR] Events file not found at {events_csv}. Run simulator first.")
        return 1

    df = pd.read_csv(events_csv)
    reconstructor = TrajectoryReconstructor()
    # Reconstruct for top 50 active vehicles for demonstration
    trajectories = reconstructor.reconstruct_from_dataframe(df, max_vehicles=50)

    # Export to GeoJSON
    geojson_path = ROOT_DIR / "data" / "sim" / "sample_trajectories.geojson"
    reconstructor.export_geojson(trajectories, geojson_path)

    # Save to DB if connected
    reconstructor.save_trajectories_to_db(trajectories)

    return 0


if __name__ == "__main__":
    sys.exit(main())
