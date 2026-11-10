import sqlite3
con = sqlite3.connect("file:data/city_anpr.db?mode=ro", uri=True)
cur = con.cursor()

cur.execute("SELECT camera_id, name, lat, lon FROM cameras WHERE camera_id LIKE '%VIDEO%'")
print("Video cameras:", cur.fetchall())

cur.execute("SELECT plate, ocr_confidence, vote_margin FROM events WHERE source='video' ORDER BY ocr_confidence ASC LIMIT 5")
print("Lowest conf video events:", cur.fetchall())

cur.execute("SELECT COUNT(DISTINCT plate) FROM events WHERE source='sim'")
print("Distinct sim plates:", cur.fetchone()[0])

cur.execute("SELECT COUNT(DISTINCT plate) FROM events WHERE source='video'")
print("Distinct video plates:", cur.fetchone()[0])

# Check exact events count vs FACTS
cur.execute("SELECT COUNT(*) FROM events WHERE source='sim'")
print("Sim events:", cur.fetchone()[0])

# Peak hour check
cur.execute("""
    SELECT strftime('%H', timestamp) AS hour, COUNT(*) AS cnt
    FROM events WHERE source='sim'
    GROUP BY hour ORDER BY cnt DESC LIMIT 5
""")
print("Top hours by sim events:", cur.fetchall())

# Unique vehicles (from analytics)
cur.execute("SELECT COUNT(DISTINCT plate) FROM events WHERE source='sim'")
print("Unique sim plates:", cur.fetchone()[0])

# Alert details
cur.execute("SELECT alert_type, COUNT(*) FROM alerts GROUP BY alert_type")
print("Alerts by type:", cur.fetchall())

# Blacklist sample
cur.execute("SELECT plate FROM blacklist LIMIT 5")
print("Blacklist sample:", cur.fetchall())

con.close()
print("Done.")

