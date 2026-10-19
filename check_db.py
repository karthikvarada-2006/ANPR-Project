import sqlite3, glob, os
db = "data/city_anpr.db"
c = sqlite3.connect(db)
q = lambda s: c.execute(s).fetchall()
print("by source:", q("select source,count(*) from events group by source"))
print("video n_frames:", q("select n_frames,count(*) from events where source='video' group by n_frames order by n_frames desc"))
print("distinct confidences:", q("select count(distinct ocr_confidence) from events where source='video'")[0][0])
print("distinct camera/time:", q("select count(*) from (select distinct camera_id,timestamp from events where source='video')")[0][0])
print("demo camera:", q("select * from cameras where camera_id='CAM_VIDEO_01'"))
print("cameras total:", q("select count(*) from cameras")[0][0])
print("sim top-5 cameras NOW:", q("select camera_id,count(*) from events where source='sim' group by camera_id order by 2 desc limit 5"))
backs = sorted(glob.glob("data/*backup*"))
print("backups:", backs)
if backs:
    b = sqlite3.connect(backs[-1])
    print("sim events in backup:", b.execute("select count(*) from events where source='sim'").fetchone()[0])
    print("sim top-5 cameras BACKUP:", b.execute("select camera_id,count(*) from events where source='sim' group by camera_id order by 2 desc limit 5").fetchall())
