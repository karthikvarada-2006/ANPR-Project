"""CLI tool for urban traffic analytics summary.

Usage:
    python -m backend.analytics_cli summary
    python backend/analytics_cli.py summary
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# Ensure project root is in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.analytics import (
    city_flow_trend,
    congestion_hotspots,
    load_events_df,
    origin_destination_matrix,
)


def print_summary():
    print("=" * 80)
    print("CITY-WIDE URBAN TRAFFIC ANALYTICS SUMMARY")
    print("=" * 80)

    # 1. Congestion Hotspots (Top 5)
    print("\n--- 1. TOP 5 CONGESTED ANPR INTERSECTIONS ---")
    cong = congestion_hotspots(window_minutes=15)
    if not cong.empty:
        cam_summary = cong.groupby(["camera_id", "camera_name"]).agg(
            congested_windows=("window_start", "count"),
            max_duration_min=("duration_minutes", "max"),
            avg_speed=("avg_speed_kmh", "mean"),
            free_flow_speed=("free_flow_speed_kmh", "first"),
            peak_severity=("severity", "max"),
        ).reset_index().sort_values(["congested_windows", "peak_severity"], ascending=[False, False]).head(5)

        print(f"{'Rank':<5} | {'Camera ID':<9} | {'Avg Spd':<8} | {'FF Spd':<7} | {'Windows':<8} | {'Max Dur':<8} | {'Intersection Name'}")
        print("-" * 80)
        for rank, (_, row) in enumerate(cam_summary.iterrows(), 1):
            cid = row["camera_id"]
            cname = row["camera_name"]
            spd = f"{row['avg_speed']:.1f}"
            ff = f"{row['free_flow_speed']:.1f}"
            wins = f"{row['congested_windows']} ({row['congested_windows'] * 15}m)"
            dur = f"{row['max_duration_min']}m"
            print(f"#{rank:<4} | {cid:<9} | {spd:>5} km/h | {ff:>4} km/h | {wins:<8} | {dur:<8} | {cname}")
    else:
        print("  No congestion events identified under current thresholds.")

    # 2. Peak Traffic Hour
    print("\n--- 2. PEAK TRAFFIC HOUR ---")
    trend = city_flow_trend(window_minutes=15)
    trend["hour"] = trend["window_start"].dt.hour
    hourly_vol = trend.groupby("hour").agg(
        total_vehicles=("vehicle_count", "sum"),
        avg_speed=("avg_speed_kmh", "mean"),
    ).reset_index()

    peak_row = hourly_vol.loc[hourly_vol["total_vehicles"].idxmax()]
    peak_hr = int(peak_row["hour"])
    print(f"  Peak Traffic Window : {peak_hr:02d}:00 - {peak_hr + 1:02d}:00")
    print(f"  Peak Vehicle Volume : {int(peak_row['total_vehicles']):,} vehicles detected")
    print(f"  Peak Average Speed  : {peak_row['avg_speed']:.1f} km/h")

    # 3. Busiest Zone Pair (Origin - Destination)
    print("\n--- 3. BUSIEST ORIGIN-DESTINATION CORRIDOR ---")
    od_pivot = origin_destination_matrix(n_zones=8)
    od_tidy = od_pivot.reset_index().melt(
        id_vars=["Origin Zone"],
        var_name="Destination Zone",
        value_name="Trip Count",
    )

    # Exclude same-zone (intra-zone) trips to find top transit corridor
    inter_zone = od_tidy[od_tidy["Origin Zone"] != od_tidy["Destination Zone"]]
    busiest = inter_zone.loc[inter_zone["Trip Count"].idxmax()]
    print(f"  Origin Zone       : {busiest['Origin Zone']}")
    print(f"  Destination Zone  : {busiest['Destination Zone']}")
    print(f"  Commuter Journeys : {busiest['Trip Count']:,} trips")

    # 4. Average City Speed & Overall Metrics
    print("\n--- 4. CITY-WIDE TRAFFIC PERFORMANCE METRICS ---")
    events_df = load_events_df()
    avg_speed = events_df["speed_kmh"].mean()
    p85_speed = np.percentile(events_df["speed_kmh"].dropna(), 85)
    min_hourly_speed = hourly_vol["avg_speed"].min()
    total_events = len(events_df)
    unique_vehicles = events_df["plate_canonical"].nunique()

    print(f"  Total ANPR Detections : {total_events:,}")
    print(f"  Unique Vehicles Tracked : {unique_vehicles:,}")
    print(f"  Average City Speed      : {avg_speed:.1f} km/h")
    print(f"  Free-Flow Speed (85th%) : {p85_speed:.1f} km/h")
    print(f"  Lowest Hourly Speed     : {min_hourly_speed:.1f} km/h (Peak Congestion Period)")
    print("=" * 80)


def main():
    parser = argparse.ArgumentParser(description="Urban traffic analytics command-line tool.")
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # Subcommand: summary
    subparsers.add_parser("summary", help="Print summary of top bottlenecks, peak hour, and busiest zones")

    args = parser.parse_args()
    if args.command == "summary" or len(sys.argv) == 1:
        print_summary()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
