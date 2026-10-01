"""Module 5 Visualization: Plot vehicle trajectory map with road network, cameras, arrows, and stops.

Usage:
    python plot_trajectory.py <PLATE>
    python -m backend.plot_trajectory <PLATE>
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import matplotlib
matplotlib.use("Agg")  # Non-interactive backend for headless / file generation
import matplotlib.pyplot as plt
import matplotlib.patheffects as pe
import numpy as np

# Ensure project root is in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.plate_utils import normalize_plate
from backend.trajectory import get_trajectory, get_road_graph, get_cameras_info
from simulator.config import DOCS_DIR


def plot_vehicle_trajectory(
    plate: str,
    output_path: Optional[Path] = None,
    fuzzy: bool = True,
) -> Path:
    """Render high-resolution map of vehicle trajectory and save to disk."""
    norm_plate = normalize_plate(plate)
    if not norm_plate:
        raise ValueError("Invalid or empty license plate provided.")

    traj = get_trajectory(norm_plate, fuzzy=fuzzy)
    trips = traj.get("trips", [])
    flagged_hops = traj.get("flagged_hops", [])

    if not trips and not flagged_hops:
        raise ValueError(f"No trajectory sightings found for vehicle plate '{norm_plate}'.")

    if output_path is None:
        DOCS_DIR.mkdir(parents=True, exist_ok=True)
        output_path = DOCS_DIR / f"trajectory_{norm_plate}.png"
    else:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

    G = get_road_graph()
    cams_info = get_cameras_info()

    # Collect all visited coordinates to calculate map bounding box
    all_lats: List[float] = []
    all_lons: List[float] = []

    for trip in trips:
        for pt in trip["points"]:
            all_lats.append(pt["lat"])
            all_lons.append(pt["lon"])
        for geom_pt in trip["route_geometry"]:
            all_lats.append(geom_pt[0])
            all_lons.append(geom_pt[1])

    for h in flagged_hops:
        c1 = cams_info.get(h["from_camera"])
        c2 = cams_info.get(h["to_camera"])
        if c1:
            all_lats.append(c1["lat"])
            all_lons.append(c1["lon"])
        if c2:
            all_lats.append(c2["lat"])
            all_lons.append(c2["lon"])

    if not all_lats or not all_lons:
        raise ValueError("No coordinates found to plot.")

    min_lat, max_lat = min(all_lats), max(all_lats)
    min_lon, max_lon = min(all_lons), max(all_lons)

    # Add margin padding around trajectory (minimum 0.015 degrees)
    lat_pad = max(0.015, (max_lat - min_lat) * 0.25)
    lon_pad = max(0.015, (max_lon - min_lon) * 0.25)

    bbox_lat_min = min_lat - lat_pad
    bbox_lat_max = max_lat + lat_pad
    bbox_lon_min = min_lon - lon_pad
    bbox_lon_max = max_lon + lon_pad

    # Create figure with sleek modern dark theme
    fig, ax = plt.subplots(figsize=(14, 11), dpi=200, facecolor="#0f172a")
    ax.set_facecolor("#0f172a")

    # 1. Plot road network edges within bounding box
    for u, v, data in G.edges(data=True):
        u_node = G.nodes[u]
        v_node = G.nodes[v]
        u_lat, u_lon = u_node["y"], u_node["x"]
        v_lat, v_lon = v_node["y"], v_node["x"]

        # Fast bounding box rejection
        if not (
            bbox_lat_min <= u_lat <= bbox_lat_max
            and bbox_lon_min <= u_lon <= bbox_lon_max
            or bbox_lat_min <= v_lat <= bbox_lat_max
            and bbox_lon_min <= v_lon <= bbox_lon_max
        ):
            continue

        if "geometry" in data:
            xs, ys = data["geometry"].xy
            ax.plot(xs, ys, color="#334155", linewidth=0.75, alpha=0.5, zorder=1)
        else:
            ax.plot([u_lon, v_lon], [u_lat, v_lat], color="#334155", linewidth=0.75, alpha=0.5, zorder=1)

    # 2. Plot all ANPR cameras across the city
    cam_lons = [c["lon"] for c in cams_info.values() if bbox_lat_min <= c["lat"] <= bbox_lat_max and bbox_lon_min <= c["lon"] <= bbox_lon_max]
    cam_lats = [c["lat"] for c in cams_info.values() if bbox_lat_min <= c["lat"] <= bbox_lat_max and bbox_lon_min <= c["lon"] <= bbox_lon_max]
    ax.scatter(cam_lons, cam_lats, color="#64748b", s=30, alpha=0.5, label="ANPR Cameras", zorder=2, edgecolors="none")

    # 3. Plot trips and route geometry with directional arrows
    trip_colors = ["#38bdf8", "#34d399", "#a78bfa", "#f472b6", "#fbbf24"]

    stop_counter = 1
    total_km = sum(t["total_distance_km"] for t in trips)
    total_sec = sum(t["duration_seconds"] for t in trips)

    for trip_idx, trip in enumerate(trips):
        color = trip_colors[trip_idx % len(trip_colors)]
        route_pts = trip["route_geometry"]
        trip_num = trip["trip_id"]

        if len(route_pts) >= 2:
            r_lons = [p[1] for p in route_pts]
            r_lats = [p[0] for p in route_pts]

            # Glowing trajectory route line
            ax.plot(r_lons, r_lats, color=color, linewidth=5.0, alpha=0.3, zorder=3)
            ax.plot(r_lons, r_lats, color=color, linewidth=2.8, alpha=0.95, label=f"Trip #{trip_num} ({trip['total_distance_km']:.2f} km)", zorder=4)

            # Draw directional arrows along the path
            num_pts = len(route_pts)
            arrow_step = max(3, num_pts // 5)
            for k in range(arrow_step // 2, num_pts - 1, arrow_step):
                p1 = route_pts[k]
                p2 = route_pts[k + 1]
                dx = p2[1] - p1[1]
                dy = p2[0] - p1[0]
                if abs(dx) > 1e-6 or abs(dy) > 1e-6:
                    ax.annotate(
                        "",
                        xy=(p2[1], p2[0]),
                        xytext=(p1[1], p1[0]),
                        arrowprops=dict(
                            arrowstyle="-|>",
                            color="#f8fafc",
                            lw=1.5,
                            mutation_scale=14,
                        ),
                        zorder=5,
                    )

        # 4. Numbered Stops on camera sightings
        pts = trip["points"]
        for pt_idx, pt in enumerate(pts):
            is_start = (trip_idx == 0 and pt_idx == 0)
            is_end = (trip_idx == len(trips) - 1 and pt_idx == len(pts) - 1)

            stop_num_str = str(stop_counter)
            stop_counter += 1

            circle_color = "#22c55e" if is_start else ("#ef4444" if is_end else "#f59e0b")

            # Draw glowing marker
            ax.scatter(
                [pt["lon"]],
                [pt["lat"]],
                s=180,
                color=circle_color,
                edgecolors="#ffffff",
                linewidth=1.5,
                zorder=6,
            )

            # Number label inside / beside circle
            ax.text(
                pt["lon"],
                pt["lat"],
                stop_num_str,
                color="#0f172a" if not (is_start or is_end) else "#ffffff",
                fontsize=8,
                fontweight="bold",
                ha="center",
                va="center",
                zorder=7,
            )

            # Camera ID + timestamp tooltip text
            ts_str = pt["timestamp"].strftime("%H:%M") if hasattr(pt["timestamp"], "strftime") else str(pt["timestamp"])[11:16]
            label_text = f"{pt['camera_id']} ({ts_str})"
            ax.text(
                pt["lon"] + 0.0008,
                pt["lat"] + 0.0006,
                label_text,
                color="#f8fafc",
                fontsize=8,
                fontweight="medium",
                zorder=8,
                path_effects=[pe.withStroke(linewidth=2.5, foreground="#0f172a")],
            )

    # 5. Flagged Impossible Hops (Cloned Plates)
    for h in flagged_hops:
        c1 = cams_info.get(h["from_camera"])
        c2 = cams_info.get(h["to_camera"])
        if c1 and c2:
            ax.plot(
                [c1["lon"], c2["lon"]],
                [c1["lat"], c2["lat"]],
                color="#ef4444",
                linestyle="--",
                linewidth=2.5,
                alpha=0.9,
                label=f"IMPOSSIBLE HOP ({h['implied_speed_kmh']:.0f} km/h)",
                zorder=6,
            )
            mid_lon = (c1["lon"] + c2["lon"]) / 2.0
            mid_lat = (c1["lat"] + c2["lat"]) / 2.0
            ax.text(
                mid_lon,
                mid_lat,
                f"⚠ CLONED ANOMALY\n{h['implied_speed_kmh']:.0f} km/h",
                color="#ef4444",
                fontsize=9,
                fontweight="bold",
                ha="center",
                va="center",
                zorder=8,
                path_effects=[pe.withStroke(linewidth=3, foreground="#0f172a")],
            )

    # Set axes limits
    ax.set_xlim(bbox_lon_min, bbox_lon_max)
    ax.set_ylim(bbox_lat_min, bbox_lat_max)

    # Title & Subtitles
    dur_min = int(total_sec // 60)
    dur_sec = int(total_sec % 60)
    ax.set_title(
        f"Vehicle Trajectory Reconstruction: {norm_plate}\n"
        f"Trips: {len(trips)} | Distance: {total_km:.2f} km | Duration: {dur_min}m {dur_sec}s | Stops: {stop_counter - 1}",
        fontsize=13,
        fontweight="bold",
        color="#f8fafc",
        pad=16,
    )

    # Clean minimalist axes styling
    ax.tick_params(colors="#94a3b8", labelsize=8)
    for spine in ax.spines.values():
        spine.set_color("#334155")
    ax.grid(True, linestyle=":", alpha=0.3, color="#475569")

    # Legend
    legend = ax.legend(loc="upper right", facecolor="#1e293b", edgecolor="#475569", fontsize=9, labelcolor="#f8fafc")
    legend.get_frame().set_alpha(0.85)

    plt.tight_layout()
    plt.savefig(output_path, dpi=200, bbox_inches="tight")
    plt.close(fig)

    print(f"[OK] Trajectory plot saved successfully to: {output_path.resolve()}")
    return output_path


def main():
    parser = argparse.ArgumentParser(description="Plot reconstructed vehicle trajectory on road network.")
    parser.add_argument("plate", help="Target vehicle license plate (e.g. TN11YD7305)")
    parser.add_argument("--output", type=str, default=None, help="Output image file path (.png)")
    parser.add_argument("--no-fuzzy", action="store_true", help="Disable fuzzy plate matching")
    args = parser.parse_args()

    out_p = Path(args.output) if args.output else None
    plot_vehicle_trajectory(args.plate, output_path=out_p, fuzzy=not args.no_fuzzy)


if __name__ == "__main__":
    main()
