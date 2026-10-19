"""End-to-End Evaluation of License Plate Detection and OCR on Real Test Images.

This script evaluates the complete ANPR pipeline (PlateReader) on the held-out TEST split
of real photos from `data/raw/indian-number-plates-dataset`.

Protocol:
1. Discovers TEST split photos using `data/processed/split_groups.json` (zero training photos).
2. Parses Pascal VOC XML annotations for ground-truth bounding boxes and plate strings.
3. Identifies plates whose text was not seen in train using `data/processed/ocr/real/labels.csv`.
4. Matches detector proposals with ground-truth boxes at IoU >= 0.5.
5. Computes:
   - Detection Precision & Recall
   - OCR Exact Match & Character Accuracy among detected plates
   - End-to-End Exact Match & Character Accuracy over all ground-truth plates
     (missed detections count as 0% accuracy)
   - Sliced metrics for unseen plate texts only
   - Average latency per image
6. Saves per-image evaluation results to `docs/ocr/end_to_end_results.csv`.
7. Saves a visual grid of 30 failures to `docs/end_to_end_failures.png`.
"""

import argparse
import csv
import json
import logging
import os
import re
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cv2
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from PIL import Image

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from pipeline.plate_reader import PlateReader

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def compute_iou(box1: List[float], box2: List[float]) -> float:
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
    union_area = area1 + area2 - inter_area

    if union_area <= 0.0:
        return 0.0
    return float(inter_area / union_area)


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
            if s1[i - 1] == s2[j - 1]:
                dp[i][j] = dp[i - 1][j - 1]
            else:
                dp[i][j] = 1 + min(dp[i - 1][j], dp[i][j - 1], dp[i - 1][j - 1])
    return dp[m][n]


def calc_char_acc(s1: str, s2: str) -> float:
    """Calculates character accuracy: 1 - (Levenshtein distance / max length)."""
    max_len = max(len(s1), len(s2))
    if max_len == 0:
        return 1.0
    return max(0.0, 1.0 - (levenshtein_dist(s1, s2) / float(max_len)))


def load_test_split_images(
    raw_dataset_dir: Path,
    split_groups_path: Path,
) -> List[Tuple[Path, Path]]:
    """Finds all real photos in indian-number-plates-dataset belonging to the TEST split.
    
    Returns:
        List of (image_path, xml_path) tuples.
    """
    if not split_groups_path.exists():
        raise FileNotFoundError(f"Split metadata not found at {split_groups_path}!")

    with open(split_groups_path, "r", encoding="utf-8") as f:
        meta = json.load(f)

    img_to_split = meta.get("image_to_split", {})
    group_splits = meta.get("group_splits", {})

    all_imgs = sorted([
        f for f in raw_dataset_dir.rglob("*")
        if f.suffix.lower() in (".jpg", ".jpeg", ".png")
    ])

    test_pairs: List[Tuple[Path, Path]] = []
    for img in all_imgs:
        rel_to_raw = str(img.relative_to(raw_dataset_dir)).replace("/", "\\")
        rel_to_parent = str(img.relative_to(raw_dataset_dir.parent)).replace("/", "\\")

        # Determine split
        split = (
            img_to_split.get(rel_to_parent)
            or img_to_split.get(rel_to_raw)
            or img_to_split.get(img.name)
            or img_to_split.get(img.stem)
        )

        if not split:
            # Fallback check on sequence group prefix
            m = re.match(r"^(video\d+)", img.name, re.IGNORECASE)
            grp = f"vid_{m.group(1).lower()}" if m else f"vid_{img.stem}"
            split = group_splits.get(grp, "train")

        if split == "test":
            cand1 = img.with_suffix(img.suffix + ".xml")
            cand2 = img.with_suffix(".xml")
            xml_p = cand1 if cand1.exists() else (cand2 if cand2.exists() else None)
            if xml_p and xml_p.exists():
                test_pairs.append((img, xml_p))

    return test_pairs


def parse_voc_xml(xml_path: Path) -> List[Dict[str, Any]]:
    """Parses Pascal VOC XML annotation file to extract plate bounding boxes and text."""
    tree = ET.parse(xml_path)
    root = tree.getroot()

    objects: List[Dict[str, Any]] = []
    for obj in root.findall("object"):
        name_el = obj.find("name")
        raw_text = name_el.text if name_el is not None and name_el.text else ""
        norm_text = PlateReader.normalize_text(raw_text)

        bnd = obj.find("bndbox")
        if bnd is None:
            continue

        try:
            xmin = float(bnd.find("xmin").text)
            ymin = float(bnd.find("ymin").text)
            xmax = float(bnd.find("xmax").text)
            ymax = float(bnd.find("ymax").text)
        except Exception:
            continue

        if xmax <= xmin or ymax <= ymin:
            continue

        objects.append({
            "box": [xmin, ymin, xmax, ymax],
            "raw_text": raw_text,
            "text": norm_text,
        })

    return objects


def run_evaluation(
    detector_path: str = "models/plate_detector.pt",
    ocr_dir: str = "models/plate_ocr",
    conf_thresh: float = 0.25,
    iou_thresh: float = 0.5,
    output_dir: str = "docs/ocr",
    demo_output_dir: str = "docs",
    max_images: Optional[int] = None,
) -> Dict[str, Any]:
    """Executes end-to-end evaluation and saves report tables and failure grid visualization."""
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    demo_out_path = Path(demo_output_dir)
    demo_out_path.mkdir(parents=True, exist_ok=True)

    # 1. Initialize PlateReader
    logger.info("Initializing PlateReader...")
    reader = PlateReader(
        detector_path=detector_path,
        ocr_dir=ocr_dir,
        conf_thresh=conf_thresh,
        device="auto",
    )

    # 2. Load set of plate texts seen in train to isolate true unseen generalization
    labels_csv_path = Path("data/processed/ocr/real/labels.csv")
    train_texts = set()
    if labels_csv_path.exists():
        df_labels = pd.read_csv(labels_csv_path)
        train_rows = df_labels[df_labels["path"].str.contains("train")]
        train_texts = set(train_rows["text"].dropna().str.upper().tolist())
        logger.info("Loaded %d unique plate texts seen during training.", len(train_texts))
    else:
        logger.warning("labels.csv not found; all plates will be marked as unseen.")

    # 3. Locate TEST split real photos
    raw_dataset_dir = Path("data/raw/indian-number-plates-dataset")
    split_meta_path = Path("data/processed/split_groups.json")
    test_pairs = load_test_split_images(raw_dataset_dir, split_meta_path)
    if max_images:
        test_pairs = test_pairs[:max_images]

    logger.info("Found %d test split images with XML annotations to evaluate.", len(test_pairs))
    if not test_pairs:
        raise RuntimeError("No test images found! Check data/raw/indian-number-plates-dataset and split_groups.json.")

    # 4. Evaluation Loop
    per_image_results: List[Dict[str, Any]] = []
    failures_to_plot: List[Dict[str, Any]] = []

    total_gt_all = 0
    total_det_all = 0
    tp_all = 0
    fp_all = 0
    fn_all = 0
    exact_match_all = 0
    char_acc_sum_matched_all = 0.0

    total_gt_unseen = 0
    tp_unseen = 0
    fn_unseen = 0
    exact_match_unseen = 0
    char_acc_sum_matched_unseen = 0.0

    latencies: List[float] = []

    print("\n" + "=" * 80)
    print("=== Running End-to-End Evaluation on Held-Out Real Test Photos ===")
    print("=" * 80)

    for idx, (img_path, xml_path) in enumerate(test_pairs, 1):
        gt_objects = parse_voc_xml(xml_path)
        if not gt_objects:
            continue

        # Time single image end-to-end inference
        t0 = time.perf_counter()
        detections = reader.read_image(img_path)
        t1 = time.perf_counter()
        latency_ms = (t1 - t0) * 1000.0
        latencies.append(latency_ms)

        # Match detections to GT using IoU >= 0.5
        matched_gt_indices = set()
        matched_det_indices = set()
        matches: List[Tuple[int, int, float]] = []

        # Compute all pairwise IoUs
        candidate_pairs = []
        for g_idx, gt in enumerate(gt_objects):
            for d_idx, det in enumerate(detections):
                iou = compute_iou(gt["box"], det["box"])
                if iou >= iou_thresh:
                    candidate_pairs.append((iou, g_idx, d_idx))

        # Greedy matching sorted by IoU descending
        candidate_pairs.sort(key=lambda x: x[0], reverse=True)
        for iou, g_idx, d_idx in candidate_pairs:
            if g_idx not in matched_gt_indices and d_idx not in matched_det_indices:
                matched_gt_indices.add(g_idx)
                matched_det_indices.add(d_idx)
                matches.append((g_idx, d_idx, iou))

        # Record per-image counts
        img_tp = len(matches)
        img_fp = len(detections) - img_tp
        img_fn = len(gt_objects) - img_tp

        total_gt_all += len(gt_objects)
        total_det_all += len(detections)
        tp_all += img_tp
        fp_all += img_fp
        fn_all += img_fn

        # Evaluate OCR on matched plates
        for g_idx, d_idx, iou in matches:
            gt_item = gt_objects[g_idx]
            det_item = detections[d_idx]

            gt_t = gt_item["text"]
            pred_t = det_item["text"]
            is_exact = (gt_t == pred_t)
            c_acc = calc_char_acc(gt_t, pred_t)
            is_unseen = (gt_t not in train_texts)

            if is_exact:
                exact_match_all += 1
            char_acc_sum_matched_all += c_acc

            if is_unseen:
                total_gt_unseen += 1
                tp_unseen += 1
                if is_exact:
                    exact_match_unseen += 1
                char_acc_sum_matched_unseen += c_acc

            per_image_results.append({
                "image_name": img_path.name,
                "image_path": str(img_path.resolve().relative_to(PROJECT_ROOT.resolve())).replace("\\", "/"),
                "gt_count": len(gt_objects),
                "det_count": len(detections),
                "tp": img_tp,
                "fp": img_fp,
                "fn": img_fn,
                "gt_text": gt_t,
                "pred_text": pred_t,
                "matched_iou": round(iou, 3),
                "exact_match": is_exact,
                "char_acc": round(c_acc, 4),
                "text_unseen": is_unseen,
                "det_conf": round(det_item["detector_confidence"], 3),
                "ocr_conf": round(det_item["ocr_confidence"], 3),
                "latency_ms": round(latency_ms, 1),
            })

            # Track failure cases (wrong text)
            if not is_exact:
                failures_to_plot.append({
                    "img_path": img_path,
                    "gt_box": gt_item["box"],
                    "det_box": det_item["box"],
                    "gt_text": gt_t,
                    "pred_text": pred_t,
                    "iou": iou,
                    "failure_type": "OCR Error",
                })

        # Track missed GT plates (False Negatives)
        for g_idx, gt_item in enumerate(gt_objects):
            if g_idx not in matched_gt_indices:
                gt_t = gt_item["text"]
                is_unseen = (gt_t not in train_texts)
                if is_unseen:
                    total_gt_unseen += 1
                    fn_unseen += 1

                per_image_results.append({
                    "image_name": img_path.name,
                    "image_path": str(img_path.resolve().relative_to(PROJECT_ROOT.resolve())).replace("\\", "/"),
                    "gt_count": len(gt_objects),
                    "det_count": len(detections),
                    "tp": 0,
                    "fp": img_fp,
                    "fn": 1,
                    "gt_text": gt_t,
                    "pred_text": "<MISSED>",
                    "matched_iou": 0.0,
                    "exact_match": False,
                    "char_acc": 0.0,
                    "text_unseen": is_unseen,
                    "det_conf": 0.0,
                    "ocr_conf": 0.0,
                    "latency_ms": round(latency_ms, 1),
                })

                failures_to_plot.append({
                    "img_path": img_path,
                    "gt_box": gt_item["box"],
                    "det_box": None,
                    "gt_text": gt_t,
                    "pred_text": "<MISSED>",
                    "iou": 0.0,
                    "failure_type": "Missed Detection",
                })

        if idx % 20 == 0 or idx == len(test_pairs):
            print(f"Processed {idx:>3}/{len(test_pairs)} images... (Avg Latency: {np.mean(latencies):.1f} ms)")

    # 5. Compute Final Metrics
    det_precision = (tp_all / (tp_all + fp_all) * 100.0) if (tp_all + fp_all) > 0 else 0.0
    det_recall = (tp_all / (tp_all + fn_all) * 100.0) if (tp_all + fn_all) > 0 else 0.0

    ocr_exact_among_det = (exact_match_all / tp_all * 100.0) if tp_all > 0 else 0.0
    ocr_char_among_det = (char_acc_sum_matched_all / tp_all * 100.0) if tp_all > 0 else 0.0

    e2e_exact_all = (exact_match_all / total_gt_all * 100.0) if total_gt_all > 0 else 0.0
    e2e_char_all = (char_acc_sum_matched_all / total_gt_all * 100.0) if total_gt_all > 0 else 0.0

    # Unseen slice metrics
    det_recall_unseen = (tp_unseen / (tp_unseen + fn_unseen) * 100.0) if (tp_unseen + fn_unseen) > 0 else 0.0
    ocr_exact_unseen = (exact_match_unseen / tp_unseen * 100.0) if tp_unseen > 0 else 0.0
    ocr_char_unseen = (char_acc_sum_matched_unseen / tp_unseen * 100.0) if tp_unseen > 0 else 0.0
    e2e_exact_unseen = (exact_match_unseen / total_gt_unseen * 100.0) if total_gt_unseen > 0 else 0.0
    e2e_char_unseen = (char_acc_sum_matched_unseen / total_gt_unseen * 100.0) if total_gt_unseen > 0 else 0.0

    avg_time_ms = float(np.mean(latencies))
    fps = 1000.0 / avg_time_ms if avg_time_ms > 0 else 0.0

    # 6. Save per-image results to CSV
    results_csv_path = out_path / "end_to_end_results.csv"
    df_results = pd.DataFrame(per_image_results)
    df_results.to_csv(results_csv_path, index=False)
    logger.info("Per-image results saved to: %s", results_csv_path)

    # 7. Print Summary Metrics Table
    summary_data = [
        {"Scope": "All Test Plates", "Metric": "1. Detection Precision (IoU >= 0.5)", "Value": f"{det_precision:.2f}% ({tp_all}/{tp_all + fp_all})"},
        {"Scope": "All Test Plates", "Metric": "2. Detection Recall (IoU >= 0.5)", "Value": f"{det_recall:.2f}% ({tp_all}/{total_gt_all})"},
        {"Scope": "All Test Plates", "Metric": "3. OCR Exact Match (Among Detected)", "Value": f"{ocr_exact_among_det:.2f}% ({exact_match_all}/{tp_all})"},
        {"Scope": "All Test Plates", "Metric": "4. OCR Character Accuracy (Among Detected)", "Value": f"{ocr_char_among_det:.2f}%"},
        {"Scope": "All Test Plates", "Metric": "5. End-to-End Exact Match (All GT Plates)", "Value": f"{e2e_exact_all:.2f}% ({exact_match_all}/{total_gt_all})"},
        {"Scope": "All Test Plates", "Metric": "6. End-to-End Char Accuracy (All GT Plates)", "Value": f"{e2e_char_all:.2f}%"},
        {"Scope": "Unseen Text Only", "Metric": "1. Detection Recall (IoU >= 0.5)", "Value": f"{det_recall_unseen:.2f}% ({tp_unseen}/{total_gt_unseen})"},
        {"Scope": "Unseen Text Only", "Metric": "2. OCR Exact Match (Among Detected)", "Value": f"{ocr_exact_unseen:.2f}% ({exact_match_unseen}/{tp_unseen})"},
        {"Scope": "Unseen Text Only", "Metric": "3. OCR Character Accuracy (Among Detected)", "Value": f"{ocr_char_unseen:.2f}%"},
        {"Scope": "Unseen Text Only", "Metric": "4. End-to-End Exact Match (All Unseen GT)", "Value": f"{e2e_exact_unseen:.2f}% ({exact_match_unseen}/{total_gt_unseen})"},
        {"Scope": "Unseen Text Only", "Metric": "5. End-to-End Char Accuracy (All Unseen GT)", "Value": f"{e2e_char_unseen:.2f}%"},
        {"Scope": "Latency & Speed", "Metric": "Average Latency per Image", "Value": f"{avg_time_ms:.1f} ms ({fps:.2f} FPS)"},
    ]

    print("\n" + "=" * 80)
    print("=== END-TO-END ANPR PIPELINE EVALUATION SUMMARY ===")
    print("=" * 80)
    summary_df = pd.DataFrame(summary_data)
    print(summary_df.to_string(index=False))
    print("=" * 80)

    # 8. Plot Grid of 30 Failures
    grid_img_path = demo_out_path / "end_to_end_failures.png"
    plot_failure_grid(failures_to_plot, grid_img_path, num_samples=30)
    logger.info("Failure grid saved to: %s", grid_img_path)

    return {
        "detection_precision": det_precision,
        "detection_recall": det_recall,
        "ocr_exact_among_det": ocr_exact_among_det,
        "ocr_char_among_det": ocr_char_among_det,
        "e2e_exact_all": e2e_exact_all,
        "e2e_char_all": e2e_char_all,
        "e2e_exact_unseen": e2e_exact_unseen,
        "e2e_char_unseen": e2e_char_unseen,
        "avg_time_ms": avg_time_ms,
        "results_csv": str(results_csv_path),
        "failures_png": str(grid_img_path),
    }


def plot_failure_grid(
    failures: List[Dict[str, Any]],
    output_path: Path,
    num_samples: int = 30,
) -> None:
    """Draws up to 30 failure cases on an image grid showing GT vs detected boxes and labels."""
    if not failures:
        logger.info("Zero failures to plot! All images evaluated perfectly.")
        return

    samples = failures[:num_samples]
    cols = 5
    rows = (len(samples) + cols - 1) // cols

    fig, axes = plt.subplots(rows, cols, figsize=(cols * 4.2, rows * 3.5))
    fig.patch.set_facecolor("#0f172a")

    axes_flat = axes.flat if hasattr(axes, "flat") else [axes]

    for idx, ax in enumerate(axes_flat):
        if idx < len(samples):
            f_item = samples[idx]
            im = cv2.imread(str(f_item["img_path"]))
            if im is not None:
                im_rgb = cv2.cvtColor(im, cv2.COLOR_BGR2RGB)
                h, w = im_rgb.shape[:2]

                # Draw Ground Truth Box in Green
                gt_box = [int(round(v)) for v in f_item["gt_box"]]
                cv2.rectangle(im_rgb, (gt_box[0], gt_box[1]), (gt_box[2], gt_box[3]), (34, 197, 94), 3)

                # Draw Detected Box in Red (if present)
                if f_item["det_box"] is not None:
                    det_box = [int(round(v)) for v in f_item["det_box"]]
                    cv2.rectangle(im_rgb, (det_box[0], det_box[1]), (det_box[2], det_box[3]), (239, 68, 68), 2)

                ax.imshow(im_rgb)

            title = (
                f"[{f_item['failure_type']}]\n"
                f"True: {f_item['gt_text']}\n"
                f"Pred: {f_item['pred_text']} (IoU: {f_item['iou']:.2f})"
            )
            ax.set_title(title, fontsize=8, color="#f87171" if f_item["failure_type"] == "OCR Error" else "#fbbf24", pad=2)
        ax.axis("off")

    plt.suptitle("End-to-End Pipeline Evaluation: 30 Failure Cases (Green = True, Red = Pred)", fontsize=14, color="#f8fafc", y=0.99)
    plt.tight_layout()
    plt.savefig(output_path, dpi=130, facecolor=fig.get_facecolor())
    plt.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate City-ANPR end-to-end pipeline on real test split.")
    parser.add_argument("--detector", type=str, default="models/plate_detector.pt", help="Path to YOLO detector weights.")
    parser.add_argument("--ocr-dir", type=str, default="models/plate_ocr", help="Directory with ONNX model and YAML config.")
    parser.add_argument("--conf", type=float, default=0.25, help="Detector confidence threshold.")
    parser.add_argument("--iou", type=float, default=0.5, help="IoU match threshold.")
    parser.add_argument("--out-dir", type=str, default="docs/ocr", help="Output directory for CSV results.")
    parser.add_argument("--demo-dir", type=str, default="docs", help="Output directory for failure grid PNG.")
    parser.add_argument("--max-images", type=int, default=None, help="Limit number of images for quick testing.")
    args = parser.parse_args()

    run_evaluation(
        detector_path=args.detector,
        ocr_dir=args.ocr_dir,
        conf_thresh=args.conf,
        iou_thresh=args.iou,
        output_dir=args.out_dir,
        demo_output_dir=args.demo_dir,
        max_images=args.max_images,
    )
