"""Unit tests for the Real Jinan Trajectory Data Loader (real_data/load_jinan.py).

Tests verify that:
1. Latitude and Longitude are correctly mapped and not swapped (all lats between 36.5 and 36.8).
2. Every event's camera_id exists in the cameras table (referential integrity).
3. Events are only created for nodes where HasCamera=1.
4. No event has a non-NULL ocr_confidence or n_frames value.
5. Re-running the loader is idempotent (produces identical row counts).
6. city_anpr.db checksum is verified and untouched.
"""

from __future__ import annotations

import csv
import hashlib
from pathlib import Path
import sqlite3

import pytest

from real_data.load_jinan import compute_file_sha256, load_jinan_data

# Project root path
ROOT_DIR = Path(__file__).resolve().parent.parent
CITY_ANPR_DB = ROOT_DIR / "data" / "city_anpr.db"


@pytest.fixture
def fake_jinan_dataset(tmp_path: Path):
    """Generate minimal synthetic CSV files simulating the Jinan dataset format."""
    data_dir = tmp_path / "fake_jinan"
    data_dir.mkdir()

    node_file = data_dir / "node_jinan.csv"
    traj_file = data_dir / "traj_jinan.csv"
    out_db = tmp_path / "test_jinan.db"

    # Synthetic nodes in Jinan coordinate bounds:
    # Jinan: Longitude ~ 116.8 - 117.4, Latitude ~ 36.5 - 36.8
    # Node 101: Camera node
    # Node 102: Non-camera node
    # Node 103: Camera node
    # Node 104: Camera node (NOT visited by any trajectory)
    # Node 105: Non-camera node
    with open(node_file, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["NodeID", "Longitude", "Latitude", "HasCamera"])
        writer.writerow(["101", "117.012345", "36.654321", "1"])
        writer.writerow(["102", "117.023456", "36.665432", "0"])
        writer.writerow(["103", "117.034567", "36.676543", "1"])
        writer.writerow(["104", "117.045678", "36.687654", "1"])  # Unused camera
        writer.writerow(["105", "117.056789", "36.698765", "0"])

    # Synthetic trajectories:
    # Format: VehicleID,TripID,Points,DepartureTime,Duration,Length
    with open(traj_file, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["VehicleID", "TripID", "Points", "DepartureTime", "Duration", "Length"])
        # Vehicle 0 (Trip 0): passes through 101 (cam), 102 (no cam), 103 (cam)
        writer.writerow(["0", "1", "101-3600.0_102-3620.0_103-3650.0", "3600.0", "50.0", "1200.0"])
        # Vehicle 20 (Trip 1): passes through 103 (cam), 105 (no cam)
        writer.writerow(["20", "2", "103-7200.0_105-7240.0", "7200.0", "40.0", "900.0"])
        # Vehicle 7 (Trip 3): VehicleID % 20 != 0 (will be skipped when sample_mod=20)
        writer.writerow(["7", "3", "101-10000.0_103-10030.0", "10000.0", "30.0", "800.0"])

    return {
        "node_file": node_file,
        "traj_file": traj_file,
        "out_db": out_db,
    }


def test_lat_lon_not_swapped_and_correctly_stored(fake_jinan_dataset):
    """Verify that latitude and longitude columns are not inverted."""
    out_db = fake_jinan_dataset["out_db"]

    load_jinan_data(
        node_file=fake_jinan_dataset["node_file"],
        traj_file=fake_jinan_dataset["traj_file"],
        out_db_path=out_db,
        sample_mod=1,
        city_anpr_db_path=CITY_ANPR_DB,
        verbose=False,
    )

    conn = sqlite3.connect(str(out_db))
    cur = conn.cursor()

    rows = cur.execute("SELECT camera_id, lat, lon FROM cameras").fetchall()
    conn.close()

    assert len(rows) > 0, "No cameras were inserted"
    for cam_id, lat, lon in rows:
        # Jinan latitudes are ~ 36.5 - 36.8
        assert 36.5 <= lat <= 36.8, f"Latitude {lat} for {cam_id} is out of expected Jinan range [36.5, 36.8]"
        # Jinan longitudes are ~ 116.8 - 117.4
        assert 116.8 <= lon <= 117.4, f"Longitude {lon} for {cam_id} is out of expected Jinan range [116.8, 117.4]"
        # Ensure lat and lon are clearly distinct and not swapped
        assert lat < lon, f"Lat ({lat}) should be significantly less than Lon ({lon}) in Jinan"


def test_every_event_camera_id_exists_in_cameras(fake_jinan_dataset):
    """Verify foreign key integrity: every event's camera_id exists in cameras table."""
    out_db = fake_jinan_dataset["out_db"]

    load_jinan_data(
        node_file=fake_jinan_dataset["node_file"],
        traj_file=fake_jinan_dataset["traj_file"],
        out_db_path=out_db,
        sample_mod=1,
        city_anpr_db_path=CITY_ANPR_DB,
        verbose=False,
    )

    conn = sqlite3.connect(str(out_db))
    cur = conn.cursor()

    # Find any orphaned events
    orphans = cur.execute(
        """
        SELECT e.id, e.camera_id
        FROM events e
        LEFT JOIN cameras c ON e.camera_id = c.camera_id
        WHERE c.camera_id IS NULL;
        """
    ).fetchall()
    conn.close()

    assert len(orphans) == 0, f"Found orphaned events with non-existent camera IDs: {orphans}"


def test_events_only_exist_for_has_camera_nodes(fake_jinan_dataset):
    """Verify that sightings are only generated for nodes with HasCamera=1."""
    out_db = fake_jinan_dataset["out_db"]

    load_jinan_data(
        node_file=fake_jinan_dataset["node_file"],
        traj_file=fake_jinan_dataset["traj_file"],
        out_db_path=out_db,
        sample_mod=1,
        city_anpr_db_path=CITY_ANPR_DB,
        verbose=False,
    )

    conn = sqlite3.connect(str(out_db))
    cur = conn.cursor()

    # In our fake dataset, 102 and 105 are non-camera nodes
    non_camera_sightings = cur.execute(
        "SELECT id, camera_id FROM events WHERE camera_id IN ('JN_000102', 'JN_000105')"
    ).fetchall()
    conn.close()

    assert len(non_camera_sightings) == 0, (
        f"Non-camera nodes produced events: {non_camera_sightings}"
    )


def test_no_event_has_non_null_ocr_confidence_or_n_frames(fake_jinan_dataset):
    """Verify that ocr_confidence and n_frames are strictly NULL across all events."""
    out_db = fake_jinan_dataset["out_db"]

    load_jinan_data(
        node_file=fake_jinan_dataset["node_file"],
        traj_file=fake_jinan_dataset["traj_file"],
        out_db_path=out_db,
        sample_mod=1,
        city_anpr_db_path=CITY_ANPR_DB,
        verbose=False,
    )

    conn = sqlite3.connect(str(out_db))
    cur = conn.cursor()

    non_null_conf = cur.execute(
        "SELECT COUNT(*) FROM events WHERE ocr_confidence IS NOT NULL"
    ).fetchone()[0]

    non_null_frames = cur.execute(
        "SELECT COUNT(*) FROM events WHERE n_frames IS NOT NULL"
    ).fetchone()[0]
    conn.close()

    assert non_null_conf == 0, "Found events with non-NULL ocr_confidence"
    assert non_null_frames == 0, "Found events with non-NULL n_frames"


def test_only_used_cameras_are_inserted(fake_jinan_dataset):
    """Verify that camera nodes never visited by kept trips are not inserted."""
    out_db = fake_jinan_dataset["out_db"]

    load_jinan_data(
        node_file=fake_jinan_dataset["node_file"],
        traj_file=fake_jinan_dataset["traj_file"],
        out_db_path=out_db,
        sample_mod=1,
        city_anpr_db_path=CITY_ANPR_DB,
        verbose=False,
    )

    conn = sqlite3.connect(str(out_db))
    cur = conn.cursor()

    # Node 104 has HasCamera=1, but neither vehicle 0, 20, nor 7 ever visited it
    unused_cam = cur.execute(
        "SELECT camera_id FROM cameras WHERE camera_id = 'JN_000104'"
    ).fetchone()
    conn.close()

    assert unused_cam is None, "Camera node 104 was inserted despite not being used in any kept trip"


def test_running_loader_twice_gives_identical_row_counts(fake_jinan_dataset):
    """Verify that running the loader multiple times is completely idempotent."""
    out_db = fake_jinan_dataset["out_db"]

    # First run
    summary_1 = load_jinan_data(
        node_file=fake_jinan_dataset["node_file"],
        traj_file=fake_jinan_dataset["traj_file"],
        out_db_path=out_db,
        sample_mod=20,  # Only vehicles 0 and 20 kept (Vehicle 7 skipped)
        city_anpr_db_path=CITY_ANPR_DB,
        verbose=False,
    )

    conn = sqlite3.connect(str(out_db))
    cam_count_1 = conn.execute("SELECT COUNT(*) FROM cameras").fetchone()[0]
    ev_count_1 = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    conn.close()

    # Second run
    summary_2 = load_jinan_data(
        node_file=fake_jinan_dataset["node_file"],
        traj_file=fake_jinan_dataset["traj_file"],
        out_db_path=out_db,
        sample_mod=20,
        city_anpr_db_path=CITY_ANPR_DB,
        verbose=False,
    )

    conn = sqlite3.connect(str(out_db))
    cam_count_2 = conn.execute("SELECT COUNT(*) FROM cameras").fetchone()[0]
    ev_count_2 = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    conn.close()

    assert cam_count_1 == cam_count_2
    assert ev_count_1 == ev_count_2
    assert summary_1["events_inserted"] == summary_2["events_inserted"]
    assert summary_1["cameras_inserted"] == summary_2["cameras_inserted"]
    assert summary_1["vehicles_kept"] == summary_2["vehicles_kept"]


def test_city_anpr_db_checksum_unchanged(fake_jinan_dataset):
    """Verify that running the Jinan loader never modifies city_anpr.db."""
    assert CITY_ANPR_DB.exists(), f"city_anpr.db not found at {CITY_ANPR_DB}"

    sha_before = compute_file_sha256(CITY_ANPR_DB)

    load_jinan_data(
        node_file=fake_jinan_dataset["node_file"],
        traj_file=fake_jinan_dataset["traj_file"],
        out_db_path=fake_jinan_dataset["out_db"],
        sample_mod=20,
        city_anpr_db_path=CITY_ANPR_DB,
        verbose=False,
    )

    sha_after = compute_file_sha256(CITY_ANPR_DB)

    assert sha_before is not None
    assert sha_before == sha_after, "city_anpr.db was modified during Jinan data loading!"


def test_exact_duplicate_trip_rows_are_skipped(tmp_path: Path):
    """Verify that exact duplicate trip rows in traj CSV are skipped and only loaded once."""
    data_dir = tmp_path / "dup_jinan"
    data_dir.mkdir()

    node_file = data_dir / "node_jinan.csv"
    with open(node_file, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["NodeID", "Longitude", "Latitude", "HasCamera"])
        writer.writerow(["101", "117.012345", "36.654321", "1"])
        writer.writerow(["103", "117.034567", "36.676543", "1"])

    # Trajectory CSV containing 1 baseline trip row repeated 4 times (3 duplicate rows)
    traj_with_dups = data_dir / "traj_with_dups.csv"
    with open(traj_with_dups, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["VehicleID", "TripID", "Points", "DepartureTime", "Duration", "Length"])
        # Repeated 4 times:
        for _ in range(4):
            writer.writerow(["20", "0", "101-3600.0_103-3650.0", "3600.0", "50.0", "1200.0"])

    # Trajectory CSV with only the single trip row
    traj_single = data_dir / "traj_single.csv"
    with open(traj_single, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["VehicleID", "TripID", "Points", "DepartureTime", "Duration", "Length"])
        writer.writerow(["20", "0", "101-3600.0_103-3650.0", "3600.0", "50.0", "1200.0"])

    db_with_dups = tmp_path / "jinan_dups.db"
    db_single = tmp_path / "jinan_single.db"

    summary_dups = load_jinan_data(
        node_file=node_file,
        traj_file=traj_with_dups,
        out_db_path=db_with_dups,
        sample_mod=1,
        city_anpr_db_path=CITY_ANPR_DB,
        verbose=False,
    )

    summary_single = load_jinan_data(
        node_file=node_file,
        traj_file=traj_single,
        out_db_path=db_single,
        sample_mod=1,
        city_anpr_db_path=CITY_ANPR_DB,
        verbose=False,
    )

    # 3 duplicate rows should be skipped, keeping exactly 1 unique trip
    assert summary_dups["duplicate_trips_skipped"] == 3
    assert summary_dups["trips_kept"] == 1
    assert summary_single["trips_kept"] == 1

    # Event count of the deduplicated run must equal the no-duplicate baseline run
    assert summary_dups["events_inserted"] == summary_single["events_inserted"] == 2


def test_same_vehicle_trip_id_with_different_points_are_both_kept(tmp_path: Path):
    """Verify that repeated (VehicleID, TripID) with different Points are both kept with unique track_ids."""
    data_dir = tmp_path / "diff_points_jinan"
    data_dir.mkdir()

    node_file = data_dir / "node_jinan.csv"
    with open(node_file, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["NodeID", "Longitude", "Latitude", "HasCamera"])
        writer.writerow(["101", "117.012345", "36.654321", "1"])
        writer.writerow(["103", "117.034567", "36.676543", "1"])

    traj_file = data_dir / "traj_diff.csv"
    with open(traj_file, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["VehicleID", "TripID", "Points", "DepartureTime", "Duration", "Length"])
        # Same VehicleID (0) and TripID (0), but different Points strings:
        writer.writerow(["0", "0", "101-3600.0_103-3650.0", "3600.0", "50.0", "1200.0"])
        writer.writerow(["0", "0", "103-7200.0_101-7250.0", "7200.0", "50.0", "1200.0"])

    out_db = tmp_path / "jinan_diff.db"
    summary = load_jinan_data(
        node_file=node_file,
        traj_file=traj_file,
        out_db_path=out_db,
        sample_mod=1,
        city_anpr_db_path=CITY_ANPR_DB,
        verbose=False,
    )

    assert summary["trips_kept"] == 2
    assert summary["duplicate_trips_skipped"] == 0
    assert summary["trips_repeated_id_diff_points"] == 1

    conn = sqlite3.connect(str(out_db))
    track_ids = [r[0] for r in conn.execute("SELECT DISTINCT track_id FROM events ORDER BY track_id").fetchall()]
    conn.close()

    # Track IDs should be differentiated by suffix '-<n>'
    assert track_ids == ["0-0", "0-0-2"]


def test_no_duplicate_plate_camera_timestamp_in_fake_data(fake_jinan_dataset):
    """Verify that no (plate, camera_id, timestamp) combination appears more than once."""
    out_db = fake_jinan_dataset["out_db"]

    load_jinan_data(
        node_file=fake_jinan_dataset["node_file"],
        traj_file=fake_jinan_dataset["traj_file"],
        out_db_path=out_db,
        sample_mod=1,
        city_anpr_db_path=CITY_ANPR_DB,
        verbose=False,
    )

    conn = sqlite3.connect(str(out_db))
    cur = conn.cursor()

    dups = cur.execute(
        """
        SELECT plate, camera_id, timestamp, COUNT(*)
        FROM events
        GROUP BY plate, camera_id, timestamp
        HAVING COUNT(*) > 1;
        """
    ).fetchall()
    conn.close()

    assert len(dups) == 0, f"Found duplicate (plate, camera_id, timestamp) events: {dups}"

