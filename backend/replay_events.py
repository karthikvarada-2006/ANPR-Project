"""Real-Time Event Replayer for City ANPR Surveillance Stream.

Replays historical or simulated ANPR events through AlertEngine as if live:
- Supports controllable simulation speed multipliers (--speed 100, --speed 0 for max speed).
- Prints each triggered alert immediately with ANSI colored severity badges.
- Persists all alerts to the SQLite database.
"""

from __future__ import annotations

import argparse
import datetime
from pathlib import Path
import sys
import time
from typing import Dict, List, Optional

import pandas as pd

# Ensure project root is in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.alert_engine import AlertEngine
from backend.alert_rules import _to_datetime
from simulator.config import EVENTS_PATH

# ANSI Color Codes for Terminal Output
COLOR_HIGH = "\033[91m\033[1m"      # Bright Bold Red
COLOR_MEDIUM = "\033[93m\033[1m"    # Bright Bold Yellow
COLOR_LOW = "\033[96m\033[1m"       # Bright Bold Cyan
COLOR_GRAY = "\033[90m"             # Dark Gray
COLOR_GREEN = "\033[92m"            # Green
COLOR_RESET = "\033[0m"             # Reset Style


def format_alert_log(alert: Dict) -> str:
    """Format an alert record into a clean, colored single-line terminal string."""
    sev = alert.get("severity", "LOW").upper()
    atype = alert.get("alert_type", "UNKNOWN")
    plate = alert.get("plate", "UNKNOWN")
    cid = alert.get("camera_id", "UNKNOWN")
    ts = alert.get("timestamp")
    ts_str = ts.strftime("%Y-%m-%d %H:%M:%S") if isinstance(ts, datetime.datetime) else str(ts)[:19]
    details = alert.get("details", {})

    if sev == "HIGH":
        badge = f"{COLOR_HIGH}[HIGH]{COLOR_RESET}"
    elif sev == "MEDIUM":
        badge = f"{COLOR_MEDIUM}[MEDIUM]{COLOR_RESET}"
    else:
        badge = f"{COLOR_LOW}[LOW]{COLOR_RESET} "

    # Build concise description based on alert type
    if atype == "BLACKLIST":
        mtype = details.get("match_type", "exact")
        reason = details.get("reason", "Blacklist target")
        desc = f"{reason} ({mtype.capitalize()} match)"
    elif atype == "CLONED_PLATE":
        prev = details.get("previous_camera", "N/A")
        spd = details.get("implied_speed_kmh", 0)
        dt = details.get("time_delta_seconds", 0)
        desc = f"Implied speed {spd:.1f} km/h from {prev} in {dt:.0f}s"
    elif atype == "WRONG_WAY":
        h = details.get("observed_heading", 0)
        dom = details.get("dominant_heading", 0)
        diff = details.get("heading_difference", 0)
        desc = f"Heading {h:.1f} deg differs by {diff:.1f} deg (Dominant: {dom:.1f} deg)"
    elif atype == "OVERSPEED":
        spd = details.get("speed_kmh", 0)
        limit = details.get("speed_limit_kmh", 80)
        desc = f"Clocked at {spd:.1f} km/h (Limit: {limit:.0f} km/h)"
    elif atype == "LOITERING":
        cnt = details.get("sighting_count", 0)
        win = details.get("window_minutes", 60)
        desc = f"Sighted {cnt} times within {win} minutes"
    elif atype == "RESTRICTED_ZONE":
        vtype = details.get("vehicle_type", "vehicle")
        win = details.get("restricted_window", "")
        desc = f"Prohibited {vtype} in restricted zone ({win})"
    else:
        desc = details.get("message", "")

    return f"{badge} {COLOR_GRAY}{ts_str}{COLOR_RESET} | {atype:<15} | {plate:<12} @ {cid:<8} | {desc}"


def replay_stream(
    events_path: Path = EVENTS_PATH,
    speed: float = 100.0,
    limit: Optional[int] = None,
    save_to_db: bool = True,
    dedup_minutes: float = 10.0,
    clear_db: bool = True,
) -> List[Dict]:
    """Replay events through the AlertEngine in chronological order."""
    if not events_path.exists():
        print(f"[ERROR] Events dataset not found at {events_path}")
        return []

    if save_to_db and clear_db:
        from backend.db import SessionLocal
        from backend.models import Alert
        s = SessionLocal()
        try:
            s.query(Alert).delete()
            s.commit()
        finally:
            s.close()

    print("=" * 80)
    print("CITY-WIDE ANPR REAL-TIME SURVEILLANCE & ALERT REPLAY STREAM")
    print("=" * 80)
    print(f"  Source Events CSV : {events_path}")
    print(f"  Replay Speed Rate : {speed}x realtime {'(AS FAST AS POSSIBLE)' if speed == 0 else ''}")
    print(f"  De-duplication    : {dedup_minutes:.0f} minutes window")
    print(f"  Database Storage  : {'Enabled (SQLite alerts table)' if save_to_db else 'Disabled'}")
    print("=" * 80)

    df = pd.read_csv(events_path)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.sort_values("timestamp")

    if limit and limit > 0:
        df = df.iloc[:limit]

    engine = AlertEngine(dedup_minutes=dedup_minutes)
    all_triggered: List[Dict] = []
    uncommitted_alerts: List[Dict] = []

    start_wall_time = time.time()
    prev_sim_time: Optional[datetime.datetime] = None

    print(f"Starting replay of {len(df):,} events...\n")

    for idx, row in df.iterrows():
        ev = row.to_dict()
        curr_sim_time = ev["timestamp"]

        # Pacing simulation
        if speed > 0 and prev_sim_time is not None:
            sim_delta_sec = (curr_sim_time - prev_sim_time).total_seconds()
            if sim_delta_sec > 0:
                sleep_sec = sim_delta_sec / speed
                # Cap sleep to at most 0.5s to avoid long idle pauses during quiet hours
                sleep_sec = min(sleep_sec, 0.5)
                time.sleep(sleep_sec)

        prev_sim_time = curr_sim_time

        # Process event through AlertEngine
        new_alerts = engine.process_event(ev, save_to_db=False)
        if new_alerts:
            for alert in new_alerts:
                print(format_alert_log(alert))
                all_triggered.append(alert)
                if save_to_db:
                    uncommitted_alerts.append(alert)

        # Batch save to DB every 200 alerts
        if save_to_db and len(uncommitted_alerts) >= 200:
            engine.save_alerts_to_db(uncommitted_alerts)
            uncommitted_alerts.clear()

    # Flush remaining alerts to DB
    if save_to_db and uncommitted_alerts:
        engine.save_alerts_to_db(uncommitted_alerts)
        uncommitted_alerts.clear()

    elapsed_wall_time = time.time() - start_wall_time
    throughput = len(df) / max(elapsed_wall_time, 0.001)

    print("\n" + "=" * 80)
    print("REPLAY RUN COMPLETE - SURVEILLANCE REPORT")
    print("=" * 80)
    print(f"  Processed Events    : {len(df):,}")
    print(f"  Total Alerts Raised : {len(all_triggered):,}")
    print(f"  Replay Wall Time    : {elapsed_wall_time:.2f} seconds")
    print(f"  Throughput Speed    : {throughput:,.1f} events/second")
    print("-" * 80)

    if all_triggered:
        alerts_df = pd.DataFrame(all_triggered)
        print("ALERTS BY SEVERITY:")
        for sev, count in alerts_df["severity"].value_counts().items():
            print(f"  - {sev:<10} : {count:>5,d}")

        print("\nALERTS BY RULE TYPE:")
        for atype, count in alerts_df["alert_type"].value_counts().items():
            print(f"  - {atype:<18} : {count:>5,d}")
    else:
        print("  No alerts triggered.")
    print("=" * 80)

    return all_triggered


def main() -> int:
    parser = argparse.ArgumentParser(description="Replay ANPR events through AlertEngine.")
    parser.add_argument("--speed", type=float, default=100.0, help="Replay speed multiplier (0 = max speed)")
    parser.add_argument("--events", type=str, default=str(EVENTS_PATH), help="Path to events CSV file")
    parser.add_argument("--limit", type=int, default=None, help="Max number of events to process")
    parser.add_argument("--no-db", action="store_true", help="Do not save alerts to database")
    parser.add_argument("--no-clear", action="store_true", help="Do not clear existing database alerts before replay")
    parser.add_argument("--dedup", type=float, default=10.0, help="De-duplication window in minutes")

    args = parser.parse_args()

    replay_stream(
        events_path=Path(args.events),
        speed=args.speed,
        limit=args.limit,
        save_to_db=not args.no_db,
        dedup_minutes=args.dedup,
        clear_db=not args.no_clear,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
