"""Video Annotation Utility for City-ANPR Pipeline.

Renders an annotated video (or image sequence) illustrating:
1. Vehicle license plate bounding boxes with unique track color-coding.
2. Active ByteTrack Track IDs.
3. Consensus multi-frame voted plate strings and OCR confidence.
4. Clean diagnostic heads-up display (HUD) with live track counts and timestamp.

Saves the annotated MP4 video to `docs/demo/`.
"""

import argparse
import datetime
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import cv2
import numpy as np

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from pipeline.plate_reader import PlateReader
from pipeline.video_pipeline import compute_box_iou, get_frame_source
from pipeline.voting import PlateVoting, Track

# Curated palette of visually distinct, high-contrast colors (BGR format)
TRACK_COLORS = [
    (0, 215, 255),    # Vibrant Amber / Gold
    (50, 205, 50),    # Lime Green
    (255, 105, 180),  # Neon Pink
    (30, 144, 255),   # Dodger Blue
    (255, 165, 0),    # Deep Orange
    (147, 112, 219),  # Medium Purple
    (0, 255, 255),    # Cyan
    (255, 69, 0),     # Orange Red
    (0, 250, 154),    # Spring Green
    (220, 20, 60),    # Crimson
]


def get_track_color(track_id: int) -> Tuple[int, int, int]:
    """Deterministically returns a distinct BGR color for each track ID."""
    return TRACK_COLORS[abs(int(track_id)) % len(TRACK_COLORS)]


def draw_hud(
    frame: np.ndarray,
    frame_idx: int,
    total_frames: int,
    timestamp_str: str,
    active_tracks_count: int,
) -> None:
    """Draws a professional heads-up display (HUD) overlay at the top-left of the frame."""
    hud_h, hud_w = 75, 340
    overlay = frame.copy()
    cv2.rectangle(overlay, (12, 12), (12 + hud_w, 12 + hud_h), (20, 20, 25), -1)
    cv2.rectangle(overlay, (12, 12), (12 + hud_w, 12 + hud_h), (60, 60, 75), 1)
    cv2.addWeighted(overlay, 0.85, frame, 0.15, 0, frame)

    # Title
    cv2.putText(
        frame,
        "CITY-ANPR VIDEO TRACKING",
        (22, 34),
        cv2.FONT_HERSHEY_DUPLEX,
        0.55,
        (0, 215, 255),
        1,
        cv2.LINE_AA,
    )

    # Telemetry
    hud_text1 = f"Frame: {frame_idx}/{total_frames}  |  Active: {active_tracks_count}"
    hud_text2 = f"Time:  {timestamp_str}"
    cv2.putText(
        frame,
        hud_text1,
        (22, 54),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.42,
        (220, 220, 225),
        1,
        cv2.LINE_AA,
    )
    cv2.putText(
        frame,
        hud_text2,
        (22, 72),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.42,
        (180, 180, 185),
        1,
        cv2.LINE_AA,
    )


def draw_plate_annotation(
    frame: np.ndarray,
    box: List[float],
    track_id: int,
    voted_plate: str,
    confidence: float,
    n_frames: int,
) -> None:
    """Draws bounding box and plate info banner for a single detected plate."""
    x1, y1, x2, y2 = [int(round(c)) for c in box]
    color = get_track_color(track_id)

    # 1. Bounding box around plate
    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2, cv2.LINE_AA)

    # Corner brackets for premium visual appearance
    corner_len = min(12, max(4, int((x2 - x1) * 0.15)))
    th = 3
    # Top-left
    cv2.line(frame, (x1, y1), (x1 + corner_len, y1), color, th)
    cv2.line(frame, (x1, y1), (x1, y1 + corner_len), color, th)
    # Top-right
    cv2.line(frame, (x2, y1), (x2 - corner_len, y1), color, th)
    cv2.line(frame, (x2, y1), (x2, y1 + corner_len), color, th)
    # Bottom-left
    cv2.line(frame, (x1, y2), (x1 + corner_len, y2), color, th)
    cv2.line(frame, (x1, y2), (x1, y2 - corner_len), color, th)
    # Bottom-right
    cv2.line(frame, (x2, y2), (x2 - corner_len, y2), color, th)
    cv2.line(frame, (x2, y2), (x2, y2 - corner_len), color, th)

    # 2. Badge label above the bounding box
    label_text = f"ID #{track_id} | {voted_plate or 'DETECTING...'} ({confidence:.0%})"
    font = cv2.FONT_HERSHEY_DUPLEX
    font_scale = 0.52
    font_th = 1

    (text_w, text_h), baseline = cv2.getTextSize(label_text, font, font_scale, font_th)
    badge_pad = 6
    badge_w = text_w + badge_pad * 2
    badge_h = text_h + badge_pad * 2

    badge_x1 = max(0, x1)
    badge_y2 = max(badge_h, y1 - 4)
    badge_y1 = badge_y2 - badge_h

    # Ensure badge doesn't bleed off right edge
    if badge_x1 + badge_w > frame.shape[1]:
        badge_x1 = max(0, frame.shape[1] - badge_w - 4)

    # Fill dark banner background with matching track color outline
    cv2.rectangle(
        frame,
        (badge_x1, badge_y1),
        (badge_x1 + badge_w, badge_y2),
        (18, 18, 22),
        -1,
    )
    cv2.rectangle(
        frame,
        (badge_x1, badge_y1),
        (badge_x1 + badge_w, badge_y2),
        color,
        1,
        cv2.LINE_AA,
    )

    # Plate text inside banner
    text_x = badge_x1 + badge_pad
    text_y = badge_y2 - badge_pad
    cv2.putText(
        frame,
        label_text,
        (text_x, text_y),
        font,
        font_scale,
        (255, 255, 255),
        font_th,
        cv2.LINE_AA,
    )


def annotate_video(
    source: Union[str, Path],
    output_path: Optional[Union[str, Path]] = None,
    fps: Optional[float] = None,
    stride: int = 1,
    detector_path: Union[str, Path] = "models/plate_detector.pt",
    ocr_dir: Union[str, Path] = "models/plate_ocr",
    max_frames: Optional[int] = None,
    min_confidence: float = 0.35,
) -> Path:
    """Annotates video frames with tracking IDs, bounding boxes, and voted plate consensus.
    
    Args:
        source: Path to video file or folder of frame images.
        output_path: Output .mp4 video path (defaults to docs/demo/<source>_annotated.mp4).
        fps: Playback frame rate of output video.
        stride: Processing step stride across frames.
        detector_path: Path to YOLO plate detector weights.
        ocr_dir: Directory containing fast-plate-ocr ONNX and YAML assets.
        max_frames: Optional frame limit.
        min_confidence: Confidence threshold for multi-frame voting.
        
    Returns:
        Path to the saved MP4 annotated video.
    """
    source_path = Path(source)
    source_name = source_path.stem

    if output_path is None:
        out_file = PROJECT_ROOT / "docs" / "demo" / f"{source_name}_annotated.mp4"
    else:
        out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    # Initialize video capture / frame source
    source_type, frame_files, cap, detected_fps, total_frames = get_frame_source(source_path)
    render_fps = fps if (fps is not None and fps > 0) else detected_fps

    # Inspect first frame for video dimensions
    if source_type == "video":
        ret, first_frame = cap.read()
        if not ret or first_frame is None:
            raise RuntimeError(f"Could not read first frame from {source_path}")
        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
    else:
        first_frame = cv2.imread(str(frame_files[0]))
        if first_frame is None:
            raise RuntimeError(f"Could not read frame image: {frame_files[0]}")

    h_out, w_out = first_frame.shape[:2]

    # Initialize OpenCV VideoWriter with MP4 codec
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(out_file), fourcc, render_fps, (w_out, h_out))
    if not writer.isOpened():
        # Fallback to MJPG / AVI if MP4 container not supported by platform
        fallback_file = out_file.with_suffix(".avi")
        fourcc_fallback = cv2.VideoWriter_fourcc(*"MJPG")
        writer = cv2.VideoWriter(str(fallback_file), fourcc_fallback, render_fps, (w_out, h_out))
        if not writer.isOpened():
            raise RuntimeError(f"Failed to open VideoWriter for {out_file} or {fallback_file}")
        out_file = fallback_file

    print("\n" + "=" * 80)
    print(f"=== ANNOTATING VIDEO: {source_name} ===")
    print("=" * 80)
    print(f"Source:       {source_path.resolve()}")
    print(f"Destination:  {out_file.resolve()}")
    print(f"Resolution:   {w_out} x {h_out}")
    print(f"FPS:          {render_fps:.2f}")
    print(f"Total Frames: {total_frames}")
    print("-" * 80)

    # Initialize PlateReader & Voter
    reader = PlateReader(
        detector_path=detector_path,
        ocr_dir=ocr_dir,
        conf_thresh=0.25,
        device="auto",
        padding_ratio=0.05,
    )
    voter = PlateVoting(min_confidence=min_confidence)

    active_tracks: Dict[int, Track] = {}
    next_fallback_id = 1000
    start_dt = datetime.datetime.now()

    frame_idx = 0
    written_count = 0

    try:
        while True:
            if max_frames and written_count >= max_frames:
                break

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

            if frame_idx % stride != 0:
                frame_idx += 1
                continue

            curr_dt = start_dt + datetime.timedelta(seconds=(frame_idx / render_fps))
            timestamp_str = curr_dt.strftime("%Y-%m-%d %H:%M:%S")

            # Track plates
            track_results = reader.detector.track(
                frame_bgr,
                persist=True,
                tracker="bytetrack.yaml",
                conf=reader.conf_thresh,
                verbose=False,
            )

            current_detections: List[Dict[str, Any]] = []

            if track_results and track_results[0].boxes is not None and len(track_results[0].boxes) > 0:
                boxes_obj = track_results[0].boxes
                for b_idx in range(len(boxes_obj)):
                    box_xyxy = boxes_obj.xyxy[b_idx].cpu().numpy().tolist()
                    det_conf = float(boxes_obj.conf[b_idx].item())

                    assigned_id = None
                    if boxes_obj.id is not None and b_idx < len(boxes_obj.id):
                        raw_id = boxes_obj.id[b_idx]
                        if raw_id is not None:
                            assigned_id = int(raw_id.item())

                    # Spatial fallback association if ByteTrack unconfirmed
                    if assigned_id is None:
                        best_iou = 0.0
                        best_aid = None
                        for aid, atrk in active_tracks.items():
                            last_box = atrk.readings[-1]["box"]
                            iou = compute_box_iou(box_xyxy, last_box)
                            if iou > best_iou:
                                best_iou = iou
                                best_aid = aid

                        if best_iou >= 0.25 and best_aid is not None:
                            assigned_id = best_aid
                        else:
                            assigned_id = next_fallback_id
                            next_fallback_id += 1
                    else:
                        if assigned_id >= next_fallback_id:
                            next_fallback_id = assigned_id + 1

                    # Crop plate
                    pad_x = (box_xyxy[2] - box_xyxy[0]) * reader.padding_ratio
                    pad_y = (box_xyxy[3] - box_xyxy[1]) * reader.padding_ratio
                    cx1 = max(0, int(round(box_xyxy[0] - pad_x)))
                    cy1 = max(0, int(round(box_xyxy[1] - pad_y)))
                    cx2 = min(frame_bgr.shape[1], int(round(box_xyxy[2] + pad_x)))
                    cy2 = min(frame_bgr.shape[0], int(round(box_xyxy[3] + pad_y)))
                    crop_bgr = frame_bgr[cy1:cy2, cx1:cx2]

                    if crop_bgr.size > 0:
                        crop_rgb = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2RGB)
                        preds = reader.recognizer.run(crop_rgb)
                        raw_txt = preds[0].plate if hasattr(preds[0], "plate") else str(preds[0])
                        norm_txt = PlateReader.normalize_text(raw_txt)
                        ocr_conf = (
                            float(np.mean(preds[0].char_probs))
                            if (hasattr(preds[0], "char_probs") and preds[0].char_probs is not None)
                            else 0.85
                        )
                    else:
                        norm_txt = ""
                        ocr_conf = 0.0

                    reading = {
                        "frame_idx": frame_idx,
                        "timestamp": timestamp_str,
                        "crop": crop_bgr,
                        "text": norm_txt,
                        "ocr_confidence": ocr_conf,
                        "detector_confidence": det_conf,
                        "box": box_xyxy,
                    }

                    if assigned_id not in active_tracks:
                        active_tracks[assigned_id] = Track(
                            track_id=assigned_id,
                            camera_id="CAM_DEMO",
                            initial_reading=reading,
                        )
                    else:
                        active_tracks[assigned_id].add_reading(reading)

                    # Compute live consensus plate for active track
                    voted_res = voter.vote(active_tracks[assigned_id].readings)
                    current_detections.append({
                        "box": box_xyxy,
                        "track_id": assigned_id,
                        "voted_plate": voted_res["plate"],
                        "confidence": voted_res["ocr_confidence"],
                        "n_frames": voted_res["n_frames"],
                    })

            # Render annotations on frame
            annotated_frame = frame_bgr.copy()

            for det in current_detections:
                draw_plate_annotation(
                    frame=annotated_frame,
                    box=det["box"],
                    track_id=det["track_id"],
                    voted_plate=det["voted_plate"],
                    confidence=det["confidence"],
                    n_frames=det["n_frames"],
                )

            # Draw HUD
            draw_hud(
                frame=annotated_frame,
                frame_idx=frame_idx + 1,
                total_frames=total_frames,
                timestamp_str=timestamp_str,
                active_tracks_count=len(active_tracks),
            )

            # Ensure frame dimensions match VideoWriter dimensions exactly
            if (annotated_frame.shape[1], annotated_frame.shape[0]) != (w_out, h_out):
                annotated_frame = cv2.resize(annotated_frame, (w_out, h_out), interpolation=cv2.INTER_LINEAR)

            # Write frame to video
            writer.write(annotated_frame)
            written_count += 1

            if written_count % 30 == 0 or frame_idx == total_frames - 1:
                print(f"Annotated frame {frame_idx + 1:>4}/{total_frames} (Active tracks: {len(active_tracks)})")

            frame_idx += 1

    finally:
        if cap is not None:
            cap.release()
        writer.release()

    print("\n" + "=" * 80)
    print(f"=== ANNOTATION COMPLETE: {written_count} FRAMES WRITTEN ===")
    print(f"Saved to: {out_file.resolve()}")
    print("=" * 80)

    return out_file


def main():
    parser = argparse.ArgumentParser(description="Generate annotated video with ByteTrack tracking and voted plates.")
    parser.add_argument("--source", type=str, required=True, help="Video file or folder of frame images.")
    parser.add_argument("--output", type=str, default=None, help="Output MP4 path (default: docs/demo/<name>_annotated.mp4).")
    parser.add_argument("--fps", type=float, default=None, help="Playback frame rate.")
    parser.add_argument("--stride", type=int, default=1, help="Frame step stride.")
    parser.add_argument("--detector-path", type=str, default="models/plate_detector.pt")
    parser.add_argument("--ocr-dir", type=str, default="models/plate_ocr")
    parser.add_argument("--max-frames", type=int, default=None, help="Optional frame limit.")
    args = parser.parse_args()

    annotate_video(
        source=args.source,
        output_path=args.output,
        fps=args.fps,
        stride=args.stride,
        detector_path=args.detector_path,
        ocr_dir=args.ocr_dir,
        max_frames=args.max_frames,
    )


if __name__ == "__main__":
    main()
