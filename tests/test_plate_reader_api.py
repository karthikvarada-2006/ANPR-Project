"""Integration & Unit Tests for Plate Reader API, Video Ingestion, and Schema Migration.

Verifies:
1. POST /api/plates/read returns detected plate(s) for a known test photo.
2. POST /api/plates/read rejects text files with 400 Bad Request.
3. POST /api/plates/read returns an empty list for a blank/solid image without plates.
4. Video events ingestion via ingest_video_events() is idempotent (re-running inserts 0 duplicates).
5. Schema migration maintains the exact row count of the events table.
"""

from io import BytesIO
from pathlib import Path
import sqlite3
import sys

import cv2
from fastapi.testclient import TestClient
import numpy as np
import pytest

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.api.main import app
from backend.migrate_events_schema import get_sqlite_path, run_migration
from ingest_video_events import ingest_video_events


@pytest.fixture(scope="module")
def client():
    """FastAPI TestClient fixture."""
    return TestClient(app)


# ==============================================================================
# 1. API: Upload Endpoint Tests
# ==============================================================================
def test_upload_endpoint_returns_plate_for_known_test_image(client):
    """Verify that uploading a known vehicle test image returns plate, box, confidences, and base64."""
    test_img_path = PROJECT_ROOT / "data" / "raw" / "indian-number-plates-dataset" / "video_images" / "video2_1360.jpg"
    if not test_img_path.exists():
        # Fallback to any valid jpg in video_images
        jpgs = list((PROJECT_ROOT / "data" / "raw" / "indian-number-plates-dataset" / "video_images").glob("*.jpg"))
        assert len(jpgs) > 0, "No test images found"
        test_img_path = jpgs[0]

    with open(test_img_path, "rb") as f:
        img_bytes = f.read()

    response = client.post(
        "/api/plates/read",
        files={"file": ("vehicle.jpg", img_bytes, "image/jpeg")},
    )

    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    data = response.json()

    assert "detected_count" in data
    assert data["detected_count"] >= 1, "Expected at least 1 detected plate on known test image"
    assert "plates" in data
    assert len(data["plates"]) == data["detected_count"]

    first_plate = data["plates"][0]
    assert "plate" in first_plate and len(first_plate["plate"]) >= 4
    assert "detector_confidence" in first_plate and 0.0 <= first_plate["detector_confidence"] <= 1.0
    assert "ocr_confidence" in first_plate and 0.0 <= first_plate["ocr_confidence"] <= 1.0
    assert "box" in first_plate and len(first_plate["box"]) == 4
    assert "is_blacklisted" in first_plate
    assert "known_sightings" in first_plate

    # Check annotated image Base64 representation
    assert "annotated_image_base64" in data
    assert data["annotated_image_base64"].startswith("data:image/jpeg;base64,")


def test_upload_endpoint_rejects_text_file(client):
    """Verify that uploading a non-image text file is rejected with 400 Bad Request."""
    text_content = b"This is a text file, not a license plate image."
    response = client.post(
        "/api/plates/read",
        files={"file": ("test_doc.txt", text_content, "text/plain")},
    )

    assert response.status_code == 400, f"Expected 400 Bad Request, got {response.status_code}"
    error_msg = response.json().get("detail", "")
    assert "Unsupported file format" in error_msg or "JPG and PNG" in error_msg


def test_upload_endpoint_returns_empty_list_for_blank_image(client):
    """Verify that uploading a blank/solid image returns detected_count=0 and empty list."""
    # Create a 300x300 solid grey blank image
    blank_img = np.full((300, 300, 3), 128, dtype=np.uint8)
    _, encoded = cv2.imencode(".jpg", blank_img)
    blank_bytes = encoded.tobytes()

    response = client.post(
        "/api/plates/read",
        files={"file": ("blank.jpg", blank_bytes, "image/jpeg")},
    )

    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    data = response.json()
    assert data["detected_count"] == 0
    assert data["plates"] == []


def test_get_events_endpoint(client):
    """Verify GET /api/events returns video source events with filters."""
    response = client.get("/api/events?source=video&limit=10")
    assert response.status_code == 200
    data = response.json()
    assert "total" in data
    assert "events" in data
    assert isinstance(data["events"], list)
    if data["events"]:
        ev = data["events"][0]
        assert ev["source"] == "video"
        assert "vote_margin" in ev
        assert "n_frames" in ev


# ==============================================================================
# 2. Ingestion: Idempotency Test
# ==============================================================================
def test_ingestion_is_idempotent():
    """Verify that running ingest_video_events() multiple times does not insert duplicate records."""
    db_path = get_sqlite_path()
    assert db_path.exists(), f"Database not found: {db_path}"

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    cursor.execute("SELECT count(*) FROM events WHERE source = 'video'")
    count_before = cursor.fetchone()[0]
    conn.close()

    # Run ingestion
    result = ingest_video_events(stop_on_missing_camera=True)
    assert result["inserted_count"] == 0, f"Expected 0 new insertions on already ingested data, got {result['inserted_count']}"

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    cursor.execute("SELECT count(*) FROM events WHERE source = 'video'")
    count_after = cursor.fetchone()[0]
    conn.close()

    assert count_after == count_before, "Database event count changed on idempotent re-run!"


# ==============================================================================
# 3. Database Migration: Row Count Integrity Test
# ==============================================================================
def test_migration_keeps_row_count():
    """Verify that running the schema migration preserves 100% of rows with zero data loss."""
    db_path = get_sqlite_path()
    assert db_path.exists(), f"Database not found: {db_path}"

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    cursor.execute("SELECT count(*) FROM events")
    count_before = cursor.fetchone()[0]
    conn.close()

    # Re-run migration (idempotent)
    migration_ok = run_migration()
    assert migration_ok is True, "Migration failed"

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    cursor.execute("SELECT count(*) FROM events")
    count_after = cursor.fetchone()[0]

    # Verify columns exist
    cursor.execute("PRAGMA table_info(events)")
    col_names = {row[1] for row in cursor.fetchall()}
    conn.close()

    assert count_after == count_before, f"Row count mismatch: before={count_before}, after={count_after}"
    required_cols = {"source", "track_id", "n_frames", "vote_margin", "best_crop_path"}
    assert required_cols.issubset(col_names), f"Missing columns in events table: {required_cols - col_names}"


# ==============================================================================
# 4. Video Events Data Quality & Confidence Tests
# ==============================================================================
def test_no_source_video_has_constant_085_confidence():
    """Verify that source='video' rows have real diverse OCR confidences and not a constant 0.85 default."""
    db_path = get_sqlite_path()
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    cursor.execute("SELECT ocr_confidence FROM events WHERE source = 'video'")
    rows = cursor.fetchall()
    conn.close()

    assert len(rows) > 0, "Expected video events in database"
    confs = [r[0] for r in rows if r[0] is not None]
    assert len(confs) > 0, "Expected non-null OCR confidences"

    distinct_confs = set(confs)
    # Must have multiple distinct confidence values computed from actual character probabilities
    assert len(distinct_confs) > 1, f"Expected diverse OCR confidences, but found only: {distinct_confs}"
    # Must NOT have all rows equal to 0.85
    assert not (len(distinct_confs) == 1 and 0.85 in distinct_confs), "All video rows had hardcoded 0.85!"


# ==============================================================================
# 5. Simulation Baseline Analytics Invariant Tests
# ==============================================================================
def test_sim_analytics_unchanged():
    """Verify simulated event baseline statistics remain strictly unchanged after video ingestion."""
    from backend.analytics import camera_stats, load_events_df

    db_path = get_sqlite_path()
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    # 1. Sim events count invariant: exactly 31,244
    cursor.execute("SELECT count(*) FROM events WHERE source = 'sim'")
    sim_count = cursor.fetchone()[0]
    assert sim_count == 31244, f"Expected 31,244 sim events, got {sim_count}"

    # 2. Simulator cameras invariant: 40 cameras
    cursor.execute("SELECT count(*) FROM cameras WHERE camera_id LIKE 'CAM_%' AND camera_id NOT LIKE '%VIDEO%'")
    sim_cams_count = cursor.fetchone()[0]
    assert sim_cams_count == 40, f"Expected 40 simulation cameras, got {sim_cams_count}"

    # 3. Average city speed invariant: 31.80 km/h
    cursor.execute("SELECT avg(speed_kmh) FROM events WHERE source = 'sim'")
    avg_speed = cursor.fetchone()[0]
    assert round(avg_speed, 2) == 31.80, f"Expected average speed 31.80 km/h, got {avg_speed:.2f}"

    # 4. Top-5 busiest cameras invariant
    cursor.execute(
        "SELECT camera_id, count(*) as cnt FROM events WHERE source = 'sim' "
        "GROUP BY camera_id ORDER BY cnt DESC LIMIT 5"
    )
    top5_cams = [r[0] for r in cursor.fetchall()]
    conn.close()

    expected_top5 = ["CAM_003", "CAM_001", "CAM_002", "CAM_004", "CAM_007"]
    assert top5_cams == expected_top5, f"Top 5 busiest cameras changed: expected {expected_top5}, got {top5_cams}"

    # 5. Analytics module defaults to sim
    df_sim = load_events_df()
    assert len(df_sim) == 31244, f"load_events_df() default count mismatch: {len(df_sim)}"

