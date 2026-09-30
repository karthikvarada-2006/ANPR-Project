"""Integration tests for the PostgreSQL + PostGIS database layer."""

import pytest
from sqlalchemy import func, inspect
from sqlalchemy.exc import OperationalError

from backend.db import SessionLocal, engine
from backend.models import Alert, Blacklist, Camera, Event


def is_database_online() -> bool:
    """Check whether the database is actively accepting connections."""
    try:
        with engine.connect() as conn:
            return True
    except Exception:
        return False


# Skip all tests in this module if the database service is offline
pytestmark = pytest.mark.skipif(
    not is_database_online(),
    reason="PostgreSQL database is offline. Start the container with 'docker compose up -d'.",
)


@pytest.fixture(scope="module")
def db_session():
    """Provide a database session fixture."""
    session = SessionLocal()
    yield session
    session.close()


def test_database_tables_exist():
    """Verify that all required tables exist in the database."""
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    expected_tables = {"cameras", "events", "blacklist", "alerts"}

    assert expected_tables.issubset(
        existing_tables
    ), f"Missing tables: {expected_tables - existing_tables}"


def test_cameras_loaded_with_geometries(db_session):
    """Verify that cameras exist and spatial coordinates are populated."""
    cam_count = db_session.query(func.count(Camera.camera_id)).scalar()
    assert cam_count > 0, "No cameras found in database. Run 'python backend/load_data.py'."

    sample_cam = db_session.query(Camera).first()
    assert sample_cam.lat is not None
    assert sample_cam.lon is not None
    assert sample_cam.geom is not None, "Camera PostGIS geometry must not be null"


def test_events_referential_integrity(db_session):
    """Verify that every event's camera_id exists in the cameras table."""
    # Query for orphaned events (events whose camera_id does not exist in cameras)
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
    assert bl_count > 0, "No blacklist records found. Run 'python backend/load_data.py'."
