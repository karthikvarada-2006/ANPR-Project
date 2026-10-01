"""Unit and Integration Tests for Real-Time Surveillance Alert System."""

from __future__ import annotations

import datetime
from pathlib import Path
import sys
from typing import Dict, List

import pytest
from sqlalchemy import delete

# Ensure project root is in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.alert_engine import AlertEngine
from backend.alert_rules import (
    RuleContext,
    check_blacklist,
    check_cloned_plate,
    check_loitering,
    check_overspeed,
    check_restricted_zone,
    check_wrong_way,
)
from backend.db import SessionLocal
from backend.models import Alert
from backend.plate_utils import normalize_plate


@pytest.fixture
def context() -> RuleContext:
    """Fixture providing loaded rule context."""
    return RuleContext.get_instance()


@pytest.fixture
def engine(context: RuleContext) -> AlertEngine:
    """Fixture providing clean AlertEngine instance."""
    eng = AlertEngine(dedup_minutes=10.0, context=context)
    eng.reset()
    return eng


def test_exact_blacklist_raises_high_alert(engine: AlertEngine, context: RuleContext):
    """Check that an exact match against a blacklisted plate raises a HIGH severity alert."""
    # Pick a known blacklisted plate from context
    assert len(context.blacklist) > 0
    bl_plate = list(context.blacklist.keys())[0]

    event = {
        "plate": bl_plate,
        "camera_id": "CAM_001",
        "timestamp": "2026-10-01 08:00:00",
        "speed_kmh": 45.0,
        "heading_degrees": 277.2,
        "ocr_confidence": 0.95,
    }

    alerts = engine.process_event(event, save_to_db=False)
    bl_alerts = [a for a in alerts if a["alert_type"] == "BLACKLIST"]

    assert len(bl_alerts) == 1
    alert = bl_alerts[0]
    assert alert["severity"] == "HIGH"
    assert alert["plate"] == bl_plate
    assert alert["details"]["match_type"] == "exact"
    assert alert["details"]["distance"] == 0.0


def test_confusable_variant_raises_medium_alert(engine: AlertEngine, context: RuleContext):
    """Check that a confusable-character variant (e.g., 'O' for '0') raises a MEDIUM alert."""
    # Find a blacklisted plate containing '0'
    target_bl = None
    for bp in context.blacklist:
        if "0" in bp:
            target_bl = bp
            break

    if target_bl is None:
        target_bl = "KA50QA9345"

    # Replace first '0' with 'O' (confusable swap, distance 0.3)
    corrupted_plate = target_bl.replace("0", "O", 1)

    event = {
        "plate": corrupted_plate,
        "camera_id": "CAM_005",
        "timestamp": "2026-10-01 09:00:00",
        "speed_kmh": 40.0,
        "ocr_confidence": 0.85,
    }

    alerts = engine.process_event(event, save_to_db=False)
    bl_alerts = [a for a in alerts if a["alert_type"] == "BLACKLIST"]

    assert len(bl_alerts) == 1
    alert = bl_alerts[0]
    assert alert["severity"] == "MEDIUM"
    assert alert["details"]["match_type"] == "fuzzy"
    assert alert["details"]["matched_plate"] == target_bl
    assert alert["details"]["distance"] <= 0.6


def test_non_blacklisted_plate_raises_none(engine: AlertEngine, context: RuleContext):
    """Check that a normal, unlisted plate raises no BLACKLIST alert."""
    event = {
        "plate": "KA99ZZ1111",
        "camera_id": "CAM_001",
        "timestamp": "2026-10-01 10:00:00",
        "speed_kmh": 42.0,
        "heading_degrees": 277.2,
        "ocr_confidence": 0.98,
    }

    alerts = engine.process_event(event, save_to_db=False)
    bl_alerts = [a for a in alerts if a["alert_type"] == "BLACKLIST"]
    assert len(bl_alerts) == 0


def test_fake_impossible_hop_raises_cloned_plate(engine: AlertEngine):
    """Check that an impossible hop (speed > 120 km/h) raises a CLONED_PLATE alert with HIGH severity."""
    # Sighting 1 at CAM_010
    ev1 = {
        "plate": "KA09TEST99",
        "camera_id": "CAM_010",
        "timestamp": "2026-10-01 11:00:00",
        "speed_kmh": 40.0,
        "heading_degrees": 208.1,
    }
    # Sighting 2 at CAM_031 within 30 seconds (~3,500m road distance -> speed > 400 km/h)
    ev2 = {
        "plate": "KA09TEST99",
        "camera_id": "CAM_031",
        "timestamp": "2026-10-01 11:00:30",
        "speed_kmh": 45.0,
        "heading_degrees": 191.3,
    }

    alerts1 = engine.process_event(ev1, save_to_db=False)
    assert len([a for a in alerts1 if a["alert_type"] == "CLONED_PLATE"]) == 0

    alerts2 = engine.process_event(ev2, save_to_db=False)
    cloned_alerts = [a for a in alerts2 if a["alert_type"] == "CLONED_PLATE"]

    assert len(cloned_alerts) == 1
    alert = cloned_alerts[0]
    assert alert["severity"] == "HIGH"
    assert alert["plate"] == "KA09TEST99"
    assert alert["details"]["implied_speed_kmh"] > 120.0
    assert alert["details"]["previous_camera"] == "CAM_010"


def test_same_alert_not_repeated_inside_10_minutes(engine: AlertEngine, context: RuleContext):
    """Check that the same alert type for the same vehicle is suppressed within 10 minutes, but fires after."""
    bl_plate = list(context.blacklist.keys())[0]

    # Event 1 at 08:00
    ev1 = {
        "plate": bl_plate,
        "camera_id": "CAM_001",
        "timestamp": "2026-10-01 08:00:00",
        "heading_degrees": 277.2,
    }
    alerts1 = engine.process_event(ev1, save_to_db=False)
    assert len([a for a in alerts1 if a["alert_type"] == "BLACKLIST"]) == 1

    # Event 2 at 08:05 (5 mins later -> inside 10m window, should be suppressed)
    ev2 = {
        "plate": bl_plate,
        "camera_id": "CAM_002",
        "timestamp": "2026-10-01 08:05:00",
        "heading_degrees": 230.8,
    }
    alerts2 = engine.process_event(ev2, save_to_db=False)
    assert len([a for a in alerts2 if a["alert_type"] == "BLACKLIST"]) == 0

    # Event 3 at 08:11 (11 mins later -> outside 10m window, should be allowed)
    ev3 = {
        "plate": bl_plate,
        "camera_id": "CAM_003",
        "timestamp": "2026-10-01 08:11:00",
        "heading_degrees": 223.5,
    }
    alerts3 = engine.process_event(ev3, save_to_db=False)
    assert len([a for a in alerts3 if a["alert_type"] == "BLACKLIST"]) == 1


def test_alerts_saved_to_database(engine: AlertEngine, context: RuleContext):
    """Check that triggered alerts are properly saved and queryable from the database."""
    session = SessionLocal()
    try:
        # Clean previous test alerts with test plate
        test_plate = "KA99DBTEST"
        session.execute(delete(Alert).where(Alert.plate == test_plate))
        session.commit()

        # Generate an alert with this plate (overspeeding)
        ev = {
            "plate": test_plate,
            "camera_id": "CAM_001",
            "timestamp": "2026-10-01 12:00:00",
            "speed_kmh": 95.5,  # > 80 km/h
            "heading_degrees": 277.2,
        }

        alerts = engine.process_event(ev, save_to_db=True, session=session)
        assert len(alerts) >= 1
        assert any(a["alert_type"] == "OVERSPEED" for a in alerts)

        # Query database directly
        db_alert = (
            session.query(Alert)
            .filter(Alert.plate == test_plate, Alert.alert_type == "OVERSPEED")
            .first()
        )
        assert db_alert is not None
        assert db_alert.severity == "LOW"
        assert db_alert.camera_id == "CAM_001"
        assert db_alert.details["speed_kmh"] == 95.5

        # Cleanup
        session.execute(delete(Alert).where(Alert.plate == test_plate))
        session.commit()

    finally:
        session.close()


def test_wrong_way_alert():
    """Check that a heading differing by > 135 degrees from dominant heading triggers WRONG_WAY."""
    # CAM_001 dominant heading is 277.2
    # Heading 75.8 deg has diff = 158.6 deg (> 135 deg)
    ev = {
        "plate": "KA01WW0001",
        "camera_id": "CAM_001",
        "timestamp": "2026-10-01 14:00:00",
        "heading_degrees": 75.8,
    }
    alerts = check_wrong_way(ev, [], dominant_headings={"CAM_001": 277.2})
    assert len(alerts) == 1
    assert alerts[0]["alert_type"] == "WRONG_WAY"
    assert alerts[0]["severity"] == "MEDIUM"
    assert alerts[0]["details"]["heading_difference"] > 135.0


def test_loitering_alert():
    """Check that sighting a vehicle > 3 times at same camera within 60 minutes triggers LOITERING."""
    history = [
        {"camera_id": "CAM_007", "timestamp": "2026-10-01 15:00:00"},
        {"camera_id": "CAM_007", "timestamp": "2026-10-01 15:15:00"},
        {"camera_id": "CAM_007", "timestamp": "2026-10-01 15:30:00"},
    ]
    # 4th sighting at 15:40 (all 4 within 40 minutes)
    ev = {
        "plate": "KA01LOITER",
        "camera_id": "CAM_007",
        "timestamp": "2026-10-01 15:40:00",
    }
    alerts = check_loitering(ev, history, window_minutes=60, count_threshold=3)
    assert len(alerts) == 1
    assert alerts[0]["alert_type"] == "LOITERING"
    assert alerts[0]["severity"] == "LOW"
    assert alerts[0]["details"]["sighting_count"] == 4


def test_restricted_zone_alert():
    """Check that a truck entering a restricted camera during curfew hours triggers RESTRICTED_ZONE."""
    ev = {
        "plate": "KA01TRUCK1",
        "camera_id": "CAM_001",
        "timestamp": "2026-10-01 03:30:00",  # 03:30 is inside (00:00, 05:00)
        "vehicle_type": "truck",
    }
    config = {
        "camera_ids": ["CAM_001", "CAM_002"],
        "time_window": ("00:00", "05:00"),
        "vehicle_types": ["truck"],
    }
    alerts = check_restricted_zone(ev, [], config=config)
    assert len(alerts) == 1
    assert alerts[0]["alert_type"] == "RESTRICTED_ZONE"
    assert alerts[0]["severity"] == "MEDIUM"
    assert alerts[0]["details"]["vehicle_type"] == "truck"


def test_cloned_plate_requires_exact_normalized_match():
    """Check that non-matching plates do not trigger a CLONED_PLATE alert."""
    history = [
        {"plate": "KA01AB1234", "camera_id": "CAM_010", "timestamp": "2026-10-01 11:00:00", "ocr_confidence": 0.95}
    ]
    ev = {
        "plate": "KA01AB1235",  # different plate
        "camera_id": "CAM_031",
        "timestamp": "2026-10-01 11:00:30",
        "ocr_confidence": 0.95,
    }
    alerts = check_cloned_plate(ev, history)
    assert len(alerts) == 0


def test_cloned_plate_requires_confidence_gte_07():
    """Check that sightings with OCR confidence < 0.70 do not trigger CLONED_PLATE."""
    # Sighting 1 has low confidence (0.65)
    history = [
        {"plate": "KA99TEST01", "camera_id": "CAM_010", "timestamp": "2026-10-01 11:00:00", "ocr_confidence": 0.65}
    ]
    ev = {
        "plate": "KA99TEST01",
        "camera_id": "CAM_031",
        "timestamp": "2026-10-01 11:00:30",
        "ocr_confidence": 0.95,
    }
    alerts = check_cloned_plate(ev, history)
    assert len(alerts) == 0

    # Sighting 2 has low confidence (0.55)
    history2 = [
        {"plate": "KA99TEST02", "camera_id": "CAM_010", "timestamp": "2026-10-01 11:00:00", "ocr_confidence": 0.95}
    ]
    ev2 = {
        "plate": "KA99TEST02",
        "camera_id": "CAM_031",
        "timestamp": "2026-10-01 11:00:30",
        "ocr_confidence": 0.55,
    }
    alerts2 = check_cloned_plate(ev2, history2)
    assert len(alerts2) == 0


def test_cloned_plate_fires_on_exact_match_even_if_variant(context: RuleContext):
    """Check that exact matching reads trigger CLONED_PLATE (OCR variant suppression undone)."""
    # Use two sightings of the same plate across far apart cameras within 30s
    plate = "KA50ES267B"
    history = [
        {"plate": plate, "camera_id": "CAM_019", "timestamp": "2026-10-01 11:00:00", "ocr_confidence": 0.90}
    ]
    ev = {
        "plate": plate,
        "camera_id": "CAM_022",
        "timestamp": "2026-10-01 11:00:30",
        "ocr_confidence": 0.90,
    }
    alerts = check_cloned_plate(ev, history)
    assert len(alerts) == 1
    assert alerts[0]["alert_type"] == "CLONED_PLATE"
    assert alerts[0]["severity"] == "HIGH"


def test_wrong_way_disabled_by_default_in_engine(engine: AlertEngine):
    """Check that WRONG_WAY alert is disabled by default in evaluate_all_rules/AlertEngine."""
    ev = {
        "plate": "KA01WW0001",
        "camera_id": "CAM_001",
        "timestamp": "2026-10-01 14:00:00",
        "heading_degrees": 75.8,  # Dominant is 277.2 -> diff 158.6 deg
        "ocr_confidence": 0.95,
    }
    alerts = engine.process_event(ev, save_to_db=False)
    wrong_way_alerts = [a for a in alerts if a["alert_type"] == "WRONG_WAY"]
    assert len(wrong_way_alerts) == 0

