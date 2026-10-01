"""Module 1: Anomaly and Security Scenario Injection.

This script injects realistic urban surveillance edge cases:
1. Generates a vehicle security blacklist of 10 plates -> data/sim/blacklist.csv
   (plates are selected from active vehicles so downstream alert modules trigger).
2. Injects 5 "cloned plate" anomalies (same plate observed at two distant cameras
   at nearly the same time, implying a physically impossible speed like >200 km/h).
3. Labels the ground truth anomalies in data/sim/anomalies.csv and inserts the anomalous
   sightings into data/sim/events.csv.
"""

from __future__ import annotations

import datetime
import math
import random
import sys
from pathlib import Path
from typing import Dict, List, Tuple

import pandas as pd

from simulator.config import (
    ANOMALIES_PATH,
    BLACKLIST_PATH,
    CAMERAS_PATH,
    EVENTS_PATH,
    GROUND_TRUTH_PATH,
    RANDOM_SEED,
    SIM_DATE,
)


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distance in meters between two lat/lon points."""
    R = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def create_blacklist(gt_df: pd.DataFrame, rnd: random.Random) -> pd.DataFrame:
    """Choose 10 active vehicle plates from TRUE ground truth plates to include in the security blacklist."""
    unique_plates = gt_df["plate"].dropna().unique().tolist()
    if len(unique_plates) < 10:
        raise ValueError("Not enough plates in ground truth to generate 10 blacklist entries.")

    selected_plates = rnd.sample(unique_plates, 10)

    reasons = [
        "Reported stolen vehicle (FIR #BLR-2026-891)",
        "Wanted in armed robbery investigation",
        "Vehicle involved in hit-and-run incident",
        "Suspended registration & counterfeit plates suspected",
        "Court impound warrant issued",
        "Commercial tax evasion & seizure order",
        "Stolen luxury sedan alert (INTER-STATE)",
        "Vehicle tagged in repeat traffic signal evasion",
        "Multiple reckless driving & speed violations",
        "High-priority security surveillance target",
    ]

    records = []
    base_date = SIM_DATE - datetime.timedelta(days=14)

    for i, plate in enumerate(selected_plates):
        added = base_date + datetime.timedelta(days=rnd.randint(0, 10))
        records.append(
            {
                "plate": plate,
                "reason": reasons[i % len(reasons)],
                "added_date": added.strftime("%Y-%m-%d"),
                "status": "ACTIVE",
            }
        )

    blacklist_df = pd.DataFrame(records)
    blacklist_df.to_csv(BLACKLIST_PATH, index=False)
    print(f"Created security blacklist with {len(blacklist_df)} TRUE plates -> {BLACKLIST_PATH}")
    return blacklist_df


def inject_cloned_plates(
    events_df: pd.DataFrame, gt_df: pd.DataFrame, cameras_df: pd.DataFrame, rnd: random.Random
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Inject 5 cloned plate anomalies with impossible travel speeds."""
    # Find camera pairs that are far apart (> 3500 meters)
    cam_coords = {
        row["camera_id"]: (row["lat"], row["lon"]) for _, row in cameras_df.iterrows()
    }
    cam_ids = list(cam_coords.keys())

    far_pairs = []
    for i in range(len(cam_ids)):
        for j in range(i + 1, len(cam_ids)):
            c1, c2 = cam_ids[i], cam_ids[j]
            lat1, lon1 = cam_coords[c1]
            lat2, lon2 = cam_coords[c2]
            d = haversine_distance(lat1, lon1, lat2, lon2)
            if d >= 3500.0:
                far_pairs.append((c1, c2, d))

    if not far_pairs:
        # Fallback to any two cameras
        c1, c2 = cam_ids[0], cam_ids[-1]
        far_pairs.append((c1, c2, 3000.0))

    # Pick 5 candidate plates from TRUE ground truth plates
    existing_plates = gt_df["plate"].dropna().unique().tolist()
    cloned_plates = rnd.sample(existing_plates, 5)

    anomalies = []
    new_event_rows = []

    for i, plate in enumerate(cloned_plates):
        c1, c2, dist_m = rnd.choice(far_pairs)

        # Baseline timestamp during daytime (between 10:00 and 16:00)
        hour = 10 + i
        minute = rnd.randint(10, 45)
        sec = rnd.randint(0, 30)

        t1 = datetime.datetime(
            SIM_DATE.year, SIM_DATE.month, SIM_DATE.day, hour, minute, sec
        )
        # Sighting at second camera only 45 to 90 seconds later
        delta_sec = rnd.randint(45, 90)
        t2 = t1 + datetime.timedelta(seconds=delta_sec)

        # Implied speed = distance / time in km/h
        speed_mps = dist_m / delta_sec
        implied_speed_kmh = round((speed_mps * 3600.0) / 1000.0, 1)

        # Anomaly entry
        anomalies.append(
            {
                "plate": plate,
                "anomaly_type": "cloned_plate",
                "camera_id_1": c1,
                "timestamp_1": t1.strftime("%Y-%m-%d %H:%M:%S"),
                "camera_id_2": c2,
                "timestamp_2": t2.strftime("%Y-%m-%d %H:%M:%S"),
                "distance_meters": round(dist_m, 1),
                "time_delta_seconds": delta_sec,
                "implied_speed_kmh": implied_speed_kmh,
                "description": (
                    f"Plate {plate} seen at {c1} and {c2} ({dist_m:.0f}m apart) "
                    f"within {delta_sec}s -> impossible speed {implied_speed_kmh} km/h."
                ),
            }
        )

        # Create the two observation records for events.csv
        new_event_rows.append(
            {
                "event_id": None,
                "plate": plate,
                "camera_id": c1,
                "timestamp": t1.strftime("%Y-%m-%d %H:%M:%S"),
                "speed_kmh": round(rnd.uniform(35, 55), 1),
                "heading_degrees": round(rnd.uniform(0, 359), 1),
                "lane": rnd.choice([1, 2]),
                "ocr_confidence": round(rnd.uniform(0.92, 0.99), 3),
            }
        )
        new_event_rows.append(
            {
                "event_id": None,
                "plate": plate,
                "camera_id": c2,
                "timestamp": t2.strftime("%Y-%m-%d %H:%M:%S"),
                "speed_kmh": round(rnd.uniform(35, 55), 1),
                "heading_degrees": round(rnd.uniform(0, 359), 1),
                "lane": rnd.choice([1, 2]),
                "ocr_confidence": round(rnd.uniform(0.92, 0.99), 3),
            }
        )

    # Save anomalies
    anomalies_df = pd.DataFrame(anomalies)
    anomalies_df.to_csv(ANOMALIES_PATH, index=False)
    print(f"Injected {len(anomalies_df)} cloned plate anomalies -> {ANOMALIES_PATH}")

    # Merge into events.csv and re-sort chronologically
    combined_events_df = pd.concat([events_df, pd.DataFrame(new_event_rows)], ignore_index=True)
    combined_events_df = combined_events_df.sort_values(by="timestamp").reset_index(drop=True)
    combined_events_df.to_csv(EVENTS_PATH, index=False)
    print(f"Updated {EVENTS_PATH} with injected anomaly observation records.")

    return combined_events_df, anomalies_df


def inject_scenarios() -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Run all scenario injections (blacklist + cloned plate anomalies)."""
    if not EVENTS_PATH.exists():
        raise FileNotFoundError(f"{EVENTS_PATH} does not exist. Run add_noise.py first.")
    if not GROUND_TRUTH_PATH.exists():
        raise FileNotFoundError(f"{GROUND_TRUTH_PATH} does not exist. Run generate_traffic.py first.")
    if not CAMERAS_PATH.exists():
        raise FileNotFoundError(f"{CAMERAS_PATH} does not exist. Run build_city.py first.")

    rnd = random.Random(RANDOM_SEED)
    events_df = pd.read_csv(EVENTS_PATH)
    gt_df = pd.read_csv(GROUND_TRUTH_PATH)
    cameras_df = pd.read_csv(CAMERAS_PATH)

    blacklist_df = create_blacklist(gt_df, rnd)
    _, anomalies_df = inject_cloned_plates(events_df, gt_df, cameras_df, rnd)

    return blacklist_df, anomalies_df


def main() -> int:
    inject_scenarios()
    return 0


if __name__ == "__main__":
    sys.exit(main())
