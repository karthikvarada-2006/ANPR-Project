"""Real-Time Surveillance and Anomaly Detection Rules for ANPR Events.

Implements rule evaluations for:
1. BLACKLIST (Exact match -> HIGH, Fuzzy confusable match -> MEDIUM)
2. CLONED_PLATE (Impossible speed > 120 km/h between cameras -> HIGH)
3. WRONG_WAY (Heading differs > 135 degrees from dominant heading -> MEDIUM)
4. OVERSPEED (Speed > 80 km/h -> LOW)
5. LOITERING (Same plate at same camera > 3 times within 60 minutes -> LOW)
6. RESTRICTED_ZONE (Restricted camera & time window violation -> MEDIUM)
"""

from __future__ import annotations

import datetime
from pathlib import Path
import pickle
import sys
from typing import Any, Dict, List, Optional, Set, Tuple

import pandas as pd

# Ensure project root is in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import collections
from backend.plate_utils import CANONICAL_MAP, normalize_plate, plate_distance
from simulator.config import (
    BLACKLIST_PATH,
    CAMERAS_PATH,
    DATA_SIM_DIR,
    EVENTS_PATH,
    GROUND_TRUTH_PATH,
    RESTRICTED_CAMERAS,
    RESTRICTED_TIME_WINDOW,
    RESTRICTED_VEHICLE_TYPES,
    WRONG_WAY_ENABLED,
)


def _to_datetime(ts: Any) -> datetime.datetime:
    """Safely convert any string, timestamp, or datetime to standard datetime.datetime."""
    if isinstance(ts, datetime.datetime):
        return ts
    if isinstance(ts, pd.Timestamp):
        return ts.to_pydatetime()
    if isinstance(ts, str):
        return pd.to_datetime(ts).to_pydatetime()
    return datetime.datetime.now()


def _is_time_in_window(t: datetime.time, start_str: str, end_str: str) -> bool:
    """Check if a time-of-day falls inside [start_str, end_str] (handles midnight crossing)."""
    start_parts = [int(p) for p in start_str.split(":")]
    end_parts = [int(p) for p in end_str.split(":")]
    start_time = datetime.time(start_parts[0], start_parts[1])
    end_time = datetime.time(end_parts[0], end_parts[1])

    if start_time <= end_time:
        return start_time <= t <= end_time
    # Wraps past midnight (e.g., 22:00 to 06:00)
    return t >= start_time or t <= end_time


class RuleContext:
    """Shared cache of precomputed lookups for fast, real-time rule evaluation."""

    _instance: Optional[RuleContext] = None

    def __init__(self) -> None:
        self.blacklist: Dict[str, str] = {}
        self.camera_paths: Dict[Tuple[str, str], Tuple[float, float, list]] = {}
        self.camera_coords: Dict[str, Tuple[float, float]] = {}
        self.dominant_headings: Dict[str, float] = {}
        self.plate_to_vehicle_type: Dict[str, str] = {}
        self.known_plates: Set[str] = set()
        self.canonical_known_plates: Dict[str, Set[str]] = collections.defaultdict(set)
        self.wrong_way_enabled: bool = WRONG_WAY_ENABLED
        self.restricted_config: Dict[str, Any] = {
            "camera_ids": list(RESTRICTED_CAMERAS),
            "time_window": RESTRICTED_TIME_WINDOW,
            "vehicle_types": list(RESTRICTED_VEHICLE_TYPES),
        }
        self.load_all()

    @classmethod
    def get_instance(cls) -> RuleContext:
        """Singleton accessor for zero-overhead rule execution."""
        if cls._instance is None:
            cls._instance = RuleContext()
        return cls._instance

    def load_all(self) -> None:
        """Load lookup datasets from disk."""
        self._load_blacklist()
        self._load_cameras()
        self._load_camera_paths()
        self._load_dominant_headings()
        self._load_vehicle_types()

    def _load_blacklist(self) -> None:
        if BLACKLIST_PATH.exists():
            df = pd.read_csv(BLACKLIST_PATH)
            for _, row in df.iterrows():
                p = normalize_plate(row["plate"])
                reason = str(row.get("reason", "Vehicle on surveillance blacklist"))
                self.blacklist[p] = reason

    def _load_cameras(self) -> None:
        if CAMERAS_PATH.exists():
            df = pd.read_csv(CAMERAS_PATH)
            for _, row in df.iterrows():
                cid = str(row["camera_id"])
                lat = float(row["lat"])
                lon = float(row["lon"])
                self.camera_coords[cid] = (lat, lon)

    def _load_camera_paths(self) -> None:
        paths_file = DATA_SIM_DIR / "camera_paths.pkl"
        if paths_file.exists():
            with open(paths_file, "rb") as f:
                self.camera_paths = pickle.load(f)

    def _load_dominant_headings(self) -> None:
        if EVENTS_PATH.exists():
            df = pd.read_csv(EVENTS_PATH)
            for cid, group in df.groupby("camera_id"):
                mode_series = group["heading_degrees"].mode()
                dom = float(mode_series.iloc[0]) if not mode_series.empty else float(group["heading_degrees"].mean())
                self.dominant_headings[str(cid)] = dom

    def _load_vehicle_types(self) -> None:
        if GROUND_TRUTH_PATH.exists():
            gt = pd.read_csv(GROUND_TRUTH_PATH)
            if "vehicle_type" in gt.columns:
                p2t = gt.drop_duplicates("plate").set_index("plate")["vehicle_type"].to_dict()
                self.plate_to_vehicle_type = {normalize_plate(k): v for k, v in p2t.items()}
                self.known_plates = set(self.plate_to_vehicle_type.keys())
                self.canonical_known_plates.clear()
                for kp in self.known_plates:
                    self.canonical_known_plates[kp.translate(CANONICAL_MAP)].add(kp)

    def is_ocr_variant(self, plate: str) -> bool:
        """Check if normalized plate looks like an OCR confusable variant of a different known plate."""
        if not self.known_plates or not plate:
            return False
        norm_p = normalize_plate(plate)
        canon = norm_p.translate(CANONICAL_MAP)
        candidates = self.canonical_known_plates.get(canon, set())
        for kp in candidates:
            if kp != norm_p and plate_distance(norm_p, kp) <= 0.6:
                return True
        return False



# ==============================================================================
# Rule 1: BLACKLIST
# ==============================================================================
def check_blacklist(
    event: Dict[str, Any],
    history: List[Dict[str, Any]],
    blacklist: Optional[Dict[str, str]] = None,
) -> List[Dict[str, Any]]:
    """Flag vehicles on security blacklist: HIGH for exact, MEDIUM for fuzzy match (dist <= 0.6)."""
    if blacklist is None:
        blacklist = RuleContext.get_instance().blacklist

    if not blacklist:
        return []

    plate = normalize_plate(event.get("plate", ""))
    if not plate:
        return []

    cid = event.get("camera_id", "UNKNOWN")
    ts = _to_datetime(event.get("timestamp"))
    ocr_conf = float(event.get("ocr_confidence", 1.0) or 1.0)

    # 1. Exact match check -> Severity HIGH
    if plate in blacklist:
        return [
            {
                "alert_type": "BLACKLIST",
                "severity": "HIGH",
                "plate": event.get("plate", plate),
                "camera_id": cid,
                "timestamp": ts,
                "event_id": event.get("event_id"),
                "details": {
                    "matched_plate": plate,
                    "reason": blacklist[plate],
                    "match_type": "exact",
                    "distance": 0.0,
                    "ocr_confidence": round(ocr_conf, 3),
                    "event_id": event.get("event_id"),
                    "message": f"Exact blacklist hit: vehicle {plate} spotted at {cid}.",
                },
            }
        ]

    # 2. Fuzzy confusable match check -> Severity MEDIUM
    # Only if OCR confidence is at least 0.5 and edit distance is <= 0.6
    if ocr_conf >= 0.5:
        plate_len = len(plate)
        best_match: Optional[Tuple[str, str, float]] = None
        min_dist = 999.0

        for bp, reason in blacklist.items():
            # A distance <= 0.6 is only mathematically possible if lengths match (each insert/del is 1.0)
            if len(bp) == plate_len:
                d = plate_distance(plate, bp)
                if d <= 0.6 and d < min_dist:
                    min_dist = d
                    best_match = (bp, reason, d)

        if best_match:
            matched_plate, reason, d = best_match
            return [
                {
                    "alert_type": "BLACKLIST",
                    "severity": "MEDIUM",
                    "plate": event.get("plate", plate),
                    "camera_id": cid,
                    "timestamp": ts,
                    "event_id": event.get("event_id"),
                    "details": {
                        "matched_plate": matched_plate,
                        "reason": reason,
                        "match_type": "fuzzy",
                        "distance": round(d, 2),
                        "ocr_confidence": round(ocr_conf, 3),
                        "event_id": event.get("event_id"),
                        "message": (
                            f"Fuzzy blacklist match: observed '{plate}' matches blacklisted '{matched_plate}' "
                            f"(distance: {d:.1f}, conf: {ocr_conf:.2f})."
                        ),
                    },
                }
            ]

    return []


# ==============================================================================
# Rule 2: CLONED_PLATE
# ==============================================================================
def check_cloned_plate(
    event: Dict[str, Any],
    history: List[Dict[str, Any]],
    camera_paths: Optional[Dict] = None,
    speed_threshold_kmh: float = 120.0,
    known_plates: Optional[Set[str]] = None,
) -> List[Dict[str, Any]]:
    """Flag impossible speed (> 120 km/h) between consecutive sightings -> Severity HIGH.

    Requires:
    1. Exact normalized plate match between sightings.
    2. OCR confidence >= 0.70 on BOTH sightings.
    """
    if not history:
        return []

    prev_event = history[-1]
    curr_cid = event.get("camera_id")
    prev_cid = prev_event.get("camera_id")

    if not curr_cid or not prev_cid or curr_cid == prev_cid:
        return []

    # 1. Require exact normalized plate match on both sightings
    curr_plate_norm = normalize_plate(event.get("plate", ""))
    prev_plate_norm = normalize_plate(prev_event.get("plate", ""))
    if not curr_plate_norm or not prev_plate_norm or curr_plate_norm != prev_plate_norm:
        return []

    # 2. Require ocr_confidence >= 0.7 on BOTH sightings
    curr_conf = float(event.get("ocr_confidence", 1.0) if event.get("ocr_confidence") is not None else 1.0)
    prev_conf = float(prev_event.get("ocr_confidence", 1.0) if prev_event.get("ocr_confidence") is not None else 1.0)
    if curr_conf < 0.7 or prev_conf < 0.7:
        return []

    curr_ts = _to_datetime(event.get("timestamp"))
    prev_ts = _to_datetime(prev_event.get("timestamp"))

    dt_sec = (curr_ts - prev_ts).total_seconds()
    if dt_sec <= 0:
        return []

    # Look up precomputed road distance
    if camera_paths is None:
        camera_paths = RuleContext.get_instance().camera_paths

    dist_m = 0.0
    pair = (str(prev_cid), str(curr_cid))
    if camera_paths and pair in camera_paths:
        dist_km = float(camera_paths[pair][0])
        dist_m = dist_km * 1000.0
    else:
        # Fallback to GPS coordinates haversine distance
        coords = RuleContext.get_instance().camera_coords
        if prev_cid in coords and curr_cid in coords:
            from simulator.build_city import haversine_distance_meters
            lat1, lon1 = coords[prev_cid]
            lat2, lon2 = coords[curr_cid]
            dist_m = haversine_distance_meters(lat1, lon1, lat2, lon2)

    if dist_m <= 0:
        return []

    implied_speed_kmh = (dist_m / dt_sec) * 3.6

    if implied_speed_kmh > speed_threshold_kmh:
        plate = event.get("plate", "")
        return [
            {
                "alert_type": "CLONED_PLATE",
                "severity": "HIGH",
                "plate": plate,
                "camera_id": curr_cid,
                "timestamp": curr_ts,
                "event_id": event.get("event_id"),
                "details": {
                    "previous_camera": prev_cid,
                    "previous_timestamp": prev_ts.isoformat(),
                    "time_delta_seconds": round(dt_sec, 1),
                    "distance_meters": round(dist_m, 1),
                    "implied_speed_kmh": round(implied_speed_kmh, 1),
                    "speed_threshold_kmh": speed_threshold_kmh,
                    "ocr_confidence": round(curr_conf, 3),
                    "previous_ocr_confidence": round(prev_conf, 3),
                    "event_id": event.get("event_id"),
                    "previous_event_id": prev_event.get("event_id"),
                    "message": (
                        f"Cloned plate suspected: vehicle {plate} seen at {prev_cid} and {curr_cid} "
                        f"({dist_m:.0f}m apart) in {dt_sec:.0f}s (implied speed {implied_speed_kmh:.1f} km/h)."
                    ),
                },
            }
        ]

    return []


# ==============================================================================
# Rule 3: WRONG_WAY
# ==============================================================================
def check_wrong_way(
    event: Dict[str, Any],
    history: List[Dict[str, Any]],
    dominant_headings: Optional[Dict[str, float]] = None,
    threshold_degrees: float = 135.0,
) -> List[Dict[str, Any]]:
    """Flag heading differing by > 135 degrees from camera's dominant heading -> Severity MEDIUM."""
    heading = event.get("heading_degrees")
    cid = event.get("camera_id")

    if heading is None or not cid:
        return []

    if dominant_headings is None:
        dominant_headings = RuleContext.get_instance().dominant_headings

    if str(cid) not in dominant_headings:
        return []

    dom = dominant_headings[str(cid)]
    h = float(heading)

    # Angular difference on circular 360-degree scale
    diff = 180.0 - abs(abs(h - dom) - 180.0)

    if diff > threshold_degrees:
        plate = event.get("plate", "")
        ts = _to_datetime(event.get("timestamp"))
        return [
            {
                "alert_type": "WRONG_WAY",
                "severity": "MEDIUM",
                "plate": plate,
                "camera_id": cid,
                "timestamp": ts,
                "details": {
                    "observed_heading": round(h, 1),
                    "dominant_heading": round(dom, 1),
                    "heading_difference": round(diff, 1),
                    "threshold_degrees": threshold_degrees,
                    "message": (
                        f"Wrong-way driving: vehicle {plate} heading {h:.1f} deg differs by {diff:.1f} deg "
                        f"from camera {cid} dominant heading ({dom:.1f} deg)."
                    ),
                },
            }
        ]

    return []


# ==============================================================================
# Rule 4: OVERSPEED
# ==============================================================================
def check_overspeed(
    event: Dict[str, Any],
    history: List[Dict[str, Any]],
    speed_threshold_kmh: float = 80.0,
) -> List[Dict[str, Any]]:
    """Flag instantaneous speed exceeding 80 km/h -> Severity LOW."""
    speed = event.get("speed_kmh")
    if speed is None:
        return []

    s = float(speed)
    if s > speed_threshold_kmh:
        plate = event.get("plate", "")
        cid = event.get("camera_id", "UNKNOWN")
        ts = _to_datetime(event.get("timestamp"))
        return [
            {
                "alert_type": "OVERSPEED",
                "severity": "LOW",
                "plate": plate,
                "camera_id": cid,
                "timestamp": ts,
                "details": {
                    "speed_kmh": round(s, 1),
                    "speed_limit_kmh": speed_threshold_kmh,
                    "excess_speed_kmh": round(s - speed_threshold_kmh, 1),
                    "message": f"Overspeed detected: vehicle {plate} clocked at {s:.1f} km/h (Limit: {speed_threshold_kmh:.0f} km/h).",
                },
            }
        ]

    return []


# ==============================================================================
# Rule 5: LOITERING
# ==============================================================================
def check_loitering(
    event: Dict[str, Any],
    history: List[Dict[str, Any]],
    window_minutes: int = 60,
    count_threshold: int = 3,
) -> List[Dict[str, Any]]:
    """Flag plate seen at same camera > 3 times in 60 minutes -> Severity LOW."""
    cid = event.get("camera_id")
    if not cid or not history:
        return []

    curr_ts = _to_datetime(event.get("timestamp"))
    cutoff = curr_ts - datetime.timedelta(minutes=window_minutes)

    # Count prior sightings at this camera within window
    past_sightings = [
        h for h in history
        if h.get("camera_id") == cid and cutoff <= _to_datetime(h.get("timestamp")) <= curr_ts
    ]

    total_sightings = len(past_sightings) + 1  # Including current sighting

    if total_sightings > count_threshold:
        plate = event.get("plate", "")
        return [
            {
                "alert_type": "LOITERING",
                "severity": "LOW",
                "plate": plate,
                "camera_id": cid,
                "timestamp": curr_ts,
                "details": {
                    "sighting_count": total_sightings,
                    "window_minutes": window_minutes,
                    "threshold": count_threshold,
                    "message": (
                        f"Suspicious loitering: vehicle {plate} sighted {total_sightings} times "
                        f"at camera {cid} within {window_minutes} minutes."
                    ),
                },
            }
        ]

    return []


# ==============================================================================
# Rule 6: RESTRICTED_ZONE
# ==============================================================================
def check_restricted_zone(
    event: Dict[str, Any],
    history: List[Dict[str, Any]],
    config: Optional[Dict[str, Any]] = None,
    plate_to_vehicle_type: Optional[Dict[str, str]] = None,
) -> List[Dict[str, Any]]:
    """Flag unauthorized vehicles (e.g., trucks) in restricted zones during prohibited hours -> Severity MEDIUM."""
    if config is None:
        config = RuleContext.get_instance().restricted_config

    restricted_cams = config.get("camera_ids", [])
    cid = event.get("camera_id")
    if not cid or cid not in restricted_cams:
        return []

    # Check time window
    time_window = config.get("time_window", ("00:00", "05:00"))
    ts = _to_datetime(event.get("timestamp"))
    if not _is_time_in_window(ts.time(), time_window[0], time_window[1]):
        return []

    # Check vehicle type restriction
    restricted_types = config.get("vehicle_types", ["truck"])
    vtype = event.get("vehicle_type")
    if not vtype:
        if plate_to_vehicle_type is None:
            plate_to_vehicle_type = RuleContext.get_instance().plate_to_vehicle_type
        plate_norm = normalize_plate(event.get("plate", ""))
        vtype = plate_to_vehicle_type.get(plate_norm, "unknown")

    # If restricted_types is None or contains "all", flag all vehicles
    is_violation = False
    if not restricted_types or "all" in restricted_types:
        is_violation = True
    elif vtype in restricted_types:
        is_violation = True

    if is_violation:
        plate = event.get("plate", "")
        return [
            {
                "alert_type": "RESTRICTED_ZONE",
                "severity": "MEDIUM",
                "plate": plate,
                "camera_id": cid,
                "timestamp": ts,
                "details": {
                    "restricted_window": f"{time_window[0]}-{time_window[1]}",
                    "vehicle_type": vtype,
                    "restricted_types": restricted_types,
                    "message": (
                        f"Restricted zone entry: {vtype.upper()} ({plate}) entered {cid} "
                        f"during prohibited curfew window ({time_window[0]} - {time_window[1]})."
                    ),
                },
            }
        ]

    return []


# ==============================================================================
# Master Rule Evaluator
# ==============================================================================
def evaluate_all_rules(
    event: Dict[str, Any],
    history: List[Dict[str, Any]],
    context: Optional[RuleContext] = None,
) -> List[Dict[str, Any]]:
    """Run all 6 surveillance rules against an incoming event and plate history."""
    if context is None:
        context = RuleContext.get_instance()

    alerts: List[Dict[str, Any]] = []

    # 1. Blacklist
    alerts.extend(check_blacklist(event, history, blacklist=context.blacklist))

    # 2. Cloned plate
    alerts.extend(check_cloned_plate(event, history, camera_paths=context.camera_paths))

    # 3. Wrong-way driving (disabled by default in config)
    if getattr(context, "wrong_way_enabled", WRONG_WAY_ENABLED):
        alerts.extend(check_wrong_way(event, history, dominant_headings=context.dominant_headings))

    # 4. Overspeeding
    alerts.extend(check_overspeed(event, history))

    # 5. Loitering
    alerts.extend(check_loitering(event, history))

    # 6. Restricted zone
    alerts.extend(
        check_restricted_zone(
            event,
            history,
            config=context.restricted_config,
            plate_to_vehicle_type=context.plate_to_vehicle_type,
        )
    )

    return alerts
