"""Unit Tests for Multi-Frame Plate Voting and Track Event Emission.

Verifies:
1. Voting picks the majority string across frame readings.
2. Voting corrects a single-character error present in a minority of readings.
3. Low-confidence readings below threshold are ignored.
4. Final emitted track event contains all required schema columns matching data/sim/events.csv
   plus track_id, n_frames, vote_margin, best_crop_path.
"""

from pathlib import Path
import numpy as np
import pytest

from pipeline.voting import PlateVoting, Track


@pytest.fixture
def dummy_crop():
    """Returns a synthetic 48x192 3-channel dummy crop array."""
    return np.zeros((48, 192, 3), dtype=np.uint8)


def test_voting_picks_majority_string(dummy_crop):
    """Verify voting picks the majority string when multiple full readings exist."""
    voter = PlateVoting(min_confidence=0.35)

    readings = [
        {"frame_idx": 0, "text": "KA05MH1234", "ocr_confidence": 0.88, "detector_confidence": 0.90, "crop": dummy_crop},
        {"frame_idx": 1, "text": "KA05MH1234", "ocr_confidence": 0.92, "detector_confidence": 0.91, "crop": dummy_crop},
        {"frame_idx": 2, "text": "KA05MH9999", "ocr_confidence": 0.85, "detector_confidence": 0.89, "crop": dummy_crop},
    ]

    result = voter.vote(readings)
    assert result["plate"] == "KA05MH1234", f"Expected 'KA05MH1234', got '{result['plate']}'"
    assert result["n_frames"] == 3
    assert result["n_valid"] == 3
    assert result["vote_margin"] > 0.0


def test_voting_corrects_single_character_error(dummy_crop):
    """Verify character-position weighted voting corrects a single-char OCR confusion.
    
    Example: Frame 1 and 2 read 'DL01AB1234' with high confidence.
    Frame 3 has minor OCR confusion at position 5 ('DL01A81234' where 'B' was misread as '8').
    Position-weighted voting must resolve consensus to 'DL01AB1234'.
    """
    voter = PlateVoting(min_confidence=0.35)

    readings = [
        {"frame_idx": 10, "text": "DL01AB1234", "ocr_confidence": 0.85, "detector_confidence": 0.90, "crop": dummy_crop},
        {"frame_idx": 11, "text": "DL01AB1234", "ocr_confidence": 0.90, "detector_confidence": 0.92, "crop": dummy_crop},
        {"frame_idx": 12, "text": "DL01A81234", "ocr_confidence": 0.70, "detector_confidence": 0.88, "crop": dummy_crop},
    ]

    result = voter.vote(readings)
    assert result["plate"] == "DL01AB1234", f"Voting failed to correct single-char error: got '{result['plate']}'"
    assert result["method"] == "positional_weighted"
    assert result["n_frames"] == 3
    assert result["vote_margin"] > 0.5


def test_voting_ignores_low_confidence_readings(dummy_crop):
    """Verify readings below configurable threshold are discarded from the vote."""
    voter = PlateVoting(min_confidence=0.40)

    readings = [
        {"frame_idx": 1, "text": "MH12DE1433", "ocr_confidence": 0.94, "detector_confidence": 0.91, "crop": dummy_crop},
        {"frame_idx": 2, "text": "MH12DE1433", "ocr_confidence": 0.89, "detector_confidence": 0.90, "crop": dummy_crop},
        # Severely degraded reading below min_confidence threshold
        {"frame_idx": 3, "text": "GARBAGE999", "ocr_confidence": 0.15, "detector_confidence": 0.35, "crop": dummy_crop},
    ]

    result = voter.vote(readings)
    assert result["plate"] == "MH12DE1433"
    assert result["n_frames"] == 3
    assert result["n_valid"] == 2, f"Expected 2 valid readings after filtering, got {result['n_valid']}"


def test_final_event_has_all_required_columns(tmp_path, dummy_crop):
    """Verify the emitted track event contains all expected schema columns.
    
    Matches data/sim/events.csv:
        plate, camera_id, timestamp, speed_kmh, heading_degrees, lane, ocr_confidence
    Plus tracking extensions:
        track_id, n_frames, vote_margin, best_crop_path
    """
    voter = PlateVoting(min_confidence=0.35)

    track = Track(
        track_id=42,
        camera_id="CAM_TEST_01",
        initial_reading={
            "frame_idx": 100,
            "timestamp": "2026-10-04 12:00:00",
            "crop": dummy_crop,
            "text": "TN07BV5200",
            "ocr_confidence": 0.95,
            "detector_confidence": 0.92,
            "box": [100.0, 150.0, 250.0, 200.0],
        },
    )

    track.add_reading({
        "frame_idx": 101,
        "timestamp": "2026-10-04 12:00:00.033",
        "crop": dummy_crop,
        "text": "TN07BV5200",
        "ocr_confidence": 0.97,
        "detector_confidence": 0.93,
        "box": [102.0, 151.0, 252.0, 201.0],
    })

    crop_dir = tmp_path / "crops"
    event = track.to_event(voter=voter, output_crop_dir=crop_dir, source_name="test_video", event_id=1)

    expected_columns = {
        "event_id",
        "plate",
        "camera_id",
        "timestamp",
        "speed_kmh",
        "heading_degrees",
        "lane",
        "ocr_confidence",
        "track_id",
        "n_frames",
        "vote_margin",
        "best_crop_path",
    }

    assert expected_columns.issubset(event.keys()), f"Missing keys: {expected_columns - set(event.keys())}"
    assert event["plate"] == "TN07BV5200"
    assert event["track_id"] == 42
    assert event["n_frames"] == 2
    assert event["speed_kmh"] == "", "Single-camera uncalibrated speed should be empty"
    assert event["heading_degrees"] == "", "Single-camera uncalibrated heading should be empty"
    assert Path(event["best_crop_path"]).exists(), f"Best crop file not saved: {event['best_crop_path']}"
