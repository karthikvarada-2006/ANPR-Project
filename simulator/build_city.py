"""Module 1: City Road Network & Camera Placement Builder.

This script:
1. Downloads the drivable road network for CITY_NAME using OSMnx (cached to data/sim/city.graphml).
2. Computes edge travel times based on road highway categories.
3. Selects NUM_CAMERAS high-traffic intersection nodes with high betweenness/degree centrality,
   enforcing a minimum spatial separation of 300 meters.
4. Generates and saves data/sim/cameras.csv with camera metadata.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import Dict, List, Tuple

import networkx as nx
import osmnx as ox
import pandas as pd

from simulator.config import (
    CITY_NAME,
    DATA_SIM_DIR,
    DEFAULT_SPEED_KMH,
    FREE_FLOW_SPEEDS_KMH,
    GRAPH_PATH,
    CAMERAS_PATH,
    MIN_CAMERA_DISTANCE_METERS,
    NETWORK_RADIUS_METERS,
    NUM_CAMERAS,
    RANDOM_SEED,
)


def haversine_distance_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the great-circle distance between two GPS points in meters."""
    R = 6371000.0  # Earth's radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c


def assign_speeds_and_travel_times(G: nx.MultiDiGraph) -> None:
    """Assign free-flow speed (km/h) and travel time (seconds) to every edge."""
    for u, v, k, data in G.edges(keys=True, data=True):
        # Extract highway tag
        highway = data.get("highway", "unclassified")
        if isinstance(highway, list):
            highway = highway[0]
        highway = str(highway).lower()

        # Determine speed in km/h
        speed_kmh = FREE_FLOW_SPEEDS_KMH.get(highway, DEFAULT_SPEED_KMH)

        # Check for explicit maxspeed tag if available
        maxspeed = data.get("maxspeed")
        if maxspeed:
            try:
                if isinstance(maxspeed, list):
                    maxspeed = maxspeed[0]
                # Filter numeric speed
                numeric_speed = float("".join(c for c in str(maxspeed) if c.isdigit() or c == "."))
                if 10.0 <= numeric_speed <= 120.0:
                    speed_kmh = numeric_speed
            except (ValueError, TypeError):
                pass

        # Length in meters
        length_m = float(data.get("length", 50.0))

        # Travel time in seconds = distance (m) / speed (m/s)
        speed_mps = (speed_kmh * 1000.0) / 3600.0
        travel_time_sec = length_m / speed_mps if speed_mps > 0 else 1.0

        data["speed_kmh"] = speed_kmh
        data["travel_time"] = travel_time_sec


def get_road_name_for_node(G: nx.MultiDiGraph, node_id: int) -> str:
    """Extract clean intersection name from adjacent edge street names."""
    names = set()
    for _, _, data in G.out_edges(node_id, data=True):
        name = data.get("name")
        if name:
            if isinstance(name, list):
                names.update(name)
            else:
                names.add(str(name))
    for _, _, data in G.in_edges(node_id, data=True):
        name = data.get("name")
        if name:
            if isinstance(name, list):
                names.update(name)
            else:
                names.add(str(name))

    cleaned = [n for n in names if n and n != "nan" and not n.startswith("Unnamed")]
    if len(cleaned) >= 2:
        return f"{cleaned[0]} & {cleaned[1]} Junction"
    elif len(cleaned) == 1:
        return f"{cleaned[0]} Crossing"
    else:
        return f"Intersection #{node_id}"


def select_camera_locations(
    G: nx.MultiDiGraph, num_cameras: int = NUM_CAMERAS, min_dist: float = MIN_CAMERA_DISTANCE_METERS
) -> List[Dict]:
    """Select strategically spaced cameras at busy graph intersections."""
    print("Computing intersection connectivity & centrality...")
    degree_dict = dict(G.degree())

    # Filter to intersection candidates (degree >= 3)
    candidates = [n for n, deg in degree_dict.items() if deg >= 3]
    if len(candidates) < num_cameras:
        candidates = list(G.nodes())

    # Subsample for fast betweenness calculation
    k_samples = min(250, len(candidates))
    bc = nx.betweenness_centrality(G, k=k_samples, weight="travel_time", seed=RANDOM_SEED)

    # Rank candidates by combined centrality and connectivity score
    scored_candidates = []
    for node in candidates:
        score = (bc.get(node, 0.0) * 10000.0) + (degree_dict.get(node, 0) * 10.0)
        lat = G.nodes[node]["y"]
        lon = G.nodes[node]["x"]
        scored_candidates.append((score, node, lat, lon))

    scored_candidates.sort(key=lambda x: x[0], reverse=True)

    # Greedily pick top candidates separated by >= min_dist
    selected_cameras = []
    for score, node, lat, lon in scored_candidates:
        # Check distance against already picked cameras
        too_close = False
        for cam in selected_cameras:
            dist = haversine_distance_meters(lat, lon, cam["lat"], cam["lon"])
            if dist < min_dist:
                too_close = True
                break

        if not too_close:
            cam_idx = len(selected_cameras) + 1
            cam_id = f"CAM_{cam_idx:03d}"
            name = get_road_name_for_node(G, node)
            selected_cameras.append(
                {
                    "camera_id": cam_id,
                    "lat": round(lat, 6),
                    "lon": round(lon, 6),
                    "node_id": node,
                    "name": name,
                }
            )

        if len(selected_cameras) >= num_cameras:
            break

    # If density constraint was too strict, fill remaining without distance constraint
    if len(selected_cameras) < num_cameras:
        chosen_nodes = {c["node_id"] for c in selected_cameras}
        for score, node, lat, lon in scored_candidates:
            if node not in chosen_nodes:
                cam_idx = len(selected_cameras) + 1
                cam_id = f"CAM_{cam_idx:03d}"
                selected_cameras.append(
                    {
                        "camera_id": cam_id,
                        "lat": round(lat, 6),
                        "lon": round(lon, 6),
                        "node_id": node,
                        "name": get_road_name_for_node(G, node),
                    }
                )
                if len(selected_cameras) >= num_cameras:
                    break

    return selected_cameras


def build_city_network(force_download: bool = False) -> Tuple[nx.MultiDiGraph, pd.DataFrame]:
    """Load or download the city network, assign speeds, and place cameras."""
    DATA_SIM_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Load or download graph
    if GRAPH_PATH.exists() and not force_download:
        print(f"Loading cached road network from: {GRAPH_PATH} ...")
        G = ox.load_graphml(GRAPH_PATH)
        print(f"Loaded road network: {len(G)} nodes, {len(G.edges)} edges.")
    else:
        print(f"Geocoding '{CITY_NAME}'...")
        lat, lon = ox.geocode(CITY_NAME)
        print(f"Downloading drivable road network within {NETWORK_RADIUS_METERS}m of ({lat:.4f}, {lon:.4f})...")
        G = ox.graph_from_point(
            (lat, lon),
            dist=NETWORK_RADIUS_METERS,
            network_type="drive",
            simplify=True,
        )
        print(f"Road network downloaded: {len(G)} nodes, {len(G.edges)} edges.")

        # Assign travel times
        print("Computing road speeds and travel times...")
        assign_speeds_and_travel_times(G)

        # Save graph
        print(f"Saving road network to: {GRAPH_PATH} ...")
        ox.save_graphml(G, GRAPH_PATH)

    # Ensure travel times are populated
    first_edge = next(iter(G.edges(data=True)), None)
    if first_edge and "travel_time" not in first_edge[2]:
        assign_speeds_and_travel_times(G)

    # 2. Select camera locations
    if CAMERAS_PATH.exists() and not force_download:
        cameras_df = pd.read_csv(CAMERAS_PATH)
        if len(cameras_df) == NUM_CAMERAS:
            print(f"Loaded existing {len(cameras_df)} ANPR cameras from {CAMERAS_PATH}")
            return G, cameras_df

    cameras_list = select_camera_locations(G, num_cameras=NUM_CAMERAS, min_dist=MIN_CAMERA_DISTANCE_METERS)
    cameras_df = pd.DataFrame(cameras_list)
    cameras_df.to_csv(CAMERAS_PATH, index=False)
    print(f"Placed {len(cameras_df)} ANPR cameras -> Saved to {CAMERAS_PATH}")

    return G, cameras_df


def main() -> int:
    build_city_network()
    return 0


if __name__ == "__main__":
    sys.exit(main())
