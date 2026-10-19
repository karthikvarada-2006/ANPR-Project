"""Integration and Unit Tests for City ANPR FastAPI Backend."""

from __future__ import annotations

import datetime
from pathlib import Path
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
from backend.plate_utils import normalize_plate


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


