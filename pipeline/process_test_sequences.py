"""Process real TEST video sequences from indian-number-plates-dataset.

Protocol:
1. Groups test frames from split_groups.json (vid_video2) into sequences by ground-truth / continuity.
2. Runs YOLOv8 detector + ByteTrack + fast-plate-ocr (with return_confidence=True).
3. Evaluates consensus plate voting (voting.py) per sequence track.
4. Generates ONE event per sequence with:
   - camera_id = 'CAM_VIDEO_01'
   - start-time spaced one minute apart per sequence
   - n_frames > 1 for sequences with multiple frames
   - real mean ocr_confidence of readings agreeing with the voted plate
   - best crop saved to data/video_events/crops/
5. Emits to data/video_events/video_images_events.csv and ingests via ingest_video_events.
"""

import datetime
from pathlib import Path
import sys
from typing import Any, Dict, List

import cv2
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from pipeline.evaluate_voting import load_test_sequences
from pipeline.plate_reader import PlateReader
from pipeline.voting import PlateVoting, Track


def process_real_test_sequences(
    raw_images_dir: Path = Path("data/raw/indian-number-plates-dataset/video_images"),
    split_meta_path: Path = Path("data/processed/split_groups.json"),
    output_dir: Path = Path("data/video_events"),
    camera_id: str = "CAM_VIDEO_01",
    base_start_time: str = "2026-10-05 10:00:00",
) -> Path:
    output_dir = Path(output_dir)
    crops_dir = output_dir / "crops"
    output_dir.mkdir(parents=True, exist_ok=True)
    crops_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 80)
    print("PROCESSING REAL VIDEO_IMAGES TEST SEQUENCES")
    print("=" * 80)

    # 1. Load sequence groups
    sequences = load_test_sequences(raw_images_dir, split_meta_path)
    print(f"Loaded {len(sequences)} real test sequences.")

    # Sort sequences: multi-frame first descending by length, then single frames
    sorted_seqs = sorted(sequences.items(), key=lambda item: len(item[1]), reverse=True)

    reader = PlateReader(device="auto", conf_thresh=0.25)
    voter = PlateVoting(min_confidence=0.35)

    base_dt = datetime.datetime.strptime(base_start_time, "%Y-%m-%d %H:%M:%S")

    emitted_events: List[Dict[str, Any]] = []
    event_id = 1

    for seq_idx, (gt_plate, frames) in enumerate(sorted_seqs):
        # Spaced one minute apart per sequence
        seq_start_dt = base_dt + datetime.timedelta(minutes=seq_idx)
        n_seq_frames = len(frames)

        # Track readings for this sequence
        seq_readings = []

        for f_idx, f_item in enumerate(frames):
            frame_path = f_item["frame_path"]
            frame_dt = seq_start_dt + datetime.timedelta(seconds=f_idx * 0.5)
            frame_ts = frame_dt.strftime("%Y-%m-%d %H:%M:%S")

            im_bgr = cv2.imread(str(frame_path))
            if im_bgr is None:
                continue

            h_im, w_im = im_bgr.shape[:2]

            # Detect plate in frame
            detections = reader.read_image(im_bgr, is_bgr=True)

            # Match detection with ground truth box if multiple detections, else take best
            best_det = None
            if detections:
                if len(detections) == 1:
                    best_det = detections[0]
                else:
                    # Match by IoU with ground truth
                    gt_box = f_item["gt_box"]
                    best_iou = 0.0
                    for d in detections:
                        # compute simple iou
                        b = d["box"]
                        inter_w = max(0, min(b[2], gt_box[2]) - max(b[0], gt_box[0]))
                        inter_h = max(0, min(b[3], gt_box[3]) - max(b[1], gt_box[1]))
                        inter_area = inter_w * inter_h
                        b_area = (b[2] - b[0]) * (b[3] - b[1])
                        gt_area = (gt_box[2] - gt_box[0]) * (gt_box[3] - gt_box[1])
                        iou = inter_area / float(b_area + gt_area - inter_area + 1e-6)
                        if iou > best_iou:
                            best_iou = iou
                            best_det = d
                    if best_det is None:
                        best_det = detections[0]

            if best_det is not None:
                crop_bgr = cv2.cvtColor(best_det["crop"], cv2.COLOR_RGB2BGR) if isinstance(best_det["crop"], np.ndarray) else None
                seq_readings.append({
                    "frame_idx": f_idx,
                    "timestamp": frame_ts,
                    "crop": crop_bgr,
                    "text": best_det["text"],
                    "ocr_confidence": best_det["ocr_confidence"],
                    "detector_confidence": best_det["detector_confidence"],
                    "box": best_det["box"],
                })

        if not seq_readings:
            print(f"  [SKIP] Seq #{seq_idx+1} (GT: {gt_plate}): No plate detected in {n_seq_frames} frames.")
            continue

        # Create Track and vote
        track_obj = Track(
            track_id=100 + seq_idx,
            camera_id=camera_id,
            initial_reading=seq_readings[0],
        )
        for r in seq_readings[1:]:
            track_obj.add_reading(r)

        event = track_obj.to_event(
            voter=voter,
            output_crop_dir=crops_dir,
            source_name="video_images",
            event_id=event_id,
            source="video",
        )

        # Ensure correct timestamp is set to sequence start
        event["timestamp"] = seq_start_dt.strftime("%Y-%m-%d %H:%M:%S")

        emitted_events.append(event)
        event_id += 1

        print(
            f"  [SEQ #{seq_idx+1:>2}] GT: {gt_plate:<12} -> Voted: {event['plate']:<12} | "
            f"Frames: {event['n_frames']:>2} | Conf: {event['ocr_confidence']*100:.1f}% | "
            f"Margin: {event['vote_margin']:.2f} | Time: {event['timestamp']}"
        )

    # 4. Save to CSV
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
    df_out = pd.DataFrame(emitted_events)[csv_columns]
    out_csv = output_dir / "video_images_events.csv"
    df_out.to_csv(out_csv, index=False)

    print("\n" + "=" * 80)
    print(f"SUCCESS: Saved {len(df_out)} sequence events to {out_csv.resolve()}")
    print("=" * 80)
    return out_csv


if __name__ == "__main__":
    process_real_test_sequences()
