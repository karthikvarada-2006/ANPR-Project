"""Module 6 Visualization: Generate publication-grade urban traffic analytics charts.

Generates 4 visual analytics artifacts saved into docs/:
1. docs/hourly_traffic_trend.png - Diurnal traffic volume & speed trends with peak hours.
2. docs/congestion_timeline.png - Temporal congestion severity matrix across top cameras.
3. docs/od_matrix_heatmap.png - Zone-to-zone Origin-Destination vehicle journey flows.
4. docs/evening_peak_heatmap.png - Road network GIS congestion map for evening peak (17:00-20:00).
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # Headless non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.patheffects as pe
import numpy as np
import pandas as pd

# Ensure project root is in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.analytics import (
    camera_stats,
    city_flow_trend,
    congestion_hotspots,
    heatmap_points,
    load_cameras_df,
    origin_destination_matrix,
)
from backend.trajectory import get_road_graph
from simulator.config import DOCS_DIR


def plot_hourly_traffic_trend(output_path: Path) -> Path:
    """Plot dual-axis diurnal volume and average speed trend with peak hours highlighted."""
    trend = city_flow_trend(window_minutes=15)
    trend["hour"] = trend["window_start"].dt.hour + trend["window_start"].dt.minute / 60.0

    # Aggregate by hour for clean bar presentation
    hourly = trend.copy()
    hourly["hour_int"] = hourly["window_start"].dt.hour
    hr_grouped = hourly.groupby("hour_int").agg(
        total_volume=("vehicle_count", "sum"),
        avg_speed=("avg_speed_kmh", "mean"),
    ).reset_index()

    fig, ax1 = plt.subplots(figsize=(13, 6.5), dpi=200, facecolor="#0f172a")
    ax1.set_facecolor("#0f172a")

    # Primary axis: Vehicle count bars
    hours = hr_grouped["hour_int"].values
    volumes = hr_grouped["total_volume"].values
    speeds = hr_grouped["avg_speed"].values

    bars = ax1.bar(
        hours, volumes, width=0.65, color="#38bdf8", alpha=0.75, label="Hourly Vehicle Volume", zorder=3
    )

    ax1.set_xlabel("Time of Day (Hour)", fontsize=11, fontweight="bold", color="#f8fafc", labelpad=10)
    ax1.set_ylabel("Total Vehicles Detected", fontsize=11, fontweight="bold", color="#38bdf8", labelpad=10)
    ax1.tick_params(colors="#94a3b8", labelsize=9)
    ax1.set_xticks(hours)
    ax1.set_xticklabels([f"{h:02d}:00" for h in hours], rotation=45)
    ax1.grid(True, linestyle=":", alpha=0.25, color="#475569", zorder=1)

    # Shaded peak periods
    ax1.axvspan(7.5, 10.5, color="#f59e0b", alpha=0.15, label="Morning Peak (08:00 - 10:00)", zorder=2)
    ax1.axvspan(16.5, 20.5, color="#ef4444", alpha=0.15, label="Evening Peak (17:00 - 20:00)", zorder=2)

    # Secondary axis: Average speed line
    ax2 = ax1.twinx()
    ax2.plot(
        hours, speeds, color="#f59e0b", linewidth=3.0, marker="o", markersize=7,
        label="Average Speed (km/h)", zorder=5
    )
    ax2.set_ylabel("Average Speed (km/h)", fontsize=11, fontweight="bold", color="#f59e0b", labelpad=10)
    ax2.tick_params(colors="#94a3b8", labelsize=9)
    ax2.set_ylim(15.0, 50.0)

    # Title & styling
    plt.title(
        "Bangalore City-Wide Traffic Flow & Speed Diurnal Profile\n"
        "Morning Peak (08:00 - 10:00) & Evening Peak (17:00 - 20:00) Congestion",
        fontsize=13, fontweight="bold", color="#f8fafc", pad=15
    )

    # Unified Legend
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    legend = ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper left", facecolor="#1e293b", edgecolor="#475569", labelcolor="#f8fafc", fontsize=9)
    legend.get_frame().set_alpha(0.85)

    for spine in ax1.spines.values():
        spine.set_color("#334155")
    for spine in ax2.spines.values():
        spine.set_color("#334155")

    plt.tight_layout()
    plt.savefig(output_path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"  [OK] Saved hourly traffic trend to: {output_path.name}")
    return output_path


def plot_congestion_timeline(output_path: Path) -> Path:
    """Plot temporal heatmap matrix of congestion severity across top congested intersections."""
    cong = congestion_hotspots(window_minutes=15)
    if cong.empty:
        return output_path

    # Rank top 15 most congested cameras by total congestion count
    top_cams = cong["camera_id"].value_counts().head(15).index.tolist()
    filtered = cong[cong["camera_id"].isin(top_cams)].copy()

    # Format time window labels
    filtered["hour"] = filtered["window_start"].dt.strftime("%H:%M")

    # Pivot into camera x time severity matrix
    piv = filtered.pivot_table(
        index="camera_name",
        columns="hour",
        values="severity",
        aggfunc="max",
        fill_value=0.0,
    )

    # Sort cameras by mean severity
    piv = piv.loc[piv.mean(axis=1).sort_values(ascending=True).index]

    fig, ax = plt.subplots(figsize=(14, 8), dpi=200, facecolor="#0f172a")
    ax.set_facecolor("#0f172a")

    im = ax.imshow(piv.values, cmap="YlOrRd", aspect="auto", vmin=0.0, vmax=1.0)

    # Ticks and labels
    ax.set_yticks(np.arange(len(piv.index)))
    ax.set_yticklabels(piv.index, fontsize=9, color="#f8fafc")
    ax.set_xticks(np.arange(0, len(piv.columns), 2))
    ax.set_xticklabels(piv.columns[::2], rotation=45, fontsize=9, color="#94a3b8")

    ax.set_xlabel("Time Window (HH:MM)", fontsize=11, fontweight="bold", color="#f8fafc", labelpad=10)
    ax.set_ylabel("ANPR Camera Intersection", fontsize=11, fontweight="bold", color="#f8fafc", labelpad=10)
    ax.set_title("Intersection Congestion Severity Timeline (15-min Intervals)\n"
                 "Severity (0.0 - 1.0) based on Speed Deficit vs. Free-Flow Baseline",
                 fontsize=13, fontweight="bold", color="#f8fafc", pad=15)

    cbar = fig.colorbar(im, ax=ax, fraction=0.02, pad=0.03)
    cbar.set_label("Congestion Severity Score", color="#f8fafc", fontsize=10, labelpad=8)
    cbar.ax.tick_params(colors="#94a3b8", labelsize=8)

    plt.tight_layout()
    plt.savefig(output_path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"  [OK] Saved congestion timeline to: {output_path.name}")
    return output_path


def plot_od_matrix_heatmap(output_path: Path) -> Path:
    """Plot annotated heatmap of zone-to-zone Origin-Destination vehicle trip volumes."""
    od_pivot = origin_destination_matrix(n_zones=8)

    fig, ax = plt.subplots(figsize=(11, 9), dpi=200, facecolor="#0f172a")
    ax.set_facecolor("#0f172a")

    im = ax.imshow(od_pivot.values, cmap="Blues", aspect="auto")

    # Annotate values inside each cell
    max_val = od_pivot.values.max()
    for i in range(od_pivot.shape[0]):
        for j in range(od_pivot.shape[1]):
            val = od_pivot.values[i, j]
            txt_color = "#ffffff" if val > (max_val * 0.5) else "#0f172a"
            ax.text(j, i, f"{val:,}", ha="center", va="center", color=txt_color, fontsize=9, fontweight="bold")

    zone_labels = [z.replace("Zone ", "Z") for z in od_pivot.index]

    ax.set_xticks(np.arange(len(zone_labels)))
    ax.set_xticklabels(zone_labels, rotation=35, ha="right", fontsize=9, color="#f8fafc")
    ax.set_yticks(np.arange(len(zone_labels)))
    ax.set_yticklabels(zone_labels, fontsize=9, color="#f8fafc")

    ax.set_xlabel("Destination Zone", fontsize=11, fontweight="bold", color="#f8fafc", labelpad=10)
    ax.set_ylabel("Origin Zone", fontsize=11, fontweight="bold", color="#f8fafc", labelpad=10)
    ax.set_title(f"Urban Origin-Destination (OD) Matrix: {od_pivot.values.sum():,} Trips\n"
                 "Spatial Trip Volume between 8 Clustered Camera Zones",
                 fontsize=13, fontweight="bold", color="#f8fafc", pad=15)

    cbar = fig.colorbar(im, ax=ax, fraction=0.03, pad=0.03)
    cbar.set_label("Trip Volume", color="#f8fafc", fontsize=10, labelpad=8)
    cbar.ax.tick_params(colors="#94a3b8", labelsize=8)

    plt.tight_layout()
    plt.savefig(output_path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"  [OK] Saved OD matrix heatmap to: {output_path.name}")
    return output_path


def plot_evening_peak_heatmap(output_path: Path) -> Path:
    """Plot geographic congestion heatmap on top of Bangalore's road network during evening peak (17:00-20:00)."""
    # 1. Compute evening peak heatmap points
    hp = heatmap_points(start="2026-10-01 17:00:00", end="2026-10-01 20:00:00")
    G = get_road_graph()

    fig, ax = plt.subplots(figsize=(14, 11), dpi=200, facecolor="#0f172a")
    ax.set_facecolor("#0f172a")

    # 2. Draw road network edges
    for _, _, data in G.edges(data=True):
        if "geometry" in data:
            xs, ys = data["geometry"].xy
            ax.plot(xs, ys, color="#334155", linewidth=0.75, alpha=0.45, zorder=1)
        else:
            pass

    # 3. Draw evening peak congestion heat points
    sc = ax.scatter(
        hp["lon"], hp["lat"],
        c=hp["weight"],
        s=hp["vehicle_count"] * 1.5 + 40,
        cmap="inferno",
        vmin=0.0,
        vmax=1.0,
        alpha=0.9,
        edgecolors="#f8fafc",
        linewidth=1.2,
        zorder=4,
    )

    # 4. Highlight top 5 congestion hotspots
    top5 = hp.sort_values("weight", ascending=False).head(5)
    for idx, (_, row) in enumerate(top5.iterrows(), 1):
        ax.scatter([row["lon"]], [row["lat"]], s=350, facecolors="none", edgecolors="#ef4444", linewidth=2.5, zorder=5)

        short_label = f"#{idx} {row['camera_id']}\n{row['vehicle_count']} veh | {row['avg_speed_kmh']:.1f} km/h"
        ax.text(
            row["lon"] + 0.001, row["lat"] + 0.0008,
            short_label,
            fontsize=8,
            fontweight="bold",
            color="#fef08a",
            zorder=6,
            path_effects=[pe.withStroke(linewidth=3, foreground="#0f172a")],
        )

    # Formatting
    ax.set_title(
        "Bangalore Urban Road Network: Evening Peak Congestion Heatmap (17:00 - 20:00)\n"
        "Bubble Size = Vehicle Count | Color = Congestion & Density Weight (0.0 to 1.0)",
        fontsize=13, fontweight="bold", color="#f8fafc", pad=15,
    )
    ax.tick_params(colors="#94a3b8", labelsize=8)
    for spine in ax.spines.values():
        spine.set_color("#334155")
    ax.grid(True, linestyle=":", alpha=0.25, color="#475569")

    cbar = fig.colorbar(sc, ax=ax, fraction=0.025, pad=0.03)
    cbar.set_label("Congestion & Density Index (0.0 - 1.0)", color="#f8fafc", fontsize=10, labelpad=8)
    cbar.ax.tick_params(colors="#94a3b8", labelsize=8)

    plt.tight_layout()
    plt.savefig(output_path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"  [OK] Saved evening peak heatmap to: {output_path.name}")
    return output_path


def generate_all_plots():
    print("=" * 70)
    print("GENERATING TRAFFIC ANALYTICS VISUALIZATIONS")
    print("=" * 70)
    DOCS_DIR.mkdir(parents=True, exist_ok=True)

    plot_hourly_traffic_trend(DOCS_DIR / "hourly_traffic_trend.png")
    plot_congestion_timeline(DOCS_DIR / "congestion_timeline.png")
    plot_od_matrix_heatmap(DOCS_DIR / "od_matrix_heatmap.png")
    plot_evening_peak_heatmap(DOCS_DIR / "evening_peak_heatmap.png")

    print("=" * 70)
    print(f"All 4 visual analytics charts saved successfully to: {DOCS_DIR.resolve()}")
    print("=" * 70)


if __name__ == "__main__":
    generate_all_plots()
