"""Unit and integration tests for Module 5: Trajectory Reconstruction Engine."""

import datetime
import io
import re
import sys
from pathlib import Path
import pytest

from backend.plate_utils import (
    CONFUSABLE_PAIRS,
    find_similar_plates,
    heading_to_compass,
    normalize_plate,
    plate_distance,
)
from backend.trajectory import (
    CAMERA_PATHS_PATH,
    get_camera_paths,
    get_cameras_info,
    get_hop_route,
    get_road_graph,
    get_trajectory,
    haversine_km,
)
from backend.trajectory_cli import main as cli_main


def test_plate_normalization():
    """Verify license plate normalization strips whitespace, dashes, and forces uppercase."""
    assert normalize_plate("ka-01 ab 1234") == "KA01AB1234"
    assert normalize_plate("mh 12 cd-5678") == "MH12CD5678"
    assert normalize_plate("  dl.01-xy_9999  ") == "DL01XY9999"
    assert normalize_plate("") == ""
    assert normalize_plate(None) == ""


def test_plate_distance_confusable_characters():
    """Verify that optical confusion pairs (O/0, B/8, I/1, S/5, D/0, Z/2, G/6) cost 0.3."""
    # Identical plates
    assert plate_distance("KA01AB1234", "KA01AB1234") == 0.0

    # Confusable swaps cost 0.3 each
    assert plate_distance("KA01AB1234", "KAO1AB1234") == 0.3  # 0 <-> O
    assert plate_distance("KA01AB1238", "KA01AB123B") == 0.3  # 8 <-> B
    assert plate_distance("KA01AB1234", "KA0IAB1234") == 0.3  # 1 <-> I
    assert plate_distance("KA51AB1234", "KAS1AB1234") == 0.3  # 5 <-> S
    assert plate_distance("KA01AD1234", "KA01A01234") == 0.3  # D <-> 0
    assert plate_distance("KA21AB1234", "KAZ1AB1234") == 0.3  # 2 <-> Z
    assert plate_distance("KA61AB1234", "KAG1AB1234") == 0.3  # 6 <-> G

    # Multiple confusables accumulate
    assert plate_distance("KAO1AB123B", "KA01AB1238") == 0.6

    # Standard substitution costs 1.0
    assert plate_distance("KA01AB1234", "KA01AB1235") == 1.0

    # Insertion and deletion cost 1.0
    assert plate_distance("KA01AB1234", "KA01AB123") == 1.0
    assert plate_distance("KA01AB1234", "KA01AB12345") == 1.0


def test_compass_heading():
    """Verify conversion from heading angles in degrees to 8-point compass directions."""
    assert heading_to_compass(0.0) == "N"
    assert heading_to_compass(45.0) == "NE"
    assert heading_to_compass(90.0) == "E"
    assert heading_to_compass(135.0) == "SE"
    assert heading_to_compass(180.0) == "S"
    assert heading_to_compass(225.0) == "SW"
    assert heading_to_compass(270.0) == "W"
    assert heading_to_compass(315.0) == "NW"
    assert heading_to_compass(355.0) == "N"
    assert heading_to_compass(None) == "N/A"


def test_known_plate_time_order():
    """Verify that a known plate returns trajectory points strictly ordered in time."""
    known_plate = "TN11YD7305"
    traj = get_trajectory(known_plate, fuzzy=True)

    assert traj["total_trips"] > 0, f"Expected at least 1 trip for {known_plate}"
    assert len(traj["trips"]) == traj["total_trips"]

    for trip in traj["trips"]:
        pts = trip["points"]
        assert len(pts) >= 1
        # Verify strict non-decreasing chronological ordering
        for i in range(len(pts) - 1):
            t_curr = pts[i]["timestamp"]
            t_next = pts[i + 1]["timestamp"]
            assert t_curr <= t_next, f"Out of order timestamps: {t_curr} > {t_next}"


def test_fuzzy_confusable_variant():
    """Verify that a confusable-character variant (e.g. O to 0 or 1 to I) matches the true plate."""
    query_variant = "TN11YD73O5"
    traj = get_trajectory(query_variant, fuzzy=True)

    assert "TN11YD7305" in traj["matched_plates"], (
        f"Fuzzy search for '{query_variant}' did not match true plate 'TN11YD7305'. "
        f"Matched: {traj['matched_plates']}"
    )
    assert traj["total_trips"] > 0, "Expected reconstructed trips for confusable plate variant"


def test_impossible_hop_detection():
    """Verify that a fake far-apart pair of reads (or cloned plate) produces an IMPOSSIBLE hop."""
    from simulator.config import ANOMALIES_PATH
    import pandas as pd
    if ANOMALIES_PATH.exists():
        df_anom = pd.read_csv(ANOMALIES_PATH)
        anom_plate = str(df_anom.iloc[0]["plate"])
    else:
        anom_plate = "DL03NV2244"
    traj = get_trajectory(anom_plate, fuzzy=True)

    assert len(traj["flagged_hops"]) > 0, f"Expected impossible hop for cloned plate {anom_plate}"

    impossible_hops = [h for h in traj["flagged_hops"] if h.get("reason") == "IMPOSSIBLE"]
    assert len(impossible_hops) >= 1, "Expected at least one IMPOSSIBLE hop flagged"

    hop = impossible_hops[0]
    assert hop["implied_speed_kmh"] > 120.0, f"Implied speed {hop['implied_speed_kmh']} should exceed 120 km/h"
    assert hop["time_delta_seconds"] > 0.0


def test_unknown_plate_returns_empty():
    """Verify that an unknown plate returns 0 trips and an empty result structure."""
    unknown_plate = "ZZ99ZZ9999"
    traj = get_trajectory(unknown_plate, fuzzy=True)

    assert traj["plate"] == unknown_plate
    assert traj["total_trips"] == 0
    assert traj["trips"] == []
    assert traj["flagged_hops"] == []


def test_precomputed_camera_paths_cache():
    """Verify that data/sim/camera_paths.pkl exists and provides fast shortest path lookup."""
    paths = get_camera_paths()
    assert len(paths) >= 1600, f"Expected 1600 camera pairs in cache, got {len(paths)}"

    cams = get_cameras_info()
    cam1 = cams["CAM_001"]
    cam2 = cams["CAM_002"]

    dist_km, coords = get_hop_route("CAM_001", "CAM_002", cam1, cam2)
    assert dist_km > 0.0
    assert len(coords) >= 2
    assert 12.0 < coords[0][0] < 14.0  # Latitude for Bangalore
    assert 76.0 < coords[0][1] < 78.0  # Longitude for Bangalore


def test_no_duplicate_points_and_all_fields_populated():
    """Verify no point appears twice in any trip and every point has heading, speed and confidence."""
    test_plates = ["TN050T8444", "TN11YD7305"]
    for plate in test_plates:
        traj = get_trajectory(plate, fuzzy=True)
        assert traj["total_trips"] > 0

        for trip in traj["trips"]:
            pts = trip["points"]
            seen_points = set()

            for idx, pt in enumerate(pts):
                key = (pt["camera_id"], str(pt["timestamp"]))
                assert key not in seen_points, f"Duplicate point found in trip: {key}"
                seen_points.add(key)

                # Ensure heading, speed, and confidence are populated
                assert pt.get("heading") is not None, f"Point {key} missing heading"
                assert pt.get("speed_kmh") is not None, f"Point {key} missing speed_kmh"
                assert pt.get("confidence") is not None, f"Point {key} missing confidence"
                assert isinstance(pt["heading"], (int, float))
                assert isinstance(pt["speed_kmh"], (int, float))
                assert isinstance(pt["confidence"], (int, float))


def test_cli_report_output_formatting(monkeypatch, capsys):
    """Verify CLI report prints every stop with heading/speed and does not duplicate stop numbers."""
    monkeypatch.setattr(sys, "argv", ["trajectory_cli", "TN050T8444"])
    cli_main()

    captured = capsys.readouterr().out
    lines = [line.strip() for line in captured.splitlines() if line.strip()]

    # Collect all stop lines like "#01 [HH:MM:SS] ..."
    stop_pattern = re.compile(r"^#(\d{2})\s+\[\d{2}:\d{2}:\d{2}\]\s+(CAM_\d{3})\s+\|\s+(.+)$")
    heading_pattern = re.compile(r"^Heading:\s+(\S+)\s+\((.+)\)\s+\|\s+Speed:\s+(.+)\s+\|\s+Conf:\s+(.+)$")

    stops_found = []
    for i, line in enumerate(lines):
        m = stop_pattern.match(line)
        if m:
            stop_num = int(m.group(1))
            cam_id = m.group(2)
            # The next non-empty line MUST be the heading/speed line
            assert i + 1 < len(lines), f"Stop #{stop_num} ({cam_id}) has no following line"
            next_line = lines[i + 1]
            assert heading_pattern.match(next_line), (
                f"Stop #{stop_num} ({cam_id}) missing heading/speed line. Got: '{next_line}'"
            )
            stops_found.append((stop_num, cam_id))

    # In Trip 3 for TN050T8444, verify stops #12 and #13 are both present and formatted
    trip3_stops = [s for s in stops_found if s[0] >= 12]
    stop_nums = [s[0] for s in trip3_stops]
    assert 12 in stop_nums, "Stop #12 must be present in CLI report"
    assert 13 in stop_nums, "Stop #13 must be present in CLI report"
    assert stop_nums.count(13) == 1, "Stop #13 must be printed exactly once"
