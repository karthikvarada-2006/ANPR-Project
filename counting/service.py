import argparse
from collections import Counter, defaultdict
import csv
import json
import math
import os
from pathlib import Path
import re
import subprocess
import time
import cv2
import imageio_ffmpeg
import numpy as np
from ultralytics import YOLO

# Configuration
VIDEO_ROOT = os.environ.get("AIC_VIDEO_ROOT", r"E:\AIC21_Track1_Vehicle_Counting")
MIN_FRAMES_IN_ROI = 10
MIN_DISPLACEMENT_PX = 60  # defined for 1280 px width; scaled by frame_width / 1280.0
MAX_ASSIGN_SCORE = 300

def run_clip(video_name: str, start_sec: float = 0.0, seconds: float = 30.0) -> dict:
    """
    Run vehicle detection, tracking, ROI filtering, and counting on a video clip.
    
    Args:
        video_name: Filename of the video in VIDEO_ROOT/Dataset_A (e.g., 'cam_1.mp4').
        start_sec: Start time offset in seconds.
        seconds: Duration in seconds to process (capped at 60).
    
    Returns:
        dict containing count metadata matching counts.json.
    """
    # 1) Validation
    if not video_name or not isinstance(video_name, str):
        raise ValueError("video_name must be a non-empty string.")
    
    # Reject path separators
    if "/" in video_name or "\\" in video_name or os.sep in video_name:
        raise ValueError(f"Invalid video_name '{video_name}': path separators are not permitted.")
    
    if not video_name.lower().endswith(".mp4"):
        raise ValueError(f"Invalid video_name '{video_name}': only .mp4 files are supported.")
    
    dataset_a_dir = Path(VIDEO_ROOT) / "Dataset_A"
    video_path = dataset_a_dir / video_name
    if not video_path.is_file():
        raise FileNotFoundError(f"Video file not found in Dataset_A: {video_path}")
    
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Could not open video file: {video_path}")
    
    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_video_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    
    if fps <= 0 or frame_width <= 0 or frame_height <= 0:
        cap.release()
        raise RuntimeError(f"Invalid video properties: fps={fps}, width={frame_width}, height={frame_height}")
    
    # Cap seconds at 60
    start_sec = max(0.0, float(start_sec))
    seconds = min(60.0, max(0.0, float(seconds)))
    
    start_frame = int(round(start_sec * fps))
    num_frames_to_read = int(round(seconds * fps))
    
    if start_frame >= total_video_frames:
        cap.release()
        raise ValueError(f"start_sec {start_sec}s corresponds to frame {start_frame}, but video only has {total_video_frames} frames.")
    
    num_frames_to_read = min(num_frames_to_read, total_video_frames - start_frame)
    if num_frames_to_read <= 0:
        cap.release()
        raise ValueError("Calculated frame count to read is 0.")
    
    # 2) ROI Loading & Scaling
    # base is camera name without _dawn, _rain or _snow suffix
    stem = Path(video_name).stem
    base = re.sub(r"(_dawn|_rain|_snow)$", "", stem)
    roi_file = Path(VIDEO_ROOT) / "ROIs" / f"{base}.txt"
    if not roi_file.is_file():
        cap.release()
        raise FileNotFoundError(f"ROI file not found: {roi_file}")
    
    roi_points = []
    with open(roi_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = [p.strip() for p in line.split(",") if p.strip()]
            if len(parts) >= 2:
                x, y = float(parts[0]), float(parts[1])
                if x < 0 or x >= frame_width or y < 0 or y >= frame_height:
                    print(f"Warning: ROI point ({x}, {y}) lies outside frame dimensions ({frame_width}, {frame_height})", flush=True)
                roi_points.append([int(round(x)), int(round(y))])
    
    if len(roi_points) < 3:
        cap.release()
        raise ValueError(f"ROI polygon in {roi_file} contains fewer than 3 valid vertices.")
    
    roi_pts = np.array(roi_points, dtype=np.int32)
    
    # Displacement threshold scaled to frame_width / 1280.0
    min_displacement = MIN_DISPLACEMENT_PX * (frame_width / 1280.0)
    
    is_cam5 = (video_name == "cam_5.mp4")
    movements = {}
    if is_cam5:
        movements_file = Path(__file__).parent / "movements_cam5_v2.json"
        if not movements_file.is_file():
            cap.release()
            raise FileNotFoundError(f"Movements config file not found: {movements_file}")
        with open(movements_file, "r", encoding="utf-8") as f:
            cam5_config = json.load(f)
        movements = cam5_config.get("movements", {})
    
    # Setup output directory
    start_str = str(int(start_sec)) if float(start_sec).is_integer() else f"{start_sec}"
    sec_str = str(int(seconds)) if float(seconds).is_integer() else f"{seconds}"
    output_dir = Path("counting_outputs") / f"{video_name}_{start_str}_{sec_str}"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    tracks_csv_path = output_dir / "tracks.csv"
    counts_json_path = output_dir / "counts.json"
    temp_annotated_mp4 = output_dir / "_temp_annotated.mp4"
    output_mp4_path = output_dir / "output.mp4"
    
    print(f"=== Running Vehicle Counting Service ===", flush=True)
    print(f"Video: {video_name} ({frame_width}x{frame_height} @ {fps:.2f} fps)")
    print(f"Clip: start_sec={start_sec}s, duration={seconds}s, frames={num_frames_to_read} (frame {start_frame} to {start_frame + num_frames_to_read - 1})")
    print(f"ROI: {len(roi_points)} vertices from {roi_file.name}")
    print(f"Scaled Min Displacement: {min_displacement:.2f} px", flush=True)
    
    # 3) Tracking with YOLOv8s + ByteTrack
    start_time = time.time()
    print("Loading YOLOv8s pretrained COCO model...", flush=True)
    model = YOLO("yolov8s.pt")
    
    cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
    
    tracks_data = defaultdict(list)
    unique_tracks = set()
    frames_processed = 0
    
    with open(tracks_csv_path, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["frame_id", "track_id", "class_name", "conf", "x1", "y1", "x2", "y2"])
        
        for frame_idx in range(num_frames_to_read):
            ret, frame = cap.read()
            if not ret or frame is None:
                break
            
            frames_processed += 1
            if frames_processed % 100 == 0:
                print(f"Progress: Processed {frames_processed}/{num_frames_to_read} frames...", flush=True)
            
            # Built-in ByteTrack tracker, classes: car(2), bus(5), truck(7), conf=0.25, imgsz=960
            results = model.track(
                source=frame,
                tracker="bytetrack.yaml",
                persist=True,
                classes=[2, 5, 7],
                conf=0.25,
                imgsz=960,
                verbose=False,
            )
            
            r = results[0]
            if r.boxes is not None and len(r.boxes) > 0 and r.boxes.id is not None:
                track_ids = r.boxes.id.int().cpu().tolist()
                confs = r.boxes.conf.cpu().tolist()
                cls_ids = r.boxes.cls.int().cpu().tolist()
                boxes = r.boxes.xyxy.cpu().tolist()
                
                for tid, cid, conf, (x1, y1, x2, y2) in zip(track_ids, cls_ids, confs, boxes):
                    class_name = model.names.get(cid, str(cid))
                    unique_tracks.add(tid)
                    
                    writer.writerow([
                        frame_idx,
                        tid,
                        class_name,
                        f"{conf:.4f}",
                        f"{x1:.2f}",
                        f"{y1:.2f}",
                        f"{x2:.2f}",
                        f"{y2:.2f}"
                    ])
                    
                    tracks_data[tid].append({
                        "frame_id": frame_idx,
                        "class_name": class_name,
                        "conf": conf,
                        "x1": x1,
                        "y1": y1,
                        "x2": x2,
                        "y2": y2
                    })
    
    # 4) Filtering and Counting Logic
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
        
        # Drop tracks whose displacement is below min_displacement
        p_first = in_roi_records[0][1]
        p_last = in_roi_records[-1][1]
        disp = math.hypot(p_last[0] - p_first[0], p_last[1] - p_first[1])
        if disp < min_displacement:
            continue
        count_moving += 1
        
        # Count frame is the last in-ROI frame of the track (exit)
        count_frame = in_roi_records[-1][0]
        exit_pos = (int(round(p_last[0])), int(round(p_last[1])))
        
        if is_cam5:
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
            
            counted_events.append({
                "track_id": tid,
                "frame_id": count_frame,
                "movement_id": best_movement,
                "vehicle_class_id": vehicle_class_id,
                "exit_pos": exit_pos
            })
        else:
            counted_events.append({
                "track_id": tid,
                "frame_id": count_frame,
                "movement_id": None,
                "vehicle_class_id": vehicle_class_id,
                "exit_pos": exit_pos
            })
    
    counted_events.sort(key=lambda x: x["frame_id"])
    
    num_cars = sum(1 for e in counted_events if e["vehicle_class_id"] == 1)
    num_trucks = sum(1 for e in counted_events if e["vehicle_class_id"] == 2)
    total_count = num_cars + num_trucks
    
    movement_counts = None
    if is_cam5:
        movement_counts = {}
        for m_id_str in sorted(movements.keys(), key=int):
            m_cars = sum(1 for e in counted_events if e["movement_id"] == int(m_id_str) and e["vehicle_class_id"] == 1)
            m_trucks = sum(1 for e in counted_events if e["movement_id"] == int(m_id_str) and e["vehicle_class_id"] == 2)
            movement_counts[m_id_str] = {
                "cars": m_cars,
                "trucks": m_trucks,
                "total": m_cars + m_trucks
            }
    
    # Label field
    if is_cam5:
        label_text = "REAL video; movement counts evaluated only on the 1-min example clip (F1 65.1% on the test half)"
    else:
        label_text = "REAL video, UNEVALUATED: no ground truth for this camera, clip counts only, not the video total"
    
    # 5) Annotate and write output video
    running_counts = Counter()
    for e in counted_events:
        c_letter = "C" if e["vehicle_class_id"] == 1 else "T"
        if is_cam5 and e["movement_id"] is not None:
            key = (e["movement_id"], e["vehicle_class_id"])
            running_counts[key] += 1
            e["label"] = f"{e['movement_id']}{c_letter}-{running_counts[key]}"
        else:
            key = e["vehicle_class_id"]
            running_counts[key] += 1
            e["label"] = f"{c_letter}-{running_counts[key]}"
    
    print(f"Creating annotated video...", flush=True)
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(str(temp_annotated_mp4), fourcc, fps, (frame_width, frame_height))
    
    cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
    roi_poly = roi_pts.reshape((-1, 1, 2))
    
    for frame_idx in range(frames_processed):
        ret, frame = cap.read()
        if not ret or frame is None:
            break
        
        # Draw ROI polygon (green)
        cv2.polylines(frame, [roi_poly], isClosed=True, color=(0, 255, 0), thickness=2)
        
        if is_cam5:
            # Draw thin red movement arrows
            for m_id_str, m_info in movements.items():
                start_p = tuple(m_info["start"])
                end_p = tuple(m_info["end"])
                cv2.arrowedLine(frame, start_p, end_p, color=(0, 0, 255), thickness=1, tipLength=0.15)
            
            # Active event labels: kept on screen for 15 frames near movement end
            active_by_mov = defaultdict(list)
            for e in counted_events:
                if e["frame_id"] <= frame_idx < e["frame_id"] + 15:
                    active_by_mov[e["movement_id"]].append(e)
            
            for m_id, ev_list in active_by_mov.items():
                m_end = movements[str(m_id)]["end"]
                for idx, ev in enumerate(ev_list):
                    text = ev["label"]
                    pos = (m_end[0] + 8, m_end[1] - 8 - idx * 22)
                    cv2.putText(frame, text, pos, cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 0, 0), 3, cv2.LINE_AA)
                    cv2.putText(frame, text, pos, cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2, cv2.LINE_AA)
        else:
            # Non-cam5: show label near vehicle exit point for 15 frames
            active_events = [e for e in counted_events if e["frame_id"] <= frame_idx < e["frame_id"] + 15]
            for idx, ev in enumerate(active_events):
                text = ev["label"]
                pos = (ev["exit_pos"][0] + 8, ev["exit_pos"][1] - 8 - (idx % 3) * 20)
                cv2.putText(frame, text, pos, cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 0, 0), 3, cv2.LINE_AA)
                cv2.putText(frame, text, pos, cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2, cv2.LINE_AA)
        
        # Running total at top-left
        total_so_far = sum(1 for e in counted_events if e["frame_id"] <= frame_idx)
        cv2.putText(frame, f"Total Count: {total_so_far}", (30, 45), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 0), 4, cv2.LINE_AA)
        cv2.putText(frame, f"Total Count: {total_so_far}", (30, 45), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2, cv2.LINE_AA)
        
        out.write(frame)
    
    cap.release()
    out.release()
    
    # Re-encode to H.264 using imageio-ffmpeg for browser playback
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    reencode_cmd = [
        ffmpeg_exe,
        "-y",
        "-i", str(temp_annotated_mp4),
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        str(output_mp4_path)
    ]
    reencode_res = subprocess.run(reencode_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if reencode_res.returncode != 0:
        print(f"Warning: ffmpeg re-encoding failed: {reencode_res.stderr.decode('utf-8', errors='ignore')}")
    else:
        if temp_annotated_mp4.is_file():
            temp_annotated_mp4.unlink()
    
    total_runtime = time.time() - start_time
    
    # 6) counts.json construction
    start_sec_val = int(start_sec) if float(start_sec).is_integer() else start_sec
    seconds_val = int(seconds) if float(seconds).is_integer() else seconds
    
    counts_data = {
        "video": video_name,
        "start_sec": start_sec_val,
        "seconds": seconds_val,
        "fps": round(fps, 2),
        "frames_processed": frames_processed,
        "runtime_seconds": round(total_runtime, 2),
        "cars": num_cars,
        "trucks": num_trucks,
        "total": total_count,
        "movement_counts": movement_counts,
        "label": label_text
    }
    
    with open(counts_json_path, "w", encoding="utf-8") as f:
        json.dump(counts_data, f, indent=2)
    
    # 7) Print summary and full counts
    print("=" * 60, flush=True)
    print(f"STAGE COUNTS FOR {video_name} (start={start_sec_val}s, duration={seconds_val}s):", flush=True)
    print(f"  All tracks:   {count_all_tracks}", flush=True)
    print(f"  In ROI:       {count_in_roi}", flush=True)
    print(f"  Long enough:  {count_long_enough}", flush=True)
    print(f"  Moving:       {count_moving}", flush=True)
    if is_cam5:
        print(f"  Assigned:     {count_assigned}", flush=True)
    print("=" * 60, flush=True)
    print("FINAL COUNTS:", flush=True)
    print(f"  Cars:   {num_cars}", flush=True)
    print(f"  Trucks: {num_trucks}", flush=True)
    print(f"  Total:  {total_count}", flush=True)
    if is_cam5 and movement_counts:
        print("PER-MOVEMENT COUNTS:", flush=True)
        for m_id_str, m_dict in movement_counts.items():
            print(f"  Movement {int(m_id_str):2d}: Total {m_dict['total']} (Cars: {m_dict['cars']}, Trucks: {m_dict['trucks']})", flush=True)
    print("=" * 60, flush=True)
    print("counts.json content:", flush=True)
    print(json.dumps(counts_data, indent=2), flush=True)
    print("=" * 60, flush=True)
    print(f"Outputs saved to: {output_dir}", flush=True)
    print(f"  tracks.csv: {tracks_csv_path}", flush=True)
    print(f"  counts.json: {counts_json_path}", flush=True)
    print(f"  output.mp4: {output_mp4_path}", flush=True)
    
    return counts_data

def main():
    parser = argparse.ArgumentParser(description="Vehicle Counting Service CLI")
    parser.add_argument("video_name", type=str, help="Video filename in Dataset_A (e.g., cam_1.mp4)")
    parser.add_argument("--start", type=float, default=0.0, help="Start time in seconds (default: 0.0)")
    parser.add_argument("--seconds", type=float, default=30.0, help="Duration in seconds (default: 30.0, max: 60.0)")
    
    args = parser.parse_args()
    run_clip(video_name=args.video_name, start_sec=args.start, seconds=args.seconds)

if __name__ == "__main__":
    main()

