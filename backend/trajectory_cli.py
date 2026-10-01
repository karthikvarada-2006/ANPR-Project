"""CLI tool to query and inspect vehicle trajectories and flagged anomalies.

Usage:
    python -m backend.trajectory_cli <PLATE>
    python backend/trajectory_cli.py <PLATE>
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure project root is in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.plate_utils import normalize_plate
from backend.trajectory import get_trajectory


def format_duration(seconds: float) -> str:
    """Format duration seconds into human readable m:ss or h:mm:ss."""
    s = int(round(seconds))
    if s < 60:
        return f"{s}s"
    m, sec = divmod(s, 60)
    if m < 60:
        return f"{m}m {sec:02d}s"
    h, m = divmod(m, 60)
    return f"{h}h {m:02d}m {sec:02d}s"


def main():
    parser = argparse.ArgumentParser(
        description="Inspect vehicle trajectory timeline and flagged anomalies."
    )
    parser.add_argument("plate", help="Target vehicle license plate (e.g. KA01AB1234)")
    parser.add_argument(
        "--no-fuzzy",
        action="store_true",
        help="Disable fuzzy OCR plate matching (exact match only)",
    )
    parser.add_argument(
        "--start",
        type=str,
        default=None,
        help="Start datetime filter (YYYY-MM-DD HH:MM:SS)",
    )
    parser.add_argument(
        "--end",
        type=str,
        default=None,
        help="End datetime filter (YYYY-MM-DD HH:MM:SS)",
    )

    args = parser.parse_args()

    plate = normalize_plate(args.plate)
    if not plate:
        print("[ERROR] Please provide a valid non-empty license plate.")
        sys.exit(1)

    print("=" * 80)
    print(f"ANPR VEHICLE TRAJECTORY REPORT: {plate}")
    print("=" * 80)

    res = get_trajectory(
        plate=plate,
        start=args.start,
        end=args.end,
        fuzzy=not args.no_fuzzy,
    )

    matched = res.get("matched_plates", [])
    if matched:
        print(f"Candidate Plates Checked: {', '.join(matched)}")

    total_trips = res.get("total_trips", 0)
    flagged_hops = res.get("flagged_hops", [])

    print(f"Total Trips Reconstructed : {total_trips}")
    print(f"Flagged Anomalies / Hops  : {len(flagged_hops)}")
    print("-" * 80)

    if total_trips == 0:
        print(f"No sightings recorded for plate '{plate}'.")
        print("=" * 80)
        return

    for trip in res.get("trips", []):
        t_id = trip["trip_id"]
        pts = trip["points"]
        dist_km = trip["total_distance_km"]
        dur_str = format_duration(trip["duration_seconds"])
        avg_speed = trip["avg_speed_kmh"]
        start_t = trip["start_time"]
        end_t = trip["end_time"]

        print(f"\nTRIP #{t_id} | {start_t} -> {end_t}")
        print(f"  Distance: {dist_km:.2f} km | Duration: {dur_str} | Avg Speed: {avg_speed:.1f} km/h | Sightings: {len(pts)}")
        print("  " + "-" * 76)

        seen_in_trip = set()
        printed_stop_idx = 1

        for pt in pts:
            pt_key = (pt["camera_id"], str(pt["timestamp"]))
            if pt_key in seen_in_trip:
                continue
            seen_in_trip.add(pt_key)

            ts = pt["timestamp"]
            ts_str = ts.strftime("%H:%M:%S") if hasattr(ts, "strftime") else str(ts)[11:19]
            cam_id = pt["camera_id"]
            # Clean camera name: replace literal '#' with 'No. ' to avoid accidental hashtag parsing
            cam_name = pt["name"].replace("#", "No. ")

            spd_val = pt.get("speed_kmh")
            speed = f"{spd_val:.1f} km/h" if spd_val is not None else "0.0 km/h"

            compass = pt.get("compass") or "N/A"
            hdg_val = pt.get("heading")
            heading = f"{hdg_val:.1f} deg" if hdg_val is not None else "0.0 deg"

            cnf_val = pt.get("confidence")
            conf = f"{int(cnf_val * 100)}%" if cnf_val is not None else "100%"

            read_plate = pt.get("plate_read", plate)
            diff_tag = f" [OCR read: {read_plate}]" if read_plate != plate else ""

            # Print stop header and metrics
            print(f"  #{printed_stop_idx:02d} [{ts_str}] {cam_id} | {cam_name}")
            print(f"       Heading: {compass} ({heading}) | Speed: {speed:>9} | Conf: {conf:>4}{diff_tag}")
            printed_stop_idx += 1

    if flagged_hops:
        print("\n" + "=" * 80)
        print("SECURITY ALERTS: FLAGGED IMPOSSIBLE HOPS (CLONED PLATES)")
        print("=" * 80)
        for h in flagged_hops:
            c1, c2 = h["from_camera"], h["to_camera"]
            n1 = h.get("from_camera_name", c1).replace("#", "No. ")
            n2 = h.get("to_camera_name", c2).replace("#", "No. ")
            t1, t2 = h["from_timestamp"], h["to_timestamp"]
            dt = h["time_delta_seconds"]
            dist = h["distance_km"]
            speed = h["implied_speed_kmh"]
            reason = h["reason"]

            print(f"  [!] {reason} HOP: {c1} -> {c2}")
            print(f"      From: {n1} ({t1})")
            print(f"      To:   {n2} ({t2})")
            print(f"      Metrics: {dist:.2f} km in {dt:.1f}s -> Implied Speed: {speed:.1f} km/h (Limit: 120 km/h)")
            print(f"      Assessment: High probability of cloned plates operating simultaneously in different sectors.")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
