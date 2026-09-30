"""Module 1: City ANPR Network & Trajectory Visualizer.

This script generates a publication-quality map visualization:
1. Renders the complete city road network in a modern dark-mode aesthetic.
2. Plots all ANPR camera locations with IDs.
3. Identifies an active vehicle with multi-camera sightings and traces its reconstructed trajectory.
4. Saves the resulting visualization to docs/city_map.png.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import List, Tuple

import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
import osmnx as ox
import pandas as pd

from simulator.config import (
    CAMERAS_PATH,
    CITY_NAME,
    DOCS_DIR,
    GRAPH_PATH,
    GROUND_TRUTH_PATH,
    MAP_PATH,
)


def generate_city_visualization() -> Path:
    """Generate and save the city road network and sample trajectory map."""
    DOCS_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Loading road graph from: {GRAPH_PATH} ...")
    G = ox.load_graphml(GRAPH_PATH)

    print(f"Loading camera registry from: {CAMERAS_PATH} ...")
    cameras_df = pd.read_csv(CAMERAS_PATH)

    print(f"Loading ground truth events from: {GROUND_TRUTH_PATH} ...")
    events_df = pd.read_csv(GROUND_TRUTH_PATH)

    # 1. Find a vehicle with multiple camera hits for an exciting trajectory
    plate_counts = events_df["plate"].value_counts()
    sample_plate = None
    for plate, count in plate_counts.items():
        if count >= 3:
            # Check that it visited at least 2 distinct cameras
            cams_visited = events_df[events_df["plate"] == plate]["camera_id"].nunique()
            if cams_visited >= 3:
                sample_plate = plate
                break

    if sample_plate is None:
        sample_plate = plate_counts.index[0]

    traj_events = events_df[events_df["plate"] == sample_plate].sort_values("timestamp")
    print(f"Selected sample trajectory for vehicle '{sample_plate}' ({len(traj_events)} camera hits).")

    # Match trajectory events with camera GPS coordinates
    cam_coord_map = dict(zip(cameras_df["camera_id"], zip(cameras_df["lon"], cameras_df["lat"])))
    traj_coords = []
    for _, row in traj_events.iterrows():
        cid = row["camera_id"]
        if cid in cam_coord_map:
            traj_coords.append((cam_coord_map[cid][0], cam_coord_map[cid][1], cid, row["timestamp"]))

    # 2. Extract road network edges for fast vector rendering
    print("Preparing road network vector segments...")
    edge_lines = []
    for u, v, data in G.edges(data=True):
        if "geometry" in data:
            coords = list(data["geometry"].coords)
            edge_lines.append(coords)
        else:
            edge_lines.append([(G.nodes[u]["x"], G.nodes[u]["y"]), (G.nodes[v]["x"], G.nodes[v]["y"])])

    # 3. Create matplotlib figure with sleek dark styling
    plt.style.use("dark_background")
    fig, ax = plt.subplots(figsize=(14, 14), dpi=300)
    fig.patch.set_facecolor("#0b0f19")
    ax.set_facecolor("#0b0f19")

    # Render road network lines
    road_collection = LineCollection(
        edge_lines,
        colors="#1e293b",
        linewidths=0.6,
        alpha=0.75,
        zorder=1,
    )
    ax.add_collection(road_collection)

    # 4. Plot all ANPR Cameras
    cam_lons = cameras_df["lon"].values
    cam_lats = cameras_df["lat"].values

    # Subtle camera halo
    ax.scatter(
        cam_lons,
        cam_lats,
        c="#38bdf8",
        s=120,
        alpha=0.25,
        zorder=2,
    )
    # Camera dot
    ax.scatter(
        cam_lons,
        cam_lats,
        c="#0ea5e9",
        edgecolors="#ffffff",
        linewidth=0.8,
        s=45,
        label=f"ANPR Cameras (N={len(cameras_df)})",
        zorder=3,
    )

    # 5. Plot Sample Vehicle Trajectory
    if len(traj_coords) >= 2:
        t_lons = [c[0] for c in traj_coords]
        t_lats = [c[1] for c in traj_coords]

        # Draw trajectory glow line
        ax.plot(
            t_lons,
            t_lats,
            color="#22c55e",
            linewidth=4.0,
            alpha=0.4,
            zorder=4,
        )
        # Draw main trajectory path
        ax.plot(
            t_lons,
            t_lats,
            color="#4ade80",
            linewidth=2.0,
            linestyle="--",
            alpha=0.95,
            label=f"Trajectory: {sample_plate}",
            zorder=5,
        )

        # Draw sequential waypoint nodes
        for idx, (lon, lat, cid, t_str) in enumerate(traj_coords):
            # Sequence circle
            ax.scatter(
                lon,
                lat,
                c="#22c55e",
                edgecolors="#ffffff",
                s=110,
                linewidth=1.2,
                zorder=6,
            )
            # Order number
            ax.text(
                lon,
                lat,
                str(idx + 1),
                color="#052e16",
                fontsize=7,
                fontweight="bold",
                ha="center",
                va="center",
                zorder=7,
            )
            # Timestamp label
            time_part = t_str.split(" ")[-1]
            ax.annotate(
                f"{cid}\n{time_part}",
                (lon, lat),
                textcoords="offset points",
                xytext=(8, 8),
                fontsize=7.5,
                color="#86efac",
                fontweight="semibold",
                bbox=dict(boxstyle="round,pad=0.2", facecolor="#064e3b", edgecolor="#22c55e", alpha=0.85),
                zorder=8,
            )

    # Auto-scale view limits with small margin
    margin = 0.005
    ax.set_xlim(min(cam_lons) - margin, max(cam_lons) + margin)
    ax.set_ylim(min(cam_lats) - margin, max(cam_lats) + margin)
    ax.set_aspect("equal")

    # Titles and annotations
    plt.title(
        f"City-Wide Multi-Camera ANPR Sensor Network & Trajectory Tracking\n"
        f"Urban Street Graph: {CITY_NAME} (Radius: 5 km)",
        fontsize=14,
        fontweight="bold",
        color="#f8fafc",
        pad=18,
    )

    # Legend
    leg = ax.legend(
        loc="upper right",
        frameon=True,
        facecolor="#1e293b",
        edgecolor="#334155",
        fontsize=9,
    )
    for text in leg.get_texts():
        text.set_color("#f1f5f9")

    # Statistics watermark box
    stats_text = (
        f"City: {CITY_NAME}\n"
        f"Road Nodes: {len(G):,}\n"
        f"Road Edges: {len(G.edges):,}\n"
        f"ANPR Cameras: {len(cameras_df)}\n"
        f"Tracked Vehicle: {sample_plate} ({len(traj_coords)} sightings)"
    )
    ax.text(
        0.02,
        0.02,
        stats_text,
        transform=ax.transAxes,
        fontsize=8.5,
        color="#94a3b8",
        family="monospace",
        bbox=dict(boxstyle="round,pad=0.5", facecolor="#0f172a", edgecolor="#334155", alpha=0.9),
        zorder=10,
    )

    ax.axis("off")
    plt.tight_layout()

    print(f"Saving high-resolution map to: {MAP_PATH} ...")
    plt.savefig(MAP_PATH, dpi=300, facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close()
    print("Map visualization generated successfully.")

    return MAP_PATH


def main() -> int:
    generate_city_visualization()
    return 0


if __name__ == "__main__":
    sys.exit(main())
