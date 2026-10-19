"""SQLAlchemy ORM Data Models for ANPR System (SQLite & PostgreSQL Compatible)."""

import datetime
from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    func,
)
from sqlalchemy.orm import relationship

from backend.db import Base


class Camera(Base):
    """ANPR Camera hardware device / intersection node."""

    __tablename__ = "cameras"

    camera_id = Column(String(50), primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    lat = Column(Float, nullable=False)
    lon = Column(Float, nullable=False)
    node_id = Column(BigInteger, nullable=True)

    # Relationships
    events = relationship("Event", back_populates="camera", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Camera {self.camera_id}: {self.name} ({self.lat:.4f}, {self.lon:.4f})>"


class Event(Base):
    """Observed license plate sighting event at a specific camera."""

    __tablename__ = "events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    plate = Column(String(20), nullable=False, index=True)
    camera_id = Column(String(50), ForeignKey("cameras.camera_id", ondelete="CASCADE"), nullable=False)
    timestamp = Column(DateTime, nullable=False, index=True)
    speed_kmh = Column(Float, nullable=True)
    heading_degrees = Column(Float, nullable=True)
    lane = Column(Integer, nullable=True)
    ocr_confidence = Column(Float, nullable=True)
    source = Column(String(20), nullable=True, default="sim", index=True)  # 'sim', 'video', 'image'
    track_id = Column(Integer, nullable=True)
    n_frames = Column(Integer, nullable=True)
    vote_margin = Column(Float, nullable=True)
    best_crop_path = Column(String(255), nullable=True)

    # Relationships
    camera = relationship("Camera", back_populates="events")

    # Composite indexes for high-throughput trajectory & time-window queries
    __table_args__ = (
        Index("ix_events_camera_timestamp", "camera_id", "timestamp"),
        Index("ix_events_plate_timestamp", "plate", "timestamp"),
        Index("ix_events_source", "source"),
    )

    def __repr__(self) -> str:
        return f"<Event {self.id}: {self.plate} @ {self.camera_id} ({self.timestamp})>"


class Blacklist(Base):
    """Vehicles of interest, stolen reports, or wanted investigation targets."""

    __tablename__ = "blacklist"

    plate = Column(String(20), primary_key=True, index=True)
    reason = Column(String(255), nullable=False)
    added_at = Column(DateTime, default=func.now(), nullable=False)

    def __repr__(self) -> str:
        return f"<Blacklist {self.plate}: {self.reason}>"


class Alert(Base):
    """Real-time security alerts (Blacklist hits, Cloned plates, Speed violations)."""

    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    alert_type = Column(String(50), nullable=False, index=True)  # 'BLACKLIST', 'CLONED_PLATE', etc.
    severity = Column(String(20), nullable=False, default="LOW", index=True)  # 'HIGH', 'MEDIUM', 'LOW'
    plate = Column(String(20), nullable=False, index=True)
    camera_id = Column(String(50), nullable=True)
    timestamp = Column(DateTime, nullable=False)
    details = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)

    def __repr__(self) -> str:
        return f"<Alert {self.id}: [{self.severity}][{self.alert_type}] {self.plate} ({self.timestamp})>"


class Trajectory(Base):
    """Reconstructed cross-camera vehicle journey path."""

    __tablename__ = "trajectories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    plate = Column(String(20), nullable=False, index=True)
    start_time = Column(DateTime, nullable=False, index=True)
    end_time = Column(DateTime, nullable=False)
    duration_seconds = Column(Float, nullable=False)
    total_distance_meters = Column(Float, nullable=False)
    avg_speed_kmh = Column(Float, nullable=False)
    num_sightings = Column(Integer, nullable=False)
    camera_sequence = Column(JSON, nullable=False)
    coordinates = Column(JSON, nullable=True)  # List of [lon, lat] pairs
    created_at = Column(DateTime, default=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_trajectories_plate_start", "plate", "start_time"),
    )

    def __repr__(self) -> str:
        return f"<Trajectory {self.id}: {self.plate} ({self.num_sightings} cameras, {self.avg_speed_kmh:.1f} km/h)>"


class CameraWindowStat(Base):
    """Aggregated camera observations per time window."""

    __tablename__ = "camera_window_stats"

    id = Column(Integer, primary_key=True, autoincrement=True)
    camera_id = Column(String(50), nullable=False, index=True)
    window_start = Column(DateTime, nullable=False, index=True)
    window_end = Column(DateTime, nullable=False)
    vehicle_count = Column(Integer, nullable=False)
    unique_plates = Column(Integer, nullable=False)
    avg_speed_kmh = Column(Float, nullable=False)
    p85_speed_kmh = Column(Float, nullable=False)
    density_score = Column(Float, nullable=False)

    __table_args__ = (
        Index("ix_cws_camera_window", "camera_id", "window_start"),
    )

    def __repr__(self) -> str:
        return f"<CameraWindowStat {self.camera_id} @ {self.window_start}: {self.vehicle_count} vehicles>"


class Congestion(Base):
    """Identified urban congestion bottlenecks and hotspot windows."""

    __tablename__ = "congestion"

    id = Column(Integer, primary_key=True, autoincrement=True)
    camera_id = Column(String(50), nullable=False, index=True)
    window_start = Column(DateTime, nullable=False, index=True)
    window_end = Column(DateTime, nullable=False)
    avg_speed_kmh = Column(Float, nullable=False)
    free_flow_speed_kmh = Column(Float, nullable=False)
    vehicle_count = Column(Integer, nullable=False)
    median_count = Column(Float, nullable=False)
    severity = Column(Float, nullable=False)
    duration_minutes = Column(Integer, nullable=False)

    def __repr__(self) -> str:
        return f"<Congestion {self.camera_id} @ {self.window_start}: severity={self.severity:.2f}>"


class ODMatrix(Base):
    """Zone-to-zone Origin-Destination vehicle trip counts."""

    __tablename__ = "od_matrix"

    id = Column(Integer, primary_key=True, autoincrement=True)
    origin_zone = Column(String(100), nullable=False, index=True)
    dest_zone = Column(String(100), nullable=False, index=True)
    trip_count = Column(Integer, nullable=False)

    def __repr__(self) -> str:
        return f"<ODMatrix {self.origin_zone} -> {self.dest_zone}: {self.trip_count}>"


class RouteDensity(Base):
    """Aggregated vehicle traversal counts along road segments per window."""

    __tablename__ = "route_density"

    id = Column(Integer, primary_key=True, autoincrement=True)
    window_start = Column(DateTime, nullable=False, index=True)
    segment_id = Column(String(100), nullable=False, index=True)
    u_lat = Column(Float, nullable=False)
    u_lon = Column(Float, nullable=False)
    v_lat = Column(Float, nullable=False)
    v_lon = Column(Float, nullable=False)
    vehicle_count = Column(Integer, nullable=False)

    def __repr__(self) -> str:
        return f"<RouteDensity {self.segment_id} @ {self.window_start}: {self.vehicle_count} vehicles>"
