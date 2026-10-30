import csv
from collections import Counter, defaultdict
import json
import math
from pathlib import Path
import cv2
import numpy as np

def main():
    tracks_csv = Path("counting_work") / "tracks_example.csv"
    v1_json_path = Path(__file__).parent / "movements_cam5.json"
    gt_csv_path = Path(r"E:\AIC21_Track1_Vehicle_Counting\counting_gt_sample\counting_example_cam_5_1min.csv")
    v2_json_path = Path(__file__).parent / "movements_cam5_v2.json"

    # Load ROI and movements from v1
    with open(v1_json_path, "r", encoding="utf-8") as f:
        v1_config = json.load(f)

    roi_pts = np.array(v1_config["roi"], dtype=np.int32)
    v1_movements = v1_config["movements"]

    # Load tracks exactly as in count_clip.py
    tracks_data = defaultdict(list)
    with open(tracks_csv, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            tid = int(row["track_id"])
            tracks_data[tid].append({
                "frame_id": int(row["frame_id"]),
                "class_name": row["class_name"],
                "x1": float(row["x1"]),
                "y1": float(row["y1"]),
                "x2": float(row["x2"]),
                "y2": float(row["y2"])
            })

    MIN_FRAMES_IN_ROI = 10
    MIN_DISPLACEMENT_PX = 60

    moving_tracks = []
    for tid, frames in sorted(tracks_data.items()):
        cls_counter = Counter(f["class_name"] for f in frames)
        maj_class = cls_counter.most_common(1)[0][0]
        if maj_class == "car":
            vehicle_class_id = 1
        elif maj_class == "truck":
            vehicle_class_id = 2
        else:
            continue

        in_roi_records = []
        for f in frames:
            bc_x = (f["x1"] + f["x2"]) / 2.0
            bc_y = f["y2"]
            if cv2.pointPolygonTest(roi_pts, (float(bc_x), float(bc_y)), False) >= 0:
                in_roi_records.append((f["frame_id"], (bc_x, bc_y)))

        if len(in_roi_records) < MIN_FRAMES_IN_ROI:
            continue

        p_first = in_roi_records[0][1]
        p_last = in_roi_records[-1][1]
        disp = math.hypot(p_last[0] - p_first[0], p_last[1] - p_first[1])
        if disp < MIN_DISPLACEMENT_PX:
            continue

        first3 = [r[1] for r in in_roi_records[:3]]
        last3 = [r[1] for r in in_roi_records[-3:]]
        start_pt = (sum(p[0] for p in first3) / 3.0, sum(p[1] for p in first3) / 3.0)
        end_pt = (sum(p[0] for p in last3) / 3.0, sum(p[1] for p in last3) / 3.0)
        last_frame = in_roi_records[-1][0]

        moving_tracks.append({
            "track_id": tid,
            "vehicle_class_id": vehicle_class_id,
            "last_frame": last_frame,
            "start_pt": start_pt,
            "end_pt": end_pt
        })

    # Load GT CSV and filter frame_id < 300
    gt_rows = []
    with open(gt_csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            fid = int(row["frame_id"])
            if fid < 300:
                gt_rows.append({
                    "frame_id": fid,
                    "movement_id": int(row["movement_id"]),
                    "vehicle_class_id": int(row["vehicle_class_id"])
                })

    # Sort GT rows by frame_id
    gt_rows.sort(key=lambda r: r["frame_id"])
    total_cal_gt = len(gt_rows)

    used_tracks = set()
    matched_by_mov = defaultdict(list)
    total_matched = 0

    for grow in gt_rows:
        g_fid = grow["frame_id"]
        m_id = grow["movement_id"]

        best_track = None
        best_diff = 11  # within +/- 10 frames
        for t in moving_tracks:
            if t["track_id"] in used_tracks:
                continue
            diff = abs(t["last_frame"] - g_fid)
            if diff <= 10 and diff < best_diff:
                best_diff = diff
                best_track = t

        if best_track is not None:
            used_tracks.add(best_track["track_id"])
            matched_by_mov[m_id].append(best_track)
            total_matched += 1

    unmatched_count = total_cal_gt - total_matched

    print("=" * 70)
    print("CALIBRATION SUMMARY (frames < 300):")
    print(f"  Total calibration GT events: {total_cal_gt}")
    print(f"  Matched to a track:          {total_matched}")
    print(f"  Unmatched (misses):          {unmatched_count} ({unmatched_count / total_cal_gt * 100:.1f}%)")
    print("=" * 70)

    print("MATCHED EVENTS PER MOVEMENT AND MEDIANS:")
    v2_movements = {}
    for m_str, m_info in v1_movements.items():
        m_int = int(m_str)
        t_list = matched_by_mov[m_int]
        cnt = len(t_list)

        if cnt >= 2:
            starts_x = [t["start_pt"][0] for t in t_list]
            starts_y = [t["start_pt"][1] for t in t_list]
            ends_x = [t["end_pt"][0] for t in t_list]
            ends_y = [t["end_pt"][1] for t in t_list]

            med_start = [int(round(float(np.median(starts_x)))), int(round(float(np.median(starts_y))))]
            med_end = [int(round(float(np.median(ends_x)))), int(round(float(np.median(ends_y))))]

            v2_movements[m_str] = {
                "start": med_start,
                "end": med_end,
                "source": "calibrated"
            }
            print(f"  Movement {m_int:2d}: count={cnt:2d} -> calibrated | start={med_start}, end={med_end}")
        else:
            if cnt == 1:
                t = t_list[0]
                s_pt = [int(round(t["start_pt"][0])), int(round(t["start_pt"][1]))]
                e_pt = [int(round(t["end_pt"][0])), int(round(t["end_pt"][1]))]
                obs_info = f" (1 observed track: start={s_pt}, end={e_pt})"
            else:
                obs_info = " (0 observed tracks)"

            v2_movements[m_str] = {
                "start": m_info["start"],
                "end": m_info["end"],
                "source": "v1_visual"
            }
            print(f"  Movement {m_int:2d}: count={cnt:2d} -> kept v1_visual{obs_info} | start={m_info['start']}, end={m_info['end']}")

    # Save movements_cam5_v2.json
    v2_config = {
        "frame_size": v1_config["frame_size"],
        "roi": v1_config["roi"],
        "movements": v2_movements
    }

    with open(v2_json_path, "w", encoding="utf-8") as f:
        json.dump(v2_config, f, indent=2)

    print("=" * 70)
    print(f"Saved calibrated movements to: {v2_json_path}")
    print("=" * 70)

if __name__ == "__main__":
    main()

