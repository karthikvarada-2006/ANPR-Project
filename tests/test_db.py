"""Integration tests for the database layer (SQLite & PostgreSQL compatible)."""

import pytest
from sqlalchemy import func, inspect

from backend.db import SessionLocal, engine
from backend.init_db import initialize_database
from backend.models import Alert, Blacklist, Camera, Event, Trajectory


@pytest.fixture(scope="module", autouse=True)
def setup_database():
    """Ensure database tables exist before running database tests."""
    initialize_database()


@pytest.fixture(scope="module")
def db_session():
    """Provide a transactional database session fixture."""
    session = SessionLocal()
    yield session
    session.close()


def test_database_tables_exist():
    """Verify that all required tables exist in the database."""
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    expected_tables = {"cameras", "events", "blacklist", "alerts", "trajectories"}

    assert expected_tables.issubset(
        existing_tables
    ), f"Missing tables: {expected_tables - existing_tables}"


def test_cameras_loaded_with_coordinates(db_session):
    """Verify that cameras exist and spatial coordinates are valid."""
    cam_count = db_session.query(func.count(Camera.camera_id)).scalar()
    if cam_count == 0:
        from backend.load_data import load_all_data
        load_all_data()
        cam_count = db_session.query(func.count(Camera.camera_id)).scalar()

    assert cam_count > 0, "No cameras found in database."
    sample_cam = db_session.query(Camera).first()
    assert sample_cam.lat is not None and 12.0 <= sample_cam.lat <= 14.0
    assert sample_cam.lon is not None and 77.0 <= sample_cam.lon <= 78.0


def test_events_referential_integrity(db_session):
    """Verify that every event's camera_id exists in the cameras table."""
    orphaned_events_count = (
        db_session.query(func.count(Event.id))
        .outerjoin(Camera, Event.camera_id == Camera.camera_id)
        .filter(Camera.camera_id.is_(None))
        .scalar()
    )

    assert (
        orphaned_events_count == 0
    ), f"Found {orphaned_events_count} orphaned events referencing non-existent cameras!"


def test_blacklist_records_exist(db_session):
    """Verify blacklist table contains target vehicles."""
    bl_count = db_session.query(func.count(Blacklist.plate)).scalar()
    assert bl_count > 0, "No blacklist records found."
