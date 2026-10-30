import csv
from collections import defaultdict
from pathlib import Path

def load_events(csv_path):
    events = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            events.append({
                "video_clip_id": int(row["video_clip_id"]),
                "frame_id": int(row["frame_id"]),
                "movement_id": int(row["movement_id"]),
                "vehicle_class_id": int(row["vehicle_class_id"])
            })
    return events

def greedy_match(pred_frames, gt_frames, max_frame_diff=20):
    """
    Greedily match predicted events to ground truth events within max_frame_diff.
    Each predicted event is matched to the closest available GT event.
    """
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

    return tp, fp, fn, precision, recall, f1, matched_pairs

def main():
    pred_csv = Path("counting_work") / "counts_pred.csv"
    gt_csv = Path(r"E:\AIC21_Track1_Vehicle_Counting\counting_gt_sample\counting_example_cam_5_1min.csv")

    if not pred_csv.exists():
        raise FileNotFoundError(f"Predicted counts file not found: {pred_csv}")
    if not gt_csv.exists():
        raise FileNotFoundError(f"Ground truth file not found: {gt_csv}")

    pred_events = load_events(pred_csv)
    gt_events = load_events(gt_csv)

    print("=" * 80)
    print("REAL video, 1 clip, 96 GT events, settings fixed before evaluation")
    print("=" * 80)

    # 1. Table per movement and class: GT count, predicted count, difference
    all_keys = set((e["movement_id"], e["vehicle_class_id"]) for e in gt_events).union(
        set((e["movement_id"], e["vehicle_class_id"]) for e in pred_events)
    )

    pred_by_key = defaultdict(list)
    for e in pred_events:
        pred_by_key[(e["movement_id"], e["vehicle_class_id"])].append(e["frame_id"])

    gt_by_key = defaultdict(list)
    for e in gt_events:
        gt_by_key[(e["movement_id"], e["vehicle_class_id"])].append(e["frame_id"])

    print("\n--- TABLE: COUNTS PER MOVEMENT AND CLASS ---")
    print(f"{'Movement':<10} {'Class':<16} {'GT Count':<10} {'Pred Count':<12} {'Difference':<12}")
    print("-" * 62)

    total_gt = len(gt_events)
    total_pred = len(pred_events)

    for m_id, c_id in sorted(all_keys):
        c_name = "Car (1)" if c_id == 1 else "Truck (2)"
        gt_cnt = len(gt_by_key[(m_id, c_id)])
        pred_cnt = len(pred_by_key[(m_id, c_id)])
        diff = pred_cnt - gt_cnt
        print(f"M{m_id:<9} {c_name:<16} {gt_cnt:<10} {pred_cnt:<12} {diff:+d}")

    print("-" * 62)
    print(f"{'TOTAL':<27} {total_gt:<10} {total_pred:<12} {total_pred - total_gt:+d}")

    # 2. Event matching per (movement, class) with absolute frame difference <= 20
    print("\n--- EVENT MATCHING PER (MOVEMENT, CLASS) (Tolerance <= 20 frames) ---")
    print(f"{'Movement':<10} {'Class':<12} {'GT':<6} {'Pred':<6} {'TP':<6} {'FP':<6} {'FN':<6} {'Precision':<10} {'Recall':<10} {'F1':<10}")
    print("-" * 84)

    total_tp = 0
    total_fp = 0
    total_fn = 0

    for m_id, c_id in sorted(all_keys):
        c_name = "Car" if c_id == 1 else "Truck"
        preds = pred_by_key[(m_id, c_id)]
        gts = gt_by_key[(m_id, c_id)]

        tp, fp, fn, prec, rec, f1, _ = greedy_match(preds, gts, max_frame_diff=20)
        total_tp += tp
        total_fp += fp
        total_fn += fn

        print(f"M{m_id:<9} {c_name:<12} {len(gts):<6} {len(preds):<6} {tp:<6} {fp:<6} {fn:<6} {prec:<10.3f} {rec:<10.3f} {f1:<10.3f}")

    tot_prec = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0.0
    tot_rec = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0.0
    tot_f1 = 2 * tot_prec * tot_rec / (tot_prec + tot_rec) if (tot_prec + tot_rec) > 0 else 0.0

    print("-" * 84)
    print(f"{'TOTAL':<23} {total_gt:<6} {total_pred:<6} {total_tp:<6} {total_fp:<6} {total_fn:<6} {tot_prec:<10.3f} {tot_rec:<10.3f} {tot_f1:<10.3f}")

    # 3. Event matching ignoring the class
    all_movements = sorted(set(e["movement_id"] for e in gt_events).union(set(e["movement_id"] for e in pred_events)))

    pred_by_mov = defaultdict(list)
    for e in pred_events:
        pred_by_mov[e["movement_id"]].append(e["frame_id"])

    gt_by_mov = defaultdict(list)
    for e in gt_events:
        gt_by_mov[e["movement_id"]].append(e["frame_id"])

    print("\n--- EVENT MATCHING PER MOVEMENT (IGNORING CLASS) (Tolerance <= 20 frames) ---")
    print(f"{'Movement':<12} {'GT':<6} {'Pred':<6} {'TP':<6} {'FP':<6} {'FN':<6} {'Precision':<10} {'Recall':<10} {'F1':<10}")
    print("-" * 74)

    mov_total_tp = 0
    mov_total_fp = 0
    mov_total_fn = 0

    for m_id in all_movements:
        preds = pred_by_mov[m_id]
        gts = gt_by_mov[m_id]

        tp, fp, fn, prec, rec, f1, _ = greedy_match(preds, gts, max_frame_diff=20)
        mov_total_tp += tp
        mov_total_fp += fp
        mov_total_fn += fn

        print(f"M{m_id:<11} {len(gts):<6} {len(preds):<6} {tp:<6} {fp:<6} {fn:<6} {prec:<10.3f} {rec:<10.3f} {f1:<10.3f}")

    mov_tot_prec = mov_total_tp / (mov_total_tp + mov_total_fp) if (mov_total_tp + mov_total_fp) > 0 else 0.0
    mov_tot_rec = mov_total_tp / (mov_total_tp + mov_total_fn) if (mov_total_tp + mov_total_fn) > 0 else 0.0
    mov_tot_f1 = 2 * mov_tot_prec * mov_tot_rec / (mov_tot_prec + mov_tot_rec) if (mov_tot_prec + mov_tot_rec) > 0 else 0.0

    print("-" * 74)
    print(f"{'TOTAL':<12} {total_gt:<6} {total_pred:<6} {mov_total_tp:<6} {mov_total_fp:<6} {mov_total_fn:<6} {mov_tot_prec:<10.3f} {mov_tot_rec:<10.3f} {mov_tot_f1:<10.3f}")
    print("=" * 80)

if __name__ == "__main__":
    main()

