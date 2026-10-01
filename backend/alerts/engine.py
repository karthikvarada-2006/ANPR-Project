"""Module 7: Real-Time Alerts & Anomaly Detection Engine.

Monitors the ANPR event stream and detects:
1. Security Blacklist matches (stolen, wanted, or suspicious vehicles).
2. Cloned Plate Anomalies (impossible vehicle speeds between disjoint cameras).
3. Section-Control Speed Violations (average speed exceeding corridor limits).
"""

from __future__ import annotations

import datetime
from pathlib import Path
import sys
from typing import Dict, List, Optional, Set, Tuple

import pandas as pd
from sqlalchemy import insert
from sqlalchemy.exc import OperationalError

# Ensure project root is in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.db import SessionLocal
from backend.models import Alert
from simulator.build_city import haversine_distance_meters
from simulator.config import CAMERAS_PATH

DEFAULT_SPEED_LIMIT_KMH = 60.0
IMPOSSIBLE_SPEED_THRESHOLD_KMH = 180.0


class AlertEngine:
    """Evaluates surveillance rules against incoming ANPR camera observations."""

    def __init__(self, speed_limit_kmh: float = DEFAULT_SPEED_LIMIT_KMH):
        self.speed_limit_kmh = speed_limit_kmh
        self.camera_coords: Dict[str, Tuple[float, float]] = {}
        self._load_camera_coordinates()

    def _load_camera_coordinates(self) -> None:
        """Load camera GPS coordinates for distance and speed calculations."""
        if CAMERAS_PATH.exists():
            df = pd.read_csv(CAMERAS_PATH)
            for _, row in df.iterrows():
                cid = str(row["camera_id"])
                lat = float(row["lat"])
                lon = float(row["lon"])
                self.camera_coords[cid] = (lat, lon)

    def evaluate_sighting(
        self,
        current_event: Dict,
        previous_event: Optional[Dict] = None,
        blacklist_set: Optional[Set[str]] = None,
    ) -> List[Dict]:
        """Evaluate a single sighting event and return any triggered alerts."""
        alerts = []
        plate = current_event["plate"]
        cid = current_event["camera_id"]
        ts = current_event["timestamp"]
        if isinstance(ts, str):
            ts = pd.to_datetime(ts).to_pydatetime()

        # 1. Rule: Blacklist match
        if blacklist_set and plate in blacklist_set:
            alerts.append(
                {
                    "alert_type": "BLACKLIST",
                    "plate": plate,
                    "camera_id": cid,
                    "timestamp": ts,
                    "details": {
                        "message": f"Security alert: Blacklisted vehicle {plate} spotted at camera {cid}.",
                        "ocr_confidence": current_event.get("ocr_confidence", 1.0),
                    },
                }
            )

        # 2. Rules: Speeding & Cloned Plate between consecutive sightings
        if previous_event:
            prev_cid = previous_event["camera_id"]
            prev_ts = previous_event["timestamp"]
            if isinstance(prev_ts, str):
                prev_ts = pd.to_datetime(prev_ts).to_pydatetime()

            delta_sec = (ts - prev_ts).total_seconds()

            if delta_sec > 0 and prev_cid in self.camera_coords and cid in self.camera_coords:
                lat1, lon1 = self.camera_coords[prev_cid]
                lat2, lon2 = self.camera_coords[cid]
                dist_m = haversine_distance_meters(lat1, lon1, lat2, lon2)

                speed_mps = dist_m / delta_sec
                speed_kmh = (speed_mps * 3600.0) / 1000.0

                # Check for physically impossible speed (Cloned Plate Anomaly)
                if speed_kmh >= IMPOSSIBLE_SPEED_THRESHOLD_KMH and dist_m >= 1500.0:
                    alerts.append(
                        {
                            "alert_type": "ROUTE_ANOMALY",
                            "plate": plate,
                            "camera_id": cid,
                            "timestamp": ts,
                            "details": {
                                "sub_type": "CLONED_PLATE",
                                "message": (
                                    f"Cloned plate suspected: {plate} seen at {prev_cid} and {cid} "
                                    f"({dist_m:.0f}m apart) in {delta_sec:.0f}s (implied speed {speed_kmh:.1f} km/h)."
                                ),
                                "previous_camera": prev_cid,
                                "distance_meters": round(dist_m, 1),
                                "time_delta_seconds": round(delta_sec, 1),
                                "implied_speed_kmh": round(speed_kmh, 1),
                            },
                        }
                    )
                # Check for section speeding violation
                elif speed_kmh > self.speed_limit_kmh and dist_m >= 400.0:
                    alerts.append(
                        {
                            "alert_type": "SPEED_VIOLATION",
                            "plate": plate,
                            "camera_id": cid,
                            "timestamp": ts,
                            "details": {
                                "message": (
                                    f"Speed violation: Vehicle {plate} traveled corridor {prev_cid} -> {cid} "
                                    f"at {speed_kmh:.1f} km/h (Limit: {self.speed_limit_kmh:.0f} km/h)."
                                ),
                                "previous_camera": prev_cid,
                                "section_speed_kmh": round(speed_kmh, 1),
                                "speed_limit_kmh": self.speed_limit_kmh,
                            },
                        }
                    )

        return alerts

    def process_all_events(
        self, events_df: pd.DataFrame, blacklist_df: pd.DataFrame
    ) -> List[Dict]:
        """Scan historical or simulated events and detect all security alerts."""
        blacklist_set = set(blacklist_df["plate"].dropna().str.strip())
        print(f"Monitoring {len(blacklist_set)} blacklisted plates across {len(events_df):,} events...")

        events_sorted = events_df.sort_values("timestamp")
        vehicle_last_sighting: Dict[str, Dict] = {}
        all_alerts: List[Dict] = []

        for _, row in events_sorted.iterrows():
            event_dict = row.to_dict()
            plate = str(row["plate"]).strip()

            prev = vehicle_last_sighting.get(plate)
            triggered = self.evaluate_sighting(event_dict, prev, blacklist_set)
            all_alerts.extend(triggered)

            vehicle_last_sighting[plate] = event_dict

        print(f"Alert evaluation complete: {len(all_alerts):,} total alerts triggered.")
        return all_alerts

    def save_alerts_to_db(self, alerts: List[Dict]) -> int:
        """Persist triggered alerts to the PostgreSQL database."""
        session = SessionLocal()
        try:
            records = []
            for a in alerts:
                records.append(
                    {
                        "alert_type": a["alert_type"],
                        "plate": a["plate"],
                        "camera_id": a["camera_id"],
                        "timestamp": a["timestamp"],
                        "details": a["details"],
                        "created_at": datetime.datetime.utcnow(),
                    }
                )

            session.execute(insert(Alert), records)
            session.commit()
            print(f"Persisted {len(records)} alerts to 'alerts' table.")
            return len(records)
        except Exception as exc:
            session.rollback()
            print(f"[NOTE] Database alert persistence skipped: {exc}")
            return 0
        finally:
            session.close()


def main() -> int:
    events_csv = ROOT_DIR / "data" / "sim" / "events.csv"
    blacklist_csv = ROOT_DIR / "data" / "sim" / "blacklist.csv"

    if not events_csv.exists() or not blacklist_csv.exists():
        print("[ERROR] Required simulation files missing. Run simulator first.")
        return 1

    events_df = pd.read_csv(events_csv)
    blacklist_df = pd.read_csv(blacklist_csv)

    engine = AlertEngine()
    alerts = engine.process_all_events(events_df, blacklist_df)

    # Print summary
    alert_types = pd.Series([a["alert_type"] for a in alerts]).value_counts()
    print("\nTriggered Alerts Breakdown:")
    for atype, count in alert_types.items():
        print(f"  - {atype:<20}: {count:>6,d} alerts")

    # Save to DB if connected
    engine.save_alerts_to_db(alerts)

    return 0


if __name__ == "__main__":
    sys.exit(main())
