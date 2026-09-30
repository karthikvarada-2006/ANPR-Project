"""Test suite for Module 1: City ANPR Simulator."""

from pathlib import Path
import pandas as pd
import pytest

from simulator.config import (
    ANOMALIES_PATH,
    BLACKLIST_PATH,
    CAMERAS_PATH,
    EVENTS_PATH,
    GRAPH_PATH,
    GROUND_TRUTH_PATH,
    NUM_CAMERAS,
)


@pytest.fixture(scope="module")
def ensure_simulation_data():
    """Ensure simulation artifacts exist; run pipeline if not yet generated."""
    if not (EVENTS_PATH.exists() and CAMERAS_PATH.exists() and GROUND_TRUTH_PATH.exists()):
        from simulator.run_all import run_pipeline
        run_pipeline()
    return True


def test_cameras_exist_and_valid(ensure_simulation_data):
    """Verify cameras.csv has expected count and valid coordinates."""
    assert CAMERAS_PATH.exists(), f"Missing cameras file: {CAMERAS_PATH}"
    df = pd.read_csv(CAMERAS_PATH)

    assert len(df) == NUM_CAMERAS, f"Expected {NUM_CAMERAS} cameras, got {len(df)}"
    assert {"camera_id", "lat", "lon", "node_id", "name"}.issubset(df.columns)

    # Coordinates within Bangalore bounding box
    assert (df["lat"].between(12.8, 13.2)).all(), "Camera latitude out of bounds"
    assert (df["lon"].between(77.4, 77.8)).all(), "Camera longitude out of bounds"
    assert df["camera_id"].nunique() == NUM_CAMERAS, "Camera IDs must be unique"


def test_events_chronologically_sorted(ensure_simulation_data):
    """Verify events.csv is strictly sorted by timestamp."""
    assert EVENTS_PATH.exists(), f"Missing events file: {EVENTS_PATH}"
    df = pd.read_csv(EVENTS_PATH)

    assert len(df) > 0, "events.csv must not be empty"
    timestamps = pd.to_datetime(df["timestamp"])
    assert timestamps.is_monotonic_increasing, "Events must be strictly time-sorted"


def test_camera_ids_all_exist_in_cameras(ensure_simulation_data):
    """Verify all camera_id values in events.csv exist in cameras.csv."""
    cameras_df = pd.read_csv(CAMERAS_PATH)
    events_df = pd.read_csv(EVENTS_PATH)

    valid_cameras = set(cameras_df["camera_id"])
    event_cameras = set(events_df["camera_id"])

    invalid = event_cameras - valid_cameras
    assert len(invalid) == 0, f"Found unknown camera IDs in events: {invalid}"


def test_noisy_events_count_relation(ensure_simulation_data):
    """Verify noisy events count is consistent with miss rate and injected anomalies."""
    gt_df = pd.read_csv(GROUND_TRUTH_PATH)
    noisy_df = pd.read_csv(EVENTS_PATH)

    # 5% miss rate removes ~5% of true events, 10 anomaly events are added
    # So noisy events should be strictly less than or very close to true events
    assert len(gt_df) > 0, "Ground truth events must not be empty"
    assert len(noisy_df) <= len(gt_df) + 15, "Noisy events count exceeded expected range"


def test_security_blacklist_and_anomalies(ensure_simulation_data):
    """Verify security blacklist and cloned plate anomaly counts."""
    assert BLACKLIST_PATH.exists(), "Missing blacklist.csv"
    assert ANOMALIES_PATH.exists(), "Missing anomalies.csv"

    bl_df = pd.read_csv(BLACKLIST_PATH)
    an_df = pd.read_csv(ANOMALIES_PATH)

    assert len(bl_df) == 10, f"Expected 10 blacklist plates, got {len(bl_df)}"
    assert len(an_df) == 5, f"Expected 5 cloned plate anomalies, got {len(an_df)}"
    assert {"plate", "reason", "added_date"}.issubset(bl_df.columns)
    assert {"plate", "anomaly_type", "camera_id_1", "camera_id_2"}.issubset(an_df.columns)
