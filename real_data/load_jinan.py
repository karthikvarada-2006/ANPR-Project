"""Loader for Real-World Jinan Trajectory Dataset.

Reads raw node and trajectory CSV files from the Jinan dataset (C:\\anpr_data\\real_jinan),
filters to camera sightings, and loads them into a new isolated SQLite database:
data/real_jinan.db.

The loader ensures:
1. Complete isolation: data/city_anpr.db is never modified (verified via SHA-256).
2. Clean separation: camera IDs use JN_<NodeID>, plates use JNV<VehicleID>, source='real_jinan'.
3. Idempotency: the destination database is completely rebuilt on each run.
4. Correctness: Longitude and Latitude are mapped accurately (input file is lon-first).
5. Transparency: ocr_confidence and n_frames remain NULL because real telemetry has no OCR.
"""

from __future__ import annotations

import argparse
import csv
import datetime
import hashlib
from pathlib import Path
import sqlite3
import sys
import time
from typing import Any, Dict, List, Optional, Set, Tuple

# Enable support for very long trajectory Point fields in traj_jinan.csv
csv.field_size_limit(10**9)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
# The real Jinan dataset only specifies clock seconds from midnight (1..86399)
# for a single day, without any specific calendar date.
# We use March 1, 2026 as a consistent placeholder date:
# "real file has no date; only the clock time is real".
PLACEHOLDER_DATE = datetime.date(2026, 3, 1)

DEFAULT_INPUT_DIR = Path(r"C:\anpr_data\real_jinan")
DEFAULT_OUT_DB = Path("data/real_jinan.db")
DEFAULT_CITY_DB = Path("data/city_anpr.db")
DEFAULT_BATCH_SIZE = 50_000


def compute_file_sha256(file_path: Path) -> Optional[str]:
    """Calculate SHA-256 checksum of a file if it exists."""
    if not file_path.exists():
        return None
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(1024 * 1024):
            hasher.update(chunk)
    return hasher.hexdigest()


def init_database(db_path: Path) -> sqlite3.Connection:
    """Create fresh SQLite database with cameras and events tables matching city_anpr schema."""
    # Ensure parent directory exists
    db_path.parent.mkdir(parents=True, exist_ok=True)

    # Delete existing database file to guarantee idempotent rebuilding
    if db_path.exists():
        db_path.unlink()

    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()

    # Performance optimizations for bulk loading
    cur.execute("PRAGMA synchronous = OFF;")
    cur.execute("PRAGMA journal_mode = MEMORY;")
    cur.execute("PRAGMA cache_size = -64000;")  # 64 MB cache

    # 1. Cameras table (schema mirrors backend.models.Camera / city_anpr.db)
    cur.execute(
        """
        CREATE TABLE cameras (
            camera_id VARCHAR(50) NOT NULL,
            name VARCHAR(255) NOT NULL,
            lat FLOAT NOT NULL,
            lon FLOAT NOT NULL,
            node_id BIGINT,
            PRIMARY KEY (camera_id)
        );
        """
    )

    # 2. Events table (schema mirrors backend.models.Event / city_anpr.db)
    cur.execute(
        """
        CREATE TABLE events (
            id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
            plate VARCHAR(20) NOT NULL,
            camera_id VARCHAR(50) NOT NULL,
            timestamp DATETIME NOT NULL,
            speed_kmh FLOAT,
            heading_degrees FLOAT,
            lane INTEGER,
            ocr_confidence FLOAT,
            source VARCHAR(20) DEFAULT 'real_jinan',
            track_id VARCHAR(50),
            n_frames INTEGER,
            vote_margin FLOAT,
            best_crop_path VARCHAR(255),
            FOREIGN KEY(camera_id) REFERENCES cameras (camera_id) ON DELETE CASCADE
        );
        """
    )

    conn.commit()
    return conn


def create_indexes(conn: sqlite3.Connection) -> None:
    """Create indexes after bulk insertion for optimal query performance."""
    cur = conn.cursor()
    cur.execute("CREATE INDEX ix_cameras_camera_id ON cameras (camera_id);")
    cur.execute("CREATE INDEX ix_events_timestamp ON events (timestamp);")
    cur.execute("CREATE INDEX ix_events_camera_timestamp ON events (camera_id, timestamp);")
    cur.execute("CREATE INDEX ix_events_plate_timestamp ON events (plate, timestamp);")
    cur.execute("CREATE INDEX ix_events_plate ON events (plate);")
    cur.execute("CREATE INDEX ix_events_source ON events (source);")
    conn.commit()


def load_jinan_data(
    data_dir: Path | str = DEFAULT_INPUT_DIR,
    node_file: Optional[Path | str] = None,
    traj_file: Optional[Path | str] = None,
    out_db_path: Path | str = DEFAULT_OUT_DB,
    sample_mod: int = 20,
    city_anpr_db_path: Path | str = DEFAULT_CITY_DB,
    batch_size: int = DEFAULT_BATCH_SIZE,
    verbose: bool = True,
) -> Dict[str, Any]:
    """Load Jinan road network nodes and vehicle trajectory events into SQLite.

    Args:
        data_dir: Folder containing node_jinan.csv and traj_jinan.csv.
        node_file: Specific path to node_jinan.csv (optional).
        traj_file: Specific path to traj_jinan.csv (optional).
        out_db_path: Path to target SQLite database (default data/real_jinan.db).
        sample_mod: Keeps vehicles where VehicleID % sample_mod == 0 (1 = all).
        city_anpr_db_path: Path to existing simulation database to verify non-modification.
        batch_size: Number of records to insert per executemany batch.
        verbose: Whether to print progress messages to stdout.

    Returns:
        Dict of summary metrics and status flags.
    """
    t_start = time.time()
    data_path = Path(data_dir)
    out_db = Path(out_db_path)
    city_db = Path(city_anpr_db_path)

    node_csv_path = Path(node_file) if node_file else data_path / "node_jinan.csv"
    traj_csv_path = Path(traj_file) if traj_file else data_path / "traj_jinan.csv"

    if not node_csv_path.exists():
        raise FileNotFoundError(f"Node CSV file not found: {node_csv_path}")
    if not traj_csv_path.exists():
        raise FileNotFoundError(f"Trajectory CSV file not found: {traj_csv_path}")

    # Checksum city_anpr.db before starting
    sha_before = compute_file_sha256(city_db)

    if verbose:
        print("=" * 70)
        print("REAL JINAN TRAJECTORY DATA LOADER")
        print("=" * 70)
        print(f"Node file:     {node_csv_path}")
        print(f"Traj file:     {traj_csv_path}")
        print(f"Output DB:     {out_db}")
        print(f"Sample modulo: {sample_mod} (keeping VehicleID % {sample_mod} == 0)")
        print(f"city_anpr.db SHA-256 before: {sha_before}")
        print("-" * 70)

    # 1. Load Road Network Nodes
    # Note: File header is: NodeID, Longitude, Latitude, HasCamera (lon is column 1, lat is column 2)
    nodes: Dict[int, Dict[str, Any]] = {}
    total_camera_nodes = 0

    with open(node_csv_path, mode="r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            node_id = int(row["NodeID"])
            # Crucial: longitude is col 1, latitude is col 2
            lon = float(row["Longitude"])
            lat = float(row["Latitude"])
            has_camera = int(row["HasCamera"]) == 1

            if has_camera:
                total_camera_nodes += 1

            nodes[node_id] = {
                "lon": lon,
                "lat": lat,
                "has_camera": has_camera,
            }

    if verbose:
        print(f"Nodes loaded: {len(nodes):,} total, {total_camera_nodes:,} camera nodes (HasCamera=1)")

    # 2. Initialize fresh destination database
    conn = init_database(out_db)
    cur = conn.cursor()

    # Base reference datetime for timestamps
    base_datetime = datetime.datetime.combine(PLACEHOLDER_DATE, datetime.time(0, 0, 0))

    # Tracking sets and counters
    kept_vehicles: Set[int] = set()
    used_camera_node_ids: Set[int] = set()
    trips_kept = 0
    duplicate_trips_skipped = 0
    trips_repeated_id_diff_points = 0
    trips_with_ge_2_cam_pts = 0
    events_inserted = 0
    max_pts_in_trip = 0
    trips_over_500 = 0

    # Deduplication tracking structures:
    # 1. seen_trip_digests: (VehicleID, TripID, blake2b_digest_of_Points) to detect exact duplicate rows.
    #    Using a 16-byte blake2b digest keeps memory minimal while ensuring run-to-run stability.
    # 2. trip_id_counts: (VehicleID, TripID) -> count of distinct point-sequences seen for this pair.
    #    If the same (VehicleID, TripID) appears with DIFFERENT points, we append "-<n>" to track_id.
    seen_trip_digests: Set[Tuple[int, int, bytes]] = set()
    trip_id_counts: Dict[Tuple[int, int], int] = {}

    min_ts_str: Optional[str] = None
    max_ts_str: Optional[str] = None
    min_sec: float = 1e18
    max_sec: float = -1.0

    # Batch accumulator for executemany
    events_batch: List[Tuple] = []

    # 3. Stream and process trajectory CSV
    with open(traj_csv_path, mode="r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        total_rows_read = 0

        for row in reader:
            total_rows_read += 1
            vehicle_id = int(row["VehicleID"])

            # Vehicle-level sampling filter: keeping VehicleID % sample_mod == 0
            if sample_mod > 1 and (vehicle_id % sample_mod != 0):
                continue

            trip_id = int(row["TripID"])
            raw_points = row["Points"]
            if not raw_points:
                continue

            # Compute compact 16-byte blake2b digest of the Points string
            points_digest = hashlib.blake2b(raw_points.encode("utf-8"), digest_size=16).digest()
            exact_trip_key = (vehicle_id, trip_id, points_digest)

            # Check 1: Exact duplicate trip row (same VehicleID, TripID, and Points)
            if exact_trip_key in seen_trip_digests:
                duplicate_trips_skipped += 1
                continue

            # Record this unique combination of (VehicleID, TripID, Points)
            seen_trip_digests.add(exact_trip_key)

            # Check 2: Repeated VehicleID and TripID but with DIFFERENT Points
            pair_key = (vehicle_id, trip_id)
            if pair_key in trip_id_counts:
                trip_id_counts[pair_key] += 1
                trips_repeated_id_diff_points += 1
                occurrence_num = trip_id_counts[pair_key]
                track_id = f"{vehicle_id}-{trip_id}-{occurrence_num}"
            else:
                trip_id_counts[pair_key] = 1
                track_id = f"{vehicle_id}-{trip_id}"

            # This is a valid unique trip: count it towards trips kept
            kept_vehicles.add(vehicle_id)
            trips_kept += 1

            pts = raw_points.split("_")
            pts_count = len(pts)
            if pts_count > max_pts_in_trip:
                max_pts_in_trip = pts_count
            if pts_count > 500:
                trips_over_500 += 1

            # Anonymous plate identifier formatted as JNV<zero-padded VehicleID>
            plate = f"JNV{vehicle_id:07d}"

            cam_pts_in_trip = 0

            for p in pts:
                if not p:
                    continue
                node_str, sec_str = p.split("-")
                node_id = int(node_str)
                sec = float(sec_str)

                node_info = nodes.get(node_id)
                if not node_info or not node_info["has_camera"]:
                    # Non-camera node: omit from ANPR events table
                    continue

                cam_pts_in_trip += 1
                used_camera_node_ids.add(node_id)

                # Track temporal bounds
                if sec < min_sec:
                    min_sec = sec
                if sec > max_sec:
                    max_sec = sec

                # Build event timestamp
                dt = base_datetime + datetime.timedelta(seconds=sec)
                ts_str = dt.strftime("%Y-%m-%d %H:%M:%S")

                camera_id = f"JN_{node_id:06d}"

                # Append event row:
                # plate, camera_id, timestamp, speed_kmh, heading_degrees, lane,
                # ocr_confidence (NULL), source ('real_jinan'), track_id,
                # n_frames (NULL), vote_margin (NULL), best_crop_path (NULL)
                events_batch.append(
                    (
                        plate,
                        camera_id,
                        ts_str,
                        None,  # speed_kmh
                        None,  # heading_degrees
                        None,  # lane
                        None,  # ocr_confidence: strictly NULL (real telemetry, no OCR)
                        "real_jinan",  # source
                        track_id,  # track_id = "<VehicleID>-<TripID>"
                        None,  # n_frames: strictly NULL
                        None,  # vote_margin
                        None,  # best_crop_path
                    )
                )

                if len(events_batch) >= batch_size:
                    cur.executemany(
                        """
                        INSERT INTO events (
                            plate, camera_id, timestamp, speed_kmh, heading_degrees, lane,
                            ocr_confidence, source, track_id, n_frames, vote_margin, best_crop_path
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                        """,
                        events_batch,
                    )
                    conn.commit()
                    events_inserted += len(events_batch)
                    events_batch.clear()

            if cam_pts_in_trip >= 2:
                trips_with_ge_2_cam_pts += 1

            if verbose and total_rows_read % 200_000 == 0:
                print(f"  ... processed {total_rows_read:,} rows ({trips_kept:,} kept trips, {events_inserted:,} events)")

    # Flush remaining event records
    if events_batch:
        cur.executemany(
            """
            INSERT INTO events (
                plate, camera_id, timestamp, speed_kmh, heading_degrees, lane,
                ocr_confidence, source, track_id, n_frames, vote_margin, best_crop_path
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            events_batch,
        )
        conn.commit()
        events_inserted += len(events_batch)
        events_batch.clear()

    # 4. Insert Cameras Table
    # "cameras: one row per node with HasCamera=1 that is actually used by kept trips."
    cameras_batch: List[Tuple] = []
    for node_id in sorted(used_camera_node_ids):
        node_info = nodes[node_id]
        camera_id = f"JN_{node_id:06d}"
        name = f"Jinan real camera node {node_id}"
        lat = node_info["lat"]
        lon = node_info["lon"]

        cameras_batch.append((camera_id, name, lat, lon, node_id))

    cur.executemany(
        """
        INSERT INTO cameras (camera_id, name, lat, lon, node_id)
        VALUES (?, ?, ?, ?, ?);
        """,
        cameras_batch,
    )
    conn.commit()

    # 5. Create Indexes After Bulk Insert
    if verbose:
        print("Creating indexes on cameras and events tables...")
    create_indexes(conn)
    conn.close()

    # Calculate formatted time range
    if min_sec < 1e18 and max_sec >= 0:
        min_dt = base_datetime + datetime.timedelta(seconds=min_sec)
        max_dt = base_datetime + datetime.timedelta(seconds=max_sec)
        min_ts_str = min_dt.strftime("%Y-%m-%d %H:%M:%S")
        max_ts_str = max_dt.strftime("%Y-%m-%d %H:%M:%S")

    # 6. Checksum city_anpr.db after completion
    sha_after = compute_file_sha256(city_db)
    is_unchanged = (sha_before == sha_after)

    elapsed_s = round(time.time() - t_start, 2)

    summary = {
        "vehicles_kept": len(kept_vehicles),
        "trips_kept": trips_kept,
        "duplicate_trips_skipped": duplicate_trips_skipped,
        "trips_repeated_id_diff_points": trips_repeated_id_diff_points,
        "trips_with_ge_2_cam_pts": trips_with_ge_2_cam_pts,
        "events_inserted": events_inserted,
        "cameras_inserted": len(used_camera_node_ids),
        "longest_trip_points": max_pts_in_trip,
        "trips_over_500_points": trips_over_500,
        "min_timestamp": min_ts_str,
        "max_timestamp": max_ts_str,
        "elapsed_seconds": elapsed_s,
        "city_anpr_unchanged": is_unchanged,
        "sha_before": sha_before,
        "sha_after": sha_after,
    }

    if verbose:
        print("-" * 70)
        print("LOADING SUMMARY")
        print("-" * 70)
        print(f"Vehicles kept:                 {summary['vehicles_kept']:,}")
        print(f"Trips kept (unique trips):     {summary['trips_kept']:,}")
        print(f"Duplicate trip rows skipped:   {summary['duplicate_trips_skipped']:,}")
        print(f"Trips with repeated ID but different Points: {summary['trips_repeated_id_diff_points']:,}")
        print(f"Trips with >= 2 camera points: {summary['trips_with_ge_2_cam_pts']:,}")
        print(f"Camera events inserted:        {summary['events_inserted']:,}")
        print(f"Cameras inserted:              {summary['cameras_inserted']:,}")
        print(f"Longest trip (total points):   {summary['longest_trip_points']:,}")
        print(f"Trips with > 500 points:       {summary['trips_over_500_points']:,}")
        print(f"Time range:                    {summary['min_timestamp']} -> {summary['max_timestamp']}")
        print(f"Execution time:                {elapsed_s}s")
        print("-" * 70)
        print(f"city_anpr.db SHA-256 before:   {sha_before}")
        print(f"city_anpr.db SHA-256 after:    {sha_after}")
        print(f"city_anpr.db unchanged: {is_unchanged}")
        print("=" * 70)

    return summary


def main() -> None:
    """CLI entry point for python -m real_data.load_jinan."""
    parser = argparse.ArgumentParser(
        description="Load real Jinan road network and vehicle trajectory data into SQLite."
    )
    parser.add_argument(
        "--data-dir",
        type=str,
        default=str(DEFAULT_INPUT_DIR),
        help=r"Folder containing node_jinan.csv and traj_jinan.csv (default: C:\anpr_data\real_jinan)",
    )
    parser.add_argument(
        "--node-file",
        type=str,
        default=None,
        help="Path to node_jinan.csv (defaults to <data-dir>/node_jinan.csv)",
    )
    parser.add_argument(
        "--traj-file",
        type=str,
        default=None,
        help="Path to traj_jinan.csv (defaults to <data-dir>/traj_jinan.csv)",
    )
    parser.add_argument(
        "--sample-mod",
        type=int,
        default=20,
        help="Sample modulo: keeps VehicleID %% N == 0 (default: 20; use 1 for all vehicles)",
    )
    parser.add_argument(
        "--out",
        type=str,
        default=str(DEFAULT_OUT_DB),
        help="Output SQLite database path (default: data/real_jinan.db)",
    )
    parser.add_argument(
        "--city-db",
        type=str,
        default=str(DEFAULT_CITY_DB),
        help="Path to city_anpr.db to verify non-modification (default: data/city_anpr.db)",
    )

    args = parser.parse_args()

    try:
        load_jinan_data(
            data_dir=args.data_dir,
            node_file=args.node_file,
            traj_file=args.traj_file,
            out_db_path=args.out,
            sample_mod=args.sample_mod,
            city_anpr_db_path=args.city_db,
            verbose=True,
        )
    except Exception as exc:
        print(f"\n[ERROR] Failed to load Jinan data: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
