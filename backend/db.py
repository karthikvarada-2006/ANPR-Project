"""Database connection, SQLAlchemy engine, and session management."""

import os
from pathlib import Path
from typing import Generator

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session

# Load environment variables from .env located at the project root
ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")

# Primary connection string (defaults to SQLite for zero-setup local development)
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite:///data/city_anpr.db",
)

connect_args = {}
engine_kwargs = {"echo": False}

if DATABASE_URL.startswith("sqlite"):
    # If SQLite path is relative, resolve relative to project root
    if DATABASE_URL.startswith("sqlite:///") and not DATABASE_URL.startswith("sqlite:////"):
        rel_path = DATABASE_URL.replace("sqlite:///", "")
        abs_db_path = (ROOT_DIR / rel_path).resolve()
        abs_db_path.parent.mkdir(parents=True, exist_ok=True)
        DATABASE_URL = f"sqlite:///{abs_db_path.as_posix()}"
    connect_args["check_same_thread"] = False
else:
    # Normalize postgresql:// to postgresql+psycopg2://
    if DATABASE_URL.startswith("postgresql://"):
        DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://", 1)
    engine_kwargs["pool_pre_ping"] = True

# Create database engine
engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    **engine_kwargs,
)

# Session factory for local transactions
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

# Declarative base for ORM models
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """Provide a transactional database session scope."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
