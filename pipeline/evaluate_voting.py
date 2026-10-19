"""Evaluation Script for Multi-Frame Plate Voting on Real Sequences and Synthetic Clips.

Protocol:
1. Table 1 (Real Video Sequences):
   - Loads `data/processed/split_groups.json` to isolate TEST split video sequences
     (`vid_video2` from `data/raw/indian-number-plates-dataset/video_images/`).
   - Reconstructs ground-truth vehicle sequences from Pascal VOC XML annotations.
   - Evaluates frame-by-frame predictions against multi-frame consensus voting.
   - Reports sequence count, average frames per sequence, and warns if single-frame
     sequences dominate where voting cannot help.
2. Table 2 (Synthetic Approaching Video Clips):
   - Loads 24-frame approaching vehicle clips from `data/video_events/synthetic/`
     (generated strictly from TEST split photos).
   - Evaluates per-frame exact match, voted exact match, and character accuracy for both.
   - Explicitly notes: "These clips are synthetic and all frames of one clip come from a
     single photo, so voting gains on them are optimistic and must not be reported as
     real-world results."
3. Exports detailed per-sequence and per-clip rows to `docs/ocr/voting_results.csv`
   and a comprehensive markdown summary to `docs/ocr/voting_summary.md`.
"""

import argparse
import json
import os
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np
import pandas as pd

from pipeline.plate_reader import PlateReader
from pipeline.voting import PlateVoting


def compute_iou(box1: List[float], box2: List[float]) -> float:
    """Computes IoU between [x1, y1, x2, y2] boxes."""
    xa = max(box1[0], box2[0])
    ya = max(box1[1], box2[1])
    xb = min(box1[2], box2[2])
    yb = min(box1[3], box2[3])

    inter = max(0.0, xb - xa) * max(0.0, yb - ya)
    area1 = max(0.0, box1[2] - box1[0]) * max(0.0, box1[3] - box1[1])
    area2 = max(0.0, box2[2] - box2[0]) * max(0.0, box2[3] - box2[1])
    union = area1 + area2 - inter
    return float(inter / union) if union > 0 else 0.0


def levenshtein_dist(s1: str, s2: str) -> int:
    """Computes Levenshtein edit distance between two strings."""
    m, n = len(s1), len(s2)
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(m + 1):
        dp[i][0] = i
    for j in range(n + 1):
        dp[0][j] = j
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            cost = 0 if s1[i - 1] == s2[j - 1] else 1
            dp[i][j] = min(dp[i - 1][j] + 1, dp[i][j - 1] + 1, dp[i - 1][j - 1] + cost)
    return dp[m][n]


def calc_char_acc(s1: str, s2: str) -> float:
    """Calculates character accuracy: 1 - (Levenshtein distance / max length)."""
    max_len = max(len(s1), len(s2))
    if max_len == 0:
        return 1.0
    return max(0.0, 1.0 - (levenshtein_dist(s1, s2) / float(max_len)))


def load_test_sequences(
    raw_images_dir: Path,
    split_meta_path: Path,
) -> Dict[str, List[Dict[str, Any]]]:
    """Loads and groups TEST split video frames into vehicle sequences by ground truth plate."""
    if not split_meta_path.exists():
        raise FileNotFoundError(f"split_groups.json not found at: {split_meta_path.resolve()}")

    with open(split_meta_path, "r", encoding="utf-8") as f:
        meta = json.load(f)

    # Collect TEST split video files
    test_files = set()
    for k, v in meta.get("image_to_split", {}).items():
        if v == "test" and "video" in k and k.endswith(".jpg"):
            test_files.add(Path(k).name)

    # Sort frame files numerically/naturally
    def frame_sort_key(p: Path) -> int:
        match = re.search(r"video\d+_(\d+)", p.stem)
        return int(match.group(1)) if match else 0

    sorted_frames = sorted(
        [raw_images_dir / fn for fn in test_files if (raw_images_dir / fn).exists()],
        key=frame_sort_key,
    )

    sequences: Dict[str, List[Dict[str, Any]]] = {}

    for frame_path in sorted_frames:
        xml_path = frame_path.with_suffix(".xml")
        if not xml_path.exists():
            continue

        try:
            tree = ET.parse(xml_path)
            root = tree.getroot()
        except Exception:
            continue

        for obj in root.findall("object"):
            raw_name = obj.find("name")
            if raw_name is None or not raw_name.text:
                continue
            gt_text = PlateReader.normalize_text(raw_name.text)
            if not gt_text:
                continue

            bnd = obj.find("bndbox")
            if bnd is None:
                continue

            box = [
                float(bnd.find("xmin").text),
                float(bnd.find("ymin").text),
                float(bnd.find("xmax").text),
                float(bnd.find("ymax").text),
            ]

            match = re.search(r"video\d+_(\d+)", frame_path.stem)
            f_num = int(match.group(1)) if match else 0

            sequences.setdefault(gt_text, []).append({
                "frame_num": f_num,
                "frame_path": frame_path,
                "gt_box": box,
                "gt_plate": gt_text,
            })

    return sequences


def evaluate_synthetic_clips(
    reader: PlateReader,
    voter: PlateVoting,
    synthetic_dir: Path,
    max_clips: Optional[int] = None,
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Evaluates multi-frame voting on synthetic approaching video clips."""
    gt_csv = synthetic_dir / "ground_truth.csv"
    if not gt_csv.exists():
        gt_csv = synthetic_dir / "synthetic_ground_truth.csv"
    if not gt_csv.exists():
        print(f"Warning: ground_truth.csv not found in {synthetic_dir}. Skipping synthetic clips.")
        return pd.DataFrame(), {}

    df_gt = pd.read_csv(gt_csv)
    if max_clips and max_clips > 0:
        df_gt = df_gt.head(max_clips)

    total_clips = len(df_gt)
    print(f"  Evaluating {total_clips} synthetic clips ({total_clips * 24} total frames) with YOLOv8 + fast-plate-ocr...", flush=True)

    records = []

    for c_idx, row in df_gt.iterrows():
        clip_name = str(row["clip_name"])
        true_plate = PlateReader.normalize_text(str(row["true_plate"]))
        clip_path = synthetic_dir / clip_name

        if not clip_path.exists():
            continue

        cap = cv2.VideoCapture(str(clip_path))
        if not cap.isOpened():
            continue

        frame_readings = []
        frame_exacts = []
        frame_chars = []
        f_idx = 0

        while True:
            ret, frame = cap.read()
            if not ret or frame is None:
                break

            # Run PlateReader on frame
            dets = reader.read_image(frame, is_bgr=True)
            if dets:
                best_det = max(dets, key=lambda d: d.get("ocr_confidence", 0.0))
                pred_txt = best_det["text"]
                ocr_conf = best_det["ocr_confidence"]
                det_conf = best_det["detector_confidence"]
                crop_arr = best_det["crop"]
            else:
                pred_txt = ""
                ocr_conf = 0.0
                det_conf = 0.0
                crop_arr = None

            is_match = (pred_txt == true_plate)
            c_acc = calc_char_acc(true_plate, pred_txt)

            frame_exacts.append(1.0 if is_match else 0.0)
            frame_chars.append(c_acc)

            frame_readings.append({
                "frame_idx": f_idx,
                "text": pred_txt,
                "ocr_confidence": ocr_conf,
                "detector_confidence": det_conf,
                "crop": crop_arr,
            })
            f_idx += 1

        cap.release()

        # Multi-frame consensus voting
        voted = voter.vote(frame_readings)
        voted_text = voted["plate"]
        voted_exact = 1.0 if (voted_text == true_plate) else 0.0
        voted_char_acc = calc_char_acc(true_plate, voted_text)

        mean_f_exact = float(np.mean(frame_exacts)) if frame_exacts else 0.0
        mean_f_char = float(np.mean(frame_chars)) if frame_chars else 0.0

        records.append({
            "dataset_type": "synthetic",
            "sequence_id": f"synth_{c_idx + 1:03d}",
            "clip_name": clip_name,
            "gt_plate": true_plate,
            "n_frames": len(frame_readings),
            "is_single_frame": False,
            "avg_frame_exact_pct": round(mean_f_exact * 100.0, 2),
            "voted_exact_pct": round(voted_exact * 100.0, 2),
            "avg_frame_char_acc_pct": round(mean_f_char * 100.0, 2),
            "voted_char_acc_pct": round(voted_char_acc * 100.0, 2),
            "voted_plate": voted_text,
            "vote_margin": voted["vote_margin"],
            "voting_method": voted["method"],
            "delta_exact_pct": round((voted_exact - mean_f_exact) * 100.0, 2),
            "delta_char_pct": round((voted_char_acc - mean_f_char) * 100.0, 2),
        })

        # Periodic live progress print so the user knows the terminal is actively working
        if (c_idx + 1) % 5 == 0 or (c_idx + 1) == total_clips:
            print(
                f"  -> Synthetic progress: [{c_idx + 1:>2}/{total_clips}] clips processed | "
                f"Latest: {clip_name} (GT: '{true_plate}', Voted: '{voted_text}')",
                flush=True,
            )

    df_synth = pd.DataFrame(records)
    if df_synth.empty:
        return df_synth, {}

    summary = {
        "n_clips": len(df_synth),
        "mean_frame_exact": float(df_synth["avg_frame_exact_pct"].mean()),
        "voted_exact": float(df_synth["voted_exact_pct"].mean()),
        "delta_exact": float(df_synth["voted_exact_pct"].mean()) - float(df_synth["avg_frame_exact_pct"].mean()),
        "mean_frame_char": float(df_synth["avg_frame_char_acc_pct"].mean()),
        "voted_char": float(df_synth["voted_char_acc_pct"].mean()),
        "delta_char": float(df_synth["voted_char_acc_pct"].mean()) - float(df_synth["avg_frame_char_acc_pct"].mean()),
    }
    return df_synth, summary


def run_evaluation(
    raw_images_dir: Path = Path("data/raw/indian-number-plates-dataset/video_images"),
    split_meta_path: Path = Path("data/processed/split_groups.json"),
    synthetic_dir: Path = Path("data/video_events/synthetic"),
    detector_path: Path = Path("models/plate_detector.pt"),
    ocr_dir: Path = Path("models/plate_ocr"),
    output_csv: Path = Path("docs/ocr/voting_results.csv"),
    output_summary: Path = Path("docs/ocr/voting_summary.md"),
    min_confidence: float = 0.35,
    max_synthetic_clips: Optional[int] = 60,
) -> Dict[str, Any]:
    """Runs sequence voting evaluation and outputs metrics and reports."""
    reader = PlateReader(
        detector_path=detector_path,
        ocr_dir=ocr_dir,
        conf_thresh=0.25,
        device="auto",
        padding_ratio=0.05,
    )
    voter = PlateVoting(min_confidence=min_confidence)

    # =========================================================================
    # PART 1: EVALUATE REAL TEST VIDEO SEQUENCES (video_images)
    # =========================================================================
    sequences = load_test_sequences(raw_images_dir, split_meta_path)
    total_seqs = len(sequences)
    if total_seqs == 0:
        raise RuntimeError("No test video sequences found!")

    lens = [len(frames) for frames in sequences.values()]
    avg_frames = float(np.mean(lens))
    single_frame_count = sum(1 for l in lens if l == 1)
    single_frame_pct = (single_frame_count / total_seqs) * 100.0

    print("\n" + "=" * 85)
    print("=== MULTI-FRAME PLATE VOTING EVALUATION: REAL & SYNTHETIC ===")
    print("=" * 85)
    print(f"Real Video Sequences:          {total_seqs}")
    print(f"Average Frames per Sequence:   {avg_frames:.2f}")
    print(f"Min / Max Frames per Sequence: {min(lens)} / {max(lens)}")
    print(f"Single-Frame Sequences:        {single_frame_count} ({single_frame_pct:.1f}%)")
    print(f"Multi-Frame Sequences:         {total_seqs - single_frame_count} ({100.0 - single_frame_pct:.1f}%)")

    if single_frame_pct >= 40.0:
        print("\n" + "!" * 85)
        print("  [WARNING] A LARGE FRACTION OF REAL SEQUENCES ARE SINGLE FRAMES:")
        print(f"  {single_frame_count} of {total_seqs} sequences ({single_frame_pct:.1f}%) contain exactly 1 frame.")
        print("  Voting cannot improve single-frame detections because there are no additional")
        print("  frames to cross-validate or resolve consensus.")
        print("!" * 85)

    print(f"\nProcessing {total_seqs} real test video sequences ({sum(lens)} frames)...", flush=True)
    real_records = []

    for s_idx, (gt_plate, frames) in enumerate(sequences.items(), 1):
        frame_readings = []
        frame_exacts = []
        frame_chars = []

        for f_item in frames:
            f_path = f_item["frame_path"]
            gt_b = f_item["gt_box"]
            im_bgr = cv2.imread(str(f_path))
            if im_bgr is None:
                continue

            h_im, w_im = im_bgr.shape[:2]

            # Detect plates
            detections = reader.read_image(im_bgr, is_bgr=True)
            matched_det = None
            best_iou = 0.0

            for det in detections:
                iou = compute_iou(gt_b, det["box"])
                if iou >= 0.4 and iou > best_iou:
                    best_iou = iou
                    matched_det = det

            if matched_det is not None:
                pred_txt = matched_det["text"]
                ocr_conf = matched_det["ocr_confidence"]
                det_conf = matched_det["detector_confidence"]
                crop_arr = matched_det["crop"]
            else:
                # Fallback crop using GT box with 5% padding
                pad_w = (gt_b[2] - gt_b[0]) * 0.05
                pad_h = (gt_b[3] - gt_b[1]) * 0.05
                x1 = max(0, int(round(gt_b[0] - pad_w)))
                y1 = max(0, int(round(gt_b[1] - pad_h)))
                x2 = min(w_im, int(round(gt_b[2] + pad_w)))
                y2 = min(h_im, int(round(gt_b[3] + pad_h)))
                crop_arr = im_bgr[y1:y2, x1:x2]
                if crop_arr.size > 0:
                    crop_rgb = cv2.cvtColor(crop_arr, cv2.COLOR_BGR2RGB)
                    preds = reader.recognizer.run(crop_rgb)
                    raw_p = preds[0].plate if hasattr(preds[0], "plate") else str(preds[0])
                    pred_txt = PlateReader.normalize_text(raw_p)
                    ocr_conf = float(np.mean(preds[0].char_probs)) if (hasattr(preds[0], "char_probs") and preds[0].char_probs is not None) else 0.85
                else:
                    pred_txt = ""
                    ocr_conf = 0.0
                det_conf = 0.0

            is_match = (pred_txt == gt_plate)
            c_acc = calc_char_acc(gt_plate, pred_txt)

            frame_exacts.append(1.0 if is_match else 0.0)
            frame_chars.append(c_acc)

            frame_readings.append({
                "frame_idx": f_item["frame_num"],
                "text": pred_txt,
                "ocr_confidence": ocr_conf,
                "detector_confidence": det_conf,
                "crop": crop_arr,
            })

        # Apply multi-frame consensus voting
        voted = voter.vote(frame_readings)
        voted_text = voted["plate"]
        voted_exact = 1.0 if (voted_text == gt_plate) else 0.0
        voted_char_acc = calc_char_acc(gt_plate, voted_text)

        mean_frame_exact = float(np.mean(frame_exacts)) if frame_exacts else 0.0
        mean_frame_char = float(np.mean(frame_chars)) if frame_chars else 0.0

        real_records.append({
            "dataset_type": "real",
            "sequence_id": f"real_{s_idx:02d}",
            "clip_name": f"seq_{gt_plate}",
            "gt_plate": gt_plate,
            "n_frames": len(frames),
            "is_single_frame": (len(frames) == 1),
            "avg_frame_exact_pct": round(mean_frame_exact * 100.0, 2),
            "voted_exact_pct": round(voted_exact * 100.0, 2),
            "avg_frame_char_acc_pct": round(mean_frame_char * 100.0, 2),
            "voted_char_acc_pct": round(voted_char_acc * 100.0, 2),
            "voted_plate": voted_text,
            "vote_margin": voted["vote_margin"],
            "voting_method": voted["method"],
            "delta_exact_pct": round((voted_exact - mean_frame_exact) * 100.0, 2),
            "delta_char_pct": round((voted_char_acc - mean_frame_char) * 100.0, 2),
        })

        if s_idx % 5 == 0 or s_idx == total_seqs:
            print(
                f"  -> Real progress: [{s_idx:>2}/{total_seqs}] sequences processed | "
                f"Latest: {gt_plate} (Voted: '{voted_text}')",
                flush=True,
            )

    df_real = pd.DataFrame(real_records)

    # Metrics for real sequences
    overall_frame_exact = float(df_real["avg_frame_exact_pct"].mean())
    overall_voted_exact = float(df_real["voted_exact_pct"].mean())
    overall_frame_char = float(df_real["avg_frame_char_acc_pct"].mean())
    overall_voted_char = float(df_real["voted_char_acc_pct"].mean())

    multi_df = df_real[~df_real["is_single_frame"]]
    multi_frame_exact = float(multi_df["avg_frame_exact_pct"].mean()) if not multi_df.empty else 0.0
    multi_voted_exact = float(multi_df["voted_exact_pct"].mean()) if not multi_df.empty else 0.0
    multi_frame_char = float(multi_df["avg_frame_char_acc_pct"].mean()) if not multi_df.empty else 0.0
    multi_voted_char = float(multi_df["voted_char_acc_pct"].mean()) if not multi_df.empty else 0.0

    single_df = df_real[df_real["is_single_frame"]]
    single_frame_exact = float(single_df["avg_frame_exact_pct"].mean()) if not single_df.empty else 0.0
    single_voted_exact = float(single_df["voted_exact_pct"].mean()) if not single_df.empty else 0.0

    # Print Table 1: Real Sequences
    print("\n" + "=" * 85)
    print("TABLE 1: REAL TEST VIDEO SEQUENCES (indian-number-plates-dataset/video_images)")
    print("=" * 85)
    print(f"{'Metric Scope':<32} | {'Per-Frame Avg':>15} | {'Voted Consensus':>17} | {'Delta':>10}")
    print("-" * 85)
    print(f"{'All Sequences (Exact Match)':<32} | {overall_frame_exact:>14.2f}% | {overall_voted_exact:>16.2f}% | {overall_voted_exact - overall_frame_exact:>+9.2f}%")
    print(f"{'All Sequences (Character Acc)':<32} | {overall_frame_char:>14.2f}% | {overall_voted_char:>16.2f}% | {overall_voted_char - overall_frame_char:>+9.2f}%")
    print("-" * 85)
    print(f"{'Multi-Frame Only (Exact Match)':<32} | {multi_frame_exact:>14.2f}% | {multi_voted_exact:>16.2f}% | {multi_voted_exact - multi_frame_exact:>+9.2f}%")
    print(f"{'Multi-Frame Only (Char Acc)':<32} | {multi_frame_char:>14.2f}% | {multi_voted_char:>16.2f}% | {multi_voted_char - multi_frame_char:>+9.2f}%")
    print(f"{'Single-Frame Only (Exact Match)':<32} | {single_frame_exact:>14.2f}% | {single_voted_exact:>16.2f}% | {single_voted_exact - single_frame_exact:>+9.2f}%")
    print("-" * 85)

    # =========================================================================
    # PART 2: EVALUATE SYNTHETIC APPROACHING VIDEO CLIPS
    # =========================================================================
    print("\n" + "=" * 85)
    print("TABLE 2: SYNTHETIC VEHICLE APPROACHING CLIPS (data/video_events/synthetic/)")
    print("=" * 85)
    print("  [IMPORTANT NOTICE ON SYNTHETIC CLIPS]:")
    print("  These clips are synthetic and all frames of one clip come from a single photo,")
    print("  so voting gains on them are optimistic and must not be reported as real-world results.")
    print("-" * 85)

    df_synth, synth_summary = evaluate_synthetic_clips(
        reader=reader,
        voter=voter,
        synthetic_dir=synthetic_dir,
        max_clips=max_synthetic_clips,
    )

    if not df_synth.empty and synth_summary:
        s_f_exact = synth_summary["mean_frame_exact"]
        s_v_exact = synth_summary["voted_exact"]
        s_d_exact = synth_summary["delta_exact"]
        s_f_char = synth_summary["mean_frame_char"]
        s_v_char = synth_summary["voted_char"]
        s_d_char = synth_summary["delta_char"]

        print(f"{'Metric Scope':<32} | {'Per-Frame Avg':>15} | {'Voted Consensus':>17} | {'Delta':>10}")
        print("-" * 85)
        print(f"{'Synthetic Clips (Exact Match)':<32} | {s_f_exact:>14.2f}% | {s_v_exact:>16.2f}% | {s_d_exact:>+9.2f}%")
        print(f"{'Synthetic Clips (Character Acc)':<32} | {s_f_char:>14.2f}% | {s_v_char:>16.2f}% | {s_d_char:>+9.2f}%")
        print("-" * 85)
    else:
        print("  (Synthetic clips not found or skipped)")
        s_f_exact = s_v_exact = s_d_exact = s_f_char = s_v_char = s_d_char = 0.0

    # Save combined results CSV
    if not df_synth.empty:
        df_combined = pd.concat([df_real, df_synth], ignore_index=True)
    else:
        df_combined = df_real

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    df_combined.to_csv(output_csv, index=False)

    # Generate Markdown Summary Report
    markdown_content = f"""# Multi-Frame Plate Voting Evaluation Report

This report evaluates temporal consensus plate voting across:
1. **Real Video Sequences** from the held-out TEST split (`indian-number-plates-dataset/video_images`).
2. **Synthetic Approaching Clips** generated from held-out TEST split photos (`data/video_events/synthetic/`).

---

## 1. Table 1: Real Video Sequences (`video_images`)

| Metric | All Real Sequences (N={total_seqs}) | Multi-Frame Only (N={len(multi_df)}) | Single-Frame Only (N={len(single_df)}) |
| :--- | :---: | :---: | :---: |
| **Average Frames / Sequence** | {avg_frames:.2f} | {float(multi_df['n_frames'].mean()):.2f} | 1.00 |
| **Per-Frame Average Exact Match** | {overall_frame_exact:.2f}% | {multi_frame_exact:.2f}% | {single_frame_exact:.2f}% |
| **Voted Consensus Exact Match** | **{overall_voted_exact:.2f}%** | **{multi_voted_exact:.2f}%** | **{single_voted_exact:.2f}%** |
| **Exact Match Delta** | **{overall_voted_exact - overall_frame_exact:+.2f}%** | **{multi_voted_exact - multi_frame_exact:+.2f}%** | **{single_voted_exact - single_frame_exact:+.2f}%** |
| **Per-Frame Average Char Acc** | {overall_frame_char:.2f}% | {multi_frame_char:.2f}% | {float(single_df['avg_frame_char_acc_pct'].mean()):.2f}% |
| **Voted Consensus Char Acc** | **{overall_voted_char:.2f}%** | **{multi_voted_char:.2f}%** | **{float(single_df['voted_char_acc_pct'].mean()):.2f}%** |
| **Character Accuracy Delta** | **{overall_voted_char - overall_frame_char:+.2f}%** | **{multi_voted_char - multi_frame_char:+.2f}%** | **0.00%** |

> [!WARNING]
> **Single-Frame Limitation on Real Sequences:**
> In this test video split, **{single_frame_count} out of {total_seqs} sequences ({single_frame_pct:.1f}%)** consist of exactly **one frame**.
> Voting fundamentally relies on temporal consensus across multiple independent looks at the vehicle plate. On single-frame detections, voting is an identity operation—it cannot correct errors or resolve consensus because no second reading exists.

---

## 2. Table 2: Synthetic Approaching Video Clips (`synthetic/`)

> [!CAUTION]
> **Optimistic Benchmark Notice:**
> These clips are synthetic and all frames of one clip originate from a single static photo in the TEST split, transformed across 24 frames with zoom, pan, noise, and compression.
> Consequently, multi-frame voting gains on them are **optimistic and must not be reported as real-world results**.

| Metric Scope | Per-Frame Average | Voted Consensus | Delta |
| :--- | :---: | :---: | :---: |
| **Synthetic Clips (Exact Match, N={len(df_synth)})** | {s_f_exact:.2f}% | **{s_v_exact:.2f}%** | **{s_d_exact:+.2f}%** |
| **Synthetic Clips (Character Accuracy)** | {s_f_char:.2f}% | **{s_v_char:.2f}%** | **{s_d_char:+.2f}%** |

---

## 3. Detailed Results Preview

| Sequence / Clip | Type | Ground Truth | Frames | Voted Plate | Frame Exact (Avg) | Voted Exact | Frame Char Acc | Voted Char Acc | Margin |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
"""
    # Sample 10 real and 10 synthetic
    sample_rows = pd.concat([df_real.head(10), df_synth.head(10)], ignore_index=True)
    for _, r in sample_rows.iterrows():
        match_sym = "MATCH" if r["voted_exact_pct"] == 100.0 else "MISMATCH"
        markdown_content += (
            f"| `{r['sequence_id']}` | `{r['dataset_type']}` | `{r['gt_plate']}` | {r['n_frames']} | "
            f"`{r['voted_plate']}` | {r['avg_frame_exact_pct']:.1f}% | {r['voted_exact_pct']:.1f}% ({match_sym}) | "
            f"{r['avg_frame_char_acc_pct']:.1f}% | {r['voted_char_acc_pct']:.1f}% | {r['vote_margin']:.2f} |\n"
        )

    output_summary.parent.mkdir(parents=True, exist_ok=True)
    with open(output_summary, "w", encoding="utf-8") as f:
        f.write(markdown_content)

    print(f"\n[OK] Results CSV saved to:     {output_csv.resolve()}")
    print(f"[OK] Markdown Summary saved to: {output_summary.resolve()}")
    print("=" * 85)

    return {
        "real_sequences": total_seqs,
        "synthetic_clips": len(df_synth),
        "results_csv": str(output_csv),
        "summary_md": str(output_summary),
    }


def main():
    parser = argparse.ArgumentParser(description="Evaluate multi-frame plate voting on real sequences and synthetic clips.")
    parser.add_argument("--raw-images-dir", type=str, default="data/raw/indian-number-plates-dataset/video_images")
    parser.add_argument("--split-meta-path", type=str, default="data/processed/split_groups.json")
    parser.add_argument("--synthetic-dir", type=str, default="data/video_events/synthetic")
    parser.add_argument("--detector-path", type=str, default="models/plate_detector.pt")
    parser.add_argument("--ocr-dir", type=str, default="models/plate_ocr")
    parser.add_argument("--output-csv", type=str, default="docs/ocr/voting_results.csv")
    parser.add_argument("--output-summary", type=str, default="docs/ocr/voting_summary.md")
    parser.add_argument("--min-confidence", type=float, default=0.35)
    parser.add_argument("--max-synthetic-clips", type=int, default=60)
    args = parser.parse_args()

    run_evaluation(
        raw_images_dir=Path(args.raw_images_dir),
        split_meta_path=Path(args.split_meta_path),
        synthetic_dir=Path(args.synthetic_dir),
        detector_path=Path(args.detector_path),
        ocr_dir=Path(args.ocr_dir),
        output_csv=Path(args.output_csv),
        output_summary=Path(args.output_summary),
        min_confidence=args.min_confidence,
        max_synthetic_clips=args.max_synthetic_clips,
    )


if __name__ == "__main__":
    main()
