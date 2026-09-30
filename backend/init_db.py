"""Database initialization script: installs PostGIS and creates all tables."""

import sys
from pathlib import Path

# Ensure project root is in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from backend.db import Base, engine
import backend.models  # Ensure all ORM models are registered with Base.metadata


def initialize_database() -> bool:
    """Connect to database, enable PostGIS extension, and create tables."""
    print("=" * 60)
    print("City ANPR Database Initialization")
    print("=" * 60)
    print(f"Connecting to database: {engine.url.render_as_string(hide_password=True)} ...")

    try:
        with engine.connect() as conn:
            # Enable PostGIS extension (PostgreSQL only)
            if "postgresql" in engine.name:
                print("Checking PostGIS extension...")
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis;"))
                conn.commit()
                print("  [OK] PostGIS extension enabled.")

        # Create all tables defined in models.py
        print("Creating database tables...")
        Base.metadata.create_all(bind=engine)

        print("\nAll database tables verified and created successfully:")
        for table_name in Base.metadata.tables:
            print(f"  - {table_name}")

        print("=" * 60)
        print("Database initialization complete.")
        print("=" * 60)
        return True

    except OperationalError as err:
        print("\n" + "!" * 60)
        print("[ERROR] Could not connect to PostgreSQL database!")
        print("!" * 60)
        print(f"Details: {err}\n")
        print("Troubleshooting Steps:")
        print("1. If using Docker, ensure Docker Desktop is running and start the database container:")
        print("     docker compose up -d")
        print("2. Check if the container is healthy:")
        print("     docker compose ps")
        print("3. Check your .env file credentials and port 5432 availability.")
        print("!" * 60)
        return False
    except Exception as exc:
        print(f"[ERROR] Database initialization failed: {exc}")
        return False


def main() -> int:
    success = initialize_database()
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
