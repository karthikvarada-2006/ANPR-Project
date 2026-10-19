"""FastAPI Backend Application for City-Wide ANPR Surveillance & Analytics System.

Exposes RESTful endpoints and real-time WebSockets:
- GET /api/health
- GET /api/cameras
- GET /api/trajectory/{plate}
- GET /api/plates/search
- GET /api/analytics/summary
- GET /api/analytics/flow-trend
- GET /api/analytics/camera-stats
- GET /api/analytics/congestion
- GET /api/analytics/od-matrix
- GET /api/analytics/route-density
- GET /api/analytics/heatmap
- GET /api/alerts
- GET, POST, DELETE /api/blacklist
- WebSocket /ws/live
"""

from __future__ import annotations

import asyncio
import base64
from contextlib import asynccontextmanager
import datetime
import json
import math
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Union

import cv2
import numpy as np
import pandas as pd
from fastapi import (
    Depends,
    FastAPI,
    File,
    HTTPException,
    Query,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import delete, func
from sqlalchemy.orm import Session

# Ensure project root is in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from pipeline.plate_reader import PlateReader

from backend.alert_engine import AlertEngine
from backend.alert_rules import RuleContext, _to_datetime
from backend.analytics import (
    camera_stats,
    city_flow_trend,
    congestion_hotspots,
    heatmap_points,
    load_cameras_df,
    origin_destination_matrix,
    route_density,
)
from backend.db import SessionLocal
from backend.models import Alert, Blacklist, Camera, Event
from backend.plate_utils import (
    CANONICAL_MAP,
    find_similar_plates,
    get_all_distinct_plates,
    normalize_plate,
)
from backend.trajectory import (
    get_camera_paths,
    get_cameras_info,
    get_road_graph,
    get_trajectory,
)
from simulator.config import EVENTS_PATH


# ==============================================================================
# Database Dependency
# ==============================================================================
def get_db():
    """FastAPI database session dependency."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ==============================================================================
# PlateReader Singleton (Loaded Once at Startup)
# ==============================================================================
_plate_reader_instance: Optional[PlateReader] = None

def get_plate_reader() -> PlateReader:
    """Returns singleton instance of PlateReader (loaded once, shared across requests)."""
    global _plate_reader_instance
    if _plate_reader_instance is None:
        det_path = ROOT_DIR / "models" / "plate_detector.pt"
        ocr_d = ROOT_DIR / "models" / "plate_ocr"
        _plate_reader_instance = PlateReader(
            detector_path=det_path,
            ocr_dir=ocr_d,
            conf_thresh=0.25,
            device="auto",
            padding_ratio=0.05,
        )
    return _plate_reader_instance


# ==============================================================================
# Startup & Lifespan Event Handler
# ==============================================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Warm up road graph, camera paths cache, surveillance rule context, and PlateReader on startup."""
    print("Warming up ANPR system caches (road graph, camera paths, rule context, PlateReader)...")
    try:
        get_road_graph()
        get_cameras_info()
        get_camera_paths()
        RuleContext.get_instance()
        get_plate_reader()
        print("  [OK] Graph, camera paths, rule context, and PlateReader loaded once at startup.")
    except Exception as exc:
        print(f"  [WARNING] Cache warmup warning: {exc}")
    yield
    print("FastAPI ANPR application shutdown complete.")


# ==============================================================================
# FastAPI Application Configuration
# ==============================================================================
app = FastAPI(
    title="City ANPR Surveillance & Traffic Intelligence API",
    description="High-throughput automated number-plate recognition, trajectory reconstruction, and surveillance alerting.",
    version="1.0.0",
    lifespan=lifespan,
)

# Enable CORS for frontend clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==============================================================================
# Pydantic Response & Request Models
# ==============================================================================
class HealthResponse(BaseModel):
    status: str
    database: str
    timestamp: str
    cameras_count: int
    events_count: int
    blacklist_count: int


class CameraItem(BaseModel):
    id: str
    camera_id: str
    name: str
    lat: float
    lon: float
    node_id: Optional[int] = None


class TrajectoryPoint(BaseModel):
    time: str
    timestamp: str
    camera: str
    camera_id: str
    name: str
    lat: float
    lon: float
    heading: float
    compass: str
    speed: float
    speed_kmh: float
    confidence: float
    plate_read: str


class FlaggedHop(BaseModel):
    previous_camera: str
    camera_id: str
    time_delta_seconds: float
    distance_meters: float
    implied_speed_kmh: float
    reason: str


class TripItem(BaseModel):
    trip_id: Union[int, str]
    track_id: Optional[str] = None
    start_time: str
    end_time: str
    duration_seconds: float
    total_distance_km: float
    avg_speed_kmh: float
    num_sightings: int
    points: List[TrajectoryPoint]
    route_geometry: List[List[float]]
    flagged_hops: List[FlaggedHop] = []
    long_trip: Optional[bool] = False
    speed_source: Optional[str] = None


class TrajectoryResponse(BaseModel):
    plate: str
    matched_plates: List[str]
    total_trips: int
    total_distance_km: float
    total_duration_seconds: float
    trips: List[TripItem]
    points: List[TrajectoryPoint]
    route_geometry: List[List[float]]
    flagged_hops: List[FlaggedHop] = []


class PlateSearchItem(BaseModel):
    plate: str
    count: int
    distance: float


class AnalyticsSummaryResponse(BaseModel):
    total_events: int
    total_cameras: int
    total_unique_plates: int
    total_blacklist_targets: int
    total_alerts: int
    average_speed_kmh: float
    congested_hotspots_count: int
    peak_hour: Optional[str] = None
    timestamp: str


class FlowTrendItem(BaseModel):
    window_start: str
    window_end: str
    vehicle_count: int
    unique_plates: int
    avg_speed_kmh: float
    p85_speed_kmh: float


class CameraStatItem(BaseModel):
    camera_id: str
    camera_name: str
    window_start: str
    window_end: str
    vehicle_count: int
    unique_plates: int
    avg_speed_kmh: float
    p85_speed_kmh: float
    density_score: float
    lat: Optional[float] = None
    lon: Optional[float] = None


class CongestionItem(BaseModel):
    camera_id: str
    camera_name: str
    window_start: str
    window_end: str
    avg_speed_kmh: float
    free_flow_speed_kmh: float
    deficit_kmh: Optional[float] = None
    vehicle_count: int
    median_count: float
    severity: float
    duration_minutes: int


class RouteDensityItem(BaseModel):
    window_start: str
    segment_id: str
    from_camera_id: Optional[str] = None
    from_camera_name: Optional[str] = None
    to_camera_id: Optional[str] = None
    to_camera_name: Optional[str] = None
    u_lat: float
    u_lon: float
    v_lat: float
    v_lon: float
    vehicle_count: int


class HeatmapPointItem(BaseModel):
    lat: float
    lon: float
    weight: float
    camera_id: str
    camera_name: str
    vehicle_count: int
    avg_speed_kmh: float


class AlertItem(BaseModel):
    id: int
    alert_type: str
    severity: str
    plate: str
    camera_id: Optional[str] = None
    timestamp: str
    details: Optional[Dict[str, Any]] = None
    created_at: str


class BlacklistItem(BaseModel):
    plate: str
    reason: str
    added_at: str


class BlacklistCreateRequest(BaseModel):
    plate: str = Field(..., description="Vehicle registration plate")
    reason: str = Field(..., description="Reason for surveillance flagging")


# ==============================================================================
# REST API Endpoints
# ==============================================================================

@app.get("/api/health", response_model=HealthResponse, tags=["System"])
def get_health(db: Session = Depends(get_db)):
    """Health check endpoint: checks database connectivity and returns table counts."""
    try:
        cams_cnt = db.query(func.count(Camera.camera_id)).scalar() or 0
        events_cnt = db.query(func.count(Event.id)).scalar() or 0
        bl_cnt = db.query(func.count(Blacklist.plate)).scalar() or 0
        db_status = "connected"
    except Exception as exc:
        db_status = f"unhealthy: {exc}"
        cams_cnt, events_cnt, bl_cnt = 0, 0, 0

    return HealthResponse(
        status="ok",
        database=db_status,
        timestamp=datetime.datetime.now().isoformat(),
        cameras_count=cams_cnt,
        events_count=events_cnt,
        blacklist_count=bl_cnt,
    )


@app.get("/api/cameras", response_model=List[CameraItem], tags=["Cameras"])
def list_cameras(
    include_demo: bool = False,
    source: Optional[str] = "sim",
    db: Session = Depends(get_db),
):
    """List deployed ANPR cameras with coordinates and intersection names.
    
    By default, returns the 40 simulation cameras (excluding demo cameras)
    to keep baseline statistics and road network map clean. Pass include_demo=True
    or source='all' to include demo video cameras.
    """
    # Simulated camera query from SQLite database
    query = db.query(Camera)
    if not include_demo and source == "sim":
        query = query.filter(Camera.camera_id.like("CAM_%"), ~Camera.camera_id.like("%VIDEO%"), ~Camera.name.ilike("%demo%"))
    cams = query.order_by(Camera.camera_id.asc()).all()
    if not cams:
        # Fallback to CSV if database was not yet loaded
        df = load_cameras_df()
        return [
            CameraItem(
                id=str(r["camera_id"]),
                camera_id=str(r["camera_id"]),
                name=str(r["name"]),
                lat=float(r["lat"]),
                lon=float(r["lon"]),
                node_id=int(r.get("node_id", 0)) if pd.notnull(r.get("node_id")) else None,
            )
            for _, r in df.iterrows()
        ]

    return [
        CameraItem(
            id=c.camera_id,
            camera_id=c.camera_id,
            name=c.name,
            lat=c.lat,
            lon=c.lon,
            node_id=c.node_id,
        )
        for c in cams
    ]


@app.get("/api/trajectory/{plate}", response_model=TrajectoryResponse, tags=["Trajectories"])
def get_vehicle_trajectory(
    plate: str,
    fuzzy: bool = Query(True, description="Enable OCR confusable plate variant searching"),
    start: Optional[str] = Query(None, description="Start timestamp (YYYY-MM-DD HH:MM:SS)"),
    end: Optional[str] = Query(None, description="End timestamp (YYYY-MM-DD HH:MM:SS)"),
    source: Optional[str] = Query("sim", description="Event source filter: 'sim' (default), 'video', 'image', or 'all'"),
    db: Session = Depends(get_db),
):
    """Reconstruct complete vehicle trajectory, route geometry, and speed violations."""
    source_val = None if (source and source.lower() in ["all", "none", "any"]) else source
    traj = get_trajectory(plate=plate, start=start, end=end, fuzzy=fuzzy, db=db, source=source_val)

    # Fallback to any source if not found in sim
    if traj["total_trips"] == 0 and source == "sim":
        alt_traj = get_trajectory(plate=plate, start=start, end=end, fuzzy=fuzzy, db=db, source=None)
        if alt_traj["total_trips"] > 0:
            traj = alt_traj

    if traj["total_trips"] == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Plate '{plate}' not found.",
        )

    trips_list: List[TripItem] = []
    all_points: List[TrajectoryPoint] = []
    all_coords: List[List[float]] = []

    for t in traj["trips"]:
        trip_pts: List[TrajectoryPoint] = []
        for p in t["points"]:
            ts_str = p["timestamp"].isoformat() if hasattr(p["timestamp"], "isoformat") else str(p["timestamp"])
            pt = TrajectoryPoint(
                time=ts_str,
                timestamp=ts_str,
                camera=str(p["camera_id"]),
                camera_id=str(p["camera_id"]),
                name=str(p.get("name", "")),
                lat=float(p["lat"]),
                lon=float(p["lon"]),
                heading=float(p.get("heading", 0.0)),
                compass=str(p.get("compass", "N")),
                speed=float(p.get("speed_kmh", 0.0)),
                speed_kmh=float(p.get("speed_kmh", 0.0)),
                confidence=float(p.get("confidence", 1.0)),
                plate_read=str(p.get("plate_read", plate)),
            )
            trip_pts.append(pt)
            all_points.append(pt)

        trip_flagged: List[FlaggedHop] = [
            FlaggedHop(
                previous_camera=str(h["previous_camera"]),
                camera_id=str(h["camera_id"]),
                time_delta_seconds=float(h["time_delta_seconds"]),
                distance_meters=float(h["distance_meters"]),
                implied_speed_kmh=float(h["implied_speed_kmh"]),
                reason=str(h["reason"]),
            )
            for h in t.get("flagged_hops", [])
        ]

        trip_geom = t.get("route_geometry", [])
        for pt in trip_geom:
            if not all_coords or all_coords[-1] != pt:
                all_coords.append(pt)

        trips_list.append(
            TripItem(
                trip_id=int(t["trip_id"]),
                start_time=str(t["start_time"]),
                end_time=str(t["end_time"]),
                duration_seconds=float(t["duration_seconds"]),
                total_distance_km=float(t["total_distance_km"]),
                avg_speed_kmh=float(t["avg_speed_kmh"]),
                num_sightings=int(t["num_sightings"]),
                points=trip_pts,
                route_geometry=trip_geom,
                flagged_hops=trip_flagged,
            )
        )

    all_flagged: List[FlaggedHop] = [
        FlaggedHop(
            previous_camera=str(h["previous_camera"]),
            camera_id=str(h["camera_id"]),
            time_delta_seconds=float(h["time_delta_seconds"]),
            distance_meters=float(h["distance_meters"]),
            implied_speed_kmh=float(h["implied_speed_kmh"]),
            reason=str(h["reason"]),
        )
        for h in traj.get("flagged_hops", [])
    ]

    total_dist = sum(t.total_distance_km for t in trips_list)
    total_dur = sum(t.duration_seconds for t in trips_list)

    return TrajectoryResponse(
        plate=traj["plate"],
        matched_plates=traj["matched_plates"],
        total_trips=len(trips_list),
        total_distance_km=round(total_dist, 3),
        total_duration_seconds=round(total_dur, 1),
        trips=trips_list,
        points=all_points,
        route_geometry=all_coords,
        flagged_hops=all_flagged,
    )


@app.get("/api/plates/search", response_model=List[PlateSearchItem], tags=["Plates"])
def search_plates(
    q: str = Query(..., min_length=1, description="License plate query or prefix"),
    limit: int = Query(10, ge=1, le=50, description="Max results to return"),
    db: Session = Depends(get_db),
):
    """Plate search with fuzzy OCR error tolerance and prefix autocomplete."""
    norm_q = normalize_plate(q)
    if not norm_q:
        return []

    # 1. First attempt fuzzy weighted edit-distance search
    matches = find_similar_plates(norm_q, max_distance=1.0, db=db)
    if matches:
        return [
            PlateSearchItem(plate=m.plate, count=m.count, distance=round(m.distance, 2))
            for m in matches[:limit]
        ]

    # 2. If short query or prefix, search substring/prefix across distinct plates
    all_plates = get_all_distinct_plates(db=db)
    prefix_matches = [
        (p, count)
        for p, count in all_plates
        if norm_q in p or p.startswith(norm_q)
    ]
    # Sort by exact prefix match, then count descending
    prefix_matches.sort(key=lambda x: (not x[0].startswith(norm_q), -x[1]))

    return [
        PlateSearchItem(plate=p, count=c, distance=0.0)
        for p, c in prefix_matches[:limit]
    ]


_CACHED_FUZZY_UNIQUE_PLATES: Optional[int] = None


def get_fuzzy_unique_plates_count(db: Session, source: Optional[str] = "sim") -> int:
    """Count unique vehicles using canonical OCR-confusable mapping to merge noisy reads."""
    global _CACHED_FUZZY_UNIQUE_PLATES
    if _CACHED_FUZZY_UNIQUE_PLATES is not None and source == "sim":
        return _CACHED_FUZZY_UNIQUE_PLATES

    q = db.query(Event.plate)
    if source is not None:
        q = q.filter(Event.source == source)
    distinct_plates = [r[0] for r in q.distinct()]
    canon_set = {p.translate(CANONICAL_MAP) for p in distinct_plates if p}
    cnt = len(canon_set)
    if source == "sim":
        _CACHED_FUZZY_UNIQUE_PLATES = cnt
    return cnt


@app.get("/api/analytics/overview", response_model=AnalyticsSummaryResponse, tags=["Analytics"])
@app.get("/api/analytics/summary", response_model=AnalyticsSummaryResponse, tags=["Analytics"])
def get_analytics_summary(
    source: Optional[str] = Query("sim", description="Event source: sim (default), video, or all"),
    db: Session = Depends(get_db),
):
    """Summary overview of city traffic volume, active blacklist, and alerts."""
    source_val = None if (source and source.lower() in ["all", "none", "any"]) else source

    events_q = db.query(func.count(Event.id))
    speed_q = db.query(func.avg(Event.speed_kmh))
    if source_val is not None:
        events_q = events_q.filter(Event.source == source_val)
        speed_q = speed_q.filter(Event.source == source_val)

    events_cnt = events_q.scalar() or 0

    # Simulation cameras count: 40 city cameras (excluding demo/video cameras)
    cams_cnt = db.query(func.count(Camera.camera_id)).filter(
        Camera.camera_id.like("CAM_%"),
        ~Camera.camera_id.like("%VIDEO%"),
        ~Camera.camera_id.like("%DEMO%"),
    ).scalar() or 40

    unique_plates = get_fuzzy_unique_plates_count(db=db, source=source_val)
    bl_cnt = db.query(func.count(Blacklist.plate)).scalar() or 0
    alerts_cnt = db.query(func.count(Alert.id)).scalar() or 0
    avg_speed = speed_q.scalar() or 0.0

    # Count congested hotspots
    cong_df = congestion_hotspots(window_minutes=15, source=source_val)
    cong_cnt = len(cong_df)

    return AnalyticsSummaryResponse(
        total_events=events_cnt,
        total_cameras=cams_cnt,
        total_unique_plates=unique_plates,
        total_blacklist_targets=bl_cnt,
        total_alerts=alerts_cnt,
        average_speed_kmh=round(float(avg_speed), 1),
        congested_hotspots_count=cong_cnt,
        timestamp=datetime.datetime.now().isoformat(),
    )


@app.get("/api/analytics/hourly-volume", response_model=List[FlowTrendItem], tags=["Analytics"])
@app.get("/api/analytics/flow-trend", response_model=List[FlowTrendItem], tags=["Analytics"])
def get_flow_trend(
    window: int = Query(15, ge=5, le=60, description="Window size in minutes"),
    start: Optional[str] = Query(None, description="Start timestamp filter"),
    end: Optional[str] = Query(None, description="End timestamp filter"),
):
    """City-wide aggregate vehicle flow and speed trends over time."""
    df = city_flow_trend(window_minutes=window, start=start, end=end)
    records = []
    for _, r in df.iterrows():
        records.append(
            FlowTrendItem(
                window_start=str(r["window_start"]),
                window_end=str(r["window_end"]),
                vehicle_count=int(r["vehicle_count"]),
                unique_plates=int(r["unique_plates"]),
                avg_speed_kmh=float(r["avg_speed_kmh"]),
                p85_speed_kmh=float(r["p85_speed_kmh"]),
            )
        )
    return records


@app.get("/api/analytics/busiest-cameras", response_model=List[CameraStatItem], tags=["Analytics"])
@app.get("/api/analytics/camera-stats", response_model=List[CameraStatItem], tags=["Analytics"])
def get_camera_stats(
    window: int = Query(15, ge=5, le=60, description="Window size in minutes"),
    start: Optional[str] = Query(None, description="Start timestamp filter"),
    end: Optional[str] = Query(None, description="End timestamp filter"),
):
    """Traffic volume, unique vehicles, speed, and normalized density per camera."""
    df = camera_stats(window_minutes=window, start=start, end=end)
    records = []
    for _, r in df.iterrows():
        records.append(
            CameraStatItem(
                camera_id=str(r["camera_id"]),
                camera_name=str(r["camera_name"]),
                window_start=str(r["window_start"]),
                window_end=str(r["window_end"]),
                vehicle_count=int(r["vehicle_count"]),
                unique_plates=int(r["unique_plates"]),
                avg_speed_kmh=float(r["avg_speed_kmh"]),
                p85_speed_kmh=float(r["p85_speed_kmh"]),
                density_score=float(r["density_score"]),
            )
        )
    return records


@app.get("/api/analytics/congestion", response_model=List[CongestionItem], tags=["Analytics"])
def get_congestion(
    window: int = Query(15, ge=5, le=60, description="Window size in minutes"),
    start: Optional[str] = Query(None, description="Start timestamp filter"),
    end: Optional[str] = Query(None, description="End timestamp filter"),
):
    """Identified bottlenecks where speed is below 60% free-flow and volume exceeds median."""
    df = congestion_hotspots(window_minutes=window, start=start, end=end)
    records = []
    for _, r in df.iterrows():
        records.append(
            CongestionItem(
                camera_id=str(r["camera_id"]),
                camera_name=str(r["camera_name"]),
                window_start=str(r["window_start"]),
                window_end=str(r["window_end"]),
                avg_speed_kmh=float(r["avg_speed_kmh"]),
                free_flow_speed_kmh=float(r["free_flow_speed_kmh"]),
                vehicle_count=int(r["vehicle_count"]),
                median_count=float(r["median_count"]),
                severity=float(r["severity"]),
                duration_minutes=int(r["duration_minutes"]),
            )
        )
    return records


@app.get("/api/analytics/od-matrix", tags=["Analytics"])
def get_od_matrix(
    start: Optional[str] = Query(None, description="Start timestamp filter"),
    end: Optional[str] = Query(None, description="End timestamp filter"),
):
    """Zone-to-zone Origin-Destination vehicle journey counts."""
    pivot = origin_destination_matrix(start=start, end=end, n_zones=8)
    zones = list(pivot.index)
    matrix_dict = {z: {col: int(pivot.loc[z, col]) for col in pivot.columns} for z in zones}
    return {
        "zones": zones,
        "matrix": matrix_dict,
        "total_trips": int(pivot.values.sum()),
    }


@app.get("/api/analytics/route-density", response_model=List[RouteDensityItem], tags=["Analytics"])
def get_route_density(
    start: Optional[str] = Query(None, description="Start timestamp filter"),
    end: Optional[str] = Query(None, description="End timestamp filter"),
):
    """Aggregated vehicle traversal loads on specific road network segments."""
    df = route_density(window_minutes=60, start=start, end=end)
    records = []
    for _, r in df.iterrows():
        records.append(
            RouteDensityItem(
                window_start=str(r["window_start"]),
                segment_id=str(r["segment_id"]),
                from_camera_id=str(r.get("from_camera_id", "")) if pd.notna(r.get("from_camera_id")) else None,
                from_camera_name=str(r.get("from_camera_name", "")) if pd.notna(r.get("from_camera_name")) else None,
                to_camera_id=str(r.get("to_camera_id", "")) if pd.notna(r.get("to_camera_id")) else None,
                to_camera_name=str(r.get("to_camera_name", "")) if pd.notna(r.get("to_camera_name")) else None,
                u_lat=float(r["u_lat"]),
                u_lon=float(r["u_lon"]),
                v_lat=float(r["v_lat"]),
                v_lon=float(r["v_lon"]),
                vehicle_count=int(r["vehicle_count"]),
            )
        )
    return records


@app.get("/api/analytics/heatmap", response_model=List[HeatmapPointItem], tags=["Analytics"])
def get_heatmap(
    window: Optional[str] = Query(None, description="Specific 15-minute window timestamp"),
    start: Optional[str] = Query(None, description="Start timestamp filter"),
    end: Optional[str] = Query(None, description="End timestamp filter"),
):
    """Geospatial traffic density and slowness heatmap points with weights between 0 and 1."""
    df = heatmap_points(window=window, start=start, end=end)
    records = []
    for _, r in df.iterrows():
        records.append(
            HeatmapPointItem(
                lat=float(r["lat"]),
                lon=float(r["lon"]),
                weight=float(r["weight"]),
                camera_id=str(r["camera_id"]),
                camera_name=str(r["camera_name"]),
                vehicle_count=int(r["vehicle_count"]),
                avg_speed_kmh=float(r["avg_speed_kmh"]),
            )
        )
    return records


@app.get("/api/alerts", response_model=List[AlertItem], tags=["Alerts"])
def list_alerts(
    severity: Optional[str] = Query(None, description="Filter by severity (HIGH, MEDIUM, LOW)"),
    type: Optional[str] = Query(None, description="Filter by alert type (e.g. BLACKLIST, CLONED_PLATE)"),
    plate: Optional[str] = Query(None, description="Filter by vehicle plate"),
    limit: int = Query(100, ge=1, le=1000, description="Max alerts to return"),
    db: Session = Depends(get_db),
):
    """Query triggered surveillance alerts with optional severity, type, and plate filters."""
    query = db.query(Alert)

    if severity:
        query = query.filter(Alert.severity == severity.upper())
    if type:
        query = query.filter(Alert.alert_type == type.upper())
    if plate:
        norm_p = normalize_plate(plate)
        query = query.filter(Alert.plate == norm_p)

    alerts = query.order_by(Alert.timestamp.desc(), Alert.id.desc()).limit(limit).all()

    return [
        AlertItem(
            id=a.id,
            alert_type=a.alert_type,
            severity=a.severity,
            plate=a.plate,
            camera_id=a.camera_id,
            timestamp=a.timestamp.isoformat() if hasattr(a.timestamp, "isoformat") else str(a.timestamp),
            details=a.details if isinstance(a.details, dict) else {},
            created_at=a.created_at.isoformat() if hasattr(a.created_at, "isoformat") else str(a.created_at),
        )
        for a in alerts
    ]


@app.get("/api/blacklist", response_model=List[BlacklistItem], tags=["Blacklist"])
def list_blacklist(
    db: Session = Depends(get_db),
):
    """List all vehicles on the security watchlist."""
    items = db.query(Blacklist).order_by(Blacklist.added_at.desc()).all()
    return [
        BlacklistItem(
            plate=b.plate,
            reason=b.reason,
            added_at=b.added_at.isoformat() if hasattr(b.added_at, "isoformat") else str(b.added_at),
        )
        for b in items
    ]


@app.post("/api/blacklist", response_model=BlacklistItem, status_code=status.HTTP_201_CREATED, tags=["Blacklist"])
def add_to_blacklist(
    payload: BlacklistCreateRequest,
    db: Session = Depends(get_db),
):
    """Add or update a target vehicle on the security blacklist."""
    norm_p = normalize_plate(payload.plate)
    if not norm_p:
        raise HTTPException(status_code=400, detail="Invalid license plate string.")

    existing = db.query(Blacklist).filter(Blacklist.plate == norm_p).first()
    now = datetime.datetime.now()

    if existing:
        existing.reason = payload.reason
        existing.added_at = now
        db.commit()
        db.refresh(existing)
        item = existing
    else:
        new_entry = Blacklist(plate=norm_p, reason=payload.reason, added_at=now)
        db.add(new_entry)
        db.commit()
        db.refresh(new_entry)
        item = new_entry

    # Update in-memory rule context cache
    RuleContext.get_instance().blacklist[norm_p] = payload.reason

    return BlacklistItem(
        plate=item.plate,
        reason=item.reason,
        added_at=item.added_at.isoformat() if hasattr(item.added_at, "isoformat") else str(item.added_at),
    )


@app.delete("/api/blacklist/{plate}", tags=["Blacklist"])
@app.delete("/api/blacklist", tags=["Blacklist"])
def remove_from_blacklist(
    plate: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Remove a vehicle registration plate from the security blacklist."""
    if not plate:
        raise HTTPException(status_code=400, detail="Plate parameter is required.")

    norm_p = normalize_plate(plate)
    target = db.query(Blacklist).filter(Blacklist.plate == norm_p).first()
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Plate '{norm_p}' not found on security blacklist.",
        )

    db.delete(target)
    db.commit()

    # Remove from in-memory rule cache
    RuleContext.get_instance().blacklist.pop(norm_p, None)

    return {"status": "ok", "message": f"Plate '{norm_p}' removed from blacklist."}


def sanitize_json_payload(obj: Any) -> Any:
    """Recursively convert float NaN/Inf to None so Starlette sends strictly valid standard JSON."""
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    if isinstance(obj, dict):
        return {k: sanitize_json_payload(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [sanitize_json_payload(v) for v in obj]
    return obj


# ==============================================================================
# Plate Reading & Video ANPR Events Endpoints
# ==============================================================================
def _levenshtein_distance(s1: str, s2: str) -> int:
    """Computes edit distance between two strings."""
    m, n = len(s1), len(s2)
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(m + 1):
        dp[i][0] = i
    for j in range(n + 1):
        dp[0][j] = j
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            cost = 0 if s1[i - 1] == s2[j - 1] else 1
            dp[i][j] = min(dp[i - 1][j] + 1, dp[i][j - 1] + 1, dp[i - 1][j - 1] + cost)
    return dp[m][n]


@app.post("/api/plates/read", tags=["Plate Reader"])
async def read_uploaded_plate(
    file: UploadFile = File(..., description="Vehicle image file (JPG or PNG, max 10MB)"),
    db: Session = Depends(get_db),
):
    """Accepts an uploaded vehicle image in memory (max 10MB, JPG/PNG only, never saved to disk),
    detects plates with YOLOv8, recognizes characters with fine-tuned fast-plate-ocr,
    checks blacklist (exact or fuzzy), counts known database sightings, and returns
    detections plus the annotated image as Base64.
    """
    filename = file.filename or ""
    ext = Path(filename).suffix.lower()

    allowed_exts = {".jpg", ".jpeg", ".png"}
    if ext and ext not in allowed_exts:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file format '{ext}'. Only JPG and PNG images are supported.",
        )

    # Enforce 10 MB file size limit in memory
    max_size = 10 * 1024 * 1024  # 10 MB
    contents = await file.read()
    if len(contents) > max_size:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Image file exceeds 10 MB limit.",
        )

    if len(contents) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded image file is empty.",
        )

    # Decode image directly from memory buffer
    nparr = np.frombuffer(contents, np.uint8)
    img_bgr = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img_bgr is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not decode image file. Please provide a valid JPG or PNG.",
        )

    # Load singleton PlateReader (loaded once at startup)
    reader = get_plate_reader()
    detections = reader.read_image(img_bgr, is_bgr=True)

    # Load blacklist records for exact and fuzzy matching
    bl_items = db.query(Blacklist).all()
    blacklist_records = {b.plate: b.reason for b in bl_items}

    annotated_bgr = img_bgr.copy()
    plates_output = []

    for det in detections:
        plate_text = det["text"]
        raw_box = det["box"]  # [x1, y1, x2, y2]
        det_conf = round(float(det["detector_confidence"]), 4)
        ocr_conf = round(float(det["ocr_confidence"]), 4)

        # Blacklist check: exact or fuzzy (edit distance <= 1 or confusable letters)
        is_bl = False
        bl_reason = None

        if plate_text in blacklist_records:
            is_bl = True
            bl_reason = blacklist_records[plate_text]
        else:
            norm_p = normalize_plate(plate_text)
            for bl_p, reason in blacklist_records.items():
                if _levenshtein_distance(plate_text, bl_p) <= 1 or norm_p == normalize_plate(bl_p):
                    is_bl = True
                    bl_reason = f"Fuzzy match to '{bl_p}': {reason}"
                    break

        # Number of known sightings in the database
        sightings_count = db.query(func.count(Event.id)).filter(Event.plate == plate_text).scalar() or 0

        plates_output.append({
            "box": [round(float(c), 1) for c in raw_box],
            "detector_confidence": det_conf,
            "plate": plate_text,
            "ocr_confidence": ocr_conf,
            "is_blacklisted": is_bl,
            "blacklist_reason": bl_reason,
            "known_sightings": sightings_count,
        })

        # Render visual annotations
        x1, y1, x2, y2 = [int(round(coord)) for coord in raw_box]
        box_color = (0, 0, 255) if is_bl else (0, 220, 100)  # Red if BL, Green if ok
        cv2.rectangle(annotated_bgr, (x1, y1), (x2, y2), box_color, 3)

        label_text = f"{plate_text} ({int(ocr_conf * 100)}%)" + (" [BLACKLIST]" if is_bl else "")
        (txt_w, txt_h), _ = cv2.getTextSize(label_text, cv2.FONT_HERSHEY_SIMPLEX, 0.65, 2)
        badge_y1 = max(0, y1 - txt_h - 10)
        cv2.rectangle(
            annotated_bgr,
            (x1, badge_y1),
            (x1 + txt_w + 12, badge_y1 + txt_h + 10),
            box_color,
            -1,
        )
        cv2.putText(
            annotated_bgr,
            label_text,
            (x1 + 6, badge_y1 + txt_h + 4),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            (255, 255, 255) if is_bl else (0, 0, 0),
            2,
            cv2.LINE_AA,
        )

    # Encode annotated image as Base64 in memory
    success, enc_buf = cv2.imencode(".jpg", annotated_bgr, [cv2.IMWRITE_JPEG_QUALITY, 85])
    base64_str = f"data:image/jpeg;base64,{base64.b64encode(enc_buf.tobytes()).decode('utf-8')}" if success else ""

    return {
        "detected_count": len(plates_output),
        "plates": plates_output,
        "annotated_image_base64": base64_str,
    }


@app.get("/api/plates/sample-images", tags=["Plate Reader"])
def get_sample_test_images():
    """Returns 10 sample test images from the held-out test split for quick testing."""
    split_file = ROOT_DIR / "data" / "processed" / "split_groups.json"
    samples = []
    if split_file.exists():
        try:
            with open(split_file, "r", encoding="utf-8") as f:
                meta = json.load(f)
            test_keys = [
                k for k, v in meta.get("image_to_split", {}).items()
                if v == "test" and (k.endswith(".jpg") or k.endswith(".png"))
            ]
            seen = set()
            for k in test_keys:
                p = ROOT_DIR / "data" / "raw" / k
                if p.exists() and p.name not in seen:
                    seen.add(p.name)
                    rel_p = str(p.relative_to(ROOT_DIR)).replace("\\", "/")
                    samples.append({
                        "id": f"sample_{len(samples)+1}",
                        "name": f"Test Sample {len(samples)+1} ({p.stem})",
                        "filename": p.name,
                        "path": rel_p,
                        "url": f"/{rel_p}",
                    })
                    if len(samples) >= 10:
                        break
        except Exception:
            pass

    # Fallback if split_groups.json didn't yield 10
    if len(samples) < 10:
        for p in sorted((ROOT_DIR / "data" / "raw" / "indian-number-plates-dataset" / "video_images").glob("video2_*.jpg")):
            if p.name not in [s["filename"] for s in samples]:
                rel_p = str(p.relative_to(ROOT_DIR)).replace("\\", "/")
                samples.append({
                    "id": f"sample_{len(samples)+1}",
                    "name": f"Test Sample {len(samples)+1} ({p.stem})",
                    "filename": p.name,
                    "path": rel_p,
                    "url": f"/{rel_p}",
                })
                if len(samples) >= 10:
                    break

    return {"count": len(samples), "samples": samples}


@app.get("/api/events", tags=["Events"])
def get_events(
    source: Optional[str] = Query(None, description="Filter by event source: 'video', 'sim', or 'image'"),
    plate: Optional[str] = Query(None, description="Filter by plate number (exact or partial)"),
    camera: Optional[str] = Query(None, description="Filter by camera_id (e.g. CAM_001)"),
    limit: int = Query(100, ge=1, le=1000, description="Max number of events to return"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    db: Session = Depends(get_db),
):
    """Query ANPR events with filtering by source ('video', 'sim'), plate, and camera."""
    q = db.query(Event)
    if source:
        q = q.filter(Event.source == source)
    if plate:
        clean_p = normalize_plate(plate)
        q = q.filter(Event.plate.like(f"%{clean_p}%"))
    if camera:
        q = q.filter(Event.camera_id == camera)

    total_count = q.count()
    events = (
        q.order_by(Event.timestamp.desc(), Event.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    results = []
    for ev in events:
        results.append({
            "id": ev.id,
            "plate": ev.plate,
            "camera_id": ev.camera_id,
            "timestamp": ev.timestamp.isoformat() if hasattr(ev.timestamp, "isoformat") else str(ev.timestamp),
            "source": ev.source or "sim",
            "speed_kmh": ev.speed_kmh,
            "heading_degrees": ev.heading_degrees,
            "lane": ev.lane,
            "ocr_confidence": ev.ocr_confidence,
            "track_id": ev.track_id,
            "n_frames": ev.n_frames,
            "vote_margin": ev.vote_margin,
            "best_crop_path": ev.best_crop_path,
        })

    return {
        "total": total_count,
        "limit": limit,
        "offset": offset,
        "events": results,
    }


# ==============================================================================
# Real-Time Surveillance WebSocket Stream
# ==============================================================================
@app.websocket("/ws/live")
async def websocket_live_surveillance(
    websocket: WebSocket,
    speed: float = Query(200.0, description="Simulation speed multiplier (0 = as fast as possible)"),
):
    """Real-time ANPR live stream: replays events.csv through AlertEngine and pushes alerts & progress."""
    await websocket.accept()

    if not EVENTS_PATH.exists():
        await websocket.send_json({"type": "error", "message": "events.csv not found"})
        await websocket.close()
        return

    # Load events for streaming
    df = pd.read_csv(EVENTS_PATH)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.sort_values("timestamp").reset_index(drop=True)

    engine = AlertEngine(dedup_minutes=10.0, context=RuleContext.get_instance())
    total_events = len(df)
    prev_sim_time: Optional[datetime.datetime] = None
    alerts_triggered_count = 0

    try:
        # Initial greeting with simulation metadata
        await websocket.send_json({
            "type": "connected",
            "message": "Connected to ANPR live surveillance stream",
            "total_events": total_events,
            "speed_multiplier": speed,
            "sim_start": df.iloc[0]["timestamp"].isoformat(),
            "sim_end": df.iloc[-1]["timestamp"].isoformat(),
        })

        for idx, row in df.iterrows():
            ev = row.to_dict()
            curr_sim_time = ev["timestamp"]

            # Simulated clock sleep pacing
            if speed > 0 and prev_sim_time is not None:
                delta_sec = (curr_sim_time - prev_sim_time).total_seconds()
                if delta_sec > 0:
                    sleep_time = min(delta_sec / speed, 0.25)
                    await asyncio.sleep(sleep_time)

            prev_sim_time = curr_sim_time

            # Evaluate rules through AlertEngine
            alerts = engine.process_event(ev, save_to_db=False)
            if alerts:
                for alert in alerts:
                    alerts_triggered_count += 1
                    # Format timestamp
                    ts = alert.get("timestamp")
                    ts_str = ts.isoformat() if isinstance(ts, datetime.datetime) else str(ts)
                    alert_payload = sanitize_json_payload(dict(alert))
                    alert_payload["timestamp"] = ts_str

                    await websocket.send_json({
                        "type": "alert",
                        "data": alert_payload,
                    })

            # Send periodic progress updates every 250 events
            if (idx + 1) % 250 == 0 or idx == total_events - 1:
                await websocket.send_json({
                    "type": "progress",
                    "events_processed": idx + 1,
                    "total_events": total_events,
                    "percent_complete": round(((idx + 1) / total_events) * 100.0, 1),
                    "simulated_clock": curr_sim_time.isoformat(),
                    "alerts_count": alerts_triggered_count,
                })

        # Final completion event
        await websocket.send_json({
            "type": "complete",
            "events_processed": total_events,
            "total_alerts": alerts_triggered_count,
            "message": "Surveillance replay stream finished successfully.",
        })

    except WebSocketDisconnect:
        # Clean disconnect when client leaves
        pass
    except Exception as exc:
        try:
            await websocket.send_json({"type": "error", "message": str(exc)})
        except Exception:
            pass
    finally:
        try:
            await websocket.close()
        except Exception:
            pass


# ==============================================================================
# Static Files Mount for Frontend Web Dashboard & Media Assets
# ==============================================================================
from fastapi.staticfiles import StaticFiles

DATA_DIR = ROOT_DIR / "data"
if DATA_DIR.exists():
    app.mount("/data", StaticFiles(directory=str(DATA_DIR)), name="data_static")

FRONTEND_DIR = ROOT_DIR / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
