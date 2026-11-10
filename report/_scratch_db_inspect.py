import sqlite3, json

con = sqlite3.connect("file:data/city_anpr.db?mode=ro", uri=True)
cur = con.cursor()

# Tables
cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
tables = [r[0] for r in cur.fetchall()]
print("TABLES:", tables)

# Row counts
for t in tables:
    cur.execute(f'SELECT COUNT(*) FROM "{t}"')
    print(f"  {t}: {cur.fetchone()[0]} rows")

# Schema of each table
print("\n=== SCHEMA ===")
for t in tables:
    cur.execute(f"PRAGMA table_info('{t}')")
    cols = cur.fetchall()
    print(f"\n{t}:")
    for c in cols:
        print(f"  {c[1]} {c[2]} {'NOT NULL' if c[3] else ''} {'PK' if c[5] else ''}")

# Sample source types in events
cur.execute("SELECT source, COUNT(*) FROM events GROUP BY source ORDER BY source")
print("\n=== events.source counts ===")
for r in cur.fetchall():
    print(f"  {r[0]}: {r[1]}")

# Camera count
cur.execute("SELECT COUNT(*) FROM cameras")
print(f"\nTotal cameras: {cur.fetchone()[0]}")

# Distinct plates in events
cur.execute("SELECT COUNT(DISTINCT plate) FROM events WHERE source='sim'")
print(f"Distinct sim plates: {cur.fetchone()[0]}")

cur.execute("SELECT COUNT(DISTINCT plate) FROM events WHERE source='video'")
print(f"Distinct video plates: {cur.fetchone()[0]}")

# Alerts table
cur.execute("SELECT alert_type, COUNT(*) FROM alerts GROUP BY alert_type ORDER BY alert_type")
print("\n=== alerts by type ===")
for r in cur.fetchall():
    print(f"  {r[0]}: {r[1]}")

# Total events
cur.execute("SELECT COUNT(*) FROM events")
print(f"\nTotal events: {cur.fetchone()[0]}")

# Video events sample
cur.execute("SELECT plate, camera_id, timestamp, source, ocr_confidence, vote_margin FROM events WHERE source='video' LIMIT 5")
print("\n=== Sample video events ===")
for r in cur.fetchall():
    print(f"  {r}")

# Blacklist
cur.execute("SELECT COUNT(*) FROM blacklist")
print(f"\nBlacklist entries: {cur.fetchone()[0]}")

# Sample cameras
cur.execute("SELECT camera_id, lat, lon FROM cameras LIMIT 5")
print("\n=== Sample cameras ===")
for r in cur.fetchall():
    print(f"  {r}")

con.close()
print("\nDone.")

