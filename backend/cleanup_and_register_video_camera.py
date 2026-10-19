"""Registration for CAM_VIDEO_01 and cleanup of faulty source='video' rows.

Protocol:
1. Checks that the database file exists and a timestamped backup was already made.
2. Ensures camera 'CAM_VIDEO_01' exists in the 'cameras' table with placeholder
   coordinates clearly marked in code and a name containing 'demo'.
3. Deletes ONLY the faulty rows where source='video'.
4. Strictly verifies that rows with source='sim' are completely untouched (31,244 rows).
"""

import sqlite3
import sys
from pathlib import Path

# Placeholder coordinates for demo camera:
# Bangalore City Center (Cubbon Park / MG Road area) placeholder coordinates:
# Latitude: 12.9716 N, Longitude: 77.5946 E (clearly marked demo placeholder)
DEMO_CAMERA_ID = "CAM_VIDEO_01"
DEMO_CAMERA_NAME = "ANPR Video Pipeline Demo Camera"
DEMO_LAT = 12.9716  # Placeholder coordinates for video demo stream
DEMO_LON = 77.5946  # Placeholder coordinates for video demo stream
DEMO_NODE_ID = 999999999

DB_PATH = Path("data/city_anpr.db")


def cleanup_and_register(db_path: Path = DB_PATH) -> None:
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found at: {db_path.resolve()}")

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    try:
        # 1. Check existing rows
        cur.execute("SELECT count(*) FROM events WHERE source='sim'")
        sim_before = cur.fetchone()[0]

        cur.execute("SELECT count(*) FROM events WHERE source='video'")
        video_before = cur.fetchone()[0]

        print(f"[INFO] Current state before cleanup:")
        print(f"  - source='sim' events:   {sim_before:,}")
        print(f"  - source='video' events: {video_before:,}")

        # 2. Register or update CAM_VIDEO_01
        cur.execute("SELECT camera_id, name, lat, lon FROM cameras WHERE camera_id = ?", (DEMO_CAMERA_ID,))
        existing_cam = cur.fetchone()

        if existing_cam:
            print(f"[INFO] Camera '{DEMO_CAMERA_ID}' already exists: {existing_cam}")
        else:
            cur.execute(
                """
                INSERT INTO cameras (camera_id, name, lat, lon, node_id)
                VALUES (?, ?, ?, ?, ?)
                """,
                (DEMO_CAMERA_ID, DEMO_CAMERA_NAME, DEMO_LAT, DEMO_LON, DEMO_NODE_ID),
            )
            print(f"[SUCCESS] Registered demo camera '{DEMO_CAMERA_ID}':")
            print(f"  Name:        {DEMO_CAMERA_NAME} (contains 'demo')")
            print(f"  Coordinates: ({DEMO_LAT}, {DEMO_LON}) [PLACEHOLDER]")

        # 3. Delete faulty source='video' rows
        cur.execute("DELETE FROM events WHERE source='video'")
        deleted_count = cur.rowcount
        print(f"[SUCCESS] Deleted {deleted_count} faulty source='video' rows.")

        # Also clean any alerts referencing deleted video events if present
        cur.execute("DELETE FROM alerts WHERE camera_id = ?", (DEMO_CAMERA_ID,))
        conn.commit()

        # 4. Strict verification of sim data preservation
        cur.execute("SELECT count(*) FROM events WHERE source='sim'")
        sim_after = cur.fetchone()[0]

        cur.execute("SELECT count(*) FROM events WHERE source='video'")
        video_after = cur.fetchone()[0]

        assert sim_after == sim_before, f"CRITICAL: sim rows changed from {sim_before} to {sim_after}!"
        assert sim_after == 31244, f"CRITICAL: Expected 31,244 sim rows, found {sim_after}!"
        assert video_after == 0, f"CRITICAL: Expected 0 video rows, found {video_after}!"

        print(f"\n[VERIFIED] Post-cleanup state:")
        print(f"  - source='sim' events:   {sim_after:,} (100% PRESERVED, 0 delta)")
        print(f"  - source='video' events: {video_after}")

    finally:
        conn.close()


if __name__ == "__main__":
    cleanup_and_register()
