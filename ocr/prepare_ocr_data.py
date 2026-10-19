"""Prepare Real OCR Dataset from Pascal VOC XML annotations.

Crops license plates from the 1,698 real photos in data/raw/indian-number-plates-dataset
using XML bounding boxes with 5% padding.

Ensures the EXACT same group split as Step 1 (detector) using data/processed/split_groups.json.
Outputs:
data/processed/ocr/real/
    ├── train/
    ├── val/
    ├── test/
    ├── labels.csv
    └── labels_review.csv (top 40 suspicious labels)
"""

import argparse
import csv
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
from PIL import Image, ImageOps

INDIAN_PLATE_PATTERN = re.compile(r"^[A-Z]{2}[0-9]{1,2}[A-Z]{0,3}[0-9]{4}$")


def get_video_group(filename: str) -> str:
    """Extract group prefix from video frame filenames."""
    m1 = re.match(r"^(video\d+)", filename, re.IGNORECASE)
    if m1:
        return f"vid_{m1.group(1).lower()}"
    m2 = re.match(r"^(car-[a-zA-Z0-9]+-[A-Z0-9]+)_\d+", filename, re.IGNORECASE)
    if m2:
        return f"vid_{m2.group(1).lower()}"
    m3 = re.match(r"^([A-Za-z0-9_-]+)_\d+\.[a-zA-Z0-9]+$", filename)
    if m3:
        return f"vid_{m3.group(1).lower()}"
    return f"vid_{Path(filename).stem}"



def normalize_plate_text(raw_text: str) -> str:
    """Uppercase, remove spaces, dashes, and surrounding whitespace."""
    if not raw_text:
        return ""
    text = raw_text.upper()
    text = text.replace(" ", "").replace("-", "").strip()
    return text


def compute_suspicion_score(norm_text: str) -> Tuple[float, List[str]]:
    """Compute suspicion score for label quality triage. Higher score = more suspicious."""
    score = 0.0
    reasons = []

    if not norm_text:
        return 999.0, ["empty label"]

    # Non-alphanumeric characters
    invalid_chars = [c for c in norm_text if not (c.isalnum())]
    if invalid_chars:
        score += 100.0
        reasons.append(f"invalid characters ({''.join(set(invalid_chars))})")

    # Pure alphabetic (likely car brand / model word like TERRANO, CRETA)
    if norm_text.isalpha():
        score += 60.0
        reasons.append("no digits (word/brand)")

    # Pure numeric
    if norm_text.isdigit():
        score += 50.0
        reasons.append("no state/letters (pure digits)")

    # Unusual length (standard Indian plates are 9-10 chars, occasionally 8)
    length = len(norm_text)
    if length < 8 or length > 10:
        score += abs(length - 9.5) * 10.0
        reasons.append(f"unusual length ({length})")

    # Does not match standard Indian plate regex
    if not INDIAN_PLATE_PATTERN.match(norm_text):
        score += 15.0
        if not reasons:
            reasons.append("pattern mismatch")

    return score, reasons


class OCRRealDataPreparer:
    def __init__(
        self,
        raw_dir: Path,
        processed_dir: Path,
        padding_ratio: float = 0.05,
    ):
        self.raw_dir = Path(raw_dir)
        self.processed_dir = Path(processed_dir)
        self.ocr_dir = self.processed_dir / "ocr"
        self.real_dir = self.ocr_dir / "real"
        self.padding_ratio = padding_ratio

        self.split_groups_file = self.processed_dir / "split_groups.json"
        self.split_map: Dict[str, str] = {}
        self.group_splits: Dict[str, str] = {}

    def load_split_mapping(self):
        """Load group split mapping created by prepare_detector_data.py."""
        if not self.split_groups_file.exists():
            raise FileNotFoundError(
                f"Split metadata {self.split_groups_file} not found! "
                f"Please run prepare_detector_data.py first to create the group split."
            )

        with open(self.split_groups_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.split_map = data.get("image_to_split", {})
        self.group_splits = data.get("group_splits", {})
        print(f"Loaded split mapping: {len(self.split_map)} entries from {self.split_groups_file.name}")

    def get_image_split(self, img_path: Path) -> str:
        """Resolve exact split for an image matching Step 1's group assignment."""
        rel_raw = str(img_path.relative_to(self.raw_dir)).replace("\\", "/")
        if rel_raw in self.split_map:
            return self.split_map[rel_raw]

        if img_path.name in self.split_map:
            return self.split_map[img_path.name]

        if img_path.stem in self.split_map:
            return self.split_map[img_path.stem]

        # Check video series prefix
        grp = get_video_group(img_path.name)
        if grp in self.group_splits:
            return self.group_splits[grp]

        # Default fallback to train
        return "train"

    def run(self):
        print("=== Step 2: Preparing Real OCR Dataset ===")
        self.load_split_mapping()

        src_dir = self.raw_dir / "indian-number-plates-dataset"
        if not src_dir.exists():
            raise FileNotFoundError(f"Source directory {src_dir} not found!")

        all_imgs = sorted([f for f in src_dir.rglob("*") if f.suffix.lower() in (".jpg", ".jpeg", ".png")])
        print(f"Found {len(all_imgs)} real photos in {src_dir.name}")

        for s in ["train", "val", "test"]:
            (self.real_dir / s).mkdir(parents=True, exist_ok=True)

        extracted_crops = []
        missing_xml = 0
        corrupt_imgs = 0

        # Step A: Parse annotations and compute crop bounding boxes
        for img in all_imgs:
            cand1 = img.with_suffix(img.suffix + ".xml")
            cand2 = img.with_suffix(".xml")
            xml_file = cand1 if cand1.exists() else (cand2 if cand2.exists() else None)

            if not xml_file:
                missing_xml += 1
                continue

            try:
                with Image.open(img) as im:
                    w_img, h_img = im.size
            except Exception:
                corrupt_imgs += 1
                continue

            try:
                root = ET.parse(xml_file).getroot()
            except Exception:
                continue

            split = self.get_image_split(img)

            objs = root.findall("object")
            for idx, obj in enumerate(objs):
                name_el = obj.find("name")
                raw_text = name_el.text if name_el is not None and name_el.text else ""
                norm_text = normalize_plate_text(raw_text)

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

                # Add 5% padding clamped to image bounds
                bw = xmax - xmin
                bh = ymax - ymin
                pad_x = self.padding_ratio * bw
                pad_y = self.padding_ratio * bh

                x1 = max(0, int(round(xmin - pad_x)))
                y1 = max(0, int(round(ymin - pad_y)))
                x2 = min(w_img, int(round(xmax + pad_x)))
                y2 = min(h_img, int(round(ymax + pad_y)))

                if x2 <= x1 or y2 <= y1:
                    continue

                crop_stem = f"{img.stem}_p{idx}" if len(objs) > 1 else img.stem
                crop_filename = f"{crop_stem}_crop.png"
                rel_crop_path = f"real/{split}/{crop_filename}"
                dst_crop_path = self.real_dir / split / crop_filename

                score, reasons = compute_suspicion_score(norm_text)

                extracted_crops.append({
                    "img_path": img,
                    "crop_box": (x1, y1, x2, y2),
                    "dst_path": dst_crop_path,
                    "rel_path": rel_crop_path,
                    "split": split,
                    "raw_text": raw_text,
                    "text": norm_text,
                    "source": "real",
                    "score": score,
                    "reasons": reasons,
                    "length": len(norm_text),
                })

        print(f"Extracted {len(extracted_crops)} plate bounding boxes with 5% padding.")

        # Step B: Save cropped images concurrently
        print("Cropping and saving plate images to disk...")
        def _save_crop(item):
            try:
                with Image.open(item["img_path"]) as im:
                    im = ImageOps.exif_transpose(im)
                    im = im.convert("RGB")
                    crop = im.crop(item["crop_box"])
                    crop.save(item["dst_path"], "PNG")
                    return True
            except Exception as e:
                print(f"Error cropping {item['img_path']}: {e}")
                return False

        with ThreadPoolExecutor(max_workers=8) as ex:
            list(ex.map(_save_crop, extracted_crops))

        # Step C: Label Quality Analysis
        total_crops = len(extracted_crops)
        lengths = Counter([it["length"] for it in extracted_crops])
        char_counts = Counter()
        for it in extracted_crops:
            for ch in it["text"]:
                char_counts[ch] += 1

        matches = sum(1 for it in extracted_crops if INDIAN_PLATE_PATTERN.match(it["text"]))
        pct_match = (matches / total_crops * 100) if total_crops > 0 else 0.0

        print("\n=== Label Quality Report ===")
        print(f"Total Plate Labels: {total_crops}")
        print(f"Matching Standard Pattern (^[A-Z]{{2}}[0-9]{{1,2}}[A-Z]{{0,3}}[0-9]{{4}}$): {matches} ({pct_match:.1f}%)")
        print(f"Non-matching / Irregular Labels: {total_crops - matches}")

        print("\nLength Distribution:")
        print(f"{'Length':<8} | {'Count':<8} | {'Percentage':<10}")
        print("-" * 32)
        for l in sorted(lengths.keys()):
            cnt = lengths[l]
            pct = cnt / total_crops * 100
            print(f"{l:<8} | {cnt:<8} | {pct:6.2f}%")

        print(f"\nCharacter Set ({len(char_counts)} distinct characters):")
        sorted_chars = sorted(char_counts.items(), key=lambda x: x[0])
        print("  " + " ".join([f"{c}:{cnt}" for c, cnt in sorted_chars]))

        # Step D: Triage 40 most suspicious labels -> labels_review.csv
        # Sort items with pattern mismatch or errors descending by suspicion score
        suspicious_candidates = [it for it in extracted_crops if it["score"] > 0]
        suspicious_candidates.sort(key=lambda x: -x["score"])

        top_40_suspicious = suspicious_candidates[:40]
        top_40_paths = {it["rel_path"] for it in top_40_suspicious}

        # Save labels_review.csv
        review_csv_path = self.real_dir / "labels_review.csv"
        root_review_csv_path = self.ocr_dir / "labels_review.csv"

        with open(review_csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["path", "text", "source", "raw_text", "length", "suspicion_reason"])
            for it in top_40_suspicious:
                writer.writerow([
                    it["rel_path"],
                    it["text"],
                    it["source"],
                    it["raw_text"],
                    it["length"],
                    ", ".join(it["reasons"]),
                ])

        # Also copy to ocr/labels_review.csv
        import shutil
        shutil.copy2(review_csv_path, root_review_csv_path)

        # Save clean labels.csv (all approved crops excluding review items)
        approved_crops = [it for it in extracted_crops if it["rel_path"] not in top_40_paths]

        labels_csv_path = self.real_dir / "labels.csv"
        with open(labels_csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["path", "text", "source"])
            for it in approved_crops:
                writer.writerow([it["rel_path"], it["text"], it["source"]])

        print(f"\nSaved {len(approved_crops)} verified labels to: {labels_csv_path}")
        print(f"Moved {len(top_40_suspicious)} suspicious labels to: {review_csv_path}")

        # Step E: Print Top 40 Suspicious Labels Table
        print("\n=== Top 40 Most Suspicious Labels for Review ===")
        print(f"{'#':<3} | {'Crop Path':<35} | {'Normalized':<15} | {'Raw Text':<15} | {'Reason'}")
        print("-" * 100)
        for i, it in enumerate(top_40_suspicious, 1):
            crop_name = Path(it["rel_path"]).name
            reasons_str = ", ".join(it["reasons"])
            print(f"{i:<3} | {crop_name:<35} | {it['text']:<15} | {it['raw_text']:<15} | {reasons_str}")

        # Summary of real splits
        split_counts = Counter([it["split"] for it in approved_crops])
        print("\nReal OCR Crops Split Distribution (verified):")
        for s in ["train", "val", "test"]:
            print(f"  {s:5s}: {split_counts[s]} crops")
        print("Real OCR data preparation completed successfully!\n")


def main():
    parser = argparse.ArgumentParser(description="Prepare Real OCR Plate Crops Dataset")
    parser.add_argument("--raw-dir", type=str, default="data/raw", help="Path to raw directory")
    parser.add_argument("--processed-dir", type=str, default="data/processed", help="Path to processed directory")
    parser.add_argument("--padding", type=float, default=0.05, help="Padding ratio around bounding box")
    args = parser.parse_args()

    preparer = OCRRealDataPreparer(
        raw_dir=Path(args.raw_dir),
        processed_dir=Path(args.processed_dir),
        padding_ratio=args.padding,
    )
    preparer.run()


if __name__ == "__main__":
    main()
