"""Tests for Module 7: Real-Time Alerts & Anomaly Detection Engine."""

import datetime
import pytest

from backend.alerts.engine import AlertEngine


@pytest.fixture(scope="module")
def alert_engine():
    """Shared AlertEngine instance."""
    engine = AlertEngine(speed_limit_kmh=60.0)
    # Ensure test camera coordinates exist
    engine.camera_coords["CAM_TEST_A"] = (12.9716, 77.5946)
    engine.camera_coords["CAM_TEST_B"] = (12.9716, 77.6346)  # ~4.3 km away
    engine.camera_coords["CAM_TEST_C"] = (12.9716, 77.6046)  # ~1.08 km away
    return engine


def test_blacklist_alert_detection(alert_engine):
    """Verify that blacklisted vehicles trigger an immediate BLACKLIST alert."""
    blacklist = {"KA01AB1234", "MH02CD5678"}

    event = {
        "plate": "KA01AB1234",
        "camera_id": "CAM_TEST_A",
        "timestamp": datetime.datetime(2026, 10, 1, 9, 30, 0),
        "ocr_confidence": 0.95,
    }

    alerts = alert_engine.evaluate_sighting(event, previous_event=None, blacklist_set=blacklist)
    assert len(alerts) == 1, "Expected 1 blacklist alert"
    assert alerts[0]["alert_type"] == "BLACKLIST"
    assert alerts[0]["plate"] == "KA01AB1234"
    assert alerts[0]["camera_id"] == "CAM_TEST_A"


def test_cloned_plate_impossible_speed(alert_engine):
    """Verify that sightings with impossible speeds trigger a ROUTE_ANOMALY alert."""
    plate = "KA50XY9999"
    t1 = datetime.datetime(2026, 10, 1, 11, 0, 0)
    # 4.3 km away in just 20 seconds -> ~770 km/h (physically impossible)
    t2 = t1 + datetime.timedelta(seconds=20)

    event1 = {"plate": plate, "camera_id": "CAM_TEST_A", "timestamp": t1}
    event2 = {"plate": plate, "camera_id": "CAM_TEST_B", "timestamp": t2}

    alerts = alert_engine.evaluate_sighting(event2, previous_event=event1, blacklist_set=set())
    cloned_alerts = [a for a in alerts if a["alert_type"] == "ROUTE_ANOMALY"]

    assert len(cloned_alerts) == 1, "Expected ROUTE_ANOMALY alert for cloned plate"
    assert cloned_alerts[0]["details"]["sub_type"] == "CLONED_PLATE"
    assert cloned_alerts[0]["details"]["implied_speed_kmh"] > 180.0


def test_speed_violation_detection(alert_engine):
    """Verify that vehicles exceeding corridor speed limits trigger SPEED_VIOLATION alerts."""
    plate = "KA03FAST01"
    t1 = datetime.datetime(2026, 10, 1, 15, 0, 0)
    # 1.08 km away in 45 seconds -> ~86.4 km/h (limit is 60 km/h)
    t2 = t1 + datetime.timedelta(seconds=45)

    event1 = {"plate": plate, "camera_id": "CAM_TEST_A", "timestamp": t1}
    event2 = {"plate": plate, "camera_id": "CAM_TEST_C", "timestamp": t2}

    alerts = alert_engine.evaluate_sighting(event2, previous_event=event1, blacklist_set=set())
    speed_alerts = [a for a in alerts if a["alert_type"] == "SPEED_VIOLATION"]

    assert len(speed_alerts) == 1, "Expected SPEED_VIOLATION alert"
    assert speed_alerts[0]["details"]["section_speed_kmh"] > 60.0


def test_normal_driving_no_alert(alert_engine):
    """Verify that law-abiding non-blacklisted vehicles produce zero alerts."""
    plate = "KA04SAFE00"
    t1 = datetime.datetime(2026, 10, 1, 16, 0, 0)
    # 1.08 km away in 120 seconds -> ~32.4 km/h (safe speed)
    t2 = t1 + datetime.timedelta(seconds=120)

    event1 = {"plate": plate, "camera_id": "CAM_TEST_A", "timestamp": t1}
    event2 = {"plate": plate, "camera_id": "CAM_TEST_C", "timestamp": t2}

    alerts = alert_engine.evaluate_sighting(event2, previous_event=event1, blacklist_set=set())
    assert len(alerts) == 0, "Compliant driving should trigger zero alerts"
