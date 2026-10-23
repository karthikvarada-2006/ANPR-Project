"""Integration and Unit Tests for City ANPR FastAPI Backend."""

from __future__ import annotations

import csv
import datetime
import io
from pathlib import Path
import re
import sys
from typing import Dict, List

import pytest
from fastapi.testclient import TestClient

# Ensure project root is in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.api.main import app
from backend.db import SessionLocal
from backend.models import Alert, Blacklist, Camera, Event
from backend.plate_utils import escape_csv_cell, normalize_plate, sanitize_filename_plate


@pytest.fixture(scope="module")
def client() -> TestClient:
    """FastAPI TestClient fixture."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="module")
def known_plate() -> str:
    """Fixture to obtain a known plate present in the database with multiple sightings."""
    from sqlalchemy import func
    db = SessionLocal()
    try:
        plate = (
            db.query(Event.plate)
            .group_by(Event.plate)
            .having(func.count(Event.id) >= 3)
            .first()
        )
        assert plate is not None, "Database has no multi-sighting events; run backend.load_data first"
        return plate[0]
    finally:
        db.close()


def test_health_ok(client: TestClient):
    """Check that GET /api/health returns 200, status 'ok', and database connected."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["database"] == "connected"
    assert data["cameras_count"] >= 40
    assert data["events_count"] > 0


def test_cameras_returns_40(client: TestClient):
    """Check that GET /api/cameras returns exactly 40 deployed cameras with coordinates."""
    response = client.get("/api/cameras")
    assert response.status_code == 200
    cameras = response.json()
    assert len(cameras) == 40

    first = cameras[0]
    assert "id" in first
    assert "name" in first
    assert "lat" in first
    assert "lon" in first
    assert isinstance(first["lat"], float)
    assert isinstance(first["lon"], float)


def test_trajectory_for_known_plate_has_time_ordered_points_and_route(client: TestClient, known_plate: str):
    """Check that GET /api/trajectory/{plate} returns time-ordered points and non-empty route geometry."""
    response = client.get(f"/api/trajectory/{known_plate}?fuzzy=true")
    assert response.status_code == 200
    data = response.json()

    assert data["plate"] == normalize_plate(known_plate)
    assert data["total_trips"] > 0
    assert len(data["points"]) > 0
    assert len(data["route_geometry"]) > 0
    assert data["total_distance_km"] > 0.0

    # Verify points are chronologically ordered
    timestamps = [p["timestamp"] for p in data["points"]]
    assert timestamps == sorted(timestamps)

    # Verify each point contains required fields
    p0 = data["points"][0]
    assert "time" in p0
    assert "camera" in p0
    assert "lat" in p0
    assert "lon" in p0
    assert "heading" in p0
    assert "speed" in p0
    assert "confidence" in p0


def test_trajectory_for_unknown_plate_returns_404(client: TestClient):
    """Check that requesting trajectory for a non-existent vehicle returns HTTP 404."""
    response = client.get("/api/trajectory/UNKNOWN99999?fuzzy=false")
    assert response.status_code == 404
    err = response.json()
    assert "detail" in err
    assert "not found" in err["detail"].lower()


def test_plate_search_tolerates_confusable_character(client: TestClient):
    """Check that GET /api/plates/search finds vehicles even with OCR confusable characters."""
    db = SessionLocal()
    target_plate = None
    try:
        # Find a distinct plate with '0' or '8' in it
        for ev in db.query(Event.plate).distinct().limit(200):
            p = ev[0]
            if "0" in p or "8" in p or "B" in p:
                target_plate = p
                break
    finally:
        db.close()

    assert target_plate is not None

    # Replace character with visual confusable
    if "0" in target_plate:
        query_str = target_plate.replace("0", "O", 1)
    elif "8" in target_plate:
        query_str = target_plate.replace("8", "B", 1)
    else:
        query_str = target_plate.replace("B", "8", 1)

    response = client.get(f"/api/plates/search?q={query_str}")
    assert response.status_code == 200
    results = response.json()
    assert len(results) > 0
    assert len(results) <= 10

    found_plates = [r["plate"] for r in results]
    assert target_plate in found_plates, (
        f"Search query '{query_str}' did not return target plate '{target_plate}'. Found: {found_plates}"
    )


def test_heatmap_weights_between_zero_and_one(client: TestClient):
    """Check that GET /api/analytics/heatmap returns valid geospatial points with weights in [0, 1]."""
    response = client.get("/api/analytics/heatmap")
    assert response.status_code == 200
    points = response.json()
    assert len(points) > 0

    for pt in points:
        assert "lat" in pt
        assert "lon" in pt
        assert "weight" in pt
        assert 0.0 <= pt["weight"] <= 1.0


def test_blacklist_post_then_delete_works(client: TestClient):
    """Check that POST /api/blacklist adds a plate, and DELETE /api/blacklist/{plate} removes it."""
    test_plate = "KA99UNIT01"
    reason = "Test fugitive vehicle warrant"

    # Ensure clean starting state
    client.delete(f"/api/blacklist/{test_plate}")

    # 1. POST add target
    post_res = client.post(
        "/api/blacklist",
        json={"plate": test_plate, "reason": reason},
    )
    assert post_res.status_code == 201
    created = post_res.json()
    assert created["plate"] == test_plate
    assert created["reason"] == reason

    # Verify present in GET /api/blacklist
    get_res = client.get("/api/blacklist")
    assert get_res.status_code == 200
    assert any(b["plate"] == test_plate for b in get_res.json())

    # 2. DELETE target
    del_res = client.delete(f"/api/blacklist/{test_plate}")
    assert del_res.status_code == 200
    del_msg = del_res.json()
    assert del_msg["status"] == "ok"

    # Verify removed from GET /api/blacklist
    get_res2 = client.get("/api/blacklist")
    assert not any(b["plate"] == test_plate for b in get_res2.json())


def test_alerts_filter_by_severity(client: TestClient):
    """Check that GET /api/alerts?severity=HIGH filters alerts strictly by severity level."""
    response = client.get("/api/alerts?severity=HIGH&limit=50")
    assert response.status_code == 200
    alerts = response.json()
    assert len(alerts) > 0

    for a in alerts:
        assert a["severity"] == "HIGH"
        assert "alert_type" in a
        assert "plate" in a
        assert "timestamp" in a


def test_websocket_live_sends_at_least_one_message(client: TestClient):
    """Check that WebSocket /ws/live?speed=0 connects and delivers stream messages."""
    with client.websocket_connect("/ws/live?speed=0") as websocket:
        # First message should be connection greeting
        msg1 = websocket.receive_json()
        assert msg1 is not None
        assert msg1.get("type") in ["connected", "progress", "alert"]

        # Second message will be progress or alert
        msg2 = websocket.receive_json()
        assert msg2 is not None
        assert "type" in msg2


def test_analytics_endpoints(client: TestClient):
    """Check that all analytics endpoints return valid structured responses."""
    # Summary
    res_summary = client.get("/api/analytics/summary")
    assert res_summary.status_code == 200
    summary = res_summary.json()
    assert summary["total_events"] > 0
    assert summary["total_cameras"] == 40

    # Flow trend
    res_flow = client.get("/api/analytics/flow-trend?window=15")
    assert res_flow.status_code == 200
    assert len(res_flow.json()) > 0

    # Camera stats
    res_stats = client.get("/api/analytics/camera-stats?window=15")
    assert res_stats.status_code == 200
    assert len(res_stats.json()) > 0

    # Congestion
    res_cong = client.get("/api/analytics/congestion")
    assert res_cong.status_code == 200

    # OD Matrix
    res_od = client.get("/api/analytics/od-matrix")
    assert res_od.status_code == 200
    od = res_od.json()
    assert "zones" in od
    assert "matrix" in od

    # Route Density
    res_rd = client.get("/api/analytics/route-density")
    assert res_rd.status_code == 200


def test_frontend_static_files_served_at_root(client: TestClient):
    """Check that frontend static files are mounted at root while keeping docs and API functional."""
    # Root index.html
    res_index = client.get("/")
    assert res_index.status_code == 200
    assert "text/html" in res_index.headers.get("content-type", "")
    assert "City ANPR" in res_index.text

    # style.css and app.js
    res_css = client.get("/style.css")
    assert res_css.status_code == 200

    res_js = client.get("/app.js")
    assert res_js.status_code == 200

    # Swagger docs still working
    res_docs = client.get("/docs")
    assert res_docs.status_code == 200


def test_websocket_live_full_stream_matches_cli_replay(client: TestClient):
    """Verify that streaming all events through /ws/live produces exactly 44 alerts (5 CLONED_PLATE)."""
    from collections import Counter

    with client.websocket_connect("/ws/live?speed=0") as ws:
        connected_msg = ws.receive_json()
        assert connected_msg["type"] == "connected"

        alerts = []
        while True:
            msg = ws.receive_json()
            if msg["type"] == "alert":
                alerts.append(msg["data"])
            elif msg["type"] == "complete":
                break

    counts = Counter(a["alert_type"] for a in alerts)
    assert len(alerts) == 44, f"Expected 44 total alerts from WebSocket replay, got {len(alerts)}"
    assert counts["CLONED_PLATE"] == 5, f"Expected 5 CLONED_PLATE alerts, got {counts['CLONED_PLATE']}"
    assert counts["BLACKLIST"] == 35, f"Expected 35 BLACKLIST alerts, got {counts['BLACKLIST']}"
    assert counts["RESTRICTED_ZONE"] == 4, f"Expected 4 RESTRICTED_ZONE alerts, got {counts['RESTRICTED_ZONE']}"


# ==============================================================================
# Journey CSV Export Tests
# ==============================================================================
def test_trajectory_export_csv_for_known_plate(client: TestClient, known_plate: str):
    """Verify GET /api/trajectory/{plate}/export returns a valid CSV with time-ordered points matching the trajectory endpoint."""
    # 1. Fetch benchmark trajectory data from the existing visual trajectory endpoint
    traj_resp = client.get(f"/api/trajectory/{known_plate}?fuzzy=true")
    assert traj_resp.status_code == 200
    traj_data = traj_resp.json()
    expected_point_count = len(traj_data["points"])
    assert expected_point_count > 0, "Known test vehicle must have at least one sighting"

    # 2. Call the CSV export endpoint
    export_resp = client.get(f"/api/trajectory/{known_plate}/export?fuzzy=true")
    assert export_resp.status_code == 200

    # Verify content type and attachment filename
    content_type = export_resp.headers.get("content-type", "")
    assert "text/csv" in content_type

    disposition = export_resp.headers.get("content-disposition", "")
    assert "attachment" in disposition
    safe_plate = sanitize_filename_plate(known_plate)
    assert f"journey_{safe_plate}.csv" in disposition

    # 3. Parse CSV content
    csv_text = export_resp.text
    rows = list(csv.reader(io.StringIO(csv_text)))
    assert len(rows) >= 2, "Export must have a header row and at least one data row"

    header = rows[0]
    expected_headers = [
        "queried_plate",
        "matched_plate",
        "point_order",
        "camera_id",
        "camera_name",
        "latitude",
        "longitude",
        "timestamp",
        "direction",
        "segment_speed",
    ]
    assert header == expected_headers, f"Header row mismatch: got {header}"

    data_rows = rows[1:]
    # Must have the exact same number of data rows as trajectory endpoint points
    assert len(data_rows) == expected_point_count, (
        f"Row count mismatch: export has {len(data_rows)} data rows, but trajectory has {expected_point_count} points"
    )

    # 4. Verify chronological order and point numbering 1..n
    timestamps = []
    for i, row in enumerate(data_rows, start=1):
        assert row[0] == known_plate  # queried_plate
        assert len(row[1]) > 0        # matched_plate
        assert int(row[2]) == i       # point_order 1..n
        assert row[3].startswith("CAM_") # camera_id
        timestamps.append(row[7])

    # Assert strictly non-decreasing timestamp ordering
    assert timestamps == sorted(timestamps), "Export rows must be in time order"


def test_trajectory_export_unknown_plate_returns_404(client: TestClient):
    """Verify requesting an export for a non-existent plate returns HTTP 404."""
    response = client.get("/api/trajectory/UNKNOWN99999/export?fuzzy=false")
    assert response.status_code == 404
    data = response.json()
    assert "detail" in data
    assert "not found" in data["detail"].lower()


def test_trajectory_export_unsafe_characters_gives_safe_filename(client: TestClient):
    """Verify that plate strings containing unsafe characters produce a safe filename keeping only A-Z, 0-9 and _."""
    # 1. Unit test the sanitization helper directly
    assert sanitize_filename_plate("KA-01/AB@1234;--=") == "KA01AB1234"
    assert sanitize_filename_plate("dl 03 nv 2244") == "DL03NV2244"
    assert sanitize_filename_plate("KA_01_TEST") == "KA_01_TEST"
    assert sanitize_filename_plate("=CMD|' /C calc'!A0") == "CMDCCALCA0"
    assert sanitize_filename_plate("???") == "UNKNOWN"

    # All characters in the sanitized plate portion must be in A-Z, 0-9, or _
    test_cases = ["KA-01-AB-1234", "TN/11;DROP", "DL 05*&^%", "=1+1"]
    for raw in test_cases:
        safe = sanitize_filename_plate(raw)
        assert re.match(r"^[A-Z0-9_]+$", safe), f"Unsafe characters found in: {safe}"

    # 2. Test via endpoint 404 header safety
    resp = client.get("/api/trajectory/KA-01;DROP%20TABLE/export?fuzzy=false")
    disposition = resp.headers.get("content-disposition", "")
    assert "attachment" in disposition
    # Ensure filename adheres to journey_<PLATE>.csv with only safe characters
    m = re.search(r'filename="?(journey_[^"]+\.csv)"?', disposition)
    assert m is not None, f"Could not find valid journey filename in: {disposition}"
    filename = m.group(1)
    # Filename must match ^journey_[A-Z0-9_]+\.csv$
    assert re.match(r"^journey_[A-Z0-9_]+\.csv$", filename), f"Filename '{filename}' contains unsafe characters"


def test_csv_formula_injection_escaping():
    """Verify that text cells starting with =, +, -, or @ are prepended with an apostrophe (')."""
    # 1. Equals sign (=)
    assert escape_csv_cell("=SUM(A1:A10)") == "'=SUM(A1:A10)"
    assert escape_csv_cell("=1+1") == "'=1+1"

    # 2. Plus sign (+)
    assert escape_csv_cell("+4412345") == "'+4412345"

    # 3. Minus sign (-)
    assert escape_csv_cell("-DANGEROUS") == "'-DANGEROUS"

    # 4. At symbol (@)
    assert escape_csv_cell("@SUM") == "'@SUM"

    # 5. Normal safe cells are left unescaped
    assert escape_csv_cell("DL03NV2244") == "DL03NV2244"
    assert escape_csv_cell("MG Road & Brigade Road") == "MG Road & Brigade Road"

    # 6. Numeric values remain numeric
    assert escape_csv_cell(42) == 42
    assert escape_csv_cell(12.9716) == 12.9716
    assert escape_csv_cell(None) == ""


def test_simulation_numbers_unchanged(client: TestClient):
    """Verify invariant simulated numbers remain unchanged:
    - 31,244 simulated events
    - 40 simulation cameras
    - 44 alerts
    """
    from sqlalchemy import func

    db = SessionLocal()
    try:
        sim_events = db.query(func.count(Event.id)).filter(Event.source == "sim").scalar()
        assert sim_events == 31244, f"Expected 31,244 sim events, got {sim_events}"

        sim_cams = db.query(func.count(Camera.camera_id)).filter(
            Camera.camera_id.like("CAM_%"),
            ~Camera.camera_id.like("%VIDEO%"),
        ).scalar()
        assert sim_cams == 40, f"Expected 40 cameras, got {sim_cams}"
    finally:
        db.close()

    resp_alerts = client.get("/api/alerts")
    assert resp_alerts.status_code == 200
    alerts = resp_alerts.json()
    assert len(alerts) == 44, f"Expected 44 alerts, got {len(alerts)}"


def test_five_sample_plates_trajectory_and_export_routes(client: TestClient):
    """Verify that all 5 dashboard sample vehicles return HTTP 200 with >= 2 points
    from both the visual trajectory endpoint and the CSV export endpoint, across both
    fuzzy=True and fuzzy=False modes.
    
    Plates tested:
    1. DL03NV2244 (Cloned Anomaly - contains impossible hop)
    2. KA53AE1276 (Cloned Anomaly - contains impossible hop)
    3. DL05VW4401 (Long Journey)
    4. KA50QA9345 (Blacklist Target)
    5. TN11YD7305 (Normal Car)
    """
    sample_plates = [
        "DL03NV2244",  # Cloned Anomaly
        "KA53AE1276",  # Cloned Anomaly
        "DL05VW4401",  # Long Journey
        "KA50QA9345",  # Blacklist Target
        "TN11YD7305",  # Normal Car
    ]

    for plate in sample_plates:
        for fuzzy in (True, False):
            # 1. Trajectory JSON Endpoint
            traj_url = f"/api/trajectory/{plate}?fuzzy={str(fuzzy).lower()}"
            traj_resp = client.get(traj_url)
            assert traj_resp.status_code == 200, f"Expected 200 for {traj_url}, got {traj_resp.status_code}: {traj_resp.text}"
            traj_data = traj_resp.json()
            assert "points" in traj_data
            assert len(traj_data["points"]) >= 2, f"Plate {plate} (fuzzy={fuzzy}) should have >= 2 points, got {len(traj_data['points'])}"

            # For cloned plates, verify impossible hop is flagged with implied speed > 120 km/h
            if plate in ("DL03NV2244", "KA53AE1276"):
                assert len(traj_data.get("flagged_hops", [])) >= 1, f"Expected flagged impossible hop for cloned plate {plate}"
                flagged = traj_data["flagged_hops"][0]
                assert flagged["implied_speed_kmh"] > 120.0, f"Expected implied speed > 120 km/h, got {flagged['implied_speed_kmh']}"
                assert "previous_camera" in flagged
                assert "camera_id" in flagged

            # 2. Trajectory CSV Export Endpoint
            export_url = f"/api/trajectory/{plate}/export?fuzzy={str(fuzzy).lower()}"
            export_resp = client.get(export_url)
            assert export_resp.status_code == 200, f"Expected 200 for {export_url}, got {export_resp.status_code}"
            assert "text/csv" in export_resp.headers.get("content-type", "")

            # Parse exported CSV
            reader = list(csv.reader(io.StringIO(export_resp.text)))
            assert len(reader) >= 3, f"Expected header + >= 2 data rows for {export_url}, got {len(reader)} rows"
            data_rows = reader[1:]
            assert len(data_rows) == len(traj_data["points"]), (
                f"Export row count ({len(data_rows)}) does not match trajectory point count ({len(traj_data['points'])}) for {plate}"
            )




