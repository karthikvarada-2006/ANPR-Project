"""Module 1: Synthetic City Traffic & ANPR Ground Truth Event Generator.

This script:
1. Generates NUM_VEHICLES with realistic Indian license plates (e.g. KA01AB1234) and vehicle types.
2. Schedules 1 to 3 trips per vehicle throughout the day with realistic morning & evening peak hours.
3. Computes shortest paths over the city road network with congestion-adjusted travel times.
4. Detects whenever a vehicle crosses a virtual ANPR camera node and logs a ground truth event:
   (plate, camera_id, timestamp, speed_kmh, heading_degrees, lane).
5. Saves all events chronologically to data/sim/ground_truth_events.csv.
"""

from __future__ import annotations

import datetime
import math
import random
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple

import networkx as nx
import osmnx as ox
import pandas as pd
from tqdm import tqdm

from simulator.config import (
    CAMERAS_PATH,
    CITY_NAME,
    GRAPH_PATH,
    GROUND_TRUTH_PATH,
    NUM_VEHICLES,
    OFF_PEAK_CONGESTION_FACTOR,
    PEAK_HOURS,
    RANDOM_SEED,
    SIM_DATE,
    VEHICLE_TYPES,
)


def generate_indian_plate(rnd: random.Random) -> str:
    """Generate a realistic Indian registration plate (e.g. KA01AB1234)."""
    # 85% Karnataka, 15% neighboring or major interstate
    states = ["KA", "KA", "KA", "KA", "KA", "KA", "MH", "TN", "DL", "AP"]
    state = rnd.choice(states)

    # Bangalore RTO districts: KA-01 to KA-05, KA-41, KA-50, KA-51, KA-53
    if state == "KA":
        rto = rnd.choice(["01", "02", "03", "04", "05", "41", "50", "51", "53"])
    else:
        rto = f"{rnd.randint(1, 15):02d}"

    # Letter series (avoid confusable letters O and I in series generation)
    letters = "ABCDEFGHJKLMNPQRSTUVWXYZ"
    series = f"{rnd.choice(letters)}{rnd.choice(letters)}"

    # 4-digit number
    num = f"{rnd.randint(1000, 9999)}"

    return f"{state}{rto}{series}{num}"


def compute_heading_degrees(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Compute heading angle in degrees (0 to 360, 0=North, 90=East)."""
    dlat = lat2 - lat1
    dlon = (lon2 - lon1) * math.cos(math.radians(lat1))
    angle = math.degrees(math.atan2(dlon, dlat))
    return round((angle + 360.0) % 360.0, 1)


def sample_departure_time(rnd: random.Random) -> datetime.datetime:
    """Sample departure time with bimodal morning (8-10) and evening (17-20) peaks."""
    # Peak probabilities:
    # 00-07: 5%, 08-10 (morning peak): 35%, 10-17: 20%, 17-20 (evening peak): 35%, 20-24: 5%
    bucket = rnd.random()
    if bucket < 0.35:
        # Morning peak: 08:00 - 10:00
        hour = rnd.randint(8, 9)
    elif bucket < 0.70:
        # Evening peak: 17:00 - 20:00
        hour = rnd.randint(17, 19)
    elif bucket < 0.90:
        # Daytime regular: 10:00 - 17:00
        hour = rnd.randint(10, 16)
    else:
        # Night / early morning
        hour = rnd.choice([6, 7, 20, 21, 22])

    minute = rnd.randint(0, 59)
    second = rnd.randint(0, 59)

    return datetime.datetime(
        SIM_DATE.year, SIM_DATE.month, SIM_DATE.day, hour, minute, second
    )


def get_congestion_factor(dt: datetime.datetime) -> float:
    """Return travel time multiplier based on time-of-day traffic congestion."""
    h = dt.hour
    if PEAK_HOURS["morning"]["start"] <= h < PEAK_HOURS["morning"]["end"]:
        return PEAK_HOURS["morning"]["congestion_factor"]
    elif PEAK_HOURS["evening"]["start"] <= h < PEAK_HOURS["evening"]["end"]:
        return PEAK_HOURS["evening"]["congestion_factor"]
    else:
        return OFF_PEAK_CONGESTION_FACTOR


def generate_traffic_events(force_regenerate: bool = False) -> pd.DataFrame:
    """Simulate vehicle fleet trips and extract true ANPR camera passages."""
    if GROUND_TRUTH_PATH.exists() and not force_regenerate:
        print(f"Loading existing ground truth events from {GROUND_TRUTH_PATH} ...")
        events_df = pd.read_csv(GROUND_TRUTH_PATH)
        print(f"Loaded {len(events_df):,} ground truth events.")
        return events_df

    rnd = random.Random(RANDOM_SEED)

    # 1. Load city road network
    print(f"Loading road network from: {GRAPH_PATH} ...")
    G = ox.load_graphml(GRAPH_PATH)

    # Extract largest strongly connected component to guarantee valid paths
    scc_nodes = list(max(nx.strongly_connected_components(G), key=len))
    print(f"Active road network has {len(scc_nodes):,} connected nodes.")

    # 2. Load cameras
    cameras_df = pd.read_csv(CAMERAS_PATH)
    camera_map: Dict[int, str] = dict(zip(cameras_df["node_id"], cameras_df["camera_id"]))
    camera_nodes: Set[int] = set(camera_map.keys())
    print(f"Loaded {len(camera_nodes)} virtual ANPR camera intersections.")

    # 3. Create vehicle fleet
    v_types = list(VEHICLE_TYPES.keys())
    v_weights = list(VEHICLE_TYPES.values())

    fleet = []
    generated_plates = set()
    for _ in range(NUM_VEHICLES):
        plate = generate_indian_plate(rnd)
        while plate in generated_plates:
            plate = generate_indian_plate(rnd)
        generated_plates.add(plate)

        v_type = rnd.choices(v_types, weights=v_weights, k=1)[0]
        fleet.append({"plate": plate, "type": v_type})

    print(f"Created fleet of {len(fleet):,} unique vehicles.")

    # 4. Generate trips and collect camera hits
    print(f"Simulating daily vehicle trips across {CITY_NAME}...")

    # Fast route pool using hub nodes
    num_hubs = min(80, len(scc_nodes))
    hubs = rnd.sample(scc_nodes, num_hubs)

    # Precompute path trees from hubs for ultra-fast Dijkstra lookups
    print("Pre-indexing hub path trees for high-speed routing...")
    hub_paths = {}
    for hub in tqdm(hubs, desc="Indexing hubs"):
        # Paths up to 25 minutes of travel time
        hub_paths[hub] = nx.single_source_dijkstra_path(
            G, hub, cutoff=1500.0, weight="travel_time"
        )

    all_events = []

    for vehicle in tqdm(fleet, desc="Simulating vehicles"):
        plate = vehicle["plate"]
        v_type = vehicle["type"]

        # 1 to 3 trips per vehicle per day
        num_trips = rnd.choices([1, 2, 3], weights=[0.40, 0.45, 0.15], k=1)[0]

        for _ in range(num_trips):
            hub = rnd.choice(hubs)
            available_dests = list(hub_paths[hub].keys())
            if len(available_dests) < 5:
                continue

            destination = rnd.choice(available_dests)
            path = hub_paths[hub][destination]

            # Ignore tiny trips with fewer than 6 road segments
            if len(path) < 6:
                continue

            # Departure time
            current_time = sample_departure_time(rnd)
            congestion = get_congestion_factor(current_time)

            # Traverse the path and advance time
            for i in range(len(path) - 1):
                u = path[i]
                v = path[i + 1]

                # Edge travel metrics
                edge_data = G.get_edge_data(u, v)
                if not edge_data:
                    continue
                # If multiple parallel edges exist, pick the first
                data = next(iter(edge_data.values())) if isinstance(edge_data, dict) else {}

                base_speed = float(data.get("speed_kmh", 30.0))
                length_m = float(data.get("length", 40.0))

                effective_speed = max(12.0, min(85.0, (base_speed / congestion) + rnd.gauss(0, 2.5)))
                speed_mps = (effective_speed * 1000.0) / 3600.0
                step_duration_sec = length_m / speed_mps if speed_mps > 0 else 2.0

                # Check if current node 'u' has an ANPR camera
                if u in camera_nodes:
                    cam_id = camera_map[u]

                    # Heading towards next node 'v'
                    u_lat, u_lon = G.nodes[u]["y"], G.nodes[u]["x"]
                    v_lat, v_lon = G.nodes[v]["y"], G.nodes[v]["x"]
                    heading = compute_heading_degrees(u_lat, u_lon, v_lat, v_lon)

                    # Lane assignment (1: inner, 2: center, 3: outer)
                    lane = rnd.choice([1, 2, 3])

                    all_events.append(
                        {
                            "plate": plate,
                            "camera_id": cam_id,
                            "timestamp": current_time.strftime("%Y-%m-%d %H:%M:%S"),
                            "speed_kmh": round(effective_speed, 1),
                            "heading_degrees": heading,
                            "lane": lane,
                            "vehicle_type": v_type,
                        }
                    )

                # Advance clock
                current_time += datetime.timedelta(seconds=step_duration_sec)

    # 5. Format and save
    events_df = pd.DataFrame(all_events)
    # Sort chronologically
    events_df = events_df.sort_values(by="timestamp").reset_index(drop=True)

    events_df.to_csv(GROUND_TRUTH_PATH, index=False)
    print(f"\nGenerated {len(events_df):,} ground-truth ANPR events.")
    print(f"Saved to: {GROUND_TRUTH_PATH}")

    return events_df


def main() -> int:
    generate_traffic_events()
    return 0


if __name__ == "__main__":
    sys.exit(main())
