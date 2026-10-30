import csv
from collections import Counter, defaultdict
import json
import math
from pathlib import Path
import cv2
import numpy as np

# Fixed settings
MIN_FRAMES_IN_ROI = 10
MIN_DISPLACEMENT_PX = 60
MAX_ASSIGN_SCORE = 300

def main():
    tracks_csv = Path("counting_work") / "tracks_example.csv"
    movements_json = Path(__file__).parent / "movements_cam5_v2.json"
    video_path = r"E:\AIC21_Track1_Vehicle_Counting\counting_gt_sample\counting_example_cam_5_1min.mp4"
    output_csv = Path("counting_work") / "counts_pred_v2.csv"
    output_video = Path("counting_work") / "counting_output_cam5_1min_v2.mp4"

    # Load ROI and movements from v2
    with open(movements_json, "r", encoding="utf-8") as f:
        config = json.load(f)
    roi_pts = np.array(config["roi"], dtype=np.int32)
    movements = config["movements"]

    # Read tracking detections grouped by track_id
    tracks_data = defaultdict(list)
    with open(tracks_csv, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            tid = int(row["track_id"])
            tracks_data[tid].append({
                "frame_id": int(row["frame_id"]),
                "class_name": row["class_name"],
                "conf": float(row["conf"]),
                "x1": float(row["x1"]),
                "y1": float(row["y1"]),
                "x2": float(row["x2"]),
                "y2": float(row["y2"])
            })

    # Stage tracking counts
    count_all_tracks = len(tracks_data)
    count_in_roi = 0
    count_long_enough = 0
    count_moving = 0
    count_assigned = 0

    counted_events = []

    for tid, frames in sorted(tracks_data.items()):
        # b) Class per track = majority vote across its frames
        cls_counter = Counter(f["class_name"] for f in frames)
        maj_class = cls_counter.most_common(1)[0][0]
        if maj_class == "car":
            vehicle_class_id = 1
        elif maj_class == "truck":
            vehicle_class_id = 2
        else:
            # Bus or other -> ignore track
            continue

        # a) Keep frames where bottom-center point ((x1+x2)/2, y2) is inside ROI
        in_roi_records = []
        for f in frames:
            bc_x = (f["x1"] + f["x2"]) / 2.0
            bc_y = f["y2"]
            if cv2.pointPolygonTest(roi_pts, (float(bc_x), float(bc_y)), False) >= 0:
                in_roi_records.append((f["frame_id"], (bc_x, bc_y)))

        if len(in_roi_records) == 0:
            continue
        count_in_roi += 1

        # c) Drop tracks with fewer than MIN_FRAMES_IN_ROI in-ROI frames
        if len(in_roi_records) < MIN_FRAMES_IN_ROI:
            continue
        count_long_enough += 1

        # Drop tracks whose displacement is below MIN_DISPLACEMENT_PX
        p_first = in_roi_records[0][1]
        p_last = in_roi_records[-1][1]
        disp = math.hypot(p_last[0] - p_first[0], p_last[1] - p_first[1])
        if disp < MIN_DISPLACEMENT_PX:
            continue
        count_moving += 1

        # d) start_pt = mean of first 3 in-ROI points, end_pt = mean of last 3 in-ROI points
        first3 = [r[1] for r in in_roi_records[:3]]
        last3 = [r[1] for r in in_roi_records[-3:]]
        start_pt = (sum(p[0] for p in first3) / 3.0, sum(p[1] for p in first3) / 3.0)
        end_pt = (sum(p[0] for p in last3) / 3.0, sum(p[1] for p in last3) / 3.0)

        # e) Distance to movements and assignment
        best_movement = None
        best_score = float("inf")
        for m_id_str, m_info in movements.items():
            m_start = m_info["start"]
            m_end = m_info["end"]
            score = (math.hypot(start_pt[0] - m_start[0], start_pt[1] - m_start[1]) +
                     math.hypot(end_pt[0] - m_end[0], end_pt[1] - m_end[1]))
            if score < best_score:
                best_score = score
                best_movement = int(m_id_str)

        if best_score > MAX_ASSIGN_SCORE:
            continue
        count_assigned += 1

        # f) Count frame is the last in-ROI frame of the track (the exit)
        count_frame = in_roi_records[-1][0]
        counted_events.append({
            "track_id": tid,
            "video_clip_id": 10,
            "frame_id": count_frame,
            "movement_id": best_movement,
            "vehicle_class_id": vehicle_class_id
        })

    # Sort counted events by frame_id
    counted_events.sort(key=lambda x: x["frame_id"])

    # g) Print stage counts and final counts per (movement, class)
    print("=" * 50)
    print("STAGE COUNTS (v2):")
    print(f"  All tracks:   {count_all_tracks}")
    print(f"  In ROI:       {count_in_roi}")
    print(f"  Long enough:  {count_long_enough}")
    print(f"  Moving:       {count_moving}")
    print(f"  Assigned:     {count_assigned}")
    print("=" * 50)

    final_counts = Counter((e["movement_id"], e["vehicle_class_id"]) for e in counted_events)
    print("FINAL COUNTS PER (MOVEMENT, CLASS) (v2):")
    for (m_id, c_id) in sorted(final_counts.keys()):
        c_name = "car" if c_id == 1 else "truck"
        print(f"  Movement {m_id:2d}, Class {c_id} ({c_name}): {final_counts[(m_id, c_id)]}")
    print(f"Total counted vehicles: {len(counted_events)}")
    print("=" * 50)

    # h) Write counting_work/counts_pred_v2.csv sorted by frame_id
    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["video_clip_id", "frame_id", "movement_id", "vehicle_class_id"])
        for e in counted_events:
            writer.writerow([e["video_clip_id"], e["frame_id"], e["movement_id"], e["vehicle_class_id"]])
    print(f"Saved predicted counts (v2) to: {output_csv}")

    # i) Write annotated video
    running_counts = Counter()
    for e in counted_events:
        c_letter = "C" if e["vehicle_class_id"] == 1 else "T"
        key = (e["movement_id"], e["vehicle_class_id"])
        running_counts[key] += 1
        e["label"] = f"{e['movement_id']}{c_letter}-{running_counts[key]}"

    print(f"Creating annotated video: {output_video}...")
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"Could not open video: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(str(output_video), fourcc, fps, (width, height))

    frame_idx = 0
    roi_poly = roi_pts.reshape((-1, 1, 2))

    while True:
        ret, frame = cap.read()
        if not ret or frame is None:
            break

        # Draw ROI polygon (green)
        cv2.polylines(frame, [roi_poly], isClosed=True, color=(0, 255, 0), thickness=2)

        # Draw thin red movement arrows
        for m_id_str, m_info in movements.items():
            start_p = tuple(m_info["start"])
            end_p = tuple(m_info["end"])
            cv2.arrowedLine(frame, start_p, end_p, color=(0, 0, 255), thickness=1, tipLength=0.15)

        # Active event labels: kept on screen for 15 frames
        active_by_mov = defaultdict(list)
        for e in counted_events:
            if e["frame_id"] <= frame_idx < e["frame_id"] + 15:
                active_by_mov[e["movement_id"]].append(e)

        for m_id, ev_list in active_by_mov.items():
            m_end = movements[str(m_id)]["end"]
            for idx, ev in enumerate(ev_list):
                label_text = ev["label"]
                pos = (m_end[0] + 8, m_end[1] - 8 - idx * 22)
                cv2.putText(frame, label_text, pos, cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 0, 0), 3, cv2.LINE_AA)
                cv2.putText(frame, label_text, pos, cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2, cv2.LINE_AA)

        # Total count so far displayed at top left
        total_so_far = sum(1 for e in counted_events if e["frame_id"] <= frame_idx)
        cv2.putText(frame, f"Total Count: {total_so_far}", (30, 45), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 0), 4, cv2.LINE_AA)
        cv2.putText(frame, f"Total Count: {total_so_far}", (30, 45), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2, cv2.LINE_AA)

        out.write(frame)
        frame_idx += 1

    cap.release()
    out.release()
    print(f"Annotated video saved successfully ({frame_idx} frames): {output_video}")

if __name__ == "__main__":
    main()

