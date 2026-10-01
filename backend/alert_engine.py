"""Real-Time ANPR Alert Engine with In-Memory History Cache & De-Duplication.

Processes incoming vehicle sightings in chronological order:
- Evaluates surveillance rules against recent plate history.
- Suppresses repeated alerts of the same type for the same vehicle within 10 minutes.
- Persists all security alerts to the database (alerts table).
"""

from __future__ import annotations

import collections
import datetime
from pathlib import Path
import sys
from typing import Any, Dict, Iterable, List, Optional, Tuple, Union

import pandas as pd
from sqlalchemy import insert
from sqlalchemy.orm import Session

# Ensure project root is in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.alert_rules import RuleContext, _to_datetime, evaluate_all_rules
from backend.db import SessionLocal
from backend.models import Alert
from backend.plate_utils import normalize_plate

DEFAULT_DEDUP_MINUTES = 10.0


class AlertEngine:
    """Surveillance event processor with in-memory temporal cache and de-duplication."""

    def __init__(
        self,
        dedup_minutes: float = DEFAULT_DEDUP_MINUTES,
        context: Optional[RuleContext] = None,
        max_history_per_plate: int = 50,
    ) -> None:
        self.dedup_minutes = dedup_minutes
        self.context = context or RuleContext.get_instance()
        self.max_history_per_plate = max_history_per_plate

        # In-memory fast recent history per vehicle plate
        self.plate_history: Dict[str, List[Dict[str, Any]]] = collections.defaultdict(list)

        # De-duplication cache: (plate_norm, alert_type) -> last_alert_datetime
        self.last_alert_time: Dict[Tuple[str, str], datetime.datetime] = {}

    def reset(self) -> None:
        """Clear all in-memory caches."""
        self.plate_history.clear()
        self.last_alert_time.clear()

    def process_event(
        self,
        event: Dict[str, Any],
        save_to_db: bool = False,
        session: Optional[Session] = None,
    ) -> List[Dict[str, Any]]:
        """Process a single ANPR sighting event and return newly triggered, non-duplicate alerts."""
        plate_raw = str(event.get("plate", ""))
        plate_norm = normalize_plate(plate_raw)
        if not plate_norm:
            return []

        ts = _to_datetime(event.get("timestamp"))
        event_copy = dict(event)
        event_copy["timestamp"] = ts

        history = self.plate_history[plate_norm]

        # 1. Evaluate all security rules
        raw_alerts = evaluate_all_rules(event_copy, history, context=self.context)

        # 2. Apply 10-minute de-duplication window
        valid_alerts: List[Dict[str, Any]] = []
        for alert in raw_alerts:
            atype = alert["alert_type"]
            dedup_key = (plate_norm, atype)

            if dedup_key in self.last_alert_time:
                prev_alert_ts = self.last_alert_time[dedup_key]
                time_diff_sec = (ts - prev_alert_ts).total_seconds()
                # If within dedup window (and not backwards in time), suppress
                if 0 <= time_diff_sec < (self.dedup_minutes * 60.0):
                    continue

            # Update deduplication timestamp and accept alert
            self.last_alert_time[dedup_key] = ts
            valid_alerts.append(alert)

        # 3. Update plate history cache (prune if history grows beyond limit)
        history.append(event_copy)
        if len(history) > self.max_history_per_plate:
            self.plate_history[plate_norm] = history[-self.max_history_per_plate:]

        # 4. Optional immediate DB persistence
        if save_to_db and valid_alerts:
            self.save_alerts_to_db(valid_alerts, session=session)

        return valid_alerts

    def process_all_events(
        self,
        events: Union[pd.DataFrame, Iterable[Dict[str, Any]]],
        save_to_db: bool = True,
        batch_size: int = 1000,
        progress_callback: Optional[callable] = None,
    ) -> List[Dict[str, Any]]:
        """Process a collection of events in timestamp order and optionally persist alerts."""
        if isinstance(events, pd.DataFrame):
            df_sorted = events.sort_values("timestamp")
            event_records = df_sorted.to_dict(orient="records")
        else:
            event_records = sorted(
                list(events),
                key=lambda x: _to_datetime(x.get("timestamp")),
            )

        all_alerts: List[Dict[str, Any]] = []
        uncommitted_alerts: List[Dict[str, Any]] = []

        session = SessionLocal() if save_to_db else None

        try:
            for idx, ev in enumerate(event_records):
                alerts = self.process_event(ev, save_to_db=False)
                if alerts:
                    all_alerts.extend(alerts)
                    if save_to_db:
                        uncommitted_alerts.extend(alerts)

                if progress_callback and (idx + 1) % 5000 == 0:
                    progress_callback(idx + 1, len(event_records), len(all_alerts))

                # Batch commit to database
                if save_to_db and len(uncommitted_alerts) >= batch_size:
                    self._persist_alert_batch(uncommitted_alerts, session)
                    uncommitted_alerts.clear()

            # Final flush of remaining uncommitted alerts
            if save_to_db and uncommitted_alerts:
                self._persist_alert_batch(uncommitted_alerts, session)
                uncommitted_alerts.clear()

        finally:
            if session:
                session.close()

        return all_alerts

    def _persist_alert_batch(self, alerts: List[Dict[str, Any]], session: Session) -> None:
        """Helper to insert a list of alerts into SQLite database."""
        if not alerts or not session:
            return

        now = datetime.datetime.utcnow()
        records = [
            {
                "alert_type": a["alert_type"],
                "severity": a.get("severity", "LOW"),
                "plate": a["plate"],
                "camera_id": a.get("camera_id"),
                "timestamp": a["timestamp"],
                "details": a.get("details", {}),
                "created_at": now,
            }
            for a in alerts
        ]

        try:
            session.execute(insert(Alert), records)
            session.commit()
        except Exception:
            session.rollback()
            raise

    def save_alerts_to_db(
        self,
        alerts: List[Dict[str, Any]],
        session: Optional[Session] = None,
    ) -> int:
        """Persist alerts to the alerts table."""
        if not alerts:
            return 0

        close_session = False
        if session is None:
            session = SessionLocal()
            close_session = True

        try:
            self._persist_alert_batch(alerts, session)
            return len(alerts)
        except Exception as exc:
            print(f"[WARNING] Failed to save alerts to database: {exc}")
            return 0
        finally:
            if close_session and session:
                session.close()
