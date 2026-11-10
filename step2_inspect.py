import os, csv, collections, cv2
root = r"E:\AIC21_Track1_Vehicle_Counting"
out = "counting_work"
os.makedirs(out, exist_ok=True)

gt = os.path.join(root, "counting_gt_sample", "counting_example_cam_5_1min.csv")
rows = list(csv.DictReader(open(gt)))
print("GT rows:", len(rows))
frames = [int(r["frame_id"]) for r in rows]
print("GT frame range:", min(frames), "to", max(frames))
cnt = collections.Counter((int(r["movement_id"]), int(r["vehicle_class_id"])) for r in rows)
print("GT counts per (movement, class):")
for k in sorted(cnt):
    print("  movement", k[0], "class", k[1], "->", cnt[k])

roi_path = os.path.join(root, "ROIs", "cam_5.txt")
pts = [tuple(int(v) for v in l.strip().split(",")) for l in open(roi_path) if l.strip()]
print("ROI points:", pts)

import numpy as np
for name, path in [
    ("cam5_full", os.path.join(root, "Dataset_A", "cam_5.mp4")),
    ("example_1min", os.path.join(root, "counting_gt_sample", "counting_example_cam_5_1min.mp4")),
]:
    cap = cv2.VideoCapture(path)
    print(name, "size", int(cap.get(3)), "x", int(cap.get(4)),
          "fps", cap.get(5), "frames", int(cap.get(7)))
    ok, fr = cap.read()
    if ok:
        cv2.polylines(fr, [np.array(pts, np.int32)], True, (0, 255, 0), 2)
        cv2.imwrite(os.path.join(out, name + "_frame0_roi.jpg"), fr)
    cap.release()

shots = os.path.join(root, "screen_shot_with_roi_and_movement")
print("Screenshots for cam_5:", [f for f in os.listdir(shots) if "5" in f])
