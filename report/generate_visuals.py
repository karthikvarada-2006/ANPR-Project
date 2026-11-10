"""Generate all 28 high-resolution figures, schematics, charts, and placeholder screenshots for the B.Tech project report.

Output directory: report/assets/
DPI: 300 (exceeds 200+ dpi requirement)
"""

import os
import sys
from pathlib import Path

# Fix MPLCONFIGDIR before importing matplotlib
assets_dir = Path(__file__).resolve().parent / "assets"
assets_dir.mkdir(parents=True, exist_ok=True)
os.environ["MPLCONFIGDIR"] = str((assets_dir / ".mpl_cache").resolve())

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.patches import FancyBboxPatch, ArrowStyle, FancyArrowPatch, Polygon
import numpy as np
from PIL import Image, ImageDraw, ImageFont

# Set consistent styling
plt.rcParams.update({
    "font.family": "serif",
    "font.size": 11,
    "axes.titlesize": 13,
    "axes.labelsize": 11,
    "xtick.labelsize": 10,
    "ytick.labelsize": 10,
    "figure.titlesize": 14,
    "figure.dpi": 300,
    "savefig.dpi": 300,
    "savefig.bbox": "tight",
})

# Color palette: Academic Navy / Slate / Teal / Coral / Gray
PRIMARY = "#1B365D"    # Deep Navy
SECONDARY = "#336699"  # Slate Blue
ACCENT = "#2E8B57"     # Sea Green / Teal
WARN = "#D9534F"       # Coral Red
HIGHLIGHT = "#F0AD4E"  # Amber Gold
BG_LIGHT = "#F8F9FA"   # Clean off-white
CARD_BG = "#FFFFFF"    # Crisp White
TEXT_DARK = "#222222"
BORDER = "#CCCCCC"

def draw_box(ax, x, y, w, h, title, subtitle=None, bg=CARD_BG, border=PRIMARY, lw=1.5, title_color=PRIMARY, text_color=TEXT_DARK, title_size=10, sub_size=8.5, radius=0.03):
    """Draw a rounded rectangular box with title and description."""
    box = FancyBboxPatch((x, y), w, h, boxstyle=f"round,pad=0.01,rounding_size={radius}",
                         facecolor=bg, edgecolor=border, linewidth=lw)
    ax.add_patch(box)
    if subtitle:
        ax.text(x + w / 2, y + h * 0.65, title, ha="center", va="center", fontsize=title_size, fontweight="bold", color=title_color)
        ax.text(x + w / 2, y + h * 0.32, subtitle, ha="center", va="center", fontsize=sub_size, color=text_color, multialignment="center")
    else:
        ax.text(x + w / 2, y + h * 0.5, title, ha="center", va="center", fontsize=title_size, fontweight="bold", color=title_color, multialignment="center")

def draw_arrow(ax, x1, y1, x2, y2, color=SECONDARY, lw=1.8, label=None, label_pos=0.5, label_offset=(0, 0.02), label_size=8):
    """Draw a styled directional arrow between two points."""
    arrow = FancyArrowPatch((x1, y1), (x2, y2),
                            arrowstyle="->,head_length=5,head_width=3.5",
                            color=color, linewidth=lw, mutation_scale=12)
    ax.add_patch(arrow)
    if label:
        lx = x1 + (x2 - x1) * label_pos + label_offset[0]
        ly = y1 + (y2 - y1) * label_pos + label_offset[1]
        ax.text(lx, ly, label, ha="center", va="center", fontsize=label_size, color=color, fontweight="semibold",
                bbox=dict(boxstyle="square,pad=0.15", fc="white", ec="none", alpha=0.85))

# ==============================================================================
# FIG 1: System Block Diagram
# ==============================================================================
def gen_fig1():
    fig, ax = plt.subplots(figsize=(12, 7.5))
    ax.set_xlim(0, 1.2)
    ax.set_ylim(0, 1.0)
    ax.axis("off")

    # Title
    ax.text(0.6, 0.96, "Figure 1.1: City-Wide ANPR System Architecture (Block Diagram)",
            ha="center", va="center", fontsize=13, fontweight="bold", color=PRIMARY)

    # 1. Real Path Group
    rect_real = FancyBboxPatch((0.03, 0.52), 0.33, 0.38, boxstyle="round,pad=0.02,rounding_size=0.03",
                               facecolor="#EBF3FA", edgecolor=SECONDARY, linewidth=1.5, linestyle="--")
    ax.add_patch(rect_real)
    ax.text(0.195, 0.88, "REAL PERCEPTION PATHWAY", ha="center", va="center", fontsize=10, fontweight="bold", color=SECONDARY)
    draw_box(ax, 0.05, 0.74, 0.29, 0.10, "Video & Photo Feeds", "Traffic cameras (76 frames, 20 seqs)\nHeld-out test photos (167 items)", bg="#FFFFFF", border=SECONDARY)
    draw_box(ax, 0.05, 0.59, 0.29, 0.11, "YOLOv8s + ByteTrack + OCR", "Plate detection (conf ≥ 0.25)\nByteTrack (persist=True)\nCCT-s-v2 ONNX fine-tuned OCR", bg="#FFFFFF", border=SECONDARY)
    draw_arrow(ax, 0.195, 0.74, 0.195, 0.70)

    # 2. Simulated Path Group
    rect_sim = FancyBboxPatch((0.03, 0.08), 0.33, 0.38, boxstyle="round,pad=0.02,rounding_size=0.03",
                              facecolor="#EAF6EC", edgecolor=ACCENT, linewidth=1.5, linestyle="--")
    ax.add_patch(rect_sim)
    ax.text(0.195, 0.44, "SIMULATED CITY PATHWAY", ha="center", va="center", fontsize=10, fontweight="bold", color=ACCENT)
    draw_box(ax, 0.05, 0.30, 0.29, 0.10, "OpenStreetMap Road Graph", "Bangalore network (r = 5 km)\n40 camera nodes (≥300m spacing)", bg="#FFFFFF", border=ACCENT)
    draw_box(ax, 0.05, 0.15, 0.29, 0.11, "Traffic Simulator & Sensor Noise", "5,000 vehicles, 31,244 events\n5% miss rate, 8% confusable noise\nInjected clones (5), Blacklist (10)", bg="#FFFFFF", border=ACCENT)
    draw_arrow(ax, 0.195, 0.30, 0.195, 0.26)

    # 3. Central Persistence
    draw_box(ax, 0.43, 0.33, 0.26, 0.36, "SQLite Database (Shared)", "URI: file:city_anpr.db?mode=ro\nEvents tagged 'sim' (31,244)\nor 'video' (20 events)\n41 cameras, blacklist, trajectories", bg="#FFF8E7", border=HIGHLIGHT, lw=2.0)
    draw_arrow(ax, 0.34, 0.645, 0.43, 0.55, color=SECONDARY, label="source='video'")
    draw_arrow(ax, 0.34, 0.205, 0.43, 0.45, color=ACCENT, label="source='sim'")

    # 4. Analytics & Surveillance Engines
    draw_box(ax, 0.75, 0.68, 0.40, 0.18, "Trajectory Reconstruction Engine", "Fuzzy Plate Matcher (canonical partition)\nWeighted Levenshtein (cost 0.3)\nSpeed validation (>120 km/h = CLONE)\nAvg query latency: 15.82 ms (F1: 97.91%)", bg="#FFFFFF", border=PRIMARY)
    draw_box(ax, 0.75, 0.45, 0.40, 0.18, "Traffic Analytics Engine", "Speed, density, bottleneck congestion\nOrigin-Destination (OD) matrix (64 zones)\nBusiest cameras & segment density", bg="#FFFFFF", border=PRIMARY)
    draw_box(ax, 0.75, 0.22, 0.40, 0.18, "Real-Time Surveillance Alert Engine", "Blacklist matching (P: 100%, R: 93.6%)\nCloned plate detection (100%, 5/5)\nRestricted curfew zones, overspeeding\nThroughput: 1,918 sightings/sec", bg="#FFFFFF", border=PRIMARY)

    draw_arrow(ax, 0.69, 0.58, 0.75, 0.77, color=PRIMARY)
    draw_arrow(ax, 0.69, 0.51, 0.75, 0.54, color=PRIMARY)
    draw_arrow(ax, 0.69, 0.44, 0.75, 0.31, color=PRIMARY)

    # 5. Presentation Layer
    rect_pres = FancyBboxPatch((0.43, 0.05), 0.72, 0.12, boxstyle="round,pad=0.015,rounding_size=0.02",
                               facecolor="#F5EEF8", edgecolor="#8E44AD", linewidth=1.5)
    ax.add_patch(rect_pres)
    ax.text(0.79, 0.12, "FastAPI Application Server & Interactive Web Dashboard", ha="center", va="center", fontsize=10, fontweight="bold", color="#8E44AD")
    ax.text(0.79, 0.075, "REST APIs (/api/trajectory, /api/analytics, /api/alerts) + WebSocket (/ws/live) -> 6 Dashboard Tabs", ha="center", va="center", fontsize=8.5, color=TEXT_DARK)
    draw_arrow(ax, 0.95, 0.22, 0.95, 0.17, color="#8E44AD")

    out = assets_dir / "fig_system_block.png"
    plt.savefig(out)
    plt.close()
    print(f"Generated: {out.name}")

# ==============================================================================
# FIG 2: Data Flow Diagram
# ==============================================================================
def gen_fig2():
    fig, ax = plt.subplots(figsize=(11, 7))
    ax.set_xlim(0, 1.1)
    ax.set_ylim(0, 1.0)
    ax.axis("off")

    ax.text(0.55, 0.96, "Figure 1.2: End-to-End System Data Flow Diagram (DFD)",
            ha="center", va="center", fontsize=13, fontweight="bold", color=PRIMARY)

    # External Entities
    draw_box(ax, 0.05, 0.78, 0.22, 0.10, "External Inputs", "CCTV Camera Streams\nOSM Street Network Graph", bg="#F2F4F4", border="#7F8C8D")
    draw_box(ax, 0.83, 0.78, 0.22, 0.10, "End Users / Operators", "Traffic Management Centre\nSurveillance Officers", bg="#F2F4F4", border="#7F8C8D")

    # Processes
    draw_box(ax, 0.05, 0.52, 0.22, 0.13, "Process 1.0\nPerception & Ingestion", "YOLOv8s BBox Detection\nCCT-s-v2 ONNX OCR\nByteTrack Association", bg="#EBF5FB", border="#2980B9")
    draw_box(ax, 0.44, 0.52, 0.22, 0.13, "Process 2.0\nConsensus & Validation", "Character-Position Voting\nQuality Score Evaluation\nREVIEW Flag Assignment", bg="#EBF5FB", border="#2980B9")
    draw_box(ax, 0.44, 0.22, 0.22, 0.13, "Process 3.0\nSpatial Storage Layer", "SQLite Event Ingestion\nSource tagging ('sim'/'video')\nIndex Maintenance", bg="#FEF9E7", border="#F39C12")
    draw_box(ax, 0.05, 0.22, 0.22, 0.13, "Process 4.0\nTraffic Analytics", "Rolling Window Flow Rate\nCongestion Hotspot Detection\nOD Matrix Aggregation", bg="#E8F8F5", border="#1ABC9C")
    draw_box(ax, 0.83, 0.52, 0.22, 0.13, "Process 5.0\nTrajectory Matching", "Canonical 3-Partition Index\nWeighted Levenshtein Search\nDijkstra Road Routing", bg="#F4ECF7", border="#8E44AD")
    draw_box(ax, 0.83, 0.22, 0.22, 0.13, "Process 6.0\nSurveillance Alerting", "Blacklist Surveillance\nSpeed Feasibility (>120 km/h)\nCurfew Zone Enforcement", bg="#FDEDEC", border="#C0392B")

    # Arrows
    draw_arrow(ax, 0.16, 0.78, 0.16, 0.65, label="Raw Frames")
    draw_arrow(ax, 0.27, 0.585, 0.44, 0.585, label="Raw Reads")
    draw_arrow(ax, 0.55, 0.52, 0.55, 0.35, label="Voted Events")
    draw_arrow(ax, 0.44, 0.285, 0.27, 0.285, label="Aggregated Events")
    draw_arrow(ax, 0.66, 0.31, 0.83, 0.55, label="Plate Sightings")
    draw_arrow(ax, 0.66, 0.26, 0.83, 0.26, label="Live Sightings")
    draw_arrow(ax, 0.94, 0.52, 0.94, 0.35, label="Trip Metadata")
    draw_arrow(ax, 0.94, 0.65, 0.94, 0.78, label="Trajectories")
    draw_arrow(ax, 0.83, 0.83, 0.27, 0.83, label="Control Parameters", label_pos=0.5)

    out = assets_dir / "fig_data_flow.png"
    plt.savefig(out)
    plt.close()
    print(f"Generated: {out.name}")

# ==============================================================================
# FIG 3: Perception Pipeline Flowchart
# ==============================================================================
def gen_fig3():
    fig, ax = plt.subplots(figsize=(10, 8))
    ax.set_xlim(0, 1.0)
    ax.set_ylim(0, 1.0)
    ax.axis("off")

    ax.text(0.5, 0.97, "Figure 3.1: Video Perception & Plate Recognition Pipeline",
            ha="center", va="center", fontsize=13, fontweight="bold", color=PRIMARY)

    steps = [
        ("1. Input Video Frame", "1280x720 / 1280x960 resolution\nRGB color representation", 0.87, "#EAECEE", "#2C3E50"),
        ("2. YOLOv8s Plate Detection", "Custom fine-tuned weights (models/plate_detector.pt)\nConfidence threshold conf ≥ 0.25", 0.72, "#EBF5FB", "#2980B9"),
        ("3. Bounding Box Boundary Expansion", "Expand plate bbox by +5% on all four edges\nPrevents character clipping during perspective skew", 0.57, "#E8F8F5", "#16A085"),
        ("4. ByteTrack Multi-Frame Association", "Track ID persistence across consecutive frames (persist=True)\nMaintains vehicle identities through brief occlusions", 0.42, "#FEF9E7", "#D4AC0D"),
        ("5. CCT-s-v2 ONNX Optical Character Recognition", "fast-plate-ocr compact convolutional transformer\nPredicts character sequence + softmax confidence scores", 0.27, "#F4ECF7", "#8E44AD"),
        ("6. Multi-Frame Plate Voting & Consensus", "Character-position weighted consensus voting\nOutputs final plate, confidence, vote margin, and REVIEW flag", 0.12, "#EAFAF1", "#27AE60"),
    ]

    for title, desc, y, bg, border in steps:
        draw_box(ax, 0.18, y, 0.64, 0.10, title, desc, bg=bg, border=border, lw=1.5, title_color=border, title_size=10, sub_size=8.5)

    for i in range(len(steps) - 1):
        y1 = steps[i][2]
        y2 = steps[i+1][2] + 0.10
        draw_arrow(ax, 0.5, y1, 0.5, y2, color=PRIMARY, lw=1.8)

    out = assets_dir / "fig_perception_pipeline.png"
    plt.savefig(out)
    plt.close()
    print(f"Generated: {out.name}")

# ==============================================================================
# FIG 4: Plate Voting and REVIEW Decision Flowchart
# ==============================================================================
def gen_fig4():
    fig, ax = plt.subplots(figsize=(11, 7.5))
    ax.set_xlim(0, 1.1)
    ax.set_ylim(0, 1.0)
    ax.axis("off")

    ax.text(0.55, 0.96, "Figure 3.2: Multi-Frame Consensus Voting and Quality Assurance Logic",
            ha="center", va="center", fontsize=13, fontweight="bold", color=PRIMARY)

    draw_box(ax, 0.38, 0.83, 0.34, 0.08, "Track Frame Sequence", "Accumulated N readings: (plate_i, conf_i)", bg="#EAECEE", border="#34495E")
    draw_box(ax, 0.42, 0.68, 0.26, 0.08, "Check Frame Count", "Is sequence length N == 1?", bg="#FEF9E7", border="#D4AC0D")
    draw_arrow(ax, 0.55, 0.83, 0.55, 0.76)

    # Branch: Single frame
    draw_box(ax, 0.08, 0.53, 0.28, 0.09, "Single-Frame Pass-Through", "Voted plate = plate_0\nVote margin = 1.00 (trivial)", bg="#FADBD8", border=WARN)
    draw_arrow(ax, 0.42, 0.72, 0.22, 0.62, color=WARN, label="Yes (N = 1)")

    # Branch: Multi-frame
    draw_box(ax, 0.40, 0.52, 0.30, 0.10, "Positional Weighted Voting", "Sum confidences per character slot\nw_pos = Σ conf_i where char = c\nWinner = argmax character sequence", bg="#E8F8F5", border=ACCENT)
    draw_arrow(ax, 0.55, 0.68, 0.55, 0.62, color=ACCENT, label="No (N > 1)")

    draw_box(ax, 0.74, 0.52, 0.30, 0.10, "Compute Vote Margin", "Margin = (Winner Score - RunnerUp Score) / Winner\nMeasures consensus decisiveness (0.0 to 1.0)", bg="#EBF5FB", border=SECONDARY)
    draw_arrow(ax, 0.70, 0.57, 0.74, 0.57)

    # Decision Box: Quality Threshold Check
    draw_box(ax, 0.34, 0.30, 0.42, 0.12, "Quality Assurance Evaluation", "REVIEW_CONFIDENCE_THRESHOLD = 0.80\nCondition: (OCR Conf < 0.80) OR (Vote Margin < 0.80)?", bg="#FFF8E7", border=HIGHLIGHT, lw=2.0)
    draw_arrow(ax, 0.22, 0.53, 0.42, 0.42, color=PRIMARY)
    draw_arrow(ax, 0.89, 0.52, 0.68, 0.42, color=PRIMARY)

    # Outcomes
    draw_box(ax, 0.14, 0.10, 0.34, 0.11, "Status: 'REVIEW' (Flagged)", "Plate requires human operator verification\nHighlighted in dashboard table with amber pill\n(2 of 20 video test events flagged)", bg="#FADBD8", border=WARN, lw=2.0)
    draw_box(ax, 0.62, 0.10, 0.34, 0.11, "Status: 'OK' (Accepted)", "High-confidence automatic acceptance\nDirectly ingested into city analytics stream\n(18 of 20 video test events accepted)", bg="#D5F5E3", border=ACCENT, lw=2.0)

    draw_arrow(ax, 0.45, 0.30, 0.31, 0.21, color=WARN, label="YES (< 0.80)")
    draw_arrow(ax, 0.65, 0.30, 0.79, 0.21, color=ACCENT, label="NO (≥ 0.80)")

    out = assets_dir / "fig_voting_review.png"
    plt.savefig(out)
    plt.close()
    print(f"Generated: {out.name}")

# ==============================================================================
# FIG 5: Simulator Flowchart
# ==============================================================================
def gen_fig5():
    fig, ax = plt.subplots(figsize=(10.5, 8))
    ax.set_xlim(0, 1.0)
    ax.set_ylim(0, 1.0)
    ax.axis("off")

    ax.text(0.5, 0.97, "Figure 3.3: City-Scale ANPR Simulator Architecture & Event Generation",
            ha="center", va="center", fontsize=13, fontweight="bold", color=PRIMARY)

    steps = [
        ("1. Urban Graph Extraction (OSMnx)", "Download drivable street network for Bangalore (radius 5 km around centre)\nConstruct NetworkX directed MultiDiGraph G with travel times per edge", 0.85, "#EBF5FB", "#2980B9"),
        ("2. Camera Node Deployment", "Place 40 simulated ANPR cameras along high-traffic arterial intersections\nEnforce strict Euclidean spacing constraint: distance(c_i, c_j) ≥ 300 meters", 0.70, "#E8F8F5", "#16A085"),
        ("3. All-Pairs Camera Route Precomputation", "Execute single-source Dijkstra algorithms between all 40 camera nodes\nSerialize shortest path distance, travel time, and geometry to camera_paths.pkl", 0.55, "#FEF9E7", "#D4AC0D"),
        ("4. Synthetic Traffic Fleet Generation", "Generate 5,000 distinct vehicles (45% cars, 35% bikes, 10% buses, 10% trucks)\nAssign realistic trips across morning/evening peak hours (dwell: 15–90 min)", 0.40, "#F4ECF7", "#8E44AD"),
        ("5. Surveillance Scenario Injection", "Sample 10 real fleet plates for Blacklist watchlist\nInject 5 cloned plate teleportation pairs (implied velocity > 120 km/h)\nDesignate CAM_001–003 as restricted truck curfew zones (22:00–06:00)", 0.25, "#FDEDEC", "#C0392B"),
        ("6. Sensor Noise Model & Serialization", "Apply 5% camera miss rate and 8% optical character confusion noise\nPersist 31,244 noisy sightings (events.csv) and ground truth (ground_truth.csv)", 0.10, "#EAFAF1", "#27AE60"),
    ]

    for title, desc, y, bg, border in steps:
        draw_box(ax, 0.14, y, 0.72, 0.105, title, desc, bg=bg, border=border, lw=1.5, title_color=border, title_size=10, sub_size=8.5)

    for i in range(len(steps) - 1):
        y1 = steps[i][2]
        y2 = steps[i+1][2] + 0.105
        draw_arrow(ax, 0.5, y1, 0.5, y2, color=PRIMARY, lw=1.8)

    out = assets_dir / "fig_simulator.png"
    plt.savefig(out)
    plt.close()
    print(f"Generated: {out.name}")

# ==============================================================================
# FIG 6: ER Diagram (SQLite Database Schema)
# ==============================================================================
def gen_fig6():
    fig, ax = plt.subplots(figsize=(12, 8))
    ax.set_xlim(0, 1.2)
    ax.set_ylim(0, 1.0)
    ax.axis("off")

    ax.text(0.6, 0.97, "Figure 3.4: Relational Entity-Relationship Diagram (SQLite Database Schema)",
            ha="center", va="center", fontsize=13, fontweight="bold", color=PRIMARY)

    # Table 1: events
    ev_text = (
        "id: INTEGER [PK]\n"
        "plate: VARCHAR(20) [IDX]\n"
        "camera_id: VARCHAR(50) [FK]\n"
        "timestamp: DATETIME [IDX]\n"
        "speed_kmh: FLOAT\n"
        "heading_degrees: FLOAT\n"
        "lane: INTEGER\n"
        "ocr_confidence: FLOAT\n"
        "source: VARCHAR(20) ['sim'|'video']\n"
        "track_id: INTEGER\n"
        "n_frames: INTEGER\n"
        "vote_margin: FLOAT\n"
        "best_crop_path: VARCHAR(255)"
    )
    draw_box(ax, 0.40, 0.38, 0.38, 0.42, "events (31,264 rows)", ev_text, bg="#FFF8E7", border="#D4AC0D", lw=1.8, sub_size=8.0)

    # Table 2: cameras
    cam_text = (
        "camera_id: VARCHAR(50) [PK]\n"
        "name: VARCHAR(255)\n"
        "lat: FLOAT\n"
        "lon: FLOAT\n"
        "node_id: BIGINT [OSM node]"
    )
    draw_box(ax, 0.04, 0.58, 0.30, 0.22, "cameras (41 rows)", cam_text, bg="#EBF5FB", border="#2980B9", lw=1.8, sub_size=8.0)

    # Table 3: blacklist
    bl_text = (
        "plate: VARCHAR(20) [PK]\n"
        "reason: VARCHAR(255)\n"
        "added_at: DATETIME"
    )
    draw_box(ax, 0.04, 0.28, 0.30, 0.18, "blacklist (10 rows)", bl_text, bg="#FDEDEC", border="#C0392B", lw=1.8, sub_size=8.0)

    # Table 4: alerts
    al_text = (
        "id: INTEGER [PK]\n"
        "alert_type: VARCHAR(50)\n"
        "plate: VARCHAR(20)\n"
        "camera_id: VARCHAR(50)\n"
        "timestamp: DATETIME\n"
        "details: JSON\n"
        "created_at: DATETIME\n"
        "severity: VARCHAR(20)"
    )
    draw_box(ax, 0.84, 0.50, 0.32, 0.30, "alerts (44 rows)", al_text, bg="#FDEDEC", border="#C0392B", lw=1.8, sub_size=8.0)

    # Table 5: trajectories
    tr_text = (
        "id: INTEGER [PK]\n"
        "plate: VARCHAR(20)\n"
        "start_time: DATETIME\n"
        "end_time: DATETIME\n"
        "duration_seconds: FLOAT\n"
        "total_distance_meters: FLOAT\n"
        "avg_speed_kmh: FLOAT\n"
        "num_sightings: INTEGER\n"
        "camera_sequence: JSON\n"
        "coordinates: JSON"
    )
    draw_box(ax, 0.84, 0.12, 0.32, 0.32, "trajectories (on-demand)", tr_text, bg="#F4ECF7", border="#8E44AD", lw=1.5, sub_size=7.5)

    # Table 6: analytics summary tables
    an_text = (
        "camera_window_stats (2,795 rows)\n"
        "congestion (463 rows)\n"
        "route_density (3,194 rows)\n"
        "od_matrix (64 rows)"
    )
    draw_box(ax, 0.40, 0.12, 0.38, 0.18, "Materialized Analytics Tables", an_text, bg="#E8F8F5", border="#16A085", lw=1.5, sub_size=8.0)

    # Relationships
    draw_arrow(ax, 0.34, 0.69, 0.40, 0.69, color="#2980B9", label="1 : N", label_offset=(0, 0.02))
    draw_arrow(ax, 0.78, 0.65, 0.84, 0.65, color="#C0392B", label="triggers", label_offset=(0, 0.02))
    draw_arrow(ax, 0.59, 0.38, 0.59, 0.30, color="#16A085", label="aggregates", label_offset=(0.04, 0))
    draw_arrow(ax, 0.78, 0.45, 0.84, 0.28, color="#8E44AD", label="reconstructs", label_offset=(0, 0.02))
    draw_arrow(ax, 0.34, 0.37, 0.40, 0.47, color="#C0392B", label="monitors", label_offset=(0, 0.02))

    out = assets_dir / "fig_er_diagram.png"
    plt.savefig(out)
    plt.close()
    print(f"Generated: {out.name}")

# ==============================================================================
# FIG 7: Trajectory Engine Flowchart
# ==============================================================================
def gen_fig7():
    fig, ax = plt.subplots(figsize=(11, 8))
    ax.set_xlim(0, 1.1)
    ax.set_ylim(0, 1.0)
    ax.axis("off")

    ax.text(0.55, 0.97, "Figure 3.5: Cross-Camera Trajectory Reconstruction & Fuzzy Search Engine",
            ha="center", va="center", fontsize=13, fontweight="bold", color=PRIMARY)

    draw_box(ax, 0.38, 0.84, 0.34, 0.08, "Plate Query Input", "Operator enters target plate string (e.g., 'TN11YD7305')", bg="#EAECEE", border="#34495E")
    draw_box(ax, 0.35, 0.70, 0.40, 0.09, "Fast Canonical Candidate Pruning", "Translate query: CANONICAL_MAP (O->0, B->8, I->1, etc.)\nQuery 3-partition canonical index: O(1) candidate lookup", bg="#EBF5FB", border="#2980B9")
    draw_arrow(ax, 0.55, 0.84, 0.55, 0.79)

    draw_box(ax, 0.35, 0.55, 0.40, 0.10, "Weighted Levenshtein Similarity", "Compute distance d(q, p): confusable pairs cost 0.3, others 1.0\nFilter candidates: distance ≤ 1.0 -> Collect sightings", bg="#E8F8F5", border="#16A085")
    draw_arrow(ax, 0.55, 0.70, 0.55, 0.65)

    draw_box(ax, 0.35, 0.39, 0.40, 0.11, "Temporal Filtering & Trip Segmentation", "Filter duplicate reads (<60s at same camera)\nSplit into distinct journeys if inactivity gap > 30 minutes\nSort sightings chronologically: [c_0, c_1, ..., c_k]", bg="#FEF9E7", border="#D4AC0D")
    draw_arrow(ax, 0.55, 0.55, 0.55, 0.50)

    # Speed validation branch
    draw_box(ax, 0.06, 0.20, 0.38, 0.13, "Speed Feasibility & Anomaly Isolation", "Lookup precomputed shortest path distance d(c_i, c_{i+1})\nImplied velocity v = d / (t_{i+1} - t_i)\nIs implied speed > 120 km/h? -> CLONED PLATE ANOMALY!\nSegment trajectory to prevent false teleportation vector", bg="#FDEDEC", border="#C0392B")
    draw_arrow(ax, 0.42, 0.39, 0.25, 0.33, color="#C0392B", label="Feasibility Check")

    draw_box(ax, 0.58, 0.20, 0.46, 0.13, "Topological Graph Reconstruction", "Retrieve cached OpenStreetMap Dijkstra road geometry\nInterpolate intermediate street coordinates\nCalculate total travel distance, duration, and average speed", bg="#F4ECF7", border="#8E44AD")
    draw_arrow(ax, 0.68, 0.39, 0.81, 0.33, color="#8E44AD", label="Feasible Hops")

    draw_box(ax, 0.32, 0.04, 0.46, 0.09, "JSON Response & GeoJSON Polyline", "Deliver reconstructed trajectory to Leaflet dashboard\nExport journey sightings to CSV with formula-injection escaping", bg="#EAFAF1", border="#27AE60")
    draw_arrow(ax, 0.25, 0.20, 0.45, 0.13, color=PRIMARY)
    draw_arrow(ax, 0.81, 0.20, 0.65, 0.13, color=PRIMARY)

    out = assets_dir / "fig_trajectory_engine.png"
    plt.savefig(out)
    plt.close()
    print(f"Generated: {out.name}")

# ==============================================================================
# FIG 8: Alert Engine Flowchart
# ==============================================================================
def gen_fig8():
    fig, ax = plt.subplots(figsize=(11, 7.5))
    ax.set_xlim(0, 1.1)
    ax.set_ylim(0, 1.0)
    ax.axis("off")

    ax.text(0.55, 0.96, "Figure 3.6: Multi-Rule Surveillance Alert Engine Evaluation Pipeline",
            ha="center", va="center", fontsize=13, fontweight="bold", color=PRIMARY)

    draw_box(ax, 0.35, 0.83, 0.40, 0.08, "Incoming Vehicle Sighting Event", "Tuple: (plate, camera_id, timestamp, speed, vehicle_type)", bg="#EAECEE", border="#34495E")

    rules = [
        ("Rule 1: Blacklist", "Exact match -> Severity HIGH\nFuzzy confusable (d ≤ 0.6) -> MEDIUM", 0.06, "#FDEDEC", "#C0392B"),
        ("Rule 2: Cloned Plate", "Consecutive sightings\nImplied road speed > 120 km/h -> HIGH", 0.32, "#FDEDEC", "#C0392B"),
        ("Rule 3: Restricted Zone", "Heavy truck at CAM_001..003\nTime 22:00–06:00 -> MEDIUM", 0.58, "#FEF9E7", "#D4AC0D"),
        ("Rule 4: Overspeed", "Radar / lane speed > 80 km/h\nExcess over limit -> LOW", 0.84, "#EBF5FB", "#2980B9"),
    ]

    for title, desc, x, bg, border in rules:
        draw_box(ax, x, 0.50, 0.22, 0.22, title, desc, bg=bg, border=border, lw=1.5, title_color=border, title_size=9.5, sub_size=8.0)
        draw_arrow(ax, 0.55, 0.83, x + 0.11, 0.72, color=PRIMARY)

    draw_box(ax, 0.25, 0.23, 0.60, 0.14, "Sliding Window Incident De-Duplication", "De-duplication window: 10 minutes per (rule_type, plate, camera_id)\nPrevents operator notification fatigue from repeated sensor triggers\n(Suppresses redundant raw hits while maintaining incident coverage)", bg="#FFF8E7", border=HIGHLIGHT, lw=2.0)

    for title, desc, x, bg, border in rules:
        draw_arrow(ax, x + 0.11, 0.50, 0.55, 0.37, color=PRIMARY)

    draw_box(ax, 0.10, 0.05, 0.42, 0.10, "Persistence: 'alerts' Table", "Store incident record with JSON metadata\nQueryable via GET /api/alerts", bg="#E8F8F5", border=ACCENT)
    draw_box(ax, 0.58, 0.05, 0.42, 0.10, "Real-Time Push: WebSocket /ws/live", "Broadcast live JSON alert payload to dashboard\nTrigger audio chime and navbar badge counter", bg="#F4ECF7", border="#8E44AD")

    draw_arrow(ax, 0.45, 0.23, 0.31, 0.15, color=ACCENT)
    draw_arrow(ax, 0.65, 0.23, 0.79, 0.15, color="#8E44AD")

    out = assets_dir / "fig_alert_engine.png"
    plt.savefig(out)
    plt.close()
    print(f"Generated: {out.name}")

# ==============================================================================
# FIG 9: API and WebSocket Sequence Diagram
# ==============================================================================
def gen_fig9():
    fig, ax = plt.subplots(figsize=(11, 7.5))
    ax.set_xlim(0, 1.1)
    ax.set_ylim(0, 1.0)
    ax.axis("off")

    ax.text(0.55, 0.96, "Figure 3.7: REST API and WebSocket Surveillance Streaming Sequence",
            ha="center", va="center", fontsize=13, fontweight="bold", color=PRIMARY)

    # Lifelines
    actors = [
        ("Web Browser Client", 0.10),
        ("FastAPI Gateway", 0.35),
        ("SQLite Database", 0.60),
        ("AlertEngine", 0.82),
        ("Graph Cache", 1.00),
    ]

    for name, x in actors:
        draw_box(ax, x - 0.08, 0.86, 0.16, 0.06, name, bg="#EAECEE", border="#34495E", title_size=9)
        ax.plot([x, x], [0.10, 0.86], linestyle="--", color="#BDC3C7", linewidth=1.2)

    # Interactions
    interactions = [
        (0.10, 0.35, "1. GET /api/analytics/overview", 0.78, SECONDARY),
        (0.35, 0.60, "2. Query camera_window_stats", 0.73, PRIMARY),
        (0.60, 0.35, "3. Return KPI counts & hourly flow", 0.68, ACCENT),
        (0.35, 0.10, "4. JSON Response (KPI Cards)", 0.63, SECONDARY),

        (0.10, 0.35, "5. GET /api/trajectory/TN11YD7305", 0.55, SECONDARY),
        (0.35, 0.60, "6. Fuzzy search events table", 0.50, PRIMARY),
        (0.60, 0.35, "7. 17 raw sightings returned", 0.45, ACCENT),
        (0.35, 1.00, "8. Lookup precomputed Dijkstra paths", 0.40, "#8E44AD"),
        (1.00, 0.35, "9. Road coordinates & travel times", 0.35, "#8E44AD"),
        (0.35, 0.10, "10. Trajectory JSON + GeoJSON polyline", 0.30, SECONDARY),

        (0.10, 0.35, "11. WebSocket Connect (/ws/live?speed=200)", 0.22, WARN),
        (0.35, 0.82, "12. Stream simulated events", 0.17, WARN),
        (0.82, 0.35, "13. Push alert payload (Blacklist/Clone)", 0.13, WARN),
        (0.35, 0.10, "14. Live alert push message (JSON)", 0.09, WARN),
    ]

    for x1, x2, msg, y, col in interactions:
        draw_arrow(ax, x1, y, x2, y, color=col, lw=1.3, label=msg, label_size=7.5, label_offset=(0, 0.015))

    out = assets_dir / "fig_api_sequence.png"
    plt.savefig(out)
    plt.close()
    print(f"Generated: {out.name}")

# ==============================================================================
# FIG 10: Dashboard Tab Layout
# ==============================================================================
def gen_fig10():
    fig, ax = plt.subplots(figsize=(11, 7.5))
    ax.set_xlim(0, 1.1)
    ax.set_ylim(0, 1.0)
    ax.axis("off")

    ax.text(0.55, 0.96, "Figure 3.8: Unified Traffic Intelligence Dashboard Interface Layout",
            ha="center", va="center", fontsize=13, fontweight="bold", color=PRIMARY)

    # Shell window
    shell = FancyBboxPatch((0.04, 0.05), 1.02, 0.87, boxstyle="round,pad=0.01,rounding_size=0.02",
                           facecolor="#F8F9FA", edgecolor="#BDC3C7", linewidth=1.5)
    ax.add_patch(shell)

    # Top Navigation Bar
    navbar = FancyBboxPatch((0.05, 0.83), 1.00, 0.07, boxstyle="round,pad=0.005,rounding_size=0.01",
                            facecolor=PRIMARY, edgecolor="none")
    ax.add_patch(navbar)
    ax.text(0.12, 0.865, "CITY ANPR", color="#FFFFFF", fontsize=11, fontweight="bold")
    ax.text(0.21, 0.865, "LIVE INTELLIGENCE", color=HIGHLIGHT, fontsize=8, fontweight="bold")

    tabs = ["1. Overview", "2. Trajectory", "3. Heatmap", "4. Alerts (44)", "5. Blacklist", "6. Plate Reader"]
    tx_start = 0.33
    for i, t in enumerate(tabs):
        active = (i == 0)
        t_bg = "#336699" if active else "none"
        t_border = "#FFFFFF" if active else "none"
        tab_box = FancyBboxPatch((tx_start + i * 0.115, 0.84), 0.11, 0.05, boxstyle="round,pad=0.005,rounding_size=0.01",
                                facecolor=t_bg, edgecolor=t_border, linewidth=1.0)
        ax.add_patch(tab_box)
        ax.text(tx_start + i * 0.115 + 0.055, 0.865, t, color="#FFFFFF", fontsize=7.5, ha="center", va="center", fontweight="bold" if active else "normal")

    # Body Split: Tab 1 (Overview) Left + Tab 2 (Trajectory) Right
    draw_box(ax, 0.06, 0.70, 0.22, 0.10, "Total Sightings", "31,264 Events\n(31,244 sim + 20 video)", bg="#FFFFFF", border="#2980B9", title_color="#2980B9")
    draw_box(ax, 0.30, 0.70, 0.22, 0.10, "Active Cameras", "41 Cameras\n(40 network + 1 demo)", bg="#FFFFFF", border="#16A085", title_color="#16A085")
    draw_box(ax, 0.54, 0.70, 0.22, 0.10, "Unique Fleet", "4,296 Vehicles\n(10,729 distinct plates)", bg="#FFFFFF", border="#8E44AD", title_color="#8E44AD")
    draw_box(ax, 0.78, 0.70, 0.25, 0.10, "Active Alerts", "44 Total Incidents\n(35 Blacklist, 5 Clones)", bg="#FFFFFF", border=WARN, title_color=WARN)

    # Main Interactive Map Canvas
    map_box = FancyBboxPatch((0.06, 0.18), 0.58, 0.49, boxstyle="round,pad=0.01,rounding_size=0.01",
                             facecolor="#EBF5FB", edgecolor="#2980B9", linewidth=1.5)
    ax.add_patch(map_box)
    ax.text(0.35, 0.45, "Interactive Leaflet.js City Map Canvas\n(40 Camera Pins, Heatmap Layer, Trajectory Polyline)",
            ha="center", va="center", fontsize=9.5, color=PRIMARY, fontweight="semibold")

    # Side Panel: Live Alert Feed & Search
    side_box = FancyBboxPatch((0.66, 0.18), 0.37, 0.49, boxstyle="round,pad=0.01,rounding_size=0.01",
                              facecolor="#FFFFFF", edgecolor="#BDC3C7", linewidth=1.5)
    ax.add_patch(side_box)
    ax.text(0.845, 0.63, "Surveillance Side Panel", ha="center", va="center", fontsize=10, fontweight="bold", color=PRIMARY)
    ax.text(0.845, 0.52, "[Plate Search Input]\n'TN11YD7305' [Search]\nFuzzy match distance ≤ 1.0\n17 sightings found", ha="center", va="center", fontsize=8.5, color=TEXT_DARK)
    ax.text(0.845, 0.33, "[Live Alert Cards Feed]\n* HIGH: Cloned Plate (352 km/h)\n* HIGH: Blacklist Match (AP05JT...)\n* MEDIUM: Truck Curfew Zone\nAudio chime & 10m de-duplication", ha="center", va="center", fontsize=8.0, color="#C0392B")

    # Status Bar
    ax.text(0.55, 0.08, "Status: Operational | WebSocket Connected | Simulated Clock: 2026-10-01 18:45:00 | SQLite: Read-Only Mode", ha="center", va="center", fontsize=8, color="#7F8C8D")

    out = assets_dir / "fig_dashboard_layout.png"
    plt.savefig(out)
    plt.close()
    print(f"Generated: {out.name}")

# ==============================================================================
# FIG 11: Counting Pipeline Flowchart
# ==============================================================================
def gen_fig11():
    fig, ax = plt.subplots(figsize=(10.5, 8))
    ax.set_xlim(0, 1.0)
    ax.set_ylim(0, 1.0)
    ax.axis("off")

    ax.text(0.5, 0.97, "Figure 3.9: AI City Challenge Vehicle Counting & Trajectory Assignment",
            ha="center", va="center", fontsize=13, fontweight="bold", color=PRIMARY)

    steps = [
        ("1. Input Traffic Video (Camera 5)", "AI City Challenge 2021 Track 1 example clip\n1280x960 resolution, 10.0 fps, 60 seconds (600 frames total)", 0.85, "#EAECEE", "#2C3E50"),
        ("2. YOLOv8s Multi-Class Vehicle Detection", "Pretrained COCO model (yolov8s.pt, imgsz=960, conf=0.25)\nClasses tracked: Car (2), Bus (5), Truck (7) -> 342 raw track IDs", 0.70, "#EBF5FB", "#2980B9"),
        ("3. Bottom-Center Point & ROI Polygon Test", "Extract vehicle road contact point: ((x1+x2)/2, y2)\nFilter using cv2.pointPolygonTest(roi) ≥ 0 -> 162 tracks in ROI", 0.55, "#E8F8F5", "#16A085"),
        ("4. Kinematic & Persistence Filtering", "Drop tracks with < 10 in-ROI frames (117 long enough)\nDrop tracks with displacement < 60 px (103 moving vehicles)", 0.40, "#FEF9E7", "#D4AC0D"),
        ("5. Start/End Centroid & Distance Assignment", "start_pt = mean(first 3 in-ROI points), end_pt = mean(last 3)\nScore = dist(start, mov_start) + dist(end, mov_end)\nAssign movement with min score (Score ≤ 300)", 0.25, "#F4ECF7", "#8E44AD"),
        ("6. Exit Frame Counting & Video Annotation", "Count frame = last in-ROI frame (exit point)\nv1 visual: 19 assigned (F1: 24.3%) | v2 calibrated: 54 assigned (F1: 65.1%)\nRender on-screen badges (15 frames) + counts_pred.csv", 0.10, "#EAFAF1", "#27AE60"),
    ]

    for title, desc, y, bg, border in steps:
        draw_box(ax, 0.12, y, 0.76, 0.105, title, desc, bg=bg, border=border, lw=1.5, title_color=border, title_size=10, sub_size=8.5)

    for i in range(len(steps) - 1):
        y1 = steps[i][2]
        y2 = steps[i+1][2] + 0.105
        draw_arrow(ax, 0.5, y1, 0.5, y2, color=PRIMARY, lw=1.8)

    out = assets_dir / "fig_counting_pipeline.png"
    plt.savefig(out)
    plt.close()
    print(f"Generated: {out.name}")

# ==============================================================================
# FIG 12: Schematic of Camera 5 ROI and 12 Movement Arrows
# ==============================================================================
def gen_fig12():
    fig, ax = plt.subplots(figsize=(10, 7.5))
    ax.set_xlim(0, 1280)
    ax.set_ylim(960, 0)  # Invert Y to match image coordinate system (0,0 top-left)

    # Road canvas
    ax.set_facecolor("#2C3E50")

    # Draw ROI Polygon
    roi = np.array([[1,277],[450,99],[599,96],[1172,280],[960,955],[0,956]])
    poly = Polygon(roi, closed=True, facecolor="#27AE60", edgecolor="#2ECC71", alpha=0.25, linewidth=2.5, linestyle="--")
    ax.add_patch(poly)

    # Movements data from movements_cam5.json
    movements = {
        "1": {"start":[75,250],"end":[55,375]},
        "2": {"start":[185,215],"end":[345,335]},
        "3": {"start":[240,205],"end":[455,243]},
        "4": {"start":[660,130],"end":[365,180]},
        "5": {"start":[690,130],"end":[488,190]},
        "6": {"start":[688,150],"end":[580,295]},
        "7": {"start":[1075,445],"end":[940,210]},
        "8": {"start":[985,480],"end":[705,320]},
        "9": {"start":[975,545],"end":[530,410]},
        "10": {"start":[95,840],"end":[715,832]},
        "11": {"start":[50,675],"end":[310,485]},
        "12": {"start":[30,590],"end":[240,365]}
    }

    # Draw Movement Arrows
    for m_id, m in movements.items():
        s = m["start"]
        e = m["end"]
        # Draw red arrow
        arrow = FancyArrowPatch((s[0], s[1]), (e[0], e[1]),
                                arrowstyle="->,head_length=8,head_width=5",
                                color="#E74C3C", linewidth=2.2, mutation_scale=15)
        ax.add_patch(arrow)

        # Draw circle at start
        circle = plt.Circle((s[0], s[1]), 8, color="#F39C12", zorder=5)
        ax.add_patch(circle)

        # Label near midpoint
        mx = (s[0] + e[0]) / 2
        my = (s[1] + e[1]) / 2
        ax.text(mx + 12, my - 8, f"M{m_id}", color="#FFFFFF", fontsize=9.5, fontweight="bold",
                bbox=dict(boxstyle="round,pad=0.2", fc="#C0392B", ec="#FFFFFF", lw=1.0, alpha=0.9))

    # Grid & labels
    ax.set_title("Figure 3.10: Schematic Coordinate Map of Camera 5 Region of Interest (ROI) and 12 Directional Movements",
                 fontsize=11, fontweight="bold", pad=15, color=PRIMARY)
    ax.set_xlabel("Horizontal Pixel Coordinate (X, 0 to 1280 px)", fontsize=10)
    ax.set_ylabel("Vertical Pixel Coordinate (Y, 0 to 960 px)", fontsize=10)
    ax.grid(color="#7F8C8D", linestyle=":", linewidth=0.7, alpha=0.5)

    # Custom legend
    from matplotlib.lines import Line2D
    legend_elements = [
        Line2D([0], [0], color="#2ECC71", lw=2.5, linestyle="--", label="Intersection ROI Polygon (Green Boundary)"),
        Line2D([0], [0], color="#E74C3C", lw=2.2, marker=">", label="Directional Movement Vectors (M1 to M12)"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor="#F39C12", markersize=8, label="Movement Ingress Point (Start)"),
    ]
    ax.legend(handles=legend_elements, loc="lower right", facecolor="#1B2631", edgecolor="#BDC3C7", labelcolor="white", fontsize=9)

    out = assets_dir / "fig_cam5_roi_movements.png"
    plt.savefig(out)
    plt.close()
    print(f"Generated: {out.name}")

# ==============================================================================
# FIG 13: Project Folder and Deployment Diagram
# ==============================================================================
def gen_fig13():
    fig, ax = plt.subplots(figsize=(11, 7.5))
    ax.set_xlim(0, 1.1)
    ax.set_ylim(0, 1.0)
    ax.axis("off")

    ax.text(0.55, 0.96, "Figure 3.11: Project Repository Hierarchy and Deployment Architecture",
            ha="center", va="center", fontsize=13, fontweight="bold", color=PRIMARY)

    # Directory Hierarchy Tree (Left Column)
    tree_text = (
        "city-anpr/ [Project Root]\n"
        "├── data/\n"
        "│   ├── city_anpr.db (SQLite, 15.5 MB)\n"
        "│   ├── sim/ (city.graphml, camera_paths.pkl)\n"
        "│   └── processed/ (detector & OCR splits)\n"
        "├── simulator/ (OSM road graph, traffic generator)\n"
        "├── pipeline/ (video_pipeline, voting, plate_reader)\n"
        "├── models/ (plate_detector.pt, plate_ocr/)\n"
        "├── backend/\n"
        "│   ├── api/ (FastAPI main.py routes)\n"
        "│   ├── trajectory/ (fuzzy plate search & router)\n"
        "│   ├── analytics/ (speed, density, OD matrix)\n"
        "│   └── alerts/ (multi-rule surveillance engine)\n"
        "├── frontend/ (index.html, styles.css, app.js)\n"
        "├── counting/ (AICity track, calibrate, evaluate)\n"
        "└── tests/ (14 test suites, 101 unit tests)"
    )
    draw_box(ax, 0.05, 0.08, 0.44, 0.82, "Codebase Directory Hierarchy", tree_text, bg="#F8F9FA", border=SECONDARY, sub_size=8.5, title_size=10.5)

    # Deployment Environment (Right Column)
    draw_box(ax, 0.54, 0.62, 0.50, 0.28, "Production Runtime Stack",
             "OS: Windows 11 / Server x86_64\n"
             "Python Runtime: v3.11.9 (.venv virtual environment)\n"
             "Vision Inference: PyTorch 2.14.1 + ONNXRuntime 1.30.0\n"
             "Spatial Engine: NetworkX 3.2 + Shapely 2.0 + OSMnx\n"
             "Database: SQLite 3 (read-only URI mode enabled)\n"
             "Test Framework: pytest (101 automated test cases)",
             bg="#EBF5FB", border="#2980B9", title_color="#2980B9")

    draw_box(ax, 0.54, 0.35, 0.50, 0.24, "Application & Serving Layer",
             "ASGI Gateway: Uvicorn HTTP/WebSocket Server\n"
             "API Framework: FastAPI (REST + streaming WebSocket)\n"
             "Binding: 0.0.0.0:8000 (Cross-Origin CORS enabled)\n"
             "Static Web Serving: / -> frontend/index.html\n"
             "Media Mount: /data -> data/ (crops & assets)",
             bg="#FEF9E7", border="#D4AC0D", title_color="#D4AC0D")

    draw_box(ax, 0.54, 0.08, 0.50, 0.24, "Client Presentation Layer",
             "Dashboard Engine: Plain HTML5 + CSS3 + Vanilla JS\n"
             "Mapping Library: Leaflet.js v1.9 (OpenStreetMap tiles)\n"
             "Analytics Charts: Chart.js v4.4 (hourly volume, flow)\n"
             "Live Stream Client: Native WebSocket (reconnection logic)\n"
             "Client Overhead: Zero build step, runs in any browser",
             bg="#E8F8F5", border="#16A085", title_color="#16A085")

    out = assets_dir / "fig_folder_deployment.png"
    plt.savefig(out)
    plt.close()
    print(f"Generated: {out.name}")

# ==============================================================================
# FIG 14: Methodology and Timeline Diagram
# ==============================================================================
def gen_fig14():
    fig, ax = plt.subplots(figsize=(11, 7))
    ax.set_xlim(0, 1.1)
    ax.set_ylim(0, 1.0)
    ax.axis("off")

    ax.text(0.55, 0.96, "Figure 3.12: Project Implementation Methodology and Milestone Timeline",
            ha="center", va="center", fontsize=13, fontweight="bold", color=PRIMARY)

    phases = [
        ("Phase 1: Architecture & Data Preparation", "Dataset audit, group-based splitting (zero leakage), deduplication, raw XML/YOLO formatting", 0.82, "#EBF5FB", "#2980B9"),
        ("Phase 2: City Simulator & Graph Modeling", "OSMnx road graph extraction (5km), 40 cameras, Dijkstra path precomputation, 5k vehicle simulation", 0.68, "#E8F8F5", "#16A085"),
        ("Phase 3: Perception, OCR Fine-Tuning & Voting", "YOLOv8s detector, CCT-s-v2 ONNX fine-tuning on Colab T4, multi-frame ByteTrack consensus voting", 0.54, "#FEF9E7", "#D4AC0D"),
        ("Phase 4: Spatial Database & Trajectory Engine", "SQLite schema design, canonical 3-partition fuzzy plate search, speed feasibility validation", 0.40, "#F4ECF7", "#8E44AD"),
        ("Phase 5: Real-Time Alerts & Interactive Dashboard", "Multi-rule alert engine (Blacklist, Clones, Curfew), FastAPI REST/WebSocket, Leaflet dashboard", 0.26, "#FDEDEC", "#C0392B"),
        ("Phase 6: Vehicle Counting & Rigorous Verification", "AI City Track 1 prototype (v1 vs v2 calibration), pytest 101 test suite, comprehensive report", 0.12, "#EAFAF1", "#27AE60"),
    ]

    for title, desc, y, bg, border in phases:
        draw_box(ax, 0.10, y, 0.85, 0.105, title, desc, bg=bg, border=border, lw=1.5, title_color=border, title_size=10, sub_size=8.5)

    for i in range(len(phases) - 1):
        y1 = phases[i][2]
        y2 = phases[i+1][2] + 0.105
        draw_arrow(ax, 0.525, y1, 0.525, y2, color=PRIMARY, lw=1.6)

    out = assets_dir / "fig_methodology_timeline.png"
    plt.savefig(out)
    plt.close()
    print(f"Generated: {out.name}")

# ==============================================================================
# FIG 15: Result Chart - OCR Progression
# ==============================================================================
def gen_fig15():
    fig, ax = plt.subplots(figsize=(8.5, 5))

    stages = [
        "1. From Scratch\n(Uninitialized)",
        "2. Zero-Shot\n(Off-the-shelf Pretrained)",
        "3. Zero-Shot +\nSyntax Rules",
        "4. Fine-Tuned\n(Unseen Test Crops)"
    ]
    accuracies = [29.4, 25.2, 37.1, 76.9]
    colors = ["#95A5A6", "#E74C3C", "#F39C12", "#27AE60"]

    bars = ax.bar(stages, accuracies, color=colors, width=0.55, edgecolor="#2C3E50", linewidth=1.2)
    ax.set_ylim(0, 100)
    ax.set_ylabel("Plate-Level Exact Match Accuracy (%)", fontsize=11, fontweight="bold")
    ax.set_title("Figure 4.1: License Plate Recognition (OCR) Progression Across Training Regimes\n(Evaluated on Real Indian Vehicle Plate Crops [REAL])",
                 fontsize=11, fontweight="bold", pad=12, color=PRIMARY)
    ax.grid(axis="y", linestyle=":", alpha=0.6)

    # Value labels on top of bars
    for bar in bars:
        h = bar.get_height()
        ax.text(bar.get_x() + bar.get_width() / 2, h + 2.0, f"{h:.1f}%",
                ha="center", va="bottom", fontsize=10.5, fontweight="bold", color=PRIMARY)

    # Highlight line for fine-tuned character level accuracy
    ax.axhline(95.7, color="#16A085", linestyle="--", linewidth=1.5, alpha=0.85)
    ax.text(1.5, 96.5, "Fine-Tuned Character-Level Accuracy: 95.7%", color="#16A085", fontsize=9.5, fontweight="bold")

    out = assets_dir / "fig_ocr_progression.png"
    plt.savefig(out)
    plt.close()
    print(f"Generated: {out.name}")

# ==============================================================================
# FIG 16: Result Chart - Detector Metrics
# ==============================================================================
def gen_fig16():
    fig, ax = plt.subplots(figsize=(8.5, 5))

    metrics = ["Precision\n(P)", "Recall\n(R)", "F1-Score\n(Harmonic Mean)", "mAP@50\n(IoU ≥ 0.50)", "mAP@50-95\n(COCO Standard)"]
    values = [98.3, 98.1, 98.2, 98.3, 84.3]
    colors = ["#2980B9", "#3498DB", "#16A085", "#27AE60", "#F39C12"]

    bars = ax.bar(metrics, values, color=colors, width=0.55, edgecolor="#2C3E50", linewidth=1.2)
    ax.set_ylim(0, 110)
    ax.set_ylabel("Metric Score (%)", fontsize=11, fontweight="bold")
    ax.set_title("Figure 4.2: YOLOv8s License Plate Detector Quantitative Evaluation\n(Held-Out Test Split, N=184 Images [REAL])",
                 fontsize=11, fontweight="bold", pad=12, color=PRIMARY)
    ax.grid(axis="y", linestyle=":", alpha=0.6)

    for bar in bars:
        h = bar.get_height()
        ax.text(bar.get_x() + bar.get_width() / 2, h + 2.0, f"{h:.1f}%",
                ha="center", va="bottom", fontsize=10.5, fontweight="bold", color=PRIMARY)

    out = assets_dir / "fig_detector_metrics.png"
    plt.savefig(out)
    plt.close()
    print(f"Generated: {out.name}")

# ==============================================================================
# FIG 17: Result Chart - End-to-End Evaluation
# ==============================================================================
def gen_fig17():
    fig, ax = plt.subplots(figsize=(8.5, 5))

    stages = ["Detection\nRecall", "Detection\nPrecision", "Plate Exact\nMatch", "Character\nAccuracy"]
    scores = [100.0, 98.8, 80.84, 96.30]
    colors = ["#16A085", "#27AE60", "#2980B9", "#8E44AD"]

    bars = ax.bar(stages, scores, color=colors, width=0.52, edgecolor="#2C3E50", linewidth=1.2)
    ax.set_ylim(0, 115)
    ax.set_ylabel("Performance Rate (%)", fontsize=11, fontweight="bold")
    ax.set_title("Figure 4.3: End-to-End Plate Recognition Benchmark on Held-Out Test Photos\n(N=167 Unseen Vehicle Photos, CPU Inference ~307 ms [REAL])",
                 fontsize=11, fontweight="bold", pad=12, color=PRIMARY)
    ax.grid(axis="y", linestyle=":", alpha=0.6)

    for bar in bars:
        h = bar.get_height()
        ax.text(bar.get_x() + bar.get_width() / 2, h + 2.0, f"{h:.2f}%",
                ha="center", va="bottom", fontsize=10, fontweight="bold", color=PRIMARY)

    # Annotation box for target check
    ax.text(2.0, 60.0, "Target Comparison:\n* 90% Target MET at character level (96.30%)\n* 90% Target NOT met at full plate level (80.84%)\n* Single misread character invalidates whole plate",
            ha="center", va="center", fontsize=8.5, bbox=dict(boxstyle="round,pad=0.5", fc="#FFF8E7", ec=HIGHLIGHT, lw=1.2))

    out = assets_dir / "fig_end_to_end.png"
    plt.savefig(out)
    plt.close()
    print(f"Generated: {out.name}")

# ==============================================================================
# FIG 18: Result Chart - Per-Frame vs Voted Video Accuracy
# ==============================================================================
def gen_fig18():
    fig, ax = plt.subplots(figsize=(9, 5))

    categories = [
        "All Real Sequences\n(N=20 [REAL])",
        "Multi-Frame Real\n(N=11 [REAL])",
        "Single-Frame Real\n(N=9 [REAL])",
        "Synthetic Clips\n(N=60 [SYNTHETIC])"
    ]

    per_frame = [85.24, 82.25, 88.89, 66.87]
    voted = [90.00, 90.91, 88.89, 78.33]

    x = np.arange(len(categories))
    w = 0.35

    rects1 = ax.bar(x - w/2, per_frame, w, label="Per-Frame Average Exact Match (%)", color="#7F8C8D", edgecolor="#2C3E50", linewidth=1.1)
    rects2 = ax.bar(x + w/2, voted, w, label="Voted Consensus Exact Match (%)", color="#27AE60", edgecolor="#2C3E50", linewidth=1.1)

    ax.set_ylim(0, 110)
    ax.set_ylabel("Exact Match Accuracy (%)", fontsize=11, fontweight="bold")
    ax.set_title("Figure 4.4: Temporal Consensus Voting Accuracy Across Real & Synthetic Video Sequences\n(Notice: Synthetic clips are optimistic; voting cannot alter single-frame reads)",
                 fontsize=10.5, fontweight="bold", pad=12, color=PRIMARY)
    ax.set_xticks(x)
    ax.set_xticklabels(categories, fontsize=9.5)
    ax.legend(loc="lower right", fontsize=9.5)
    ax.grid(axis="y", linestyle=":", alpha=0.6)

    for r in rects1:
        h = r.get_height()
        ax.text(r.get_x() + r.get_width() / 2, h + 1.5, f"{h:.1f}%", ha="center", va="bottom", fontsize=8.5, color="#555555")

    for r in rects2:
        h = r.get_height()
        ax.text(r.get_x() + r.get_width() / 2, h + 1.5, f"{h:.1f}%", ha="center", va="bottom", fontsize=9, fontweight="bold", color="#1B365D")

    out = assets_dir / "fig_voting_accuracy.png"
    plt.savefig(out)
    plt.close()
    print(f"Generated: {out.name}")

# ==============================================================================
# FIG 19: Result Chart - Alert Breakdown
# ==============================================================================
def gen_fig19():
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4.8))

    # Subplot 1: Alert Types (44 total)
    types = ["Blacklist Watchlist", "Cloned Plate Anomaly", "Restricted Zone Curfew", "Overspeeding Violation"]
    counts = [35, 5, 4, 0]
    colors1 = ["#C0392B", "#D35400", "#F39C12", "#95A5A6"]

    bars = ax1.bar(types, counts, color=colors1, width=0.55, edgecolor="#2C3E50", linewidth=1.1)
    ax1.set_ylim(0, 40)
    ax1.set_ylabel("Triggered Incident Count", fontsize=10, fontweight="bold")
    ax1.set_title("Alerts by Rule Category (44 Total)\n[SIMULATED]", fontsize=10.5, fontweight="bold", color=PRIMARY)
    ax1.set_xticklabels(types, rotation=20, ha="right", fontsize=9)
    ax1.grid(axis="y", linestyle=":", alpha=0.6)

    for b in bars:
        h = b.get_height()
        ax1.text(b.get_x() + b.get_width() / 2, h + 0.8, f"{int(h)} ({h/44*100:.1f}%)" if h > 0 else "0 (0%)",
                 ha="center", va="bottom", fontsize=8.5, fontweight="bold", color=PRIMARY)

    # Subplot 2: Alert Severities
    severities = ["HIGH Severity\n(Exact Blacklist, Clones)", "MEDIUM Severity\n(Fuzzy Blacklist, Curfew)", "LOW Severity\n(Overspeed, Loiter)"]
    sev_counts = [28, 16, 0]
    colors2 = ["#C0392B", "#E67E22", "#27AE60"]

    wedges, texts, autotexts = ax2.pie([28, 16], labels=["HIGH (63.6%)", "MEDIUM (36.4%)"],
                                       colors=["#C0392B", "#E67E22"], autopct="%1.1f%%",
                                       startangle=140, explode=(0.04, 0.04), textprops=dict(color="#222222", fontsize=9))
    ax2.set_title("Alerts by Severity Level\n(HIGH: 28, MEDIUM: 16, LOW: 0)", fontsize=10.5, fontweight="bold", color=PRIMARY)

    plt.suptitle("Figure 4.5: Surveillance Alert Engine Incident Classification & Severity Breakdown",
                 fontsize=11.5, fontweight="bold", y=1.03, color=PRIMARY)

    out = assets_dir / "fig_alert_breakdown.png"
    plt.savefig(out)
    plt.close()
    print(f"Generated: {out.name}")

# ==============================================================================
# FIG 20: Result Chart - Trajectory Engine Metrics
# ==============================================================================
def gen_fig20():
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4.8))

    # Subplot 1: Accuracy metrics
    metrics = ["Precision", "Recall", "F1-Score", "Clone Anomaly\nDetection"]
    acc_vals = [99.95, 96.35, 97.91, 100.0]
    colors1 = ["#2980B9", "#3498DB", "#16A085", "#27AE60"]

    bars = ax1.bar(metrics, acc_vals, color=colors1, width=0.52, edgecolor="#2C3E50", linewidth=1.1)
    ax1.set_ylim(85, 105)
    ax1.set_ylabel("Metric Rate (%)", fontsize=10, fontweight="bold")
    ax1.set_title("Reconstruction Accuracy (N=200 Trips)\n[SIMULATED]", fontsize=10.5, fontweight="bold", color=PRIMARY)
    ax1.grid(axis="y", linestyle=":", alpha=0.6)

    for b in bars:
        h = b.get_height()
        ax1.text(b.get_x() + b.get_width() / 2, h + 0.5, f"{h:.2f}%", ha="center", va="bottom", fontsize=8.5, fontweight="bold", color=PRIMARY)

    # Subplot 2: Latencies
    lat_labels = ["Average\nLatency", "Median\nLatency", "95th Percentile\n(P95) Latency", "Target\nBenchmark"]
    lat_vals = [15.82, 20.47, 24.00, 100.0]
    colors2 = ["#27AE60", "#2ECC71", "#1ABC9C", "#BDC3C7"]

    bars2 = ax2.bar(lat_labels, lat_vals, color=colors2, width=0.52, edgecolor="#2C3E50", linewidth=1.1)
    ax2.set_ylim(0, 115)
    ax2.set_ylabel("Query Latency (milliseconds)", fontsize=10, fontweight="bold")
    ax2.set_title("Query Latency vs Target Threshold\n(In-Memory Road Graph Cache)", fontsize=10.5, fontweight="bold", color=PRIMARY)
    ax2.grid(axis="y", linestyle=":", alpha=0.6)

    for b in bars2:
        h = b.get_height()
        ax2.text(b.get_x() + b.get_width() / 2, h + 2.0, f"{h:.1f} ms", ha="center", va="bottom", fontsize=8.5, fontweight="bold", color=PRIMARY)

    plt.suptitle("Figure 4.6: Cross-Camera Trajectory Reconstruction Performance & Latency Benchmarks",
                 fontsize=11.5, fontweight="bold", y=1.03, color=PRIMARY)

    out = assets_dir / "fig_trajectory_metrics.png"
    plt.savefig(out)
    plt.close()
    print(f"Generated: {out.name}")

# ==============================================================================
# FIG 21: Result Chart - Counting v1 vs v2
# ==============================================================================
def gen_fig21():
    fig, ax = plt.subplots(figsize=(9, 5))

    metrics = [
        "Precision\n(with class)",
        "Recall\n(with class)",
        "F1-Score\n(with class)",
        "Precision\n(ignoring class)",
        "Recall\n(ignoring class)",
        "F1-Score\n(ignoring class)",
    ]

    v1_scores = [60.0, 10.5, 17.9, 60.0, 10.5, 17.9]
    v2_scores = [96.6, 49.1, 65.1, 100.0, 50.9, 67.4]

    x = np.arange(len(metrics))
    w = 0.35

    rects1 = ax.bar(x - w/2, v1_scores, w, label="v1 Visual Zones (Uncalibrated)", color="#E74C3C", edgecolor="#2C3E50", linewidth=1.1)
    rects2 = ax.bar(x + w/2, v2_scores, w, label="v2 Calibrated Zones (Calibrated on f<300)", color="#27AE60", edgecolor="#2C3E50", linewidth=1.1)

    ax.set_ylim(0, 115)
    ax.set_ylabel("Evaluation Rate (%)", fontsize=11, fontweight="bold")
    ax.set_title("Figure 4.7: Vehicle Movement Counting Performance (v1 Visual vs. v2 Calibrated)\n(Evaluated Strictly on Test Split frame_id ≥ 300, 57 GT Events [REAL])",
                 fontsize=10.5, fontweight="bold", pad=12, color=PRIMARY)
    ax.set_xticks(x)
    ax.set_xticklabels(metrics, fontsize=9)
    ax.legend(loc="upper left", fontsize=9.5)
    ax.grid(axis="y", linestyle=":", alpha=0.6)

    for r in rects1:
        h = r.get_height()
        ax.text(r.get_x() + r.get_width() / 2, h + 1.5, f"{h:.1f}%", ha="center", va="bottom", fontsize=8.5, color="#A93226")

    for r in rects2:
        h = r.get_height()
        ax.text(r.get_x() + r.get_width() / 2, h + 1.5, f"{h:.1f}%", ha="center", va="bottom", fontsize=9, fontweight="bold", color="#1E8449")

    out = assets_dir / "fig_counting_v1_v2.png"
    plt.savefig(out)
    plt.close()
    print(f"Generated: {out.name}")

# ==============================================================================
# Placeholder Screenshots (SS-1 to SS-6)
# ==============================================================================
def gen_placeholder_screenshot(name, tab_name, description):
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.set_xlim(0, 1.0)
    ax.set_ylim(0, 1.0)
    ax.axis("off")

    # Outer dashed frame
    box = FancyBboxPatch((0.04, 0.04), 0.92, 0.92, boxstyle="round,pad=0.01,rounding_size=0.02",
                         facecolor="#FAFAFA", edgecolor="#7F8C8D", linewidth=2.0, linestyle="--")
    ax.add_patch(box)

    # Header bar
    hbar = FancyBboxPatch((0.06, 0.82), 0.88, 0.10, boxstyle="round,pad=0.005,rounding_size=0.01",
                          facecolor=PRIMARY, edgecolor="none")
    ax.add_patch(hbar)
    ax.text(0.5, 0.87, f"CITY ANPR LIVE DASHBOARD — {tab_name.upper()} VIEW", color="#FFFFFF", fontsize=12, fontweight="bold", ha="center", va="center")

    # Center notice
    ax.text(0.5, 0.58, f"SCREENSHOT TO BE INSERTED: {tab_name}",
            color="#C0392B", fontsize=15, fontweight="bold", ha="center", va="center",
            bbox=dict(boxstyle="round,pad=0.6", fc="#FDEDEC", ec="#E74C3C", lw=1.5))

    ax.text(0.5, 0.40, description,
            color="#333333", fontsize=10, ha="center", va="center", multialignment="center")

    ax.text(0.5, 0.22, "Instructions for Manual Capture:\n1. Launch: python run_api.py (http://127.0.0.1:8000)\n2. Navigate to this tab in a web browser\n3. Capture full tab view at 1920x1080, blur any real plate numbers, and replace this image file.",
            color="#555555", fontsize=8.5, ha="center", va="center", multialignment="center",
            bbox=dict(boxstyle="square,pad=0.4", fc="#FFFFFF", ec="#BDC3C7", lw=1.0))

    ax.text(0.5, 0.08, f"Asset Target: report/assets/{name}", color="#7F8C8D", fontsize=8, ha="center", va="center")

    out = assets_dir / name
    plt.savefig(out)
    plt.close()
    print(f"Generated placeholder screenshot: {out.name}")

# ==============================================================================
# Contact Sheet Generator
# ==============================================================================
def gen_contact_sheet():
    """Build a composite contact sheet image indexing all generated visual assets."""
    image_files = sorted([f for f in assets_dir.glob("*.png") if f.name != "contact_sheet.png"])
    n = len(image_files)
    print(f"Generating contact sheet for {n} visual assets...")

    cols = 4
    rows = (n + cols - 1) // cols

    thumb_w, thumb_h = 450, 320
    header_h = 100
    sheet_w = cols * thumb_w + 40
    sheet_h = rows * thumb_h + header_h + 30

    sheet = Image.new("RGB", (sheet_w, sheet_h), "#F2F4F4")
    draw = ImageDraw.Draw(sheet)

    # Title Banner
    draw.rectangle([(0, 0), (sheet_w, header_h)], fill="#1B365D")
    draw.text((sheet_w // 2, 45), "CITY ANPR PROJECT REPORT — VISUAL ASSETS CONTACT SHEET (STAGE 2)",
              fill="#FFFFFF", anchor="mm")
    draw.text((sheet_w // 2, 80), f"Total Verified Visual Assets: {n} Figures & Screenshots (300 DPI)",
              fill="#F0AD4E", anchor="mm")

    for idx, fpath in enumerate(image_files):
        r = idx // cols
        c = idx % cols
        x = 20 + c * thumb_w
        y = header_h + 15 + r * thumb_h

        # Draw card container
        draw.rectangle([(x + 5, y + 5), (x + thumb_w - 5, y + thumb_h - 5)], fill="#FFFFFF", outline="#BDC3C7", width=1)

        # Thumbnail image
        try:
            with Image.open(fpath) as img:
                img.thumbnail((thumb_w - 20, thumb_h - 60))
                ix = x + (thumb_w - img.width) // 2
                iy = y + 10 + (thumb_h - 60 - img.height) // 2
                sheet.paste(img, (ix, iy))
        except Exception as e:
            draw.text((x + thumb_w // 2, y + thumb_h // 2), f"Error: {e}", fill="red", anchor="mm")

        # Label caption
        label = fpath.stem
        if len(label) > 32:
            label = label[:30] + "..."
        draw.rectangle([(x + 5, y + thumb_h - 35), (x + thumb_w - 5, y + thumb_h - 5)], fill="#EAECEE")
        draw.text((x + thumb_w // 2, y + thumb_h - 20), f"#{idx+1}: {label}", fill="#1B365D", anchor="mm")

    out = assets_dir / "contact_sheet.png"
    sheet.save(out, dpi=(300, 300))
    print(f"Generated Contact Sheet: {out.name} ({sheet_w}x{sheet_h} px)")

def main():
    print("=" * 70)
    print("STARTING STAGE 2: GENERATING ALL REPORT VISUAL ASSETS (300 DPI)")
    print("=" * 70)

    # 1. Structural and Architecture Diagrams (14)
    gen_fig1()   # fig_system_block.png
    gen_fig2()   # fig_data_flow.png
    gen_fig3()   # fig_perception_pipeline.png
    gen_fig4()   # fig_voting_review.png
    gen_fig5()   # fig_simulator.png
    gen_fig6()   # fig_er_diagram.png
    gen_fig7()   # fig_trajectory_engine.png
    gen_fig8()   # fig_alert_engine.png
    gen_fig9()   # fig_api_sequence.png
    gen_fig10()  # fig_dashboard_layout.png
    gen_fig11()  # fig_counting_pipeline.png
    gen_fig12()  # fig_cam5_roi_movements.png
    gen_fig13()  # fig_folder_deployment.png
    gen_fig14()  # fig_methodology_timeline.png

    # 2. Result Charts (7)
    gen_fig15()  # fig_ocr_progression.png
    gen_fig16()  # fig_detector_metrics.png
    gen_fig17()  # fig_end_to_end.png
    gen_fig18()  # fig_voting_accuracy.png
    gen_fig19()  # fig_alert_breakdown.png
    gen_fig20()  # fig_trajectory_metrics.png
    gen_fig21()  # fig_counting_v1_v2.png

    # 3. Placeholder Screenshots (6)
    gen_placeholder_screenshot("ss_overview.png", "Overview Tab", "Shows KPI Metric Summary Cards, Live Leaflet City Map with 40 Cameras,\nand Top Congested Corridor Statistics Table.")
    gen_placeholder_screenshot("ss_trajectory.png", "Trajectory Search Tab", "Shows Fuzzy Plate Search Input ('TN11YD7305'), Chronological Sightings List,\nInterpolated GeoJSON Road Trajectory Polyline, and CSV Export Button.")
    gen_placeholder_screenshot("ss_heatmap.png", "Traffic Heatmap Tab", "Shows Spatial Sighting Intensity Heatmap across Bangalore Road Corridors\nand Busiest Segment Table.")
    gen_placeholder_screenshot("ss_alerts.png", "Live Alerts Tab", "Shows Real-Time Streaming Surveillance Alert Cards (44 Simulated Incidents),\nSeverity Badges (HIGH, MEDIUM, LOW), and Audio Indicator.")
    gen_placeholder_screenshot("ss_blacklist.png", "Blacklist Tab", "Shows High-Priority Watchlist Plates (10 Vehicles), Target Addition Form,\nand Reason Descriptions (Wanted, Stolen, Expired).")
    gen_placeholder_screenshot("ss_plate_reader.png", "Plate Reader Tab", "Shows Direct Single-Image Inference Dropzone, Detected Bounding Box Overlay,\nNormalised Plate Text, OCR Confidence Meter, and REVIEW Status Badge.")

    # 4. Composite Contact Sheet
    gen_contact_sheet()

    print("=" * 70)
    print("STAGE 2 ASSET GENERATION COMPLETE: 28 ASSETS READY IN report/assets/")
    print("=" * 70)

if __name__ == "__main__":
    main()

