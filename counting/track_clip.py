import csv
import os
from pathlib import Path
import time
from ultralytics import YOLO

def main():
    video_path = r"E:\AIC21_Track1_Vehicle_Counting\counting_gt_sample\counting_example_cam_5_1min.mp4"
    output_dir = Path("counting_work")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_csv = output_dir / "tracks_example.csv"

    print("Loading YOLOv8s pretrained COCO model...", flush=True)
    model = YOLO("yolov8s.pt")

    print(f"Starting tracking on {video_path}...", flush=True)
    start_time = time.time()

    # Built-in ByteTrack tracker, classes: car(2), bus(5), truck(7), conf=0.25, imgsz=960
    results = model.track(
        source=video_path,
        tracker="bytetrack.yaml",
        persist=True,
        classes=[2, 5, 7],
        conf=0.25,
        imgsz=960,
        stream=True,
        verbose=False,
    )

    unique_tracks = set()
    total_frames = 0

    with open(output_csv, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["frame_id", "track_id", "class_name", "conf", "x1", "y1", "x2", "y2"])

        for frame_id, r in enumerate(results):
            total_frames = frame_id + 1

            if (frame_id + 1) % 100 == 0:
                print(f"Progress: Processed {frame_id + 1} frames...", flush=True)

            if r.boxes is not None and len(r.boxes) > 0 and r.boxes.id is not None:
                track_ids = r.boxes.id.int().cpu().tolist()
                confs = r.boxes.conf.cpu().tolist()
                cls_ids = r.boxes.cls.int().cpu().tolist()
                boxes = r.boxes.xyxy.cpu().tolist()

                for tid, cid, conf, (x1, y1, x2, y2) in zip(track_ids, cls_ids, confs, boxes):
                    class_name = model.names.get(cid, str(cid))
                    unique_tracks.add(tid)
                    writer.writerow([
                        frame_id,
                        tid,
                        class_name,
                        f"{conf:.4f}",
                        f"{x1:.2f}",
                        f"{y1:.2f}",
                        f"{x2:.2f}",
                        f"{y2:.2f}"
                    ])

    total_time = time.time() - start_time

    print("Tracking complete.", flush=True)
    print(f"Saved tracks to: {output_csv}", flush=True)
    print(f"Total frames processed: {total_frames}", flush=True)
    print(f"Number of unique track IDs: {len(unique_tracks)}", flush=True)
    print(f"Total run time: {total_time:.2f} seconds", flush=True)

if __name__ == "__main__":
    main()
