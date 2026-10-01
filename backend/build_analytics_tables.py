"""Script to build, persist, and export urban traffic analytics tables.

Saves analytics results to SQLite database tables:
- camera_window_stats
- congestion
- od_matrix
- route_density

Also exports CSV copies to data/analytics/.
Safe to re-run idempotently.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pandas as pd

# Ensure project root is in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.analytics import (
    camera_stats,
    city_flow_trend,
    congestion_hotspots,
    origin_destination_matrix,
    route_density,
)
from backend.db import engine

ANALYTICS_DATA_DIR = ROOT_DIR / "data" / "analytics"


def build_tables():
    print("=" * 70)
    print("BUILDING URBAN TRAFFIC ANALYTICS TABLES & EXPORTS")
    print("=" * 70)
    ANALYTICS_DATA_DIR.mkdir(parents=True, exist_ok=True)
    t_start = time.perf_counter()

    # 1. Camera Window Statistics (15-min intervals)
    print("\n1. Computing camera window statistics (15-min intervals)...")
    t0 = time.perf_counter()
    cws_df = camera_stats(window_minutes=15)
    cws_df.to_sql("camera_window_stats", engine, if_exists="replace", index=False)
    cws_csv = ANALYTICS_DATA_DIR / "camera_window_stats.csv"
    cws_df.to_csv(cws_csv, index=False)
    print(f"   [OK] Saved {len(cws_df):,} rows to DB [camera_window_stats] & CSV ({time.perf_counter() - t0:.2f}s)")

    # 2. Congestion Hotspots
    print("\n2. Identifying congestion hotspots and speed deficits...")
    t0 = time.perf_counter()
    cong_df = congestion_hotspots(window_minutes=15)
    cong_df.to_sql("congestion", engine, if_exists="replace", index=False)
    cong_csv = ANALYTICS_DATA_DIR / "congestion_hotspots.csv"
    cong_df.to_csv(cong_csv, index=False)
    print(f"   [OK] Saved {len(cong_df):,} rows to DB [congestion] & CSV ({time.perf_counter() - t0:.2f}s)")

    # 3. Origin-Destination Matrix
    print("\n3. Computing zone-to-zone Origin-Destination matrix...")
    t0 = time.perf_counter()
    od_pivot = origin_destination_matrix(n_zones=8)
    # Save pivoted matrix to CSV
    od_csv = ANALYTICS_DATA_DIR / "od_matrix.csv"
    od_pivot.to_csv(od_csv)

    # Convert to tidy rows (origin_zone, dest_zone, trip_count) for database table
    od_tidy = od_pivot.reset_index().melt(
        id_vars=["Origin Zone"],
        var_name="dest_zone",
        value_name="trip_count",
    ).rename(columns={"Origin Zone": "origin_zone"})
    od_tidy.to_sql("od_matrix", engine, if_exists="replace", index=False)
    print(f"   [OK] Saved {od_pivot.shape[0]}x{od_pivot.shape[1]} matrix ({od_pivot.values.sum():,} trips) to DB [od_matrix] & CSV ({time.perf_counter() - t0:.2f}s)")

    # 4. Route Density (Road segment traversal loads per 60-min window)
    print("\n4. Calculating route segment traversal densities...")
    t0 = time.perf_counter()
    rd_df = route_density(window_minutes=60)
    rd_df.to_sql("route_density", engine, if_exists="replace", index=False)
    rd_csv = ANALYTICS_DATA_DIR / "route_density.csv"
    rd_df.to_csv(rd_csv, index=False)
    print(f"   [OK] Saved {len(rd_df):,} segment loads to DB [route_density] & CSV ({time.perf_counter() - t0:.2f}s)")

    # 5. City Flow Trend CSV
    print("\n5. Exporting city flow trends...")
    trend_df = city_flow_trend(window_minutes=15)
    trend_csv = ANALYTICS_DATA_DIR / "city_flow_trend.csv"
    trend_df.to_csv(trend_csv, index=False)
    print(f"   [OK] Saved {len(trend_df):,} windows to {trend_csv.name}")

    total_time = time.perf_counter() - t_start
    print("\n" + "=" * 70)
    print("ANALYTICS BUILD SUMMARY")
    print("=" * 70)
    print(f"  Camera Window Stats : {len(cws_df):>6,} rows  ({cws_csv.stat().st_size / 1024:.1f} KB)")
    print(f"  Congestion Records  : {len(cong_df):>6,} rows  ({cong_csv.stat().st_size / 1024:.1f} KB)")
    print(f"  OD Matrix Pairs     : {len(od_tidy):>6,} pairs ({od_csv.stat().st_size / 1024:.1f} KB)")
    print(f"  Route Segment Loads : {len(rd_df):>6,} rows  ({rd_csv.stat().st_size / 1024:.1f} KB)")
    print(f"  Total Duration      : {total_time:.2f} seconds")
    print(f"  Destination Dir     : {ANALYTICS_DATA_DIR.resolve()}")
    print("=" * 70)


if __name__ == "__main__":
    build_tables()
