import csv
from collections import defaultdict
from pathlib import Path

def load_events(csv_path, min_frame_id=300):
    events = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            fid = int(row["frame_id"])
            if fid >= min_frame_id:
                events.append({
                    "video_clip_id": int(row["video_clip_id"]),
                    "frame_id": fid,
                    "movement_id": int(row["movement_id"]),
                    "vehicle_class_id": int(row["vehicle_class_id"])
                })
    return events

def greedy_match(pred_frames, gt_frames, max_frame_diff=20):
    sorted_gt = sorted(gt_frames)
    sorted_pred = sorted(pred_frames)
    matched_gt_indices = set()
    matched_pairs = []

    for p in sorted_pred:
        best_idx = None
        best_diff = max_frame_diff + 1
        for idx, g in enumerate(sorted_gt):
            if idx not in matched_gt_indices:
                diff = abs(p - g)
                if diff <= max_frame_diff and diff < best_diff:
                    best_diff = diff
                    best_idx = idx
        if best_idx is not None:
            matched_gt_indices.add(best_idx)
            matched_pairs.append((p, sorted_gt[best_idx]))

    tp = len(matched_pairs)
    fp = len(sorted_pred) - tp
    fn = len(sorted_gt) - tp
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    return tp, fp, fn, precision, recall, f1

def main():
    v1_csv = Path("counting_work") / "counts_pred.csv"
    v2_csv = Path("counting_work") / "counts_pred_v2.csv"
    gt_csv = Path(r"E:\AIC21_Track1_Vehicle_Counting\counting_gt_sample\counting_example_cam_5_1min.csv")

    if not v1_csv.exists():
        raise FileNotFoundError(f"V1 counts file not found: {v1_csv}")
    if not v2_csv.exists():
        raise FileNotFoundError(f"V2 counts file not found: {v2_csv}")
    if not gt_csv.exists():
        raise FileNotFoundError(f"GT file not found: {gt_csv}")

    # Evaluate ONLY events with frame_id >= 300
    gt_events = load_events(gt_csv, min_frame_id=300)
    v1_events = load_events(v1_csv, min_frame_id=300)
    v2_events = load_events(v2_csv, min_frame_id=300)

    print("=" * 115)
    print("REAL video, 1 clip; v2 calibrated on frames <300, tested on frames >=300; revised after seeing v1 results")
    print("=" * 115)
    print(f"Number of GT events in test split (frame_id >= 300): {len(gt_events)}")
    print(f"Number of V1 events in test split (frame_id >= 300): {len(v1_events)}")
    print(f"Number of V2 events in test split (frame_id >= 300): {len(v2_events)}")

    # -------------------------------------------------------------
    # 1. SIDE-BY-SIDE MATCHING PER (MOVEMENT, CLASS)
    # -------------------------------------------------------------
    all_keys = set((e["movement_id"], e["vehicle_class_id"]) for e in gt_events).union(
        set((e["movement_id"], e["vehicle_class_id"]) for e in v1_events)
    ).union(
        set((e["movement_id"], e["vehicle_class_id"]) for e in v2_events)
    )

    gt_by_key = defaultdict(list)
    for e in gt_events:
        gt_by_key[(e["movement_id"], e["vehicle_class_id"])].append(e["frame_id"])

    v1_by_key = defaultdict(list)
    for e in v1_events:
        v1_by_key[(e["movement_id"], e["vehicle_class_id"])].append(e["frame_id"])

    v2_by_key = defaultdict(list)
    for e in v2_events:
        v2_by_key[(e["movement_id"], e["vehicle_class_id"])].append(e["frame_id"])

    print("\n" + "=" * 115)
    print("SIDE-BY-SIDE EVALUATION PER (MOVEMENT, CLASS) (Tolerance <= 20 frames, frame_id >= 300)")
    print("=" * 115)
    header = (
        f"{'Mov':<5} {'Class':<7} {'GT':<4} | "
        f"{'V1:Pred':<7} {'TP':<4} {'FP':<4} {'FN':<4} {'Prec':<6} {'Rec':<6} {'F1':<6} | "
        f"{'V2:Pred':<7} {'TP':<4} {'FP':<4} {'FN':<4} {'Prec':<6} {'Rec':<6} {'F1':<6}"
    )
    print(header)
    print("-" * 115)

    v1_tot_tp, v1_tot_fp, v1_tot_fn = 0, 0, 0
    v2_tot_tp, v2_tot_fp, v2_tot_fn = 0, 0, 0

    for m_id, c_id in sorted(all_keys):
        c_str = "Car" if c_id == 1 else "Truck"
        gts = gt_by_key[(m_id, c_id)]
        v1_preds = v1_by_key[(m_id, c_id)]
        v2_preds = v2_by_key[(m_id, c_id)]

        v1_tp, v1_fp, v1_fn, v1_p, v1_r, v1_f1 = greedy_match(v1_preds, gts, max_frame_diff=20)
        v2_tp, v2_fp, v2_fn, v2_p, v2_r, v2_f1 = greedy_match(v2_preds, gts, max_frame_diff=20)

        v1_tot_tp += v1_tp
        v1_tot_fp += v1_fp
        v1_tot_fn += v1_fn

        v2_tot_tp += v2_tp
        v2_tot_fp += v2_fp
        v2_tot_fn += v2_fn

        row_str = (
            f"M{m_id:<4} {c_str:<7} {len(gts):<4} | "
            f"{len(v1_preds):<7} {v1_tp:<4} {v1_fp:<4} {v1_fn:<4} {v1_p:<6.3f} {v1_r:<6.3f} {v1_f1:<6.3f} | "
            f"{len(v2_preds):<7} {v2_tp:<4} {v2_fp:<4} {v2_fn:<4} {v2_p:<6.3f} {v2_r:<6.3f} {v2_f1:<6.3f}"
        )
        print(row_str)

    v1_tot_p = v1_tot_tp / (v1_tot_tp + v1_tot_fp) if (v1_tot_tp + v1_tot_fp) > 0 else 0.0
    v1_tot_r = v1_tot_tp / (v1_tot_tp + v1_tot_fn) if (v1_tot_tp + v1_tot_fn) > 0 else 0.0
    v1_tot_f1 = 2 * v1_tot_p * v1_tot_r / (v1_tot_p + v1_tot_r) if (v1_tot_p + v1_tot_r) > 0 else 0.0

    v2_tot_p = v2_tot_tp / (v2_tot_tp + v2_tot_fp) if (v2_tot_tp + v2_tot_fp) > 0 else 0.0
    v2_tot_r = v2_tot_tp / (v2_tot_tp + v2_tot_fn) if (v2_tot_tp + v2_tot_fn) > 0 else 0.0
    v2_tot_f1 = 2 * v2_tot_p * v2_tot_r / (v2_tot_p + v2_tot_r) if (v2_tot_p + v2_tot_r) > 0 else 0.0

    print("-" * 115)
    total_row = (
        f"{'TOTAL':<13} {len(gt_events):<4} | "
        f"{len(v1_events):<7} {v1_tot_tp:<4} {v1_tot_fp:<4} {v1_tot_fn:<4} {v1_tot_p:<6.3f} {v1_tot_r:<6.3f} {v1_tot_f1:<6.3f} | "
        f"{len(v2_events):<7} {v2_tot_tp:<4} {v2_tot_fp:<4} {v2_tot_fn:<4} {v2_tot_p:<6.3f} {v2_tot_r:<6.3f} {v2_tot_f1:<6.3f}"
    )
    print(total_row)

    # -------------------------------------------------------------
    # 2. SIDE-BY-SIDE MATCHING IGNORING CLASS (PER MOVEMENT)
    # -------------------------------------------------------------
    all_movements = sorted(
        set(e["movement_id"] for e in gt_events).union(
            set(e["movement_id"] for e in v1_events)
        ).union(
            set(e["movement_id"] for e in v2_events)
        )
    )

    gt_by_mov = defaultdict(list)
    for e in gt_events:
        gt_by_mov[e["movement_id"]].append(e["frame_id"])

    v1_by_mov = defaultdict(list)
    for e in v1_events:
        v1_by_mov[e["movement_id"]].append(e["frame_id"])

    v2_by_mov = defaultdict(list)
    for e in v2_events:
        v2_by_mov[e["movement_id"]].append(e["frame_id"])

    print("\n" + "=" * 105)
    print("SIDE-BY-SIDE EVALUATION PER MOVEMENT (IGNORING CLASS) (Tolerance <= 20 frames, frame_id >= 300)")
    print("=" * 105)
    header_mov = (
        f"{'Mov':<5} {'GT':<4} | "
        f"{'V1:Pred':<7} {'TP':<4} {'FP':<4} {'FN':<4} {'Prec':<6} {'Rec':<6} {'F1':<6} | "
        f"{'V2:Pred':<7} {'TP':<4} {'FP':<4} {'FN':<4} {'Prec':<6} {'Rec':<6} {'F1':<6}"
    )
    print(header_mov)
    print("-" * 105)

    v1_m_tot_tp, v1_m_tot_fp, v1_m_tot_fn = 0, 0, 0
    v2_m_tot_tp, v2_m_tot_fp, v2_m_tot_fn = 0, 0, 0

    for m_id in all_movements:
        gts = gt_by_mov[m_id]
        v1_preds = v1_by_mov[m_id]
        v2_preds = v2_by_mov[m_id]

        v1_tp, v1_fp, v1_fn, v1_p, v1_r, v1_f1 = greedy_match(v1_preds, gts, max_frame_diff=20)
        v2_tp, v2_fp, v2_fn, v2_p, v2_r, v2_f1 = greedy_match(v2_preds, gts, max_frame_diff=20)

        v1_m_tot_tp += v1_tp
        v1_m_tot_fp += v1_fp
        v1_m_tot_fn += v1_fn

        v2_m_tot_tp += v2_tp
        v2_m_tot_fp += v2_fp
        v2_m_tot_fn += v2_fn

        row_str = (
            f"M{m_id:<4} {len(gts):<4} | "
            f"{len(v1_preds):<7} {v1_tp:<4} {v1_fp:<4} {v1_fn:<4} {v1_p:<6.3f} {v1_r:<6.3f} {v1_f1:<6.3f} | "
            f"{len(v2_preds):<7} {v2_tp:<4} {v2_fp:<4} {v2_fn:<4} {v2_p:<6.3f} {v2_r:<6.3f} {v2_f1:<6.3f}"
        )
        print(row_str)

    v1_m_p = v1_m_tot_tp / (v1_m_tot_tp + v1_m_tot_fp) if (v1_m_tot_tp + v1_m_tot_fp) > 0 else 0.0
    v1_m_r = v1_m_tot_tp / (v1_m_tot_tp + v1_m_tot_fn) if (v1_m_tot_tp + v1_m_tot_fn) > 0 else 0.0
    v1_m_f1 = 2 * v1_m_p * v1_m_r / (v1_m_p + v1_m_r) if (v1_m_p + v1_m_r) > 0 else 0.0

    v2_m_p = v2_m_tot_tp / (v2_m_tot_tp + v2_m_tot_fp) if (v2_m_tot_tp + v2_m_tot_fp) > 0 else 0.0
    v2_m_r = v2_m_tot_tp / (v2_m_tot_tp + v2_m_tot_fn) if (v2_m_tot_tp + v2_m_tot_fn) > 0 else 0.0
    v2_m_f1 = 2 * v2_m_p * v2_m_r / (v2_m_p + v2_m_r) if (v2_m_p + v2_m_r) > 0 else 0.0

    print("-" * 105)
    total_row_mov = (
        f"{'TOTAL':<5} {len(gt_events):<4} | "
        f"{len(v1_events):<7} {v1_m_tot_tp:<4} {v1_m_tot_fp:<4} {v1_m_tot_fn:<4} {v1_m_p:<6.3f} {v1_m_r:<6.3f} {v1_m_f1:<6.3f} | "
        f"{len(v2_events):<7} {v2_m_tot_tp:<4} {v2_m_tot_fp:<4} {v2_m_tot_fn:<4} {v2_m_p:<6.3f} {v2_m_r:<6.3f} {v2_m_f1:<6.3f}"
    )
    print(total_row_mov)
    print("=" * 105)

if __name__ == "__main__":
    main()

