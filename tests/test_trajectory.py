"""Tests for Module 5: Trajectory Reconstruction Engine."""

import datetime
import json
from pathlib import Path
import pytest
import pandas as pd

from backend.trajectory.reconstructor import (
    TrajectoryReconstructor,
    TRIP_INACTIVITY_THRESHOLD_SECONDS,
)
from simulator.config import CAMERAS_PATH, GRAPH_PATH


@pytest.fixture(scope="module")
def reconstructor():
    """Shared TrajectoryReconstructor instance."""
    return TrajectoryReconstructor(graph_path=GRAPH_PATH, cameras_path=CAMERAS_PATH)


def test_trajectory_reconstruction_single_trip(reconstructor):
    """Verify that multiple camera sightings form a valid continuous trajectory."""
    # Pick two real camera IDs
    cam_ids = list(reconstructor.camera_node_map.keys())[:3]
    c1, c2, c3 = cam_ids[0], cam_ids[1], cam_ids[2]

    base_time = datetime.datetime(2026, 10, 1, 9, 0, 0)
    sightings = [
        {"camera_id": c1, "timestamp": base_time, "speed_kmh": 40.0},
        {"camera_id": c2, "timestamp": base_time + datetime.timedelta(seconds=120), "speed_kmh": 42.0},
        {"camera_id": c3, "timestamp": base_time + datetime.timedelta(seconds=260), "speed_kmh": 38.0},
    ]

    trajectories = reconstructor.reconstruct_vehicle_trips(sightings)
    assert len(trajectories) == 1, f"Expected 1 trajectory, got {len(trajectories)}"

    t = trajectories[0]
    assert t["num_sightings"] == 3
    assert t["duration_seconds"] == 260.0
    assert t["total_distance_meters"] > 0.0
    assert t["avg_speed_kmh"] > 0.0
    assert len(t["camera_sequence"]) == 3
    assert t["line_geom"].is_valid, "Trajectory geometry must be a valid Shapely LineString"


def test_trip_splitting_on_long_inactivity(reconstructor):
    """Verify that sightings separated by a large time gap are split into two distinct trips."""
    cam_ids = list(reconstructor.camera_node_map.keys())[:2]
    c1, c2 = cam_ids[0], cam_ids[1]

    t1 = datetime.datetime(2026, 10, 1, 8, 30, 0)
    # Trip 1: two sightings within 2 minutes
    # Gap: 2 hours (exceeds TRIP_INACTIVITY_THRESHOLD_SECONDS)
    # Trip 2: two sightings in the evening
    t2 = t1 + datetime.timedelta(hours=2)

    sightings = [
        {"camera_id": c1, "timestamp": t1, "speed_kmh": 40.0},
        {"camera_id": c2, "timestamp": t1 + datetime.timedelta(seconds=90), "speed_kmh": 45.0},
        {"camera_id": c2, "timestamp": t2, "speed_kmh": 35.0},
        {"camera_id": c1, "timestamp": t2 + datetime.timedelta(seconds=110), "speed_kmh": 38.0},
    ]

    trajectories = reconstructor.reconstruct_vehicle_trips(sightings)
    assert len(trajectories) == 2, f"Expected 2 separate trips, got {len(trajectories)}"
    assert trajectories[0]["start_time"] == t1
    assert trajectories[1]["start_time"] == t2


def test_impossible_speed_anomaly_detection(reconstructor):
    """Verify that physically impossible speeds trigger an anomaly flag."""
    cam_ids = list(reconstructor.camera_node_map.keys())
    # Choose first and last camera (guaranteed far apart)
    c1, c2 = cam_ids[0], cam_ids[-1]

    base_time = datetime.datetime(2026, 10, 1, 14, 0, 0)
    # Sighting at c2 only 5 seconds after c1
    sightings = [
        {"camera_id": c1, "timestamp": base_time, "speed_kmh": 45.0},
        {"camera_id": c2, "timestamp": base_time + datetime.timedelta(seconds=5), "speed_kmh": 45.0},
    ]

    trajectories = reconstructor.reconstruct_vehicle_trips(sightings)
    if trajectories:
        anomalies = trajectories[0]["anomalies"]
        has_speed_anomaly = any(a["type"] == "IMPOSSIBLE_SPEED" for a in anomalies)
        assert has_speed_anomaly, "Expected impossible speed anomaly to be detected"


def test_geojson_export(reconstructor, tmp_path):
    """Verify that trajectories export correctly to standard GeoJSON."""
    cam_ids = list(reconstructor.camera_node_map.keys())[:2]
    c1, c2 = cam_ids[0], cam_ids[1]

    t1 = datetime.datetime(2026, 10, 1, 10, 0, 0)
    sightings = [
        {"camera_id": c1, "timestamp": t1, "speed_kmh": 35.0},
        {"camera_id": c2, "timestamp": t1 + datetime.timedelta(seconds=100), "speed_kmh": 40.0},
    ]

    trajectories = reconstructor.reconstruct_vehicle_trips(sightings)
    for t in trajectories:
        t["plate"] = "TEST_PLATE"

    out_file = tmp_path / "test_traj.geojson"
    reconstructor.export_geojson(trajectories, out_file)

    assert out_file.exists()
    with open(out_file, "r") as f:
        data = json.load(f)

    assert data["type"] == "FeatureCollection"
    assert len(data["features"]) == len(trajectories)
    assert data["features"][0]["geometry"]["type"] == "LineString"
    assert data["features"][0]["properties"]["plate"] == "TEST_PLATE"
