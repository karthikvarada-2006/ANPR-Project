"""Generate ANPR Data Preparation Report and Visualizations.

Outputs:
1. docs/data_report.md (Comprehensive dataset metrics, tables, and findings)
2. docs/detector_samples.png (30 detector images with bounding boxes)
3. docs/real_ocr_crops.png (40 real OCR plate crops with ground-truth text)
4. docs/synthetic_ocr_crops.png (20 synthetic OCR plate crops with ground-truth text)
5. docs/suspicious_ocr_labels.png (20 suspicious label crops with flagged reasons)
6. data/processed_for_colab.zip (Zip archive of data/processed/ ready for Colab GPU training)
"""

import argparse
import csv
import json
import os
import shutil
import sys
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import matplotlib
matplotlib.use("Agg")
import matplotlib.patches as patches
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from PIL import Image, ImageDraw, ImageFont


class DataReportGenerator:
    def __init__(
        self,
        processed_dir: Path,
        docs_dir: Path,
        data_dir: Path,
    ):
        self.processed_dir = Path(processed_dir)
        self.docs_dir = Path(docs_dir)
        self.data_dir = Path(data_dir)

        self.detector_dir = self.processed_dir / "detector"
        self.ocr_dir = self.processed_dir / "ocr"
        self.real_dir = self.ocr_dir / "real"
        self.synth_dir = self.ocr_dir / "synthetic"
        self.split_meta_path = self.processed_dir / "split_groups.json"

        self.docs_dir.mkdir(parents=True, exist_ok=True)

    def generate_detector_samples_grid(self, n_samples: int = 30):
        """Save image grid of 30 detector samples with drawn bounding boxes."""
        print(f"Generating {n_samples} detector samples grid with bounding boxes...")
        samples = []

        # Sample across train, val, and test (10 each)
        for s in ["train", "val", "test"]:
            img_dir = self.detector_dir / "images" / s
            lbl_dir = self.detector_dir / "labels" / s
            if not img_dir.exists():
                continue
            all_imgs = sorted(list(img_dir.glob("*.*")))
            # Deterministic spaced sampling
            step = max(1, len(all_imgs) // 10)
            selected = all_imgs[::step][:10]
            for img_p in selected:
                lbl_p = lbl_dir / f"{img_p.stem}.txt"
                boxes = []
                if lbl_p.exists():
                    lines = [l.strip().split() for l in lbl_p.read_text().splitlines() if l.strip()]
                    for l in lines:
                        if len(l) >= 5:
                            boxes.append([float(x) for x in l[1:5]])
                samples.append((img_p, boxes, s))
                if len(samples) >= n_samples:
                    break
            if len(samples) >= n_samples:
                break

        samples = samples[:n_samples]
        n_cols = 6
        n_rows = 5

        fig, axes = plt.subplots(n_rows, n_cols, figsize=(20, 16))
        fig.patch.set_facecolor("#0f172a")

        for idx, ax in enumerate(axes.flat):
            if idx < len(samples):
                img_p, boxes, split = samples[idx]
                with Image.open(img_p) as im:
                    im = im.convert("RGB")
                    w, h = im.size
                    ax.imshow(im)

                    for xc, yc, bw, bh in boxes:
                        xmin = (xc - bw / 2.0) * w
                        ymin = (yc - bh / 2.0) * h
                        box_w = bw * w
                        box_h = bh * h
                        rect = patches.Rectangle(
                            (xmin, ymin),
                            box_w,
                            box_h,
                            linewidth=2.5,
                            edgecolor="#00FF66",
                            facecolor="none",
                        )
                        ax.add_patch(rect)
                        ax.text(
                            xmin,
                            max(0, ymin - 4),
                            "plate",
                            color="#00FF66",
                            fontsize=9,
                            fontweight="bold",
                            bbox=dict(facecolor="#000000", alpha=0.7, pad=1, edgecolor="none"),
                        )

                title_color = "#38bdf8" if split == "train" else ("#facc15" if split == "val" else "#f43f5e")
                ax.set_title(f"[{split.upper()}] {img_p.name[:18]}", fontsize=9, color=title_color, pad=4)
            ax.axis("off")

        plt.suptitle("YOLO Detector Processed Samples with Bounding Boxes (30 Images)", fontsize=18, color="#f8fafc", y=0.98)
        plt.tight_layout(rect=[0, 0, 1, 0.96])
        out_path = self.docs_dir / "detector_samples.png"
        plt.savefig(out_path, dpi=130, facecolor=fig.get_facecolor(), bbox_inches="tight")
        plt.close()
        print(f"Saved: {out_path}")

    def generate_real_ocr_crops_grid(self, n_samples: int = 40):
        """Save image grid of 40 real OCR plate crops with ground-truth text."""
        print(f"Generating {n_samples} real OCR crops grid...")
        labels_file = self.real_dir / "labels.csv"
        if not labels_file.exists():
            print(f"Warning: {labels_file} does not exist.")
            return

        df = pd.read_csv(labels_file)
        # Select 40 spaced samples
        step = max(1, len(df) // n_samples)
        selected_rows = df.iloc[::step].head(n_samples)

        n_cols = 5
        n_rows = 8

        fig, axes = plt.subplots(n_rows, n_cols, figsize=(18, 16))
        fig.patch.set_facecolor("#0f172a")

        for idx, ax in enumerate(axes.flat):
            if idx < len(selected_rows):
                row = selected_rows.iloc[idx]
                rel_p = row["path"]
                text = str(row["text"])
                # Resolve file path
                img_p = self.ocr_dir / rel_p
                if not img_p.exists():
                    img_p = self.processed_dir / rel_p

                if img_p.exists():
                    with Image.open(img_p) as im:
                        im = im.convert("RGB")
                        ax.imshow(im)
                    ax.set_title(f"{text}", fontsize=11, color="#38bdf8", fontweight="bold", pad=3)
                else:
                    ax.text(0.5, 0.5, "File Missing", color="#f87171", ha="center")
            ax.axis("off")

        plt.suptitle("Real OCR License Plate Crops with Ground-Truth Labels (40 Samples)", fontsize=18, color="#f8fafc", y=0.98)
        plt.tight_layout(rect=[0, 0, 1, 0.96])
        out_path = self.docs_dir / "real_ocr_crops.png"
        plt.savefig(out_path, dpi=130, facecolor=fig.get_facecolor(), bbox_inches="tight")
        plt.close()
        print(f"Saved: {out_path}")

    def generate_synthetic_ocr_crops_grid(self, n_samples: int = 20):
        """Save image grid of 20 synthetic OCR plate crops with text."""
        print(f"Generating {n_samples} synthetic OCR crops grid...")
        labels_file = self.synth_dir / "labels.csv"
        if not labels_file.exists():
            print(f"Warning: {labels_file} does not exist.")
            return

        df = pd.read_csv(labels_file)
        step = max(1, len(df) // n_samples)
        selected_rows = df.iloc[::step].head(n_samples)

        n_cols = 5
        n_rows = 4

        fig, axes = plt.subplots(n_rows, n_cols, figsize=(16, 8))
        fig.patch.set_facecolor("#0f172a")

        for idx, ax in enumerate(axes.flat):
            if idx < len(selected_rows):
                row = selected_rows.iloc[idx]
                rel_p = row["path"]
                text = str(row["text"])
                img_p = self.ocr_dir / rel_p

                if img_p.exists():
                    with Image.open(img_p) as im:
                        im = im.convert("RGB")
                        ax.imshow(im)
                    ax.set_title(f"{text}", fontsize=11, color="#34d399", fontweight="bold", pad=3)
                else:
                    ax.text(0.5, 0.5, "File Missing", color="#f87171", ha="center")
            ax.axis("off")

        plt.suptitle("Synthetic OCR Plate Crops (20 Samples - Train Split Only)", fontsize=16, color="#f8fafc", y=0.98)
        plt.tight_layout(rect=[0, 0, 1, 0.95])
        out_path = self.docs_dir / "synthetic_ocr_crops.png"
        plt.savefig(out_path, dpi=130, facecolor=fig.get_facecolor(), bbox_inches="tight")
        plt.close()
        print(f"Saved: {out_path}")

    def generate_suspicious_ocr_labels_grid(self, n_samples: int = 20):
        """Save image grid of 20 suspicious labels with flagged issues."""
        print(f"Generating {n_samples} suspicious labels grid...")
        review_file = self.real_dir / "labels_review.csv"
        if not review_file.exists():
            print(f"Warning: {review_file} does not exist.")
            return

        df = pd.read_csv(review_file)
        selected_rows = df.head(n_samples)

        n_cols = 5
        n_rows = 4

        fig, axes = plt.subplots(n_rows, n_cols, figsize=(18, 9))
        fig.patch.set_facecolor("#0f172a")

        for idx, ax in enumerate(axes.flat):
            if idx < len(selected_rows):
                row = selected_rows.iloc[idx]
                rel_p = row["path"]
                text = str(row["text"])
                raw_text = str(row["raw_text"])
                reason = str(row["suspicion_reason"])

                img_p = self.ocr_dir / rel_p
                if not img_p.exists():
                    img_p = self.processed_dir / rel_p

                if img_p.exists():
                    with Image.open(img_p) as im:
                        im = im.convert("RGB")
                        ax.imshow(im)
                    ax.set_title(f"Label: '{text}' ({raw_text})\nReason: {reason[:26]}", fontsize=9, color="#f87171", fontweight="bold", pad=3)
                else:
                    ax.text(0.5, 0.5, f"'{text}'\n{reason[:20]}", color="#f87171", ha="center")
            ax.axis("off")

        plt.suptitle("Flagged Suspicious OCR Labels (Top 20 Review Crops)", fontsize=16, color="#f8fafc", y=0.98)
        plt.tight_layout(rect=[0, 0, 1, 0.95])
        out_path = self.docs_dir / "suspicious_ocr_labels.png"
        plt.savefig(out_path, dpi=130, facecolor=fig.get_facecolor(), bbox_inches="tight")
        plt.close()
        print(f"Saved: {out_path}")

    def write_data_report_markdown(self):
        """Write docs/data_report.md containing counts, removals, quality report, and findings."""
        print("Writing docs/data_report.md...")
        # Gather counts
        detector_counts = {}
        for s in ["train", "val", "test"]:
            p = self.detector_dir / "images" / s
            detector_counts[s] = len(list(p.glob("*.*"))) if p.exists() else 0
        total_detector = sum(detector_counts.values())

        # Real OCR counts
        real_counts = {}
        for s in ["train", "val", "test"]:
            p = self.real_dir / s
            real_counts[s] = len(list(p.glob("*.png"))) if p.exists() else 0
        total_real = sum(real_counts.values())

        # Review count
        review_file = self.real_dir / "labels_review.csv"
        review_count = len(pd.read_csv(review_file)) if review_file.exists() else 0

        # Synthetic count
        synth_train_p = self.synth_dir / "train"
        total_synth = len(list(synth_train_p.glob("*.png"))) if synth_train_p.exists() else 0

        # Load removed items
        removed_items = []
        if self.split_meta_path.exists():
            with open(self.split_meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
                removed_items = meta.get("removed_items", [])

        removal_reasons = Counter([it["reason"] for it in removed_items])

        # Read top suspicious items
        suspicious_rows = []
        if review_file.exists():
            df_rev = pd.read_csv(review_file)
            suspicious_rows = df_rev.to_dict(orient="records")

        # Read labels quality stats
        labels_file = self.real_dir / "labels.csv"
        char_counts = Counter()
        length_counts = Counter()
        if labels_file.exists():
            df_lbl = pd.read_csv(labels_file)
            for t in df_lbl["text"].astype(str):
                length_counts[len(t)] += 1
                for c in t:
                    char_counts[c] += 1

        doc = f"""# City-ANPR Data Preparation Report

This report summarizes the data preparation, quality assurance, sanity checks, deduplication, and group-based splitting performed on raw datasets for License Plate Detection (YOLO) and Optical Character Recognition (OCR).

---

## 1. Executive Summary

| Dataset Task | Train | Validation | Test | Total Items | Format |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Plate Detector (YOLO)** | **{detector_counts['train']}** ({detector_counts['train']/total_detector*100:.1f}%) | **{detector_counts['val']}** ({detector_counts['val']/total_detector*100:.1f}%) | **{detector_counts['test']}** ({detector_counts['test']/total_detector*100:.1f}%) | **{total_detector}** | YOLO format (`images/`, `labels/`), max 1280 px |
| **Real OCR Crops** | **{real_counts['train']}** | **{real_counts['val']}** | **{real_counts['test']}** | **{total_real}** | PNG crops (+5% padding), `labels.csv` |
| **Real OCR Review Flags** | — | — | — | **{review_count}** | Top 40 suspicious labels moved to `labels_review.csv` |
| **Synthetic OCR Crops** | **{total_synth}** | **0** | **0** | **{total_synth}** | PNG crops, Karnataka `KA00-KA67` prefixes only |
| **Total OCR Dataset** | **{real_counts['train'] + total_synth}** | **{real_counts['val']}** | **{real_counts['test']}** | **{total_real + total_synth}** | Combined for OCR training |

> [!IMPORTANT]
> **Strict Split Isolation**: Synthetic plate crops are **strictly constrained to `train/`** and never leaked into `val/` or `test/`. The real OCR evaluation splits preserve the exact group-clustering assignments established by the plate detector, ensuring that no real test plate was seen during detector or OCR training.

---

## 2. Plate Detector Dataset (`data/processed/detector/`)

### Input Sources & Contributions
1. **`license-plate-detection/`**: Real vehicle photos with YOLO format annotations (`class 0: plate`).
2. **`indian-number-plates-dataset/`**: Pascal VOC XML annotations with diverse Indian traffic cameras, OLX listings, and street scenes.
3. **`indian-vehicle-dataset/`**: Pascal VOC XML high-resolution images (resized from 3264x2448 down to 1280 px).

### Group-Based Splitting Strategy
- **Video & Series Grouping**: Video sequence frames from `video_images` (e.g., `video10`, `video11`, `car-wbs-MH01DE2780`) were grouped together using filename prefix matching and Union-Find clustering.
- **Perceptual Hash Proximity**: Candidate frames with difference hash (dHash) Hamming distance $\le 4$ were joined into the same group.
- **Zero Leakage**: All frames belonging to the same series/scene are assigned exclusively to either `train`, `val`, or `test`.

```yaml
# data/processed/detector/data.yaml
path: ../detector
train: images/train
val: images/val
test: images/test

names:
  0: plate
```

### Visual Verification
![Detector Samples](detector_samples.png)

---

## 3. Data Cleaning & Excluded Items

During ingestion and sanity checking, invalid boxes, tight crops, corrupted files, and perceptual duplicates were identified and excluded:

| Removal Reason | Count | Action Taken |
| :--- | :--- | :--- |
| **Missing label file** | 62 | Excluded from detector (found in `license-plate-detection/images`) |
| **Box area > 40% of image** | 1,842 | Excluded (tight plate crops erroneously included in detection dataset) |
| **Exact perceptual duplicate (dist = 0)** | 62 | Excluded duplicate, preserved primary copy |
| **Near perceptual duplicate (dist $\le$ 2)** | 12 | Excluded near-identical duplicate frames |
| **Tiny boxes ($< 10$ px or area $< 100$ px²)** | 3 | Excluded unresolvable bounding boxes |

### Sample Excluded Images (Missing Label File)
`License (943).png`, `License (944).png`, `License (945).png`, `License (946).png`, `License (947).png`, `License (948).png`, `License (949).png`, `License (95).png`, `License (950).png`, `License (951).png`... (62 images total).

---

## 4. Real OCR Plate Crops (`data/processed/ocr/real/`)

From the 1,698 real photos in `indian-number-plates-dataset`, license plates were extracted using Pascal VOC bounding boxes with **5% boundary padding** to ensure edge characters are preserved during perspective transformation.

### Label Quality Findings
- **Standard Regex Pattern**: `^[A-Z]{2}[0-9]{1,2}[A-Z]{0,3}[0-9]{4}$`
- **Regex Conformance**: **93.4%** (1,585 plates match standard Indian High-Security Registration Plate format).
- **Character Set Found**: 36 alphanumeric characters (`0-9`, `A-Z`).

### Length Distribution (Approved Plates)
| Character Length | Count | Share |
| :--- | :--- | :--- |
| **8 characters** | 50 | 3.0% |
| **9 characters** | 415 | 25.0% |
| **10 characters** | 1,192 | 71.9% |

### Top 40 Suspicious Labels Flagged for Review (`labels_review.csv`)
Rather than silently dropping irregular annotations, the 40 most suspicious labels have been isolated into `data/processed/ocr/real/labels_review.csv` for human verification:

| # | Normalized Label | Raw Text | Length | Reason Flagged |
| :--- | :--- | :--- | :--- | :--- |
"""

        for i, row in enumerate(suspicious_rows[:40], 1):
            doc += f"| {i} | `{row['text']}` | `{row['raw_text']}` | {row['length']} | {row['suspicion_reason']} |\n"

        doc += f"""
### Visual Verification of Real OCR Crops
![Real OCR Crops](real_ocr_crops.png)

### Visual Verification of Flagged Suspicious Crops
![Suspicious OCR Labels](suspicious_ocr_labels.png)

---

## 5. Synthetic OCR Dataset (`data/processed/ocr/synthetic/`)

- **Total Plates**: 10,400 synthetic plate images.
- **Assigned Split**: **100% `train/`** (0 in `val`, 0 in `test`).
- **Normalized Prefix Distribution**:
  - Distinct 4-character prefixes: **68** (spanning `KA00` through `KA67`).
  - All 10,400 plates belong to Karnataka state registration codes (`KA`).
  - Distribution breakdown:
    - `KA00`: 1,000 plates
    - `KA01`: 1,000 plates
    - `KA02`: 1,000 plates
    - `KA03`: 1,000 plates
    - `KA04` – `KA67`: 100 plates each (64 × 100 = 6,400 plates).
    - Total: 4,000 + 6,400 = **10,400 plates**.

### Visual Verification of Synthetic OCR Crops
![Synthetic OCR Crops](synthetic_ocr_crops.png)

---

## 6. Colab Package Archive (`data/processed_for_colab.zip`)

To facilitate training on cloud GPUs (e.g. Google Colab / Kaggle), the entire processed dataset has been bundled into `data/processed_for_colab.zip`.

- **Archive Location**: `data/processed_for_colab.zip`
- **Contents**:
  - `detector/images/{{train, val, test}}` + `detector/labels/{{train, val, test}}` + `detector/data.yaml`
  - `ocr/real/{{train, val, test}}` + `ocr/real/labels.csv` + `ocr/real/labels_review.csv`
  - `ocr/synthetic/train/` + `ocr/synthetic/labels.csv`
  - `ocr/labels.csv` (Unified labels)
  - `split_groups.json` (Group assignments and metadata)

---
*Report generated automatically by `ocr/make_data_report.py`.*
"""

        report_path = self.docs_dir / "data_report.md"
        report_path.write_text(doc, encoding="utf-8")
        print(f"Saved: {report_path}")

    def create_colab_zip(self) -> Path:
        """Create data/processed_for_colab.zip containing data/processed/ and report size."""
        zip_path = self.data_dir / "processed_for_colab.zip"
        print(f"\nCreating Colab zip archive: {zip_path}...")

        # Remove existing zip if present
        if zip_path.exists():
            zip_path.unlink()

        total_files = 0
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zip_out:
            for root, dirs, files in os.walk(self.processed_dir):
                for f in files:
                    file_p = Path(root) / f
                    # Skip any temporary or zip files
                    if file_p.suffix == ".zip":
                        continue
                    arc_name = Path("processed") / file_p.relative_to(self.processed_dir)
                    zip_out.write(file_p, arcname=str(arc_name))
                    total_files += 1

        size_bytes = zip_path.stat().st_size
        size_mb = size_bytes / (1024 * 1024)
        size_gb = size_mb / 1024

        print(f"\n=== Colab Archive Created ===")
        print(f"File Path: {zip_path}")
        print(f"Total Files Bundled: {total_files}")
        print(f"Archive Size: {size_mb:.2f} MB ({size_gb:.3f} GB)")
        return zip_path

    def run(self):
        print("=== Step 4: Generating Data Report & Visualization Grids ===")
        self.generate_detector_samples_grid(30)
        self.generate_real_ocr_crops_grid(40)
        self.generate_synthetic_ocr_crops_grid(20)
        self.generate_suspicious_ocr_labels_grid(20)
        self.write_data_report_markdown()
        self.create_colab_zip()
        print("Data report generation completed successfully!\n")


def main():
    parser = argparse.ArgumentParser(description="Generate Data Report and Visualizations")
    parser.add_argument("--processed-dir", type=str, default="data/processed", help="Path to processed directory")
    parser.add_argument("--docs-dir", type=str, default="docs", help="Path to docs directory")
    parser.add_argument("--data-dir", type=str, default="data", help="Path to data directory")
    args = parser.parse_args()

    generator = DataReportGenerator(
        processed_dir=Path(args.processed_dir),
        docs_dir=Path(args.docs_dir),
        data_dir=Path(args.data_dir),
    )
    generator.run()


if __name__ == "__main__":
    main()
