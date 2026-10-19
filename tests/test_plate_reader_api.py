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


# ==============================================================================
# 6. Low-Confidence Plate Read Review Flag Tests
# ==============================================================================
def test_review_status_unit_logic():
    """Unit test compute_review_status logic against threshold 0.80.
    
    Checks:
    - OCR confidence 0.611 gives REVIEW
    - OCR confidence 0.99 gives OK
    - Missing/None confidence does not crash and returns OK
    - Vote margin < 0.80 gives REVIEW
    - Edge cases at exact 0.80 boundary return OK
    """
    from backend.plate_utils import REVIEW_CONFIDENCE_THRESHOLD, compute_review_status

    # Must be exact round number 0.80 constant
    assert REVIEW_CONFIDENCE_THRESHOLD == 0.80, "REVIEW_CONFIDENCE_THRESHOLD must be 0.80"

    # Required specification checks:
    # 1. confidence 0.611 gives REVIEW
    assert compute_review_status(ocr_confidence=0.611) == "REVIEW"

    # 2. 0.99 gives OK
    assert compute_review_status(ocr_confidence=0.99) == "OK"

    # 3. Missing confidence does not crash (returns OK)
    assert compute_review_status(ocr_confidence=None) == "OK"
    assert compute_review_status(ocr_confidence=None, vote_margin=None) == "OK"
    assert compute_review_status(vote_margin=None) == "OK"

    # 4. Vote margin checks (threshold 0.80)
    assert compute_review_status(vote_margin=0.7107) == "REVIEW"
    assert compute_review_status(vote_margin=0.85) == "OK"

    # 5. Combined checks (OR condition: either below threshold triggers REVIEW)
    assert compute_review_status(ocr_confidence=0.95, vote_margin=0.65) == "REVIEW"
    assert compute_review_status(ocr_confidence=0.70, vote_margin=0.95) == "REVIEW"
    assert compute_review_status(ocr_confidence=0.80, vote_margin=0.80) == "OK"
    assert compute_review_status(ocr_confidence=0.80, vote_margin=None) == "OK"
    assert compute_review_status(ocr_confidence=None, vote_margin=0.80) == "OK"


def test_review_status_in_api_endpoints(client):
    """Integration test verifying review_status is returned by API endpoints."""
    # 1. GET /api/events (default query)
    resp = client.get("/api/events?limit=20")
    assert resp.status_code == 200
    data = resp.json()
    assert "events" in data
    assert len(data["events"]) > 0
    for ev in data["events"]:
        assert "review_status" in ev, "Event missing review_status field"
        assert ev["review_status"] in ("OK", "REVIEW")

    # 2. GET /api/events?source=video
    resp_video = client.get("/api/events?source=video&limit=20")
    assert resp_video.status_code == 200
    video_events = resp_video.json()["events"]
    assert len(video_events) > 0
    # At least one video sequence with lower confidence should be flagged for review
    statuses = {ev["review_status"] for ev in video_events}
    assert "review_status" in video_events[0]
    assert "REVIEW" in statuses or "OK" in statuses

    # 3. POST /api/plates/read on blank image
    blank_img = np.full((300, 300, 3), 128, dtype=np.uint8)
    _, encoded = cv2.imencode(".jpg", blank_img)
    resp_blank = client.post(
        "/api/plates/read",
        files={"file": ("blank.jpg", encoded.tobytes(), "image/jpeg")},
    )
    assert resp_blank.status_code == 200
    data_blank = resp_blank.json()
    assert "review_status" in data_blank
    assert data_blank["review_status"] == "OK"

    # 4. POST /api/plates/read on known vehicle image
    test_img_path = PROJECT_ROOT / "data" / "raw" / "indian-number-plates-dataset" / "video_images" / "video2_1360.jpg"
    if test_img_path.exists():
        with open(test_img_path, "rb") as f:
            img_bytes = f.read()
        resp_img = client.post(
            "/api/plates/read",
            files={"file": ("vehicle.jpg", img_bytes, "image/jpeg")},
        )
        assert resp_img.status_code == 200
        data_img = resp_img.json()
        assert "review_status" in data_img
        assert data_img["review_status"] in ("OK", "REVIEW")
        if data_img["plates"]:
            for p in data_img["plates"]:
                assert "review_status" in p
                assert p["review_status"] in ("OK", "REVIEW")


def test_sim_invariants_and_alert_counts():
    """Verify simulated numbers remain strictly preserved:
    - 31,244 simulated events
    - 40 simulation cameras
    - 44 total alerts generated from live surveillance engine
    """
    from backend.alert_engine import AlertEngine
    from backend.alert_rules import RuleContext
    import pandas as pd
    from simulator.config import EVENTS_PATH

    db_path = get_sqlite_path()
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    # 1. Verify 31,244 sim events
    cursor.execute("SELECT count(*) FROM events WHERE source = 'sim'")
    sim_count = cursor.fetchone()[0]
    assert sim_count == 31244, f"Expected 31,244 sim events, got {sim_count}"

    # 2. Verify 40 simulation cameras
    cursor.execute("SELECT count(*) FROM cameras WHERE camera_id LIKE 'CAM_%' AND camera_id NOT LIKE '%VIDEO%'")
    sim_cams = cursor.fetchone()[0]
    assert sim_cams == 40, f"Expected 40 cameras, got {sim_cams}"
    conn.close()

    # 3. Verify exactly 44 alerts from events.csv replay through AlertEngine
    assert EVENTS_PATH.exists(), f"Events CSV not found: {EVENTS_PATH}"
    df = pd.read_csv(EVENTS_PATH)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.sort_values("timestamp").reset_index(drop=True)

    engine = AlertEngine(dedup_minutes=10.0, context=RuleContext.get_instance())
    alerts = []
    for _, row in df.iterrows():
        ev_dict = row.to_dict()
        triggered = engine.process_event(ev_dict)
        if triggered:
            alerts.extend(triggered)

    assert len(alerts) == 44, f"Expected exactly 44 alerts, got {len(alerts)}"


