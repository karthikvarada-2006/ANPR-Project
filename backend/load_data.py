"""Data loader script: populates PostgreSQL/PostGIS tables from simulator CSVs."""

import datetime
from pathlib import Path
import sys
from typing import List

# Ensure project root is in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import pandas as pd
from sqlalchemy import delete, insert
from sqlalchemy.exc import OperationalError
from tqdm import tqdm

from backend.db import SessionLocal, engine
from backend.models import Alert, Blacklist, Camera, Event, Trajectory

# Simulator data paths
ROOT_DIR = Path(__file__).resolve().parent.parent
SIM_DIR = ROOT_DIR / "data" / "sim"
CAMERAS_CSV = SIM_DIR / "cameras.csv"
EVENTS_CSV = SIM_DIR / "events.csv"
BLACKLIST_CSV = SIM_DIR / "blacklist.csv"

BATCH_SIZE = 5000


def clear_tables(session) -> None:
    """Clear all tables in foreign-key safe order."""
    print("Clearing existing table records (safe re-run)...")
    session.execute(delete(Trajectory))
    session.execute(delete(Alert))
    session.execute(delete(Event))
    session.execute(delete(Blacklist))
    session.execute(delete(Camera))
    session.commit()
    print("  [OK] All tables cleared.")


def load_cameras(session) -> int:
    """Load cameras from cameras.csv into database with lat/lon coordinates."""
    print(f"\nLoading cameras from {CAMERAS_CSV.name}...")
    df = pd.read_csv(CAMERAS_CSV)

    camera_records = []
    for _, row in df.iterrows():
        lat = float(row["lat"])
        lon = float(row["lon"])

        camera_records.append(
            {
                "camera_id": str(row["camera_id"]),
                "name": str(row["name"]),
                "lat": lat,
                "lon": lon,
                "node_id": int(row["node_id"]),
            }
        )

    session.execute(insert(Camera), camera_records)
    session.commit()
    print(f"  [OK] Inserted {len(camera_records)} cameras.")
    return len(camera_records)


def load_blacklist(session) -> int:
    """Load security blacklist from blacklist.csv."""
    print(f"\nLoading security blacklist from {BLACKLIST_CSV.name}...")
    df = pd.read_csv(BLACKLIST_CSV)

    blacklist_records = []
    for _, row in df.iterrows():
        added_date = pd.to_datetime(row["added_date"]).to_pydatetime()
        blacklist_records.append(
            {
                "plate": str(row["plate"]),
                "reason": str(row["reason"]),
                "added_at": added_date,
            }
        )

    session.execute(insert(Blacklist), blacklist_records)
    session.commit()
    print(f"  [OK] Inserted {len(blacklist_records)} blacklist plates.")
    return len(blacklist_records)


def load_events(session) -> int:
    """Load ANPR sighting events from events.csv in high-speed batches."""
    print(f"\nLoading ANPR sighting events from {EVENTS_CSV.name}...")
    df = pd.read_csv(EVENTS_CSV)
    total_rows = len(df)

    # Convert timestamps to native python datetimes
    df["timestamp"] = pd.to_datetime(df["timestamp"])

    inserted_count = 0
    with tqdm(total=total_rows, desc="Inserting events", unit="rows") as pbar:
        for start_idx in range(0, total_rows, BATCH_SIZE):
            end_idx = min(start_idx + BATCH_SIZE, total_rows)
            batch_df = df.iloc[start_idx:end_idx]

            batch_records = []
            for _, row in batch_df.iterrows():
                batch_records.append(
                    {
                        "plate": str(row["plate"]),
                        "camera_id": str(row["camera_id"]),
                        "timestamp": row["timestamp"].to_pydatetime(),
                        "speed_kmh": float(row["speed_kmh"]) if pd.notnull(row["speed_kmh"]) else None,
                        "heading_degrees": float(row["heading_degrees"]) if pd.notnull(row["heading_degrees"]) else None,
                        "lane": int(row["lane"]) if pd.notnull(row["lane"]) else None,
                        "ocr_confidence": float(row["ocr_confidence"]) if pd.notnull(row["ocr_confidence"]) else None,
                        "source": "sim",
                    }
                )

            session.execute(insert(Event), batch_records)
            session.commit()
            pbar.update(len(batch_records))
            inserted_count += len(batch_records)

    print(f"  [OK] Inserted {inserted_count:,} events.")
    return inserted_count


def load_all_data() -> bool:
    """Execute data ingestion pipeline."""
    # Check that required CSV files exist
    missing = [f for f in [CAMERAS_CSV, EVENTS_CSV, BLACKLIST_CSV] if not f.exists()]
    if missing:
        print("[ERROR] Missing simulator data files:")
        for m in missing:
            print(f"  - {m}")
        print("\nPlease run the simulator first:")
        print("  python -m simulator.run_all")
        return False

    session = SessionLocal()
    try:
        clear_tables(session)
        num_cams = load_cameras(session)
        num_bl = load_blacklist(session)
        num_ev = load_events(session)

        print("\n" + "=" * 60)
        print("DATABASE INGESTION SUMMARY")
        print("=" * 60)
        print(f"  Cameras loaded:    {num_cams:>8,d}")
        print(f"  Blacklist loaded:  {num_bl:>8,d}")
        print(f"  Events loaded:     {num_ev:>8,d}")
        print("=" * 60)
        print("All data ingested successfully.")
        return True

    except OperationalError as err:
        session.rollback()
        print("\n[ERROR] Database connection lost during load:")
        print(f"  {err}")
        print("Ensure PostgreSQL is running: docker compose up -d")
        return False
    except Exception as exc:
        session.rollback()
        print(f"\n[ERROR] Data load failed: {exc}")
        return False
    finally:
        session.close()


def main() -> int:
    success = load_all_data()
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
