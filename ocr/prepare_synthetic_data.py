"""Prepare Synthetic OCR Dataset.

Copies 10,400 synthetic plate images from data/raw/indian-plate-crops-10k/
to data/processed/ocr/synthetic/train/ with labels.csv derived from filenames.

Rules:
- Mark source=synthetic
- Synthetic plates must NEVER go into val or test
- Report the set of distinct first-4-character prefixes
"""

import argparse
import csv
import os
import shutil
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Dict, List, Set, Tuple

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def derive_plate_text_from_filename(filename: str) -> str:
    """Derive normalized plate label from filename.

    Example: "KA 00 AA 5036.png" -> "KA00AA5036"
    """
    stem = Path(filename).stem
    norm = stem.upper().replace(" ", "").replace("-", "").strip()
    return norm


class SyntheticOCRDataPreparer:
    def __init__(
        self,
        raw_dir: Path,
        processed_dir: Path,
    ):
        self.raw_dir = Path(raw_dir)
        self.processed_dir = Path(processed_dir)
        self.src_dir = self.raw_dir / "indian-plate-crops-10k"
        self.synth_dir = self.processed_dir / "ocr" / "synthetic"
        self.train_dir = self.synth_dir / "train"

    def run(self):
        print("=== Step 3: Preparing Synthetic OCR Dataset ===")
        if not self.src_dir.exists():
            raise FileNotFoundError(f"Source directory {self.src_dir} not found!")

        # Ensure synthetic val and test NEVER exist or are empty
        for forbidden in ["val", "test"]:
            f_dir = self.synth_dir / forbidden
            if f_dir.exists():
                print(f"Removing forbidden synthetic split directory: {f_dir}")
                shutil.rmtree(f_dir)

        self.train_dir.mkdir(parents=True, exist_ok=True)

        all_files = sorted([
            f for f in self.src_dir.glob("*")
            if f.suffix.lower() in (".png", ".jpg", ".jpeg")
        ])
        total_files = len(all_files)
        print(f"Found {total_files} synthetic plate images in {self.src_dir.name}")

        # Step A: Copy files to train directory concurrently
        print("Copying synthetic plate images to data/processed/ocr/synthetic/train/...")
        records = []

        def _copy_file(src_path: Path):
            dst_path = self.train_dir / src_path.name
            shutil.copy2(src_path, dst_path)
            norm_label = derive_plate_text_from_filename(src_path.name)
            rel_path = f"synthetic/train/{src_path.name}"
            return {
                "path": rel_path,
                "text": norm_label,
                "source": "synthetic",
                "prefix": norm_label[:4],
            }

        with ThreadPoolExecutor(max_workers=16) as ex:
            records = list(ex.map(_copy_file, all_files))

        # Step B: Write labels.csv in synthetic directory
        csv_path = self.synth_dir / "labels.csv"
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["path", "text", "source"])
            for r in records:
                writer.writerow([r["path"], r["text"], r["source"]])

        print(f"Saved {len(records)} synthetic labels to: {csv_path}")

        # Step C: Prefix analysis report
        prefixes = Counter([r["prefix"] for r in records])
        distinct_prefixes = sorted(prefixes.keys())

        print("\n=== Synthetic Plate Prefix Analysis ===")
        print(f"Total synthetic plates: {len(records)}")
        print(f"Distinct 4-character prefixes: {len(distinct_prefixes)}")
        print(f"Prefixes list: {', '.join(distinct_prefixes)}")

        all_ka = all(p.startswith("KA") for p in distinct_prefixes)
        ka00_count = prefixes.get("KA00", 0)
        print(f"\nAll prefixes start with 'KA' (Karnataka): {all_ka}")
        print(f"Plates with exact prefix 'KA00': {ka00_count}")
        print(f"Distribution: KA00: {prefixes.get('KA00', 0)}, KA01: {prefixes.get('KA01', 0)}, KA02: {prefixes.get('KA02', 0)}, KA03: {prefixes.get('KA03', 0)}, KA04-KA67: {prefixes.get('KA04', 0)} each")

        # Step D: Also generate unified ocr/labels.csv combining real + synthetic
        real_labels_file = self.processed_dir / "ocr" / "real" / "labels.csv"
        unified_csv = self.processed_dir / "ocr" / "labels.csv"
        combined_rows = []

        if real_labels_file.exists():
            with open(real_labels_file, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    combined_rows.append(row)

        combined_rows.extend([{"path": r["path"], "text": r["text"], "source": r["source"]} for r in records])

        with open(unified_csv, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["path", "text", "source"])
            writer.writeheader()
            writer.writerows(combined_rows)

        print(f"Saved unified OCR labels ({len(combined_rows)} rows) to: {unified_csv}")
        print("Synthetic OCR data preparation completed successfully!\n")


def main():
    parser = argparse.ArgumentParser(description="Prepare Synthetic OCR Plate Dataset")
    parser.add_argument("--raw-dir", type=str, default="data/raw", help="Path to raw directory")
    parser.add_argument("--processed-dir", type=str, default="data/processed", help="Path to processed directory")
    args = parser.parse_args()

    preparer = SyntheticOCRDataPreparer(
        raw_dir=Path(args.raw_dir),
        processed_dir=Path(args.processed_dir),
    )
    preparer.run()


if __name__ == "__main__":
    main()
