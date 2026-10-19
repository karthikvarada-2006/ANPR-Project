"""Video ANPR Pipeline with Multi-Frame ByteTrack Tracking and Plate Voting.

Processes a video file (MP4, AVI, MKV) OR a folder of frame images:
1. Detects vehicle license plates frame-by-frame with PlateReader (YOLOv8 + 5% padding).
2. Tracks plates across frames with Ultralytics ByteTrack (persist=True).
3. Gathers per-track readings: (frame_idx, crop, text, ocr_confidence, detector_confidence).
4. Aggregates multi-frame readings with PlateVoting (character-position weighted voting).
5. Emits events when a track is lost for N frames or stream finishes, saving results to:
   data/video_events/<name>_events.csv and crops to data/video_events/crops/.
"""

import argparse
import datetime
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional, Tuple, Union

import cv2
import numpy as np
import pandas as pd

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from pipeline.plate_reader import PlateReader
from pipeline.voting import PlateVoting, Track


def compute_box_iou(box1: List[float], box2: List[float]) -> float:
    """Computes Intersection over Union (IoU) between two bounding boxes [x1, y1, x2, y2]."""
    xa = max(box1[0], box2[0])
    ya = max(box1[1], box2[1])
    xb = min(box1[2], box2[2])
    yb = min(box1[3], box2[3])

    inter_w = max(0.0, xb - xa)
    inter_h = max(0.0, yb - ya)
    inter_area = inter_w * inter_h

    area1 = max(0.0, box1[2] - box1[0]) * max(0.0, box1[3] - box1[1])
    area2 = max(0.0, box2[2] - box2[0]) * max(0.0, box2[3] - box2[1])
    union = area1 + area2 - inter_area
    return float(inter_area / union) if union > 0 else 0.0


def natural_sort_key(s: Union[str, Path]) -> List[Any]:
    """Helper for natural alphanumeric sorting of frame filenames (e.g. frame_2 before frame_10)."""
    text = str(s)
    return [int(c) if c.isdigit() else c.lower() for c in re.split(r"(\d+)", text)]


def get_frame_source(source_path: Path) -> Tuple[str, List[Path], Optional[cv2.VideoCapture], float, int]:
    """Inspects source input and initializes video capture or sorted list of frame image files.
    
    Returns:
        (source_type, frame_files, cap, detected_fps, total_frames)
    """
    if not source_path.exists():
        raise FileNotFoundError(f"Source path not found: {source_path.resolve()}")

    if source_path.is_file():
        # Video file input (e.g. .mp4, .avi)
        cap = cv2.VideoCapture(str(source_path))
        if not cap.isOpened():
            raise RuntimeError(f"Could not open video file: {source_path}")
        fps = float(cap.get(cv2.CAP_PROP_FPS))
        if fps <= 0 or np.isnan(fps):
            fps = 30.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        return "video", [], cap, fps, total_frames

    elif source_path.is_dir():
        # Directory of frame images
        valid_exts = {".jpg", ".jpeg", ".png", ".bmp"}
        files = sorted(
            [p for p in source_path.iterdir() if p.is_file() and p.suffix.lower() in valid_exts],
            key=natural_sort_key,
        )
        if not files:
            raise FileNotFoundError(f"No image frames found in directory: {source_path}")
        return "folder", files, None, 30.0, len(files)

    else:
        raise ValueError(f"Invalid source path: {source_path}")


def process_video_pipeline(
    source: Union[str, Path],
    camera_id: str = "CAM_001",
    start_time: str = "2026-10-04 12:00:00",
    fps: Optional[float] = None,
    stride: int = 1,
    max_lost_frames: int = 30,
    min_confidence: float = 0.35,
    detector_path: Union[str, Path] = "models/plate_detector.pt",
    ocr_dir: Union[str, Path] = "models/plate_ocr",
    output_dir: Union[str, Path] = "data/video_events",
    max_frames: Optional[int] = None,
    source_label: str = "video",
) -> Dict[str, Any]:
    """Executes the end-to-end video tracking and voting pipeline on a video or image folder.
    
    Args:
        source: Video file path or directory of frame images.
        camera_id: Identifier for camera source.
        start_time: Starting timestamp string in ISO or 'YYYY-MM-DD HH:MM:SS' format.
        fps: Target frame rate for timestamps (if None, auto-detected from video or defaults to 30.0).
        stride: Process every Nth frame (1 = every frame).
        max_lost_frames: Frames before an unseen active track is declared completed and finalized.
        min_confidence: Minimum OCR confidence to include a reading in voting.
        detector_path: Path to YOLO plate detector checkpoint.
        ocr_dir: Path to fast-plate-ocr ONNX model and config.
        output_dir: Directory where events CSV and best crops are stored.
        max_frames: Optional limit on total frames to process.
        
    Returns:
        Dict with execution summary and paths to generated artifacts.
    """
    source_path = Path(source)
    source_name = source_path.stem
    output_dir = Path(output_dir)
    crops_dir = output_dir / "crops"
    output_dir.mkdir(parents=True, exist_ok=True)
    crops_dir.mkdir(parents=True, exist_ok=True)

    # 1. Initialize Frame Source
    source_type, frame_files, cap, detected_fps, total_frames = get_frame_source(source_path)
    actual_fps = fps if (fps is not None and fps > 0) else detected_fps

    # Parse start time
    try:
        start_dt = datetime.datetime.fromisoformat(start_time.replace("Z", ""))
    except Exception:
        start_dt = datetime.datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")

    print("\n" + "=" * 80)
    print(f"=== ANPR VIDEO PIPELINE: {source_name} ===")
    print("=" * 80)
    print(f"Source Type:     {source_type.upper()} ({source_path.resolve()})")
    print(f"Total Frames:    {total_frames}")
    print(f"Sampling Stride: {stride} (evaluating every {stride} frame(s))")
    print(f"Camera ID:       {camera_id}")
    print(f"Target FPS:      {actual_fps:.2f}")
    print(f"Start Timestamp: {start_dt.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Output Folder:   {output_dir.resolve()}")
    print("-" * 80)

    # 2. Initialize PlateReader (Detector + ONNX Recognizer)
    reader = PlateReader(
        detector_path=detector_path,
        ocr_dir=ocr_dir,
        conf_thresh=0.25,
        device="auto",
        padding_ratio=0.05,
    )
    voter = PlateVoting(min_confidence=min_confidence)

    # Tracking state
    active_tracks: Dict[int, Track] = {}
    emitted_events: List[Dict[str, Any]] = []
    next_event_id = 1
    next_fallback_track_id = 1000

    frame_idx = 0
    processed_count = 0

    try:
        while True:
            # Check maximum frames cutoff
            if max_frames and processed_count >= max_frames:
                break

            # Read frame
            if source_type == "video":
                ret, frame_bgr = cap.read()
                if not ret or frame_bgr is None:
                    break
            else:
                if frame_idx >= len(frame_files):
                    break
                frame_path = frame_files[frame_idx]
                frame_bgr = cv2.imread(str(frame_path))
                if frame_bgr is None:
                    frame_idx += 1
                    continue

            # Stride check
            if frame_idx % stride != 0:
                frame_idx += 1
                continue

            processed_count += 1
            curr_dt = start_dt + datetime.timedelta(seconds=(frame_idx / actual_fps))
            curr_timestamp = curr_dt.strftime("%Y-%m-%d %H:%M:%S")

            h_img, w_img = frame_bgr.shape[:2]

            # 3. Detect and Track Plates with ByteTrack (persist=True)
            # Ultralytics track runs ByteTrack assignment and associates tracks across frames
            track_results = reader.detector.track(
                frame_bgr,
                persist=True,
                tracker="bytetrack.yaml",
                conf=reader.conf_thresh,
                verbose=False,
            )

            current_frame_track_ids = set()

            if track_results and track_results[0].boxes is not None and len(track_results[0].boxes) > 0:
                boxes_obj = track_results[0].boxes

                for b_idx in range(len(boxes_obj)):
                    box_xyxy = boxes_obj.xyxy[b_idx].cpu().numpy().tolist()
                    det_conf = float(boxes_obj.conf[b_idx].item())

                    # ByteTrack assigns IDs when available
                    assigned_id = None
                    if boxes_obj.id is not None and b_idx < len(boxes_obj.id):
                        raw_id = boxes_obj.id[b_idx]
                        if raw_id is not None:
                            assigned_id = int(raw_id.item())

                    # Fallback track association if ByteTrack has not yet confirmed the tracklet
                    if assigned_id is None:
                        best_iou = 0.0
                        best_active_id = None
                        for aid, atrk in active_tracks.items():
                            last_box = atrk.readings[-1]["box"]
                            iou = compute_box_iou(box_xyxy, last_box)
                            if iou > best_iou:
                                best_iou = iou
                                best_active_id = aid

                        if best_iou >= 0.25 and best_active_id is not None:
                            assigned_id = best_active_id
                        else:
                            assigned_id = next_fallback_track_id
                            next_fallback_track_id += 1
                    else:
                        if assigned_id >= next_fallback_track_id:
                            next_fallback_track_id = assigned_id + 1

                    current_frame_track_ids.add(assigned_id)

                    # 4. Extract Crop with 5% Padding (matching training protocol)
                    x1, y1, x2, y2 = box_xyxy
                    bw = x2 - x1
                    bh = y2 - y1
                    pad_x = bw * reader.padding_ratio
                    pad_y = bh * reader.padding_ratio

                    crop_x1 = max(0, int(round(x1 - pad_x)))
                    crop_y1 = max(0, int(round(y1 - pad_y)))
                    crop_x2 = min(w_img, int(round(x2 + pad_x)))
                    crop_y2 = min(h_img, int(round(y2 + pad_y)))

                    crop_bgr = frame_bgr[crop_y1:crop_y2, crop_x1:crop_x2]
                    if crop_bgr.size == 0:
                        continue

                    # 5. Run OCR Recognizer with character confidence probabilities
                    crop_rgb = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2RGB)
                    preds = reader.recognizer.run(crop_rgb, return_confidence=True)
                    raw_pred = preds[0].plate if hasattr(preds[0], "plate") else str(preds[0])
                    norm_text = PlateReader.normalize_text(raw_pred)

                    # Real character probability confidence calculation
                    char_probs = getattr(preds[0], "char_probs", None)
                    if char_probs is not None and len(char_probs) > 0:
                        plate_len = len(raw_pred) if raw_pred else len(norm_text)
                        if plate_len > 0 and len(char_probs) >= plate_len:
                            ocr_conf = float(np.mean(char_probs[:plate_len]))
                        else:
                            ocr_conf = float(np.mean(char_probs))
                    else:
                        ocr_conf = 0.0

                    reading = {
                        "frame_idx": frame_idx,
                        "timestamp": curr_timestamp,
                        "crop": crop_bgr,
                        "text": norm_text,
                        "ocr_confidence": round(ocr_conf, 4),
                        "detector_confidence": round(det_conf, 4),
                        "box": [round(c, 1) for c in box_xyxy],
                    }

                    # Update track history
                    if assigned_id not in active_tracks:
                        active_tracks[assigned_id] = Track(
                            track_id=assigned_id,
                            camera_id=camera_id,
                            initial_reading=reading,
                        )
                    else:
                        active_tracks[assigned_id].add_reading(reading)

            # 6. Check for Lost Tracks (unseen for >= max_lost_frames)
            lost_ids = [
                tid for tid, trk in active_tracks.items()
                if (frame_idx - trk.last_frame) >= max_lost_frames
            ]
            for tid in lost_ids:
                trk = active_tracks.pop(tid)
                event = trk.to_event(
                    voter=voter,
                    output_crop_dir=crops_dir,
                    source_name=source_name,
                    event_id=next_event_id,
                    source=source_label,
                )
                if event["plate"]:  # Only emit if plate text was resolved
                    emitted_events.append(event)
                    next_event_id += 1
                    print(
                        f"  [TRACK ENDED] Track #{event['track_id']:<4} | "
                        f"Plate: {event['plate']:<12} | Frames: {event['n_frames']:<3} | "
                        f"Margin: {event['vote_margin']:.3f} | Best Crop: {Path(event['best_crop_path']).name}"
                    )

            if processed_count % 30 == 0:
                print(f"Processed frame {frame_idx:>4}/{total_frames} (Active tracks: {len(active_tracks)}, Emitted: {len(emitted_events)})")

            frame_idx += 1

    finally:
        if cap is not None:
            cap.release()

    # 7. Finalize All Remaining Active Tracks at End of Video / Stream
    for tid, trk in list(active_tracks.items()):
        event = trk.to_event(
            voter=voter,
            output_crop_dir=crops_dir,
            source_name=source_name,
            event_id=next_event_id,
            source=source_label,
        )
        if event["plate"]:
            emitted_events.append(event)
            next_event_id += 1
            print(
                f"  [STREAM END] Track #{event['track_id']:<4} | "
                f"Plate: {event['plate']:<12} | Frames: {event['n_frames']:<3} | "
                f"Margin: {event['vote_margin']:.3f} | Best Crop: {Path(event['best_crop_path']).name}"
            )

    # 8. Save Events CSV Matching data/sim/events.csv Structure
    csv_columns = [
        "event_id",
        "plate",
        "camera_id",
        "timestamp",
        "source",
        "speed_kmh",
        "heading_degrees",
        "lane",
        "ocr_confidence",
        "track_id",
        "n_frames",
        "vote_margin",
        "best_crop_path",
    ]

    out_csv_path = output_dir / f"{source_name}_events.csv"
    if emitted_events:
        df_events = pd.DataFrame(emitted_events)[csv_columns]
    else:
        df_events = pd.DataFrame(columns=csv_columns)

    df_events.to_csv(out_csv_path, index=False)
    print("\n" + "=" * 80)
    print(f"=== PIPELINE COMPLETED: {len(df_events)} EVENTS EMITTED ===")
    print("=" * 80)
    print(f"Events CSV Saved: {out_csv_path.resolve()}")
    print(f"Best Crops Saved: {crops_dir.resolve()}")
    if not df_events.empty:
        print("\nEmitted Events Preview:")
        print(df_events[["event_id", "plate", "camera_id", "timestamp", "track_id", "n_frames", "vote_margin"]].to_string(index=False))
    print("=" * 80)

    return {
        "source": str(source_path),
        "source_name": source_name,
        "total_frames_read": frame_idx,
        "processed_frames": processed_count,
        "events_count": len(emitted_events),
        "events_csv": str(out_csv_path),
        "crops_dir": str(crops_dir),
    }


def main():
    parser = argparse.ArgumentParser(description="Run ANPR video pipeline with ByteTrack and multi-frame voting.")
    parser.add_argument("--source", type=str, required=True, help="Path to video file (.mp4/.avi) or folder of frames.")
    parser.add_argument("--camera-id", type=str, default="CAM_001", help="Camera ID identifier (e.g. CAM_001).")
    parser.add_argument("--start-time", type=str, default="2026-10-04 12:00:00", help="Initial timestamp string.")
    parser.add_argument("--fps", type=float, default=None, help="Frame rate (if None, auto-detected from video or 30.0).")
    parser.add_argument("--stride", type=int, default=1, help="Process every Nth frame (default: 1).")
    parser.add_argument("--max-lost-frames", type=int, default=30, help="Frames before ending an inactive track.")
    parser.add_argument("--min-confidence", type=float, default=0.35, help="OCR confidence threshold for voting.")
    parser.add_argument("--detector-path", type=str, default="models/plate_detector.pt", help="Path to YOLO weights.")
    parser.add_argument("--ocr-dir", type=str, default="models/plate_ocr", help="Path to fast-plate-ocr directory.")
    parser.add_argument("--source-type", type=str, default="video", choices=["video", "image"], help="Source type: video (sequence) or image (individual photo).")
    args = parser.parse_args()

    process_video_pipeline(
        source=args.source,
        camera_id=args.camera_id,
        start_time=args.start_time,
        fps=args.fps,
        stride=args.stride,
        max_lost_frames=args.max_lost_frames,
        min_confidence=args.min_confidence,
        detector_path=args.detector_path,
        ocr_dir=args.ocr_dir,
        output_dir=args.output_dir,
        max_frames=args.max_frames,
        source_label=args.source_type,
    )


if __name__ == "__main__":
    main()
