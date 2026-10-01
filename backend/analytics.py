"""Module 6: Urban Traffic Analytics & Congestion Detection Engine.

Provides city-scale spatio-temporal traffic analytics:
- camera_stats(): Volume, unique plates (fuzzy-merged), speeds, and density score per window.
- city_flow_trend(): City-wide flow and average speed trends revealing diurnal peaks.
- congestion_hotspots(): Flags congestion based on free-flow speed deficit & median volume.
- origin_destination_matrix(): Zone-to-zone OD trip matrices via KMeans camera clustering.
- route_density(): Road network segment load tracking using precomputed camera paths.
- heatmap_points(): Weighted geo-spatial density & slowness points for GIS mapping.
"""

from __future__ import annotations

import collections
import datetime
import math
import pickle
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sqlalchemy.orm import Session

# Ensure project root is in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.db import SessionLocal, engine
from backend.models import Camera, Event
from backend.plate_utils import CANONICAL_MAP
from backend.trajectory import get_camera_paths, get_cameras_info
from simulator.config import CAMERAS_PATH, DATA_SIM_DIR

# Global caches for camera metadata and zone clustering
_CAMERAS_DF: Optional[pd.DataFrame] = None
_ZONE_ASSIGNMENTS: Optional[Dict[str, str]] = None
_ZONE_NAMES: Optional[List[str]] = None


def load_cameras_df() -> pd.DataFrame:
    """Load camera coordinates and names into a cached DataFrame."""
    global _CAMERAS_DF
    if _CAMERAS_DF is not None:
        return _CAMERAS_DF

    if CAMERAS_PATH.exists():
        df = pd.read_csv(CAMERAS_PATH)
    else:
        df = pd.read_sql("SELECT camera_id, name, lat, lon, node_id FROM cameras", engine)

    # Sanitize camera names (replace '#' with 'No. ')
    df["name"] = df["name"].astype(str).str.replace("#", "No. ")
    _CAMERAS_DF = df
    return _CAMERAS_DF


def get_zone_clustering(n_zones: int = 8) -> Tuple[Dict[str, str], List[str]]:
    """Cluster cameras into spatial zones using KMeans on GPS coordinates.

    Returns:
        Mapping of camera_id -> zone_name, and the list of unique zone names.
    """
    global _ZONE_ASSIGNMENTS, _ZONE_NAMES
    if _ZONE_ASSIGNMENTS is not None and len(_ZONE_NAMES) == n_zones:
        return _ZONE_ASSIGNMENTS, _ZONE_NAMES

    cams = load_cameras_df().copy()
    coords = cams[["lat", "lon"]].values

    kmeans = KMeans(n_clusters=n_zones, random_state=42, n_init=10).fit(coords)
    cams["zone_id"] = kmeans.labels_

    # Assign descriptive names based on central landmark or coordinates
    zone_names_list: List[str] = []
    zone_map: Dict[str, str] = {}

    for z in range(n_zones):
        z_cams = cams[cams["zone_id"] == z]
        # Choose the most central or first camera as representative landmark
        rep_name = z_cams.iloc[0]["name"]
        short_name = rep_name.split("&")[0].split("Junction")[0].split("Crossing")[0].strip()
        zone_label = f"Zone {z + 1} ({short_name})"
        zone_names_list.append(zone_label)

        for cid in z_cams["camera_id"]:
            zone_map[cid] = zone_label

    _ZONE_ASSIGNMENTS = zone_map
    _ZONE_NAMES = zone_names_list
    return _ZONE_ASSIGNMENTS, _ZONE_NAMES


def load_events_df(
    start: Optional[Union[str, datetime.datetime]] = None,
    end: Optional[Union[str, datetime.datetime]] = None,
) -> pd.DataFrame:
    """Load raw ANPR events from SQLite with optional time window filtering."""
    query = "SELECT id, plate, camera_id, timestamp, speed_kmh, heading_degrees, lane, ocr_confidence FROM events"
    conditions = []
    params = {}

    if start is not None:
        start_dt = pd.to_datetime(start).to_pydatetime()
        conditions.append("timestamp >= :start")
        params["start"] = start_dt

    if end is not None:
        end_dt = pd.to_datetime(end).to_pydatetime()
        conditions.append("timestamp <= :end")
        params["end"] = end_dt

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    df = pd.read_sql(query, engine, params=params)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    # Map OCR confusable characters to canonical representatives to merge optical noise
    df["plate_canonical"] = df["plate"].astype(str).str.translate(CANONICAL_MAP)
    return df


def camera_stats(
    window_minutes: int = 15,
    start: Optional[Union[str, datetime.datetime]] = None,
    end: Optional[Union[str, datetime.datetime]] = None,
) -> pd.DataFrame:
    """Calculate volume, unique fuzzy plates, average/p85 speed, and density score per camera-window.

    Density score is normalized 0 to 1 per camera based on its observed volume range.
    """
    events_df = load_events_df(start=start, end=end)
    if events_df.empty:
        return pd.DataFrame(columns=[
            "camera_id", "camera_name", "window_start", "window_end",
            "vehicle_count", "unique_plates", "avg_speed_kmh", "p85_speed_kmh", "density_score"
        ])

    cams_df = load_cameras_df()
    cam_names = dict(zip(cams_df["camera_id"], cams_df["name"]))

    # Assign 15-minute time window
    events_df["window_start"] = events_df["timestamp"].dt.floor(f"{window_minutes}min")
    events_df["window_end"] = events_df["window_start"] + pd.Timedelta(minutes=window_minutes)

    # Group by camera and time window
    grouped = events_df.groupby(["camera_id", "window_start", "window_end"])

    stats = grouped.agg(
        vehicle_count=("id", "count"),
        unique_plates=("plate_canonical", "nunique"),
        avg_speed_kmh=("speed_kmh", "mean"),
        p85_speed_kmh=("speed_kmh", lambda s: float(np.percentile(s.dropna(), 85)) if len(s.dropna()) > 0 else 0.0),
    ).reset_index()

    stats["camera_name"] = stats["camera_id"].map(lambda cid: cam_names.get(cid, cid))
    stats["avg_speed_kmh"] = stats["avg_speed_kmh"].round(1)
    stats["p85_speed_kmh"] = stats["p85_speed_kmh"].round(1)

    # Calculate density score: count normalized 0 to 1 per camera
    cam_max = stats.groupby("camera_id")["vehicle_count"].transform("max")
    stats["density_score"] = (stats["vehicle_count"] / cam_max).round(3)

    # Reorder columns
    cols = [
        "camera_id", "camera_name", "window_start", "window_end",
        "vehicle_count", "unique_plates", "avg_speed_kmh", "p85_speed_kmh", "density_score"
    ]
    return stats[cols].sort_values(["window_start", "camera_id"]).reset_index(drop=True)


def city_flow_trend(
    window_minutes: int = 15,
    start: Optional[Union[str, datetime.datetime]] = None,
    end: Optional[Union[str, datetime.datetime]] = None,
) -> pd.DataFrame:
    """City-wide aggregate vehicle volume, unique plates, and speed trends per time window."""
    events_df = load_events_df(start=start, end=end)
    if events_df.empty:
        return pd.DataFrame(columns=[
            "window_start", "window_end", "vehicle_count", "unique_plates",
            "avg_speed_kmh", "p85_speed_kmh"
        ])

    events_df["window_start"] = events_df["timestamp"].dt.floor(f"{window_minutes}min")
    events_df["window_end"] = events_df["window_start"] + pd.Timedelta(minutes=window_minutes)

    grouped = events_df.groupby(["window_start", "window_end"])
    trend = grouped.agg(
        vehicle_count=("id", "count"),
        unique_plates=("plate_canonical", "nunique"),
        avg_speed_kmh=("speed_kmh", "mean"),
        p85_speed_kmh=("speed_kmh", lambda s: float(np.percentile(s.dropna(), 85)) if len(s.dropna()) > 0 else 0.0),
    ).reset_index()

    trend["avg_speed_kmh"] = trend["avg_speed_kmh"].round(1)
    trend["p85_speed_kmh"] = trend["p85_speed_kmh"].round(1)
    return trend.sort_values("window_start").reset_index(drop=True)


def congestion_hotspots(
    window_minutes: int = 15,
    start: Optional[Union[str, datetime.datetime]] = None,
    end: Optional[Union[str, datetime.datetime]] = None,
) -> pd.DataFrame:
    """Flag camera-windows as congested based on free-flow speed deficit & median volume.

    Criteria:
    - Average speed < 60% of that camera's whole-day free-flow speed (85th percentile speed).
    - Vehicle count > camera's median volume across windows.
    Returns: camera_id, camera_name, window_start, window_end, severity (0-1), duration_minutes.
    """
    stats = camera_stats(window_minutes=window_minutes, start=start, end=end)
    if stats.empty:
        return pd.DataFrame(columns=[
            "camera_id", "camera_name", "window_start", "window_end",
            "avg_speed_kmh", "free_flow_speed_kmh", "vehicle_count",
            "median_count", "severity", "duration_minutes"
        ])

    # Whole-day free-flow speed (85th percentile of whole day) and median count per camera
    all_events = load_events_df()
    cam_free_flow = all_events.groupby("camera_id")["speed_kmh"].apply(
        lambda s: float(np.percentile(s.dropna(), 85)) if len(s.dropna()) > 0 else 40.0
    ).to_dict()

    cam_median_count = stats.groupby("camera_id")["vehicle_count"].median().to_dict()

    congested_rows: List[Dict[str, Any]] = []

    for _, row in stats.iterrows():
        cid = row["camera_id"]
        ff_speed = cam_free_flow.get(cid, 40.0)
        med_cnt = cam_median_count.get(cid, 10.0)

        threshold_speed = 0.60 * ff_speed
        is_congested = (row["avg_speed_kmh"] < threshold_speed) and (row["vehicle_count"] > med_cnt)

        if is_congested:
            # Severity bounded between 0.0 and 1.0 as speed drops to 0
            sev = max(0.0, min(1.0, (threshold_speed - row["avg_speed_kmh"]) / max(1.0, threshold_speed)))

            congested_rows.append({
                "camera_id": cid,
                "camera_name": row["camera_name"],
                "window_start": row["window_start"],
                "window_end": row["window_end"],
                "avg_speed_kmh": row["avg_speed_kmh"],
                "free_flow_speed_kmh": round(ff_speed, 1),
                "vehicle_count": row["vehicle_count"],
                "median_count": round(med_cnt, 1),
                "severity": round(sev, 3),
                "duration_minutes": window_minutes,
            })

    cong_df = pd.DataFrame(congested_rows)
    if cong_df.empty:
        return pd.DataFrame(columns=[
            "camera_id", "camera_name", "window_start", "window_end",
            "avg_speed_kmh", "free_flow_speed_kmh", "vehicle_count",
            "median_count", "severity", "duration_minutes"
        ])

    # Calculate cumulative continuous duration for consecutive congested windows per camera
    cong_df = cong_df.sort_values(["camera_id", "window_start"]).reset_index(drop=True)
    durations = []
    current_cam = None
    last_end = None
    accum_dur = window_minutes

    for _, r in cong_df.iterrows():
        if r["camera_id"] == current_cam and r["window_start"] == last_end:
            accum_dur += window_minutes
        else:
            current_cam = r["camera_id"]
            accum_dur = window_minutes
        last_end = r["window_end"]
        durations.append(accum_dur)

    cong_df["duration_minutes"] = durations
    return cong_df.sort_values(["severity", "vehicle_count"], ascending=[False, False]).reset_index(drop=True)


def extract_vehicle_trips(
    start: Optional[Union[str, datetime.datetime]] = None,
    end: Optional[Union[str, datetime.datetime]] = None,
) -> pd.DataFrame:
    """Extract individual journeys from events grouped by vehicle plate and inactivity gaps."""
    events_df = load_events_df(start=start, end=end)
    if events_df.empty:
        return pd.DataFrame(columns=[
            "trip_id", "plate", "origin_camera", "dest_camera", "start_time", "end_time", "num_sightings"
        ])

    events_df = events_df.sort_values(["plate", "timestamp"]).reset_index(drop=True)
    events_df["dt"] = events_df.groupby("plate")["timestamp"].diff().dt.total_seconds()
    events_df["new_trip"] = events_df["dt"].isna() | (events_df["dt"] > 1800.0)
    events_df["trip_id"] = events_df["new_trip"].cumsum()

    trips = events_df.groupby("trip_id").agg(
        plate=("plate", "first"),
        origin_camera=("camera_id", "first"),
        dest_camera=("camera_id", "last"),
        start_time=("timestamp", "first"),
        end_time=("timestamp", "last"),
        num_sightings=("camera_id", "count"),
    ).reset_index()

    return trips


def origin_destination_matrix(
    start: Optional[Union[str, datetime.datetime]] = None,
    end: Optional[Union[str, datetime.datetime]] = None,
    n_zones: int = 8,
) -> pd.DataFrame:
    """Compute zone-to-zone Origin-Destination vehicle trip counts matrix.

    Returns:
        Square pivot DataFrame with Origin zones as index and Destination zones as columns.
    """
    zone_map, zone_names = get_zone_clustering(n_zones=n_zones)
    trips = extract_vehicle_trips(start=start, end=end)

    if trips.empty:
        return pd.DataFrame(0, index=zone_names, columns=zone_names)

    trips["origin_zone"] = trips["origin_camera"].map(lambda cid: zone_map.get(cid, "Unknown"))
    trips["dest_zone"] = trips["dest_camera"].map(lambda cid: zone_map.get(cid, "Unknown"))

    # Pivot table into square zone matrix
    od_pivot = pd.crosstab(
        trips["origin_zone"],
        trips["dest_zone"],
        rownames=["Origin Zone"],
        colnames=["Destination Zone"],
    )

    # Reindex to ensure all zones are present
    od_pivot = od_pivot.reindex(index=zone_names, columns=zone_names, fill_value=0)
    return od_pivot


def route_density(
    window_minutes: int = 60,
    start: Optional[Union[str, datetime.datetime]] = None,
    end: Optional[Union[str, datetime.datetime]] = None,
) -> pd.DataFrame:
    """Aggregate vehicle traversal counts along road segments per time window."""
    events_df = load_events_df(start=start, end=end)
    if events_df.empty:
        return pd.DataFrame(columns=[
            "window_start", "segment_id", "u_lat", "u_lon", "v_lat", "v_lon", "vehicle_count"
        ])

    events_df = events_df.sort_values(["plate", "timestamp"]).reset_index(drop=True)
    events_df["prev_camera"] = events_df.groupby("plate")["camera_id"].shift()
    events_df["prev_time"] = events_df.groupby("plate")["timestamp"].shift()
    events_df["dt"] = (events_df["timestamp"] - events_df["prev_time"]).dt.total_seconds()

    # Valid transitions between different cameras within 30 min
    valid_hops = events_df[
        (events_df["prev_camera"].notna())
        & (events_df["camera_id"] != events_df["prev_camera"])
        & (events_df["dt"] <= 1800.0)
    ].copy()

    valid_hops["window_start"] = valid_hops["timestamp"].dt.floor(f"{window_minutes}min")

    camera_paths = get_camera_paths()
    segment_counts: Dict[Tuple[Any, str, float, float, float, float], int] = collections.defaultdict(int)

    for _, row in valid_hops.iterrows():
        c1 = row["prev_camera"]
        c2 = row["camera_id"]
        w = row["window_start"]

        hop_info = camera_paths.get((c1, c2))
        if not hop_info:
            continue

        coords = hop_info[2]
        if len(coords) < 2:
            continue

        # Traverse road segments along path
        for i in range(len(coords) - 1):
            p1 = coords[i]
            p2 = coords[i + 1]
            seg_id = f"{p1[0]:.4f},{p1[1]:.4f}->{p2[0]:.4f},{p2[1]:.4f}"
            segment_counts[(w, seg_id, p1[0], p1[1], p2[0], p2[1])] += 1

    records = [
        {
            "window_start": k[0],
            "segment_id": k[1],
            "u_lat": k[2],
            "u_lon": k[3],
            "v_lat": k[4],
            "v_lon": k[5],
            "vehicle_count": count,
        }
        for k, count in segment_counts.items()
    ]

    res_df = pd.DataFrame(records)
    if res_df.empty:
        return pd.DataFrame(columns=[
            "window_start", "segment_id", "u_lat", "u_lon", "v_lat", "v_lon", "vehicle_count"
        ])

    return res_df.sort_values(["window_start", "vehicle_count"], ascending=[True, False]).reset_index(drop=True)


def heatmap_points(
    window: Optional[Union[str, datetime.datetime]] = None,
    start: Optional[Union[str, datetime.datetime]] = None,
    end: Optional[Union[str, datetime.datetime]] = None,
) -> pd.DataFrame:
    """Generate geospatial heatmap weight points based on density and slowness.

    Weights are guaranteed to be strictly bounded between 0.0 and 1.0.
    """
    stats = camera_stats(window_minutes=15, start=start, end=end)
    if stats.empty:
        return pd.DataFrame(columns=["lat", "lon", "weight", "camera_id", "camera_name", "vehicle_count", "avg_speed_kmh"])

    cams = load_cameras_df().set_index("camera_id")

    # If window is provided, filter for that specific window; otherwise pick the peak window
    if window is not None:
        target_w = pd.to_datetime(window)
        stats = stats[stats["window_start"] == target_w]
        if stats.empty:
            return pd.DataFrame(columns=["lat", "lon", "weight", "camera_id", "camera_name", "vehicle_count", "avg_speed_kmh"])
    elif start is None and end is None:
        # Default: select the single busiest 15-minute window of the day
        peak_w = stats.groupby("window_start")["vehicle_count"].sum().idxmax()
        stats = stats[stats["window_start"] == peak_w]

    # Calculate free-flow speed benchmark per camera
    all_events = load_events_df()
    cam_free_flow = all_events.groupby("camera_id")["speed_kmh"].apply(
        lambda s: float(np.percentile(s.dropna(), 85)) if len(s.dropna()) > 0 else 40.0
    ).to_dict()

    max_cnt = max(1, stats["vehicle_count"].max())

    points: List[Dict[str, Any]] = []
    for _, row in stats.iterrows():
        cid = row["camera_id"]
        if cid not in cams.index:
            continue

        lat = float(cams.loc[cid, "lat"])
        lon = float(cams.loc[cid, "lon"])
        cname = str(cams.loc[cid, "name"])

        # Density score (0 to 1)
        density_factor = min(1.0, max(0.0, row["vehicle_count"] / max_cnt))

        # Slowness factor (0 to 1): 0 when free flow, 1 when completely stopped
        ff_speed = cam_free_flow.get(cid, 40.0)
        slowness_factor = max(0.0, min(1.0, 1.0 - (row["avg_speed_kmh"] / max(1.0, ff_speed))))

        # Composite congestion weight
        weight = round(0.5 * density_factor + 0.5 * slowness_factor, 3)

        points.append({
            "lat": round(lat, 6),
            "lon": round(lon, 6),
            "weight": weight,
            "camera_id": cid,
            "camera_name": cname,
            "vehicle_count": int(row["vehicle_count"]),
            "avg_speed_kmh": float(row["avg_speed_kmh"]),
        })

    return pd.DataFrame(points)
