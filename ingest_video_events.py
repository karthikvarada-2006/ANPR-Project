"""Ingest Video ANPR Events into Database and Run Real-Time Surveillance Alert Engine.

Protocol:
1. Discovers and reads all `*_events.csv` files in `data/video_events/`.
2. Strictly verifies that all `camera_id` values exist in the database `cameras` table.
   If any camera_id is missing, halts immediately with a clear message (never invents fake coordinates).
3. Inserts events into the `events` table with `source='video'`.
4. Checks for existing events (plate, camera_id, timestamp, source='video') and skips already-inserted rows (idempotent).
5. Passes newly inserted events through `AlertEngine` to detect security violations (e.g. Blacklist hits, cloned plates, speeding)
   and saves any triggered alerts into the `alerts` table.
"""

import argparse
import datetime
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Set, Tuple

import pandas as pd
from sqlalchemy import func
from sqlalchemy.orm import Session

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.alert_engine import AlertEngine
from backend.alert_rules import RuleContext
from backend.db import SessionLocal
from backend.models import Alert, Camera, Event
from backend.plate_utils import normalize_plate


def get_known_camera_ids(session: Session) -> Set[str]:
    """Fetches all registered camera IDs from the database."""
    cams = session.query(Camera.camera_id).all()
    return {c[0] for c in cams}


def ingest_video_events(
    events_dir: Path = Path("data/video_events"),
    target_file: Optional[Path] = None,
    stop_on_missing_camera: bool = True,
) -> Dict[str, Any]:
    """Ingests video events from CSV files into the SQLite database."""
    session = SessionLocal()

    print("\n" + "=" * 80)
    print("=== ANPR VIDEO EVENTS INGESTION & ALERT PIPELINE ===")
    print("=" * 80)

    try:
        # 1. Discover CSV files
        if target_file is not None:
            csv_files = [target_file] if target_file.exists() else []
        else:
            csv_files = sorted(list(events_dir.glob("*_events.csv")))

        if not csv_files:
            print(f"[INFO] No '*_events.csv' files found in {events_dir.resolve()}.")
            return {
                "files_count": 0,
                "read_count": 0,
                "inserted_count": 0,
                "skipped_count": 0,
                "alerts_count": 0,
            }

        print(f"Found {len(csv_files)} event file(s) to process:")
        for cf in csv_files:
            print(f"  - {cf.resolve()}")

        # 2. Load registered cameras
        known_cameras = get_known_camera_ids(session)
        print(f"\nRegistered cameras in database: {len(known_cameras)} cameras.")

        total_read = 0
        total_inserted = 0
        total_skipped = 0
        newly_inserted_events: List[Dict[str, Any]] = []

        # 3. Process each CSV file
        for csv_path in csv_files:
            print(f"\nReading {csv_path.name}...")
            df = pd.read_csv(csv_path)
            if df.empty:
                print(f"  [INFO] File {csv_path.name} is empty. Skipping.")
                continue

            # Validate required columns
            required_cols = {"plate", "camera_id", "timestamp"}
            missing_cols = required_cols - set(df.columns)
            if missing_cols:
                raise ValueError(f"File {csv_path.name} missing required columns: {missing_cols}")

            # Check camera IDs across all rows in file
            file_cameras = set(df["camera_id"].dropna().unique())
            unknown_cameras = file_cameras - known_cameras

            if unknown_cameras:
                unknown_list = sorted(list(unknown_cameras))
                error_msg = (
                    f"\n[ERROR] Unknown camera_id '{unknown_list[0]}' found in '{csv_path.name}'.\n"
                    f"Camera '{unknown_list[0]}' is NOT registered in the database 'cameras' table.\n"
                    f"Halting ingestion: Cannot invent coordinates for unregistered cameras.\n"
                    f"Please register this camera in cameras.csv / database before ingesting."
                )
                if stop_on_missing_camera:
                    print(error_msg, file=sys.stderr)
                    raise RuntimeError(error_msg)
                else:
                    print(error_msg)
                    continue

            # Process rows
            for _, row in df.iterrows():
                total_read += 1
                raw_plate = str(row["plate"]).strip()
                clean_plate = normalize_plate(raw_plate)
                cam_id = str(row["camera_id"]).strip()
                
                # Timestamp parsing
                ts_raw = row["timestamp"]
                if isinstance(ts_raw, str):
                    ts = pd.to_datetime(ts_raw).to_pydatetime()
                else:
                    ts = ts_raw

                track_id = int(row["track_id"]) if pd.notnull(row.get("track_id")) else None
                n_frames = int(row["n_frames"]) if pd.notnull(row.get("n_frames")) else 1
                vote_margin = float(row["vote_margin"]) if pd.notnull(row.get("vote_margin")) else None
                best_crop_path = str(row["best_crop_path"]) if pd.notnull(row.get("best_crop_path")) else None
                ocr_conf = float(row["ocr_confidence"]) if pd.notnull(row.get("ocr_confidence")) else None
                speed_kmh = float(row["speed_kmh"]) if pd.notnull(row.get("speed_kmh")) else None
                heading_deg = float(row["heading_degrees"]) if pd.notnull(row.get("heading_degrees")) else None
                lane = int(row["lane"]) if pd.notnull(row.get("lane")) else 1
                source_val = str(row["source"]).strip() if pd.notnull(row.get("source")) and str(row["source"]).strip() else "video"

                # Check if this event was already inserted (idempotency check)
                existing = session.query(Event.id).filter(
                    Event.plate == clean_plate,
                    Event.camera_id == cam_id,
                    Event.timestamp == ts,
                    Event.source == source_val,
                ).first()

                if existing:
                    total_skipped += 1
                    continue

                # Create and add Event
                event_obj = Event(
                    plate=clean_plate,
                    camera_id=cam_id,
                    timestamp=ts,
                    speed_kmh=speed_kmh,
                    heading_degrees=heading_deg,
                    lane=lane,
                    ocr_confidence=ocr_conf,
                    source=source_val,
                    track_id=track_id,
                    n_frames=n_frames,
                    vote_margin=vote_margin,
                    best_crop_path=best_crop_path,
                )
                session.add(event_obj)
                total_inserted += 1

                # Collect event dict for AlertEngine
                newly_inserted_events.append({
                    "plate": clean_plate,
                    "camera_id": cam_id,
                    "timestamp": ts,
                    "speed_kmh": speed_kmh,
                    "lane": lane,
                    "ocr_confidence": ocr_conf,
                    "source": source_val,
                })

            session.commit()
            print(f"  [OK] Processed {csv_path.name}: {len(df)} rows read.")

        print(f"\nDatabase Event Summary:")
        print(f"  Total Rows Read:      {total_read}")
        print(f"  Existing (Skipped):   {total_skipped}")
        print(f"  Newly Inserted:       {total_inserted}")

        # 4. Run AlertEngine on newly inserted events
        alerts_triggered = 0
        if newly_inserted_events:
            print("\nRunning Surveillance Alert Engine on new video events...")
            rule_ctx = RuleContext.get_instance()
            engine = AlertEngine(dedup_minutes=10.0, context=rule_ctx)

            for ev in newly_inserted_events:
                alerts = engine.process_event(ev, save_to_db=True, session=session)
                if alerts:
                    alerts_triggered += len(alerts)
                    for a in alerts:
                        print(f"  🚨 ALERT TRIGGERED: [{a['severity']}][{a['alert_type']}] Vehicle '{a['plate']}' @ {a['camera_id']}")

            session.commit()
            print(f"  [OK] Alerts evaluated: {alerts_triggered} alert(s) triggered and saved to database.")
        else:
            print("\nNo new events to evaluate for alerts.")

        print("\n" + "=" * 80)
        print("=== INGESTION FINISHED SUCCESSFULLY ===")
        print("=" * 80)

        return {
            "files_count": len(csv_files),
            "read_count": total_read,
            "inserted_count": total_inserted,
            "skipped_count": total_skipped,
            "alerts_count": alerts_triggered,
        }

    except Exception as exc:
        session.rollback()
        raise
    finally:
        session.close()


def main():
    parser = argparse.ArgumentParser(description="Ingest video ANPR events into database and run alert engine.")
    parser.add_argument("--dir", type=str, default="data/video_events", help="Directory containing *_events.csv files.")
    parser.add_argument("--file", type=str, default=None, help="Optional single CSV file to ingest.")
    args = parser.parse_args()

    target_file = Path(args.file) if args.file else None
    events_dir = Path(args.dir)

    try:
        ingest_video_events(events_dir=events_dir, target_file=target_file)
        sys.exit(0)
    except Exception as e:
        print(f"\n[FATAL] Ingestion terminated: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
