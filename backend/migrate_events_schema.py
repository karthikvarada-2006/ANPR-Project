"""Safe Schema Migration Script for ANPR SQLite Database.

Adds nullable columns to the 'events' table:
- source (values: 'sim', 'video', 'image'; existing rows become 'sim')
- track_id (INTEGER, nullable)
- n_frames (INTEGER, nullable)
- vote_margin (FLOAT, nullable)
- best_crop_path (VARCHAR(255), nullable)

Safety Guarantees:
1. Automatically creates a backup of the existing SQLite .db file BEFORE making any alterations.
2. Checks column presence using 'PRAGMA table_info' so it is completely safe to run multiple times (idempotent).
3. Updates all existing rows where source IS NULL to 'sim'.
4. Verifies that the row count before and after the migration is 100% identical (no data loss).
"""

import datetime
import os
from pathlib import Path
import shutil
import sqlite3
import sys

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.db import DATABASE_URL


def get_sqlite_path() -> Path:
    """Extracts absolute SQLite file path from DATABASE_URL or defaults to data/city_anpr.db."""
    if "sqlite:///" in DATABASE_URL:
        raw_path = DATABASE_URL.split("sqlite:///")[-1]
        db_path = Path(raw_path)
        if not db_path.is_absolute():
            db_path = PROJECT_ROOT / db_path
        return db_path
    return PROJECT_ROOT / "data" / "city_anpr.db"


def run_migration() -> bool:
    """Executes the safe database schema migration."""
    db_path = get_sqlite_path()

    print("\n" + "=" * 80)
    print("=== ANPR DATABASE SCHEMA MIGRATION: EVENTS TABLE ===")
    print("=" * 80)
    print(f"Target Database: {db_path.resolve()}")

    if not db_path.exists():
        print(f"[ERROR] Database file not found at: {db_path.resolve()}")
        print("Please ensure the database exists or run: python backend/init_db.py")
        return False

    # 1. Create a safe backup before doing any modifications
    timestamp_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = db_path.parent / f"{db_path.name}.bak"
    timestamped_backup = db_path.parent / f"{db_path.stem}_backup_{timestamp_str}.db"

    print(f"\n1. Creating database backup...")
    shutil.copy2(db_path, backup_path)
    shutil.copy2(db_path, timestamped_backup)
    print(f"   [OK] Primary backup saved:      {backup_path.resolve()}")
    print(f"   [OK] Timestamped backup saved:  {timestamped_backup.resolve()}")

    # Connect to SQLite database
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    try:
        # 2. Check initial row count
        cursor.execute("SELECT count(*) FROM events")
        initial_row_count = cursor.fetchone()[0]
        print(f"\n2. Initial 'events' row count: {initial_row_count:,}")

        # 3. Inspect existing columns
        cursor.execute("PRAGMA table_info(events)")
        existing_columns = {row[1]: row[2] for row in cursor.fetchall()}
        print(f"\n3. Existing columns in 'events': {', '.join(existing_columns.keys())}")

        # Columns to add
        new_columns = [
            ("source", "VARCHAR(20) DEFAULT 'sim'"),
            ("track_id", "INTEGER"),
            ("n_frames", "INTEGER"),
            ("vote_margin", "FLOAT"),
            ("best_crop_path", "VARCHAR(255)"),
        ]

        print("\n4. Applying schema alterations...")
        added_count = 0
        for col_name, col_def in new_columns:
            if col_name not in existing_columns:
                alter_stmt = f"ALTER TABLE events ADD COLUMN {col_name} {col_def}"
                print(f"   -> Adding column '{col_name}': {alter_stmt}")
                cursor.execute(alter_stmt)
                added_count += 1
            else:
                print(f"   -> Column '{col_name}' already exists. Skipping.")

        # 5. Populate default 'sim' for existing rows
        print("\n5. Normalizing source values for existing records...")
        cursor.execute("UPDATE events SET source = 'sim' WHERE source IS NULL OR source = ''")
        updated_rows = cursor.rowcount
        print(f"   [OK] Updated {updated_rows:,} existing rows to source='sim'.")

        # 6. Create index on source for fast filtering by video/sim
        print("\n6. Creating index on 'events(source)'...")
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_events_source ON events(source)")

        conn.commit()

        # 7. Post-migration verification
        cursor.execute("SELECT count(*) FROM events")
        final_row_count = cursor.fetchone()[0]

        cursor.execute("SELECT source, count(*) FROM events GROUP BY source")
        source_counts = cursor.fetchall()

        print("\n" + "=" * 80)
        print("=== MIGRATION VERIFICATION & INTEGRITY CHECK ===")
        print("=" * 80)
        print(f"  Initial row count:  {initial_row_count:,}")
        print(f"  Final row count:    {final_row_count:,}")
        print(f"  Row count delta:    {final_row_count - initial_row_count} (zero data loss)")
        print("\n  Events breakdown by source:")
        for src, cnt in source_counts:
            print(f"    - source='{src}': {cnt:,} rows")
        print("=" * 80)

        assert final_row_count == initial_row_count, "Integrity Error: Row count mismatch after migration!"
        print("\n[SUCCESS] Migration completed safely with zero data loss!\n")
        return True

    except Exception as exc:
        conn.rollback()
        print(f"\n[ERROR] Migration failed: {exc}")
        print("Restoring database from backup...")
        shutil.copy2(backup_path, db_path)
        print("Database restored to pre-migration state.")
        return False
    finally:
        cursor.close()
        conn.close()


def main():
    success = run_migration()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
