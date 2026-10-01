"""Database inspection and verification script."""

import sys
from pathlib import Path

# Ensure project root is in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from sqlalchemy import desc, func
from sqlalchemy.exc import OperationalError

from backend.db import SessionLocal, engine
from backend.models import Alert, Blacklist, Camera, Event, Trajectory


def check_database() -> bool:
    """Inspect and print database table counts, busiest cameras, and sample plate sightings."""
    print("=" * 65)
    print("CITY ANPR DATABASE STATUS & VERIFICATION")
    print("=" * 65)
    print(f"Target Database: {engine.url.render_as_string(hide_password=True)}\n")

    session = SessionLocal()
    try:
        # 1. Row counts per table
        print("--- Table Row Counts ---")
        cam_count = session.query(func.count(Camera.camera_id)).scalar()
        event_count = session.query(func.count(Event.id)).scalar()
        bl_count = session.query(func.count(Blacklist.plate)).scalar()
        alert_count = session.query(func.count(Alert.id)).scalar()
        traj_count = session.query(func.count(Trajectory.id)).scalar()

        print(f"  cameras:       {cam_count:>10,d} rows")
        print(f"  events:        {event_count:>10,d} rows")
        print(f"  blacklist:     {bl_count:>10,d} rows")
        print(f"  alerts:        {alert_count:>10,d} rows")
        print(f"  trajectories:  {traj_count:>10,d} rows")

        if cam_count == 0 or event_count == 0:
            print("\n[NOTE] Tables are currently empty. Run data loading script:")
            print("  python backend/load_data.py")
            return True

        # 2. Top 5 Busiest Cameras
        print("\n--- Top 5 Busiest ANPR Cameras ---")
        top_cameras = (
            session.query(
                Camera.camera_id,
                Camera.name,
                func.count(Event.id).label("total_events"),
            )
            .join(Event, Camera.camera_id == Event.camera_id)
            .group_by(Camera.camera_id, Camera.name)
            .order_by(desc("total_events"))
            .limit(5)
            .all()
        )

        print(f"{'Camera ID':<12} | {'Total Events':<14} | {'Intersection Name'}")
        print("-" * 65)
        for cam_id, name, total in top_cameras:
            print(f"{cam_id:<12} | {total:>12,d}   | {name}")

        # 3. Sample Plate Sightings
        print("\n--- Sample Vehicle Plate Activity ---")
        # Find the vehicle with the most sightings
        sample_plate_row = (
            session.query(
                Event.plate,
                func.count(Event.id).label("plate_events"),
            )
            .group_by(Event.plate)
            .order_by(desc("plate_events"))
            .first()
        )

        if sample_plate_row:
            sample_plate, total_sightings = sample_plate_row
            print(f"Sample Vehicle Plate: {sample_plate}")
            print(f"Total Sightings Logged: {total_sightings}")

            # Fetch chronological sightings for this plate
            sightings = (
                session.query(
                    Event.camera_id,
                    Event.timestamp,
                    Event.speed_kmh,
                    Camera.name,
                )
                .join(Camera, Event.camera_id == Camera.camera_id)
                .filter(Event.plate == sample_plate)
                .order_by(Event.timestamp)
                .limit(5)
                .all()
            )

            print("\nRecent Sightings Timeline (First 5):")
            for cid, ts, speed, cam_name in sightings:
                print(f"  [{ts}] {cid} ({speed:.1f} km/h) -> {cam_name}")

        print("\n" + "=" * 65)
        print("Database verification passed successfully.")
        print("=" * 65)
        return True

    except OperationalError as err:
        print("\n[ERROR] Unable to connect to the database:")
        print(f"  {err}")
        print("Ensure PostgreSQL container is running: docker compose up -d")
        return False
    except Exception as exc:
        print(f"\n[ERROR] Database check failed: {exc}")
        return False
    finally:
        session.close()


def main() -> int:
    success = check_database()
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
