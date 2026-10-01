"""SQLAlchemy & GeoAlchemy2 ORM Data Models for ANPR System."""

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
    func,
)
from sqlalchemy.orm import relationship
from geoalchemy2 import Geometry

from backend.db import Base


class Camera(Base):
    """ANPR Camera hardware device / intersection node."""

    __tablename__ = "cameras"

    camera_id = Column(String(50), primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    lat = Column(Float, nullable=False)
    lon = Column(Float, nullable=False)
    geom = Column(Geometry("POINT", srid=4326), nullable=True)
    node_id = Column(BigInteger, nullable=True)

    # Relationships
    events = relationship("Event", back_populates="camera", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Camera {self.camera_id}: {self.name}>"


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

    # Relationships
    camera = relationship("Camera", back_populates="events")

    # Composite indexes for high-throughput trajectory & time-window queries
    __table_args__ = (
        Index("ix_events_camera_timestamp", "camera_id", "timestamp"),
        Index("ix_events_plate_timestamp", "plate", "timestamp"),
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
    alert_type = Column(String(50), nullable=False, index=True)  # 'BLACKLIST', 'ROUTE_ANOMALY', etc.
    plate = Column(String(20), nullable=False, index=True)
    camera_id = Column(String(50), nullable=True)
    timestamp = Column(DateTime, nullable=False)
    details = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)

    def __repr__(self) -> str:
        return f"<Alert {self.id}: [{self.alert_type}] {self.plate} ({self.timestamp})>"


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
    geom = Column(Geometry("LINESTRING", srid=4326), nullable=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_trajectories_plate_start", "plate", "start_time"),
    )

    def __repr__(self) -> str:
        return f"<Trajectory {self.id}: {self.plate} ({self.num_sightings} cameras, {self.avg_speed_kmh:.1f} km/h)>"
