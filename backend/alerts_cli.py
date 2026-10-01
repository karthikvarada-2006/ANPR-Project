"""Command-Line Interface for ANPR Surveillance Alerts.

Commands:
  python -m backend.alerts_cli list [--severity HIGH] [--plate KA50QA9345] [--limit 50]
  python -m backend.alerts_cli summary
"""

from __future__ import annotations

import argparse
import datetime
from pathlib import Path
import sys
from typing import Optional

# Ensure project root is in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from sqlalchemy import desc, func
from backend.db import SessionLocal
from backend.models import Alert
from backend.plate_utils import normalize_plate

# ANSI styling
COLOR_HIGH = "\033[91m\033[1m"
COLOR_MEDIUM = "\033[93m\033[1m"
COLOR_LOW = "\033[96m\033[1m"
COLOR_GRAY = "\033[90m"
COLOR_BOLD = "\033[1m"
COLOR_RESET = "\033[0m"


def format_severity_badge(severity: Optional[str]) -> str:
    sev = (severity or "LOW").upper()
    if sev == "HIGH":
        return f"{COLOR_HIGH}HIGH  {COLOR_RESET}"
    if sev == "MEDIUM":
        return f"{COLOR_MEDIUM}MEDIUM{COLOR_RESET}"
    return f"{COLOR_LOW}LOW   {COLOR_RESET}"


def cmd_list(
    severity: Optional[str] = None,
    plate: Optional[str] = None,
    alert_type: Optional[str] = None,
    limit: int = 50,
) -> int:
    """Query and display alerts from the database."""
    session = SessionLocal()
    try:
        query = session.query(Alert)

        if severity:
            query = query.filter(Alert.severity == severity.upper())

        if plate:
            p_norm = normalize_plate(plate)
            query = query.filter(func.upper(Alert.plate).like(f"%{p_norm}%"))

        if alert_type:
            query = query.filter(Alert.alert_type == alert_type.upper())

        total_matching = query.count()
        alerts = query.order_by(desc(Alert.timestamp), desc(Alert.id)).limit(limit).all()

        print("=" * 105)
        print("REAL-TIME SURVEILLANCE ALERTS LOG")
        print("=" * 105)
        filters = []
        if severity:
            filters.append(f"Severity={severity.upper()}")
        if plate:
            filters.append(f"Plate={plate.upper()}")
        if alert_type:
            filters.append(f"Type={alert_type.upper()}")
        filter_str = f" [Filters: {', '.join(filters)}]" if filters else ""
        print(f"Showing {len(alerts)} of {total_matching:,} matching alerts{filter_str}")
        print("-" * 105)

        if not alerts:
            print("No matching alerts found in database.")
            print("Tip: Run `python -m backend.replay_events --speed 0` to stream simulated events into the database.")
            print("=" * 105)
            return 0

        # Print table header
        print(f"{'ID':<6} | {'Timestamp':<19} | {'Severity':<6} | {'Type':<15} | {'Plate':<12} | {'Camera':<8} | Details")
        print("-" * 105)

        for a in alerts:
            ts_str = a.timestamp.strftime("%Y-%m-%d %H:%M:%S") if isinstance(a.timestamp, datetime.datetime) else str(a.timestamp)[:19]
            badge = format_severity_badge(a.severity)
            atype = a.alert_type or "UNKNOWN"
            plt = a.plate or "UNKNOWN"
            cid = a.camera_id or "-"
            
            # Format concise description from details dict
            details = a.details or {}
            if isinstance(details, dict):
                desc_str = (
                    details.get("message")
                    or details.get("reason")
                    or str(details)
                )
            else:
                desc_str = str(details)

            # Truncate details if overly long
            if len(desc_str) > 42:
                desc_str = desc_str[:39] + "..."

            print(f"{a.id:<6} | {COLOR_GRAY}{ts_str}{COLOR_RESET} | {badge} | {atype:<15} | {COLOR_BOLD}{plt:<12}{COLOR_RESET} | {cid:<8} | {desc_str}")

        print("=" * 105)
        return 0

    finally:
        session.close()


def cmd_summary() -> int:
    """Print high-level summary of alerts in database."""
    session = SessionLocal()
    try:
        total = session.query(Alert).count()
        print("=" * 80)
        print("SURVEILLANCE ALERTS DATABASE SUMMARY")
        print("=" * 80)
        print(f"Total Recorded Alerts: {total:,}")

        if total == 0:
            print("\nDatabase contains 0 alerts.")
            print("Run `python -m backend.replay_events --speed 0` to process the event stream.")
            print("=" * 80)
            return 0

        # By Severity
        print("\n--- Alerts by Severity ---")
        by_sev = session.query(Alert.severity, func.count(Alert.id)).group_by(Alert.severity).all()
        for sev, count in sorted(by_sev, key=lambda x: x[1], reverse=True):
            badge = format_severity_badge(sev)
            pct = (count / total) * 100.0
            print(f"  {badge} : {count:>6,d} ({pct:>5.1f}%)")

        # By Type
        print("\n--- Alerts by Rule Type ---")
        by_type = session.query(Alert.alert_type, func.count(Alert.id)).group_by(Alert.alert_type).all()
        for atype, count in sorted(by_type, key=lambda x: x[1], reverse=True):
            pct = (count / total) * 100.0
            print(f"  {atype:<18} : {count:>6,d} ({pct:>5.1f}%)")

        # Top cameras with alerts
        print("\n--- Top 5 Intersections by Alert Volume ---")
        top_cams = session.query(Alert.camera_id, func.count(Alert.id)).filter(Alert.camera_id != None).group_by(Alert.camera_id).order_by(desc(func.count(Alert.id))).limit(5).all()
        for rank, (cid, count) in enumerate(top_cams, start=1):
            print(f"  #{rank} {cid:<10} : {count:>5,d} alerts")

        print("=" * 80)
        return 0
    finally:
        session.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="ANPR Surveillance Alerts CLI.")
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # Command: list
    list_parser = subparsers.add_parser("list", help="List security alerts with filtering")
    list_parser.add_argument("--severity", type=str, choices=["HIGH", "MEDIUM", "LOW", "high", "medium", "low"], help="Filter by alert severity")
    list_parser.add_argument("--plate", type=str, help="Filter by vehicle license plate")
    list_parser.add_argument("--type", type=str, dest="alert_type", help="Filter by alert type (e.g. BLACKLIST, CLONED_PLATE)")
    list_parser.add_argument("--limit", type=int, default=50, help="Maximum number of alerts to display (default: 50)")

    # Command: summary
    subparsers.add_parser("summary", help="Print summary metrics of alerts in database")

    args = parser.parse_args()

    if args.command == "summary":
        return cmd_summary()
    elif args.command == "list" or args.command is None:
        # Default to list if arguments are supplied or if list is explicitly invoked
        sev = getattr(args, "severity", None)
        plt = getattr(args, "plate", None)
        atype = getattr(args, "alert_type", None)
        limit = getattr(args, "limit", 50)
        return cmd_list(severity=sev, plate=plt, alert_type=atype, limit=limit)
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())
