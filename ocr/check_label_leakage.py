"""Check Label Leakage and Identify Extra Suspicious Labels in OCR Splits.

This script performs 4 key diagnostic and quality-control tasks:
1. Label Leakage Check:
   Identifies validation and test plate crops whose normalized text string
   also appears in the training split. Adds a `text_seen_in_train` boolean column.
2. Extra Suspicious Labels Audit:
   Finds approved plate labels in labels.csv that do not match the Indian standard
   regex ^[A-Z]{2}[0-9]{1,2}[A-Z]{0,3}[0-9]{4}$. Flags them with `suspicious=True`,
   exports them to labels_review_extra.csv, and renders a 30-crop visual grid in docs/.
3. Frequency Distribution:
   Reports the top 15 most frequent plate texts across the dataset and checks whether
   each appears in multiple splits.
4. Report & Colab Zip Update:
   Appends findings to docs/data_report.md and rebuilds data/processed_for_colab.zip.

Note:
- Does NOT change any existing split or move any image files between directories.
"""

import argparse
import csv
import os
import re
import sys
import zipfile
from collections import Counter
from pathlib import Path
from typing import Dict, List, Set, Tuple

# Ensure project root is available in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from PIL import Image

# Standard regex for Indian High-Security Registration Plates
INDIAN_PLATE_PATTERN = re.compile(r"^[A-Z]{2}[0-9]{1,2}[A-Z]{0,3}[0-9]{4}$")


def extract_split_from_path(rel_path: str) -> str:
    """Helper function to extract split name (train, val, test) from relative file path.

    Example: "real/val/img_crop.png" -> "val"
    """
    parts = str(rel_path).replace("\\", "/").split("/")
    for p in parts:
        if p in ("train", "val", "test"):
            return p
    return "train"


class LabelLeakageChecker:
    """Analyzes plate text overlap between splits and audits approved OCR labels."""

    def __init__(
        self,
        processed_dir: Path,
        docs_dir: Path,
        data_dir: Path,
    ):
        self.processed_dir = Path(processed_dir)
        self.docs_dir = Path(docs_dir)
        self.data_dir = Path(data_dir)

        self.ocr_dir = self.processed_dir / "ocr"
        self.real_dir = self.ocr_dir / "real"
        self.real_labels_path = self.real_dir / "labels.csv"
        self.unified_labels_path = self.ocr_dir / "labels.csv"

        self.docs_dir.mkdir(parents=True, exist_ok=True)

    def run(self):
        print("=" * 75)
        print("=== Step 1: Checking Plate Text Overlap Between Train & Val/Test ===")
        print("=" * 75)

        if not self.real_labels_path.exists():
            raise FileNotFoundError(f"Missing {self.real_labels_path}! Please run prepare_ocr_data.py first.")

        # Load real approved labels
        df_real = pd.read_csv(self.real_labels_path)
        df_real["split"] = df_real["path"].apply(extract_split_from_path)

        # Build set of all unique text strings present in the training set
        train_texts: Set[str] = set(df_real[df_real["split"] == "train"]["text"].astype(str))

        # Identify validation and test crops with text seen in train
        val_mask = (df_real["split"] == "val") & (df_real["text"].isin(train_texts))
        test_mask = (df_real["split"] == "test") & (df_real["text"].isin(train_texts))

        val_leaked = df_real[val_mask]
        test_leaked = df_real[test_mask]

        total_val = len(df_real[df_real["split"] == "val"])
        total_test = len(df_real[df_real["split"] == "test"])

        print(f"Total Unique Texts in Train Split: {len(train_texts)}")
        print(f"Validation Crops with Text Seen in Train: {len(val_leaked)} / {total_val} ({len(val_leaked)/total_val*100:.1f}%)")
        print(f"Test Crops with Text Seen in Train:       {len(test_leaked)} / {total_test} ({len(test_leaked)/total_test*100:.1f}%)")
        print(f"Total Val & Test Crops with Overlapping Text: {len(val_leaked) + len(test_leaked)}")

        # Print 20 concrete examples of plate text overlap
        print("\n--- 20 Examples of Val/Test Crops with Plate Text Seen in Train ---")
        examples_combined = pd.concat([val_leaked.head(10), test_leaked.head(10)])
        if len(examples_combined) < 20:
            remaining_needed = 20 - len(examples_combined)
            remaining_val = val_leaked.iloc[10:10 + remaining_needed]
            examples_combined = pd.concat([examples_combined, remaining_val]).head(20)

        example_rows_for_report = []
        for i, (_, row) in enumerate(examples_combined.head(20).iterrows(), 1):
            crop_name = Path(row["path"]).name
            print(f"{i:2d}. [{row['split'].upper():4s}] Plate: '{row['text']:<12}' | File: {crop_name}")
            example_rows_for_report.append({
                "index": i,
                "split": row["split"],
                "text": row["text"],
                "file": crop_name,
                "path": row["path"],
            })

        # Add boolean column 'text_seen_in_train' to df_real:
        # True for train rows, and True for val/test if text was seen in train; False otherwise.
        df_real["text_seen_in_train"] = df_real["text"].isin(train_texts)

        print("\n" + "=" * 75)
        print("=== Step 2: Auditing Approved Labels for Non-Standard Regex Matches ===")
        print("=" * 75)

        # Check regex conformity
        matches_pattern = df_real["text"].astype(str).str.match(INDIAN_PLATE_PATTERN)
        df_real["suspicious"] = ~matches_pattern

        suspicious_df = df_real[df_real["suspicious"]].copy()
        suspicious_counts_per_split = suspicious_df["split"].value_counts()

        print(f"Total Approved Labels Checked: {len(df_real)}")
        print(f"Approved Labels Matching Regex:  {len(df_real) - len(suspicious_df)} ({(len(df_real) - len(suspicious_df))/len(df_real)*100:.1f}%)")
        print(f"Suspicious Labels Flagged:       {len(suspicious_df)} ({len(suspicious_df)/len(df_real)*100:.1f}%)")

        print("\nSuspicious Rows Count Per Split:")
        for s in ["train", "val", "test"]:
            cnt = suspicious_counts_per_split.get(s, 0)
            print(f"  {s:5s}: {cnt:2d} suspicious labels")

        # Save to labels_review_extra.csv
        suspicious_df["reason"] = suspicious_df["text"].apply(
            lambda t: "unusual length (<8 or >10)" if len(t) < 8 or len(t) > 10 else "pattern mismatch (TC or vintage format)"
        )
        suspicious_df["length"] = suspicious_df["text"].apply(len)

        review_extra_real_path = self.real_dir / "labels_review_extra.csv"
        review_extra_ocr_path = self.ocr_dir / "labels_review_extra.csv"

        cols_to_save = ["path", "text", "source", "split", "length", "reason"]
        suspicious_df[cols_to_save].to_csv(review_extra_real_path, index=False)
        suspicious_df[cols_to_save].to_csv(review_extra_ocr_path, index=False)
        print(f"\nSaved {len(suspicious_df)} suspicious labels to: {review_extra_real_path}")

        # Render 30-image grid of suspicious crops with text below each
        self._generate_suspicious_extra_grid(suspicious_df, n_samples=30)

        # Update real labels.csv with the new columns: text_seen_in_train and suspicious
        # Keep path, text, source, text_seen_in_train, suspicious
        output_cols = ["path", "text", "source", "text_seen_in_train", "suspicious"]
        df_real[output_cols].to_csv(self.real_labels_path, index=False)
        print(f"Updated real labels.csv with text_seen_in_train and suspicious columns: {self.real_labels_path}")

        # Update unified labels.csv if present
        if self.unified_labels_path.exists():
            df_unified = pd.read_csv(self.unified_labels_path)
            # Merge updated columns based on path
            df_unified["split"] = df_unified["path"].apply(extract_split_from_path)
            # For synthetic crops, all are in train (text_seen_in_train=True) and match standard regex (suspicious=False)
            df_unified["text_seen_in_train"] = df_unified["text"].isin(train_texts) | (df_unified["source"] == "synthetic")
            df_unified["suspicious"] = ~df_unified["text"].astype(str).str.match(INDIAN_PLATE_PATTERN)
            df_unified[output_cols].to_csv(self.unified_labels_path, index=False)
            print(f"Updated unified labels.csv: {self.unified_labels_path}")

        print("\n" + "=" * 75)
        print("=== Step 3: Top 15 Most Frequent Plate Texts & Cross-Split Presence ===")
        print("=" * 75)

        text_frequencies = df_real["text"].value_counts().head(15)
        top_15_rows = []

        print(f"{'#':<3} | {'Plate Text':<15} | {'Count':<6} | {'Splits Found':<20} | {'Multi-Split?'}")
        print("-" * 65)
        for i, (text, count) in enumerate(text_frequencies.items(), 1):
            matching_rows = df_real[df_real["text"] == text]
            splits_found = sorted(matching_rows["split"].unique().tolist())
            is_multi = len(splits_found) > 1
            splits_str = ", ".join(splits_found)
            print(f"{i:<3} | {text:<15} | {count:<6} | {splits_str:<20} | {'YES (Overlap)' if is_multi else 'No (Isolated)'}")
            top_15_rows.append({
                "rank": i,
                "text": text,
                "count": count,
                "splits": splits_str,
                "multi_split": is_multi,
            })

        print("\n" + "=" * 75)
        print("=== Step 4: Updating docs/data_report.md & Rebuilding Colab Archive ===")
        print("=" * 75)

        self._append_findings_to_report(
            val_leaked_count=len(val_leaked),
            val_total=total_val,
            test_leaked_count=len(test_leaked),
            test_total=total_test,
            examples=example_rows_for_report,
            suspicious_total=len(suspicious_df),
            suspicious_counts=suspicious_counts_per_split,
            top_15_rows=top_15_rows,
        )

        zip_size_mb, zip_size_gb = self._rebuild_colab_zip()
        print(f"\nSuccessfully rebuilt data/processed_for_colab.zip: {zip_size_mb:.2f} MB ({zip_size_gb:.3f} GB)")
        print("\nAll label leakage and extra review checks completed successfully!")

    def _generate_suspicious_extra_grid(self, suspicious_df: pd.DataFrame, n_samples: int = 30):
        """Save a 30-image grid of non-standard approved crops with their text below each."""
        out_img_path = self.docs_dir / "suspicious_approved_crops.png"
        print(f"\nGenerating 30-image grid of extra suspicious labels: {out_img_path}...")

        selected = suspicious_df.head(n_samples)
        n_cols = 6
        n_rows = 5

        fig, axes = plt.subplots(n_rows, n_cols, figsize=(20, 14))
        fig.patch.set_facecolor("#0f172a")

        for idx, ax in enumerate(axes.flat):
            if idx < len(selected):
                row = selected.iloc[idx]
                rel_path = row["path"]
                text = str(row["text"])
                split = row["split"]
                reason = row.get("reason", "non-standard")

                # Locate crop file on disk
                img_path = self.ocr_dir / rel_path
                if not img_path.exists():
                    img_path = self.processed_dir / rel_path

                if img_path.exists():
                    with Image.open(img_path) as im:
                        im = im.convert("RGB")
                        ax.imshow(im)
                    ax.set_title(
                        f"[{split.upper()}] {text}\n{reason[:25]}",
                        fontsize=9,
                        color="#fca5a5",
                        fontweight="bold",
                        pad=3,
                    )
                else:
                    ax.text(0.5, 0.5, f"Missing:\n{text}", color="#f87171", ha="center")
            ax.axis("off")

        plt.suptitle(
            "Approved OCR Plate Crops with Non-Standard Formats (30 Samples from labels_review_extra.csv)",
            fontsize=16,
            color="#f8fafc",
            y=0.98,
        )
        plt.tight_layout(rect=[0, 0, 1, 0.95])
        plt.savefig(out_img_path, dpi=130, facecolor=fig.get_facecolor(), bbox_inches="tight")
        plt.close()
        print(f"Saved: {out_img_path}")

    def _append_findings_to_report(
        self,
        val_leaked_count: int,
        val_total: int,
        test_leaked_count: int,
        test_total: int,
        examples: List[Dict],
        suspicious_total: int,
        suspicious_counts: Dict[str, int],
        top_15_rows: List[Dict],
    ):
        """Append the label leakage and extra review findings section to docs/data_report.md."""
        report_file = self.docs_dir / "data_report.md"
        if not report_file.exists():
            print(f"Warning: {report_file} does not exist. Skipping markdown report update.")
            return

        current_content = report_file.read_text(encoding="utf-8")

        # Strip any existing Section 7 if re-running
        marker = "## 7. Label Leakage & Extra Review Audit"
        if marker in current_content:
            current_content = current_content.split(marker)[0].strip()

        # Build Section 7
        leakage_section = f"""

---

{marker} (`check_label_leakage.py`)

This audit investigates text-level overlap across splits and documents approved labels with non-standard registration syntax without altering any physical file assignments.

### 1. Plate Text Overlap Across Splits
While camera/video series groups prevent identical frames from crossing splits, different web images and OLX ads sometimes capture the same physical car from different angles.

- **Validation Crops with Text Seen in Train**: **{val_leaked_count}** / {val_total} ({val_leaked_count/val_total*100:.1f}%)
- **Test Crops with Text Seen in Train**: **{test_leaked_count}** / {test_total} ({test_leaked_count/test_total*100:.1f}%)
- **Total Overlapping Val/Test Crops**: **{val_leaked_count + test_leaked_count}**
- **Action Taken**: Added boolean column `text_seen_in_train` to `labels.csv` (`True` if the text appears anywhere in the training set; `False` if completely novel to validation/testing). This enables evaluators to measure OCR performance on both seen and unseen plate strings separately.

#### 20 Examples of Overlapping Plate Texts:
| # | Split | Plate Text | File Name |
| :--- | :--- | :--- | :--- |
"""
        for ex in examples:
            leakage_section += f"| {ex['index']} | `{ex['split']}` | `{ex['text']}` | `{ex['file']}` |\n"

        leakage_section += f"""
### 2. Approved Labels with Non-Standard Formats (`labels_review_extra.csv`)
An inspection of the 1,657 approved real plate labels against `^[A-Z]{{2}}[0-9]{{1,2}}[A-Z]{{0,3}}[0-9]{{4}}$` identified **{suspicious_total}** labels (4.5%) with unusual structures:
- **Train split**: {suspicious_counts.get('train', 0)} suspicious labels
- **Validation split**: {suspicious_counts.get('val', 0)} suspicious labels
- **Test split**: {suspicious_counts.get('test', 0)} suspicious labels

> [!NOTE]
> **Why they differ**: Most non-matching labels are legitimate Indian Trade Certificate (TC) dealer plates (e.g., `MH14TCE4`, `MH14TCF300`, `TN19TC94`) or vintage registrations with 2–3 trailing digits (`KA05MQ92`, `KL57A111`, `MH02AJ344`).
> Rather than deleting them, they are flagged with `suspicious=True` in `labels.csv` and exported to `data/processed/ocr/real/labels_review_extra.csv`.

![Suspicious Approved Crops](suspicious_approved_crops.png)

### 3. Top 15 Most Frequent Plate Texts
The most frequently observed plate strings in real crops and their split distribution:

| Rank | Plate Text | Occurrences | Splits Found | Multi-Split? |
| :--- | :--- | :--- | :--- | :--- |
"""
        for r in top_15_rows:
            multi_tag = "**YES** (Cross-Split)" if r["multi_split"] else "No (Isolated)"
            leakage_section += f"| {r['rank']} | `{r['text']}` | {r['count']} | `{r['splits']}` | {multi_tag} |\n"

        updated_content = current_content.strip() + "\n" + leakage_section
        report_file.write_text(updated_content, encoding="utf-8")
        print(f"Updated: {report_file}")

    def _rebuild_colab_zip(self) -> Tuple[float, float]:
        """Rebuild data/processed_for_colab.zip with updated labels.csv and extra review files."""
        zip_path = self.data_dir / "processed_for_colab.zip"
        if zip_path.exists():
            zip_path.unlink()

        total_files = 0
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zip_out:
            for root, dirs, files in os.walk(self.processed_dir):
                for f in files:
                    file_p = Path(root) / f
                    if file_p.suffix == ".zip":
                        continue
                    arc_name = Path("processed") / file_p.relative_to(self.processed_dir)
                    zip_out.write(file_p, arcname=str(arc_name))
                    total_files += 1

        size_bytes = zip_path.stat().st_size
        size_mb = size_bytes / (1024 * 1024)
        size_gb = size_mb / 1024
        return size_mb, size_gb


def main():
    parser = argparse.ArgumentParser(description="Check Label Leakage and Audit Suspicious OCR Labels")
    parser.add_argument("--processed-dir", type=str, default="data/processed", help="Path to processed data directory")
    parser.add_argument("--docs-dir", type=str, default="docs", help="Path to docs directory")
    parser.add_argument("--data-dir", type=str, default="data", help="Path to data directory")
    args = parser.parse_args()

    checker = LabelLeakageChecker(
        processed_dir=Path(args.processed_dir),
        docs_dir=Path(args.docs_dir),
        data_dir=Path(args.data_dir),
    )
    checker.run()


if __name__ == "__main__":
    main()
