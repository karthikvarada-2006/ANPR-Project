import json
import os
from pathlib import Path
import cv2
import numpy as np

def main():
    video_path = r"E:\AIC21_Track1_Vehicle_Counting\counting_gt_sample\counting_example_cam_5_1min.mp4"
    json_path = Path(__file__).parent / "movements_cam5.json"
    output_dir = Path("counting_work")
    output_path = output_dir / "movements_overlay.jpg"

    output_dir.mkdir(parents=True, exist_ok=True)

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"Could not open video file: {video_path}")

    ret, frame = cap.read()
    cap.release()

    if not ret or frame is None:
        raise RuntimeError(f"Failed to read first frame from {video_path}")

    # Draw ROI polygon (green)
    roi_pts = np.array(data["roi"], dtype=np.int32).reshape((-1, 1, 2))
    cv2.polylines(frame, [roi_pts], isClosed=True, color=(0, 255, 0), thickness=2)

    # Draw movements: arrow from start to end (red) with movement number
    movements = data.get("movements", {})
    for mov_id, mov_info in movements.items():
        start = tuple(mov_info["start"])
        end = tuple(mov_info["end"])
        
        # Draw red arrow
        cv2.arrowedLine(frame, start, end, color=(0, 0, 255), thickness=2, tipLength=0.2)
        
        # Position label near midpoint of arrow
        mid_x = (start[0] + end[0]) // 2
        mid_y = (start[1] + end[1]) // 2
        text_pos = (mid_x + 6, mid_y - 6)
        
        # Text with black outline for readability, red text
        cv2.putText(frame, str(mov_id), text_pos, cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 3, cv2.LINE_AA)
        cv2.putText(frame, str(mov_id), text_pos, cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2, cv2.LINE_AA)

    success = cv2.imwrite(str(output_path), frame)
    if not success:
        raise RuntimeError(f"Failed to save image to {output_path}")

    print(f"Saved movements overlay to {output_path}")

if __name__ == "__main__":
    main()

