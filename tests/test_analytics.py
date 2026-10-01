"""Unit and integration tests for Module 6: Traffic Analytics & OD Matrix Engine."""

import sys
from pathlib import Path
import pytest
import pandas as pd

# Ensure project root is in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.analytics import (
    camera_stats,
    city_flow_trend,
    congestion_hotspots,
    extract_vehicle_trips,
    heatmap_points,
    load_cameras_df,
    load_events_df,
    origin_destination_matrix,
    route_density,
)
from backend.analytics_cli import print_summary
from backend.db import engine


@pytest.fixture(scope="module")
def total_events_count():
    """Count total events in SQLite database."""
    events_df = load_events_df()
    return len(events_df)


@pytest.fixture(scope="module")
def valid_camera_ids():
    """Set of valid registered camera IDs."""
    cams_df = load_cameras_df()
    return set(cams_df["camera_id"])


def test_camera_stats_counts_sum_to_total_events(total_events_count):
    """Verify that counts across all camera-windows sum exactly to total events."""
    cs = camera_stats(window_minutes=15)
    assert not cs.empty, "Camera stats DataFrame should not be empty"

    sum_count = cs["vehicle_count"].sum()
    assert sum_count == total_events_count, (
        f"Sum of camera_stats counts ({sum_count}) does not equal total events ({total_events_count})"
    )

    # Verify city_flow_trend also sums to total events
    cft = city_flow_trend(window_minutes=15)
    assert not cft.empty
    assert cft["vehicle_count"].sum() == total_events_count


def test_every_congested_camera_exists(valid_camera_ids):
    """Verify that every flagged congested camera exists in the camera registry."""
    cong = congestion_hotspots(window_minutes=15)
    assert not cong.empty, "Expected congestion hotspots to be identified"

    for _, row in cong.iterrows():
        cid = row["camera_id"]
        assert cid in valid_camera_ids, f"Congested camera '{cid}' not found in registered cameras"

        sev = row["severity"]
        assert 0.0 <= sev <= 1.0, f"Congestion severity {sev} out of bounds [0.0, 1.0]"

        dur = row["duration_minutes"]
        assert dur >= 15, f"Congestion duration {dur} should be at least 15 minutes"


def test_od_matrix_totals_equal_number_of_trips():
    """Verify that OD matrix cells sum exactly to the total number of trips."""
    trips = extract_vehicle_trips()
    assert not trips.empty, "Trips DataFrame should not be empty"

    od_matrix = origin_destination_matrix(n_zones=8)
    assert od_matrix.shape == (8, 8), f"Expected 8x8 OD matrix, got {od_matrix.shape}"

    matrix_total_trips = int(od_matrix.values.sum())
    assert matrix_total_trips == len(trips), (
        f"OD matrix total ({matrix_total_trips}) does not equal trips count ({len(trips)})"
    )


def test_heatmap_weights_between_zero_and_one():
    """Verify that all heatmap points have weights strictly between 0.0 and 1.0."""
    hp = heatmap_points()
    assert not hp.empty, "Heatmap points should not be empty"
    assert len(hp) == 40, f"Expected 40 cameras in heatmap, got {len(hp)}"

    for _, row in hp.iterrows():
        w = row["weight"]
        assert 0.0 <= w <= 1.0, f"Heatmap point weight {w} is not between 0 and 1"

        lat = row["lat"]
        lon = row["lon"]
        assert 12.8 <= lat <= 13.2, f"Latitude {lat} out of range for Bangalore"
        assert 77.4 <= lon <= 77.8, f"Longitude {lon} out of range for Bangalore"


def test_analytics_database_tables_populated():
    """Verify that SQLite analytics tables (camera_window_stats, congestion, od_matrix, route_density) exist."""
    tables = ["camera_window_stats", "congestion", "od_matrix", "route_density"]
    for t in tables:
        count_df = pd.read_sql(f"SELECT COUNT(*) as cnt FROM {t}", engine)
        count = count_df.iloc[0]["cnt"]
        assert count > 0, f"Database table '{t}' is empty"


def test_analytics_cli_summary(capsys):
    """Verify analytics CLI summary output format and metrics."""
    print_summary()
    captured = capsys.readouterr().out
    assert "CITY-WIDE URBAN TRAFFIC ANALYTICS SUMMARY" in captured
    assert "TOP 5 CONGESTED ANPR INTERSECTIONS" in captured
    assert "PEAK TRAFFIC HOUR" in captured
    assert "BUSIEST ORIGIN-DESTINATION CORRIDOR" in captured
    assert "CITY-WIDE TRAFFIC PERFORMANCE METRICS" in captured
