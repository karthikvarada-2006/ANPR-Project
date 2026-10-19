import sqlite3
import sys
from pathlib import Path
sys.path.insert(0, str(Path(".").resolve()))

import pandas as pd
from backend.analytics import camera_stats, load_events_df, city_flow_trend
from backend.models import Event, Camera
from backend.db import SessionLocal
from backend.trajectory import get_trajectory

conn = sqlite3.connect('data/city_anpr.db')

# 1. Total sim events count
c = conn.cursor()
c.execute("SELECT count(*) FROM events WHERE source='sim'")
sim_events = c.fetchone()[0]

# 2. Total video events count
c.execute("SELECT count(*) FROM events WHERE source='video'")
video_events = c.fetchone()[0]

# 3. Simulator cameras count (excluding demo camera)
c.execute("SELECT count(*) FROM cameras WHERE camera_id LIKE 'CAM_%' AND camera_id NOT LIKE '%VIDEO%'")
cams_sim_count = c.fetchone()[0]

# 4. Total cameras count
c.execute("SELECT count(*) FROM cameras")
cams_total_count = c.fetchone()[0]

# 5. Top-5 busiest cameras from events where source='sim'
df_cams = pd.read_sql("SELECT camera_id, count(*) as count FROM events WHERE source='sim' GROUP BY camera_id ORDER BY count DESC LIMIT 5", conn)

# 6. Average city speed for source='sim'
c.execute("SELECT avg(speed_kmh) FROM events WHERE source='sim'")
avg_speed = c.fetchone()[0]

print("=" * 80)
print("=== VERIFICATION OF SIMULATED AND VIDEO SEPARATION ===")
print("=" * 80)
print(f"Events (sim):                  {sim_events:,} (Expected: 31,244)")
print(f"Events (video):                {video_events}")
print(f"Cameras (sim):                 {cams_sim_count} (Expected: 40)")
print(f"Total Cameras in DB:           {cams_total_count} (40 sim + 1 demo)")
print(f"Average City Speed (sim):      {avg_speed:.2f} km/h (Expected: 31.80 km/h)")
print("\nTop-5 Busiest Cameras (sim):")
for idx, row in df_cams.iterrows():
    print(f"  {idx+1}. {row['camera_id']}: {row['count']:,} sightings")

# Check OCR confidence in source='video' rows
c.execute("SELECT distinct ocr_confidence FROM events WHERE source='video'")
ocr_confs = [r[0] for r in c.fetchall()]
print(f"\nDistinct OCR confidence values in source='video': {len(ocr_confs)} values:")
print(f"  Min: {min(ocr_confs)*100:.1f}%, Max: {max(ocr_confs)*100:.1f}%")
print(f"  Sample values: {[round(v, 4) for v in ocr_confs[:5]]}")
has_constant_085 = (len(ocr_confs) == 1 and ocr_confs[0] == 0.85)
print(f"  Has constant 0.85 on every row? {'YES (BAD)' if has_constant_085 else 'NO (FIXED!)'}")

# Multi-frame vs single frame in video events
c.execute("SELECT count(*) FROM events WHERE source='video' AND n_frames > 1")
multi_frames_cnt = c.fetchone()[0]
print(f"\nVideo events with n_frames > 1 (multi-frame voted): {multi_frames_cnt}")

conn.close()
