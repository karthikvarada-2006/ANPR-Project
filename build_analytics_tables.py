"""Root shim to build analytics database tables and CSVs."""

from backend.build_analytics_tables import build_tables

if __name__ == "__main__":
    build_tables()
