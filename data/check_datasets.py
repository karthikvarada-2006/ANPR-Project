"""Dataset Verification and Health Check for City-Wide ANPR System.

Scans data/raw/ and inspects dataset folders for:
- Image counts (.jpg, .jpeg, .png)
- Total disk size (in GB)
- Annotation formats (.txt, .xml, .json, .csv)
- Matching annotation counts
- 3 sample file paths
- Example plate-text labels for Indian datasets
- Verdicts: READY, PARTIAL, or MISSING
- Summary table and training readiness analysis.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path
import re
import sys
from typing import Any, Dict, List, Optional, Set, Tuple
import xml.etree.ElementTree as ET

# Image and annotation extensions
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}
ANNOTATION_EXTENSIONS = {".txt", ".xml", ".json", ".csv"}

# Regex pattern for Indian registration license plates
INDIAN_PLATE_REGEX = re.compile(
    r"\b[A-Z]{2}[-\s]?[0-9]{1,2}[-\s]?[A-Z]{0,3}[-\s]?[0-9]{4}\b",
    re.IGNORECASE,
)

# Known benchmark and Kaggle datasets
RECOGNIZED_DATASETS = [
    {
        "key": "ccpd",
        "name": "CCPD (Chinese City Parking Dataset)",
        "aliases": ["ccpd", "CCPD"],
        "category": "benchmark",
        "role": "License Plate Detection & Recognition Benchmark",
        "min_images": 50,
        "annotation_type": "filename_embedded",
        "notes": "Large-scale benchmark. Annotations embedded in image filenames.",
    },
    {
        "key": "ufpr_alpr",
        "name": "UFPR-ALPR Dataset",
        "aliases": ["ufpr_alpr", "ufpr-alpr", "UFPR-ALPR", "UFPR_ALPR"],
        "category": "benchmark",
        "role": "Multi-Frame Video ALPR (Cars & Motorcycles)",
        "min_images": 50,
        "annotation_type": "txt",
        "notes": "Video frames with bbox, character positions, and plate text in .txt files.",
    },
    {
        "key": "cityflowv2",
        "name": "CityFlowV2 (AI City Challenge)",
        "aliases": ["cityflowv2", "CityFlowV2", "cityflow_v2", "cityflow"],
        "category": "benchmark",
        "role": "Multi-Camera Multi-Target (MC-MT) Vehicle Re-ID",
        "min_images": 50,
        "annotation_type": "mot_txt",
        "notes": "Synchronized multi-camera video streams with gt/gt.txt tracking labels.",
    },
    {
        "key": "indian_number_plates",
        "name": "Indian Number Plates Dataset (Kaggle / DataCluster Labs)",
        "aliases": [
            "indian-number-plates-dataset",
            "indian_number_plates_dataset",
            "indian-number-plates",
            "indian_number_plates",
        ],
        "category": "indian",
        "role": "Indian Plate Localization & Character OCR Training",
        "min_images": 20,
        "annotation_type": "xml_json_txt",
        "notes": "Indian vehicles with bounding boxes and alphanumeric plate text labels.",
    },
    {
        "key": "indian_vehicles",
        "name": "Indian Vehicle Dataset (Kaggle / Sai Sirishan)",
        "aliases": [
            "indian-vehicle-dataset",
            "indian_vehicle_dataset",
            "indian-vehicles",
            "indian_vehicles",
        ],
        "category": "indian",
        "role": "Indian Vehicle Classification & Localization",
        "min_images": 20,
        "annotation_type": "xml_json_txt",
        "notes": "Indian urban traffic images for vehicle type classification and localization.",
    },
    {
        "key": "license_plate_detection",
        "name": "License Plate Detection Dataset (Kaggle / Sunraj Bishnolia)",
        "aliases": [
            "license-plate-detection",
            "license_plate_detection",
            "license-plates-detection",
            "license_plates_detection",
        ],
        "category": "indian",
        "role": "Plate Bounding Box Object Detector Training",
        "min_images": 20,
        "annotation_type": "json_txt_xml",
        "notes": "Vehicle images with plate bounding box annotations (YOLO/VOC/JSON).",
    },
]


def format_bytes_to_gb(bytes_size: int) -> float:
    """Convert bytes to gigabytes (GB)."""
    return round(bytes_size / (1024.0**3), 3)


def is_ccpd_filename(filename: str) -> bool:
    """Check if filename matches standard CCPD embedded annotation pattern."""
    # CCPD filenames contain 7 hyphen-separated fields, e.g. 025-95_113-154&383_386&473-...jpg
    stem = Path(filename).stem
    parts = stem.split("-")
    if len(parts) >= 6:
        # Check if coordinates with & exist in parts
        return any("&" in p for p in parts)
    return False


def extract_plate_text_samples(folder: Path, max_samples: int = 3) -> List[str]:
    """Search annotation files (.xml, .json, .csv, .txt) for plate-text labels."""
    samples: List[str] = []
    seen: Set[str] = set()

    # 1. Search XML files (Pascal VOC format)
    xml_files = list(folder.rglob("*.xml"))
    for xf in xml_files:
        if len(samples) >= max_samples:
            break
        try:
            tree = ET.parse(xf)
            root = tree.getroot()

            # Search specific tags
            for elem in root.iter():
                tag_lower = elem.tag.lower()
                text = (elem.text or "").strip()
                if not text:
                    continue

                if tag_lower in {
                    "number_plate_text",
                    "plate_number",
                    "platetext",
                    "plate",
                    "license_plate",
                    "ocr_text",
                }:
                    if text not in seen:
                        seen.add(text)
                        samples.append(
                            f"XML <{elem.tag}>: '{text}' (file: {xf.name})"
                        )
                        if len(samples) >= max_samples:
                            break

                elif tag_lower in {"name", "label", "text"}:
                    # Check if text matches Indian plate pattern
                    if INDIAN_PLATE_REGEX.search(text) and text not in seen:
                        seen.add(text)
                        samples.append(
                            f"XML <{elem.tag}>: '{text}' (file: {xf.name})"
                        )
                        if len(samples) >= max_samples:
                            break
        except Exception:
            continue

    # 2. Search JSON / JSONL files (Dataturks, COCO, or generic format)
    if len(samples) < max_samples:
        json_files = list(folder.rglob("*.json"))
        for jf in json_files:
            if len(samples) >= max_samples:
                break
            try:
                with open(jf, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read(500000)  # Read first 500KB to avoid memory stall on massive files

                # Check for line-delimited JSON
                lines = content.strip().split("\n")
                if len(lines) > 1 and lines[0].strip().startswith("{"):
                    for line in lines[:50]:
                        try:
                            obj = json.loads(line)
                            # Check Dataturks style: annotation -> notes or label
                            annots = obj.get("annotation", [])
                            if isinstance(annots, list):
                                for a in annots:
                                    if isinstance(a, dict):
                                        notes = a.get("notes") or a.get("text") or a.get("label")
                                        if isinstance(notes, list) and notes:
                                            notes = str(notes[0])
                                        if notes and INDIAN_PLATE_REGEX.search(str(notes)):
                                            val = str(notes).strip()
                                            if val not in seen:
                                                seen.add(val)
                                                samples.append(
                                                    f"JSON Line 'annotation.notes': '{val}' (file: {jf.name})"
                                                )
                                                if len(samples) >= max_samples:
                                                    break
                        except Exception:
                            continue
                else:
                    # Standard JSON object
                    try:
                        data = json.loads(content)
                        # Traverse recursive for plate keys
                        def find_json_plates(node: Any):
                            if len(samples) >= max_samples:
                                return
                            if isinstance(node, dict):
                                for k, v in node.items():
                                    k_lower = k.lower()
                                    if k_lower in {"number_plate_text", "plate_number", "plate", "text"}:
                                        if isinstance(v, str) and v.strip() and v not in seen:
                                            seen.add(v.strip())
                                            samples.append(
                                                f"JSON key '{k}': '{v.strip()}' (file: {jf.name})"
                                            )
                                    elif isinstance(v, str) and INDIAN_PLATE_REGEX.search(v):
                                        if v.strip() not in seen:
                                            seen.add(v.strip())
                                            samples.append(
                                                f"JSON key '{k}': '{v.strip()}' (file: {jf.name})"
                                            )
                                    else:
                                        find_json_plates(v)
                            elif isinstance(node, list):
                                for item in node[:30]:
                                    find_json_plates(item)

                        find_json_plates(data)
                    except Exception:
                        pass
            except Exception:
                continue

    # 3. Search CSV files
    if len(samples) < max_samples:
        csv_files = list(folder.rglob("*.csv"))
        for cf in csv_files:
            if len(samples) >= max_samples:
                break
            try:
                with open(cf, "r", encoding="utf-8", errors="ignore") as f:
                    reader = csv.reader(f)
                    header = next(reader, None)
                    if header:
                        # Find plate column index
                        plate_col_idx = None
                        for i, col in enumerate(header):
                            if col.lower() in {
                                "plate",
                                "plate_number",
                                "number_plate",
                                "plate_text",
                                "text",
                                "label",
                            }:
                                plate_col_idx = i
                                break

                        for row_idx, row in enumerate(reader):
                            if len(samples) >= max_samples or row_idx > 50:
                                break
                            if plate_col_idx is not None and len(row) > plate_col_idx:
                                val = row[plate_col_idx].strip()
                                if val and val not in seen and len(val) >= 4:
                                    seen.add(val)
                                    samples.append(
                                        f"CSV col '{header[plate_col_idx]}': '{val}' (file: {cf.name})"
                                    )
                            else:
                                for cell in row:
                                    if INDIAN_PLATE_REGEX.search(cell) and cell not in seen:
                                        seen.add(cell.strip())
                                        samples.append(
                                            f"CSV text: '{cell.strip()}' (file: {cf.name})"
                                        )
                                        break
            except Exception:
                continue

    # 4. Search TXT files (e.g., label text files)
    if len(samples) < max_samples:
        txt_files = list(folder.rglob("*.txt"))
        for tf in txt_files:
            if len(samples) >= max_samples:
                break
            # Skip common generic files
            if tf.name.lower() in {"classes.txt", "readme.txt", "requirements.txt"}:
                continue
            try:
                with open(tf, "r", encoding="utf-8", errors="ignore") as f:
                    lines = [line.strip() for line in f.readlines()[:10]]
                for line in lines:
                    match = INDIAN_PLATE_REGEX.search(line)
                    if match and match.group(0) not in seen:
                        val = match.group(0)
                        seen.add(val)
                        samples.append(f"TXT label: '{val}' (file: {tf.name})")
                        if len(samples) >= max_samples:
                            break
                    elif line.lower().startswith("plate:"):
                        val = line.split(":", 1)[1].strip()
                        if val not in seen:
                            seen.add(val)
                            samples.append(f"TXT label '{line}': '{val}' (file: {tf.name})")
                            if len(samples) >= max_samples:
                                break
            except Exception:
                continue

    return samples


def inspect_dataset_folder(folder: Path, dataset_meta: Optional[Dict] = None) -> Dict[str, Any]:
    """Scan and analyze a specific dataset subfolder."""
    folder_name = folder.name
    all_files = []
    images = []
    annotations_by_ext: Dict[str, List[Path]] = {ext: [] for ext in ANNOTATION_EXTENSIONS}
    other_annotations = []
    total_bytes = 0

    if folder.exists():
        for item in folder.rglob("*"):
            if item.is_file():
                all_files.append(item)
                try:
                    total_bytes += item.stat().st_size
                except OSError:
                    pass

                ext = item.suffix.lower()
                if ext in IMAGE_EXTENSIONS:
                    images.append(item)
                elif ext in ANNOTATION_EXTENSIONS:
                    annotations_by_ext[ext].append(item)
                elif ext in {".yaml", ".yml"}:
                    other_annotations.append(item)

    num_images = len(images)
    total_gb = format_bytes_to_gb(total_bytes)

    # Active annotation formats present
    active_annot_formats = [
        ext.replace(".", "").upper()
        for ext, file_list in annotations_by_ext.items()
        if len(file_list) > 0
    ]
    if other_annotations:
        active_annot_formats.append("YAML")

    # Check for matching annotations
    matching_count = 0
    is_ccpd = dataset_meta and dataset_meta.get("key") == "ccpd"

    if is_ccpd and num_images > 0:
        # In CCPD, annotations are embedded in the image filename itself
        ccpd_annotated = sum(1 for img in images if is_ccpd_filename(img.name))
        matching_count = ccpd_annotated if ccpd_annotated > 0 else num_images
        active_annot_formats.append("FILENAME_EMBEDDED")
    else:
        # 1. Stem-based matching (e.g. img01.jpg -> img01.xml / img01.txt / img01.json)
        all_annot_stems = set()
        for file_list in annotations_by_ext.values():
            for f in file_list:
                all_annot_stems.add(f.stem.lower())

        if all_annot_stems:
            matching_count = sum(1 for img in images if img.stem.lower() in all_annot_stems)

        # 2. Check single-manifest files (JSON, CSV, or TXT list) if stem matching found few/none
        if matching_count == 0 and num_images > 0:
            manifest_images: Set[str] = set()

            # Inspect JSON files
            for jf in annotations_by_ext[".json"]:
                try:
                    with open(jf, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read(500000)
                    for img in images:
                        if img.name in content or img.stem in content:
                            manifest_images.add(img.name)
                except Exception:
                    pass

            # Inspect CSV files
            for cf in annotations_by_ext[".csv"]:
                try:
                    with open(cf, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read(500000)
                    for img in images:
                        if img.name in content or img.stem in content:
                            manifest_images.add(img.name)
                except Exception:
                    pass

            if manifest_images:
                matching_count = len(manifest_images)

        # 3. Check for CityFlow / MOT style (gt.txt in sequence folders)
        if matching_count == 0 and annotations_by_ext[".txt"] and num_images > 0:
            gt_files = [tf for tf in annotations_by_ext[".txt"] if "gt" in tf.name.lower()]
            if gt_files:
                # Sequence-level ground truth tracking format
                matching_count = num_images

    # 3 Sample file paths (images first, then annotations)
    sample_files: List[str] = []
    if images:
        sample_files.extend([str(img.relative_to(folder.parent)) for img in images[:3]])
    elif all_files:
        sample_files.extend([str(f.relative_to(folder.parent)) for f in all_files[:3]])

    # Verdict determination
    min_imgs = dataset_meta.get("min_images", 10) if dataset_meta else 10

    if not folder.exists() or len(all_files) == 0:
        verdict = "MISSING"
    elif num_images >= min_imgs and (matching_count > 0 or "FILENAME_EMBEDDED" in active_annot_formats):
        verdict = "READY"
    elif num_images > 0:
        verdict = "PARTIAL"
    else:
        verdict = "PARTIAL"

    # Example plate-text labels for Indian datasets
    is_indian = (dataset_meta and dataset_meta.get("category") == "indian") or "indian" in folder_name.lower()
    plate_text_samples: List[str] = []
    if folder.exists() and is_indian:
        plate_text_samples = extract_plate_text_samples(folder, max_samples=3)

    return {
        "folder_name": folder_name,
        "folder_path": folder,
        "exists": folder.exists(),
        "num_images": num_images,
        "total_gb": total_gb,
        "annotation_formats": active_annot_formats,
        "matching_annotations": matching_count,
        "sample_files": sample_files,
        "verdict": verdict,
        "is_indian": is_indian,
        "plate_text_samples": plate_text_samples,
        "dataset_meta": dataset_meta,
    }


def scan_raw_datasets(raw_dir: Path) -> List[Dict[str, Any]]:
    """Scan data/raw/ and match recognized benchmark & Kaggle datasets."""
    results: List[Dict[str, Any]] = []
    visited_folders: Set[str] = set()

    # 1. Process recognized datasets first
    for d_meta in RECOGNIZED_DATASETS:
        target_folder = None
        # Check if any alias exists on disk
        for alias in d_meta["aliases"]:
            candidate = raw_dir / alias
            if candidate.exists():
                target_folder = candidate
                break

        # If not found on disk, point to primary canonical alias
        if target_folder is None:
            target_folder = raw_dir / d_meta["aliases"][0]

        visited_folders.add(target_folder.name.lower())
        info = inspect_dataset_folder(target_folder, dataset_meta=d_meta)
        results.append(info)

    # 2. Check for any additional unrecognized subfolders in data/raw/
    if raw_dir.exists():
        for sub in sorted(raw_dir.iterdir()):
            if sub.is_dir() and sub.name.lower() not in visited_folders:
                visited_folders.add(sub.name.lower())
                info = inspect_dataset_folder(sub, dataset_meta=None)
                results.append(info)

    return results


def print_dataset_report(r: Dict[str, Any], index: int) -> None:
    """Print detailed inspection block for a single dataset."""
    name = r["dataset_meta"]["name"] if r.get("dataset_meta") else r["folder_name"]
    verdict = r["verdict"]

    verdict_badge = {
        "READY": "[READY]   ",
        "PARTIAL": "[PARTIAL] ",
        "MISSING": "[MISSING] ",
    }.get(verdict, f"[{verdict}] ")

    print(f"\n{index}. {verdict_badge} {name}")
    print(f"   Folder Name           : data/raw/{r['folder_name']}/")
    print(f"   Images (JPG/JPEG/PNG) : {r['num_images']:,}")
    print(f"   Total Disk Size       : {r['total_gb']:.3f} GB")

    annot_str = ", ".join(r["annotation_formats"]) if r["annotation_formats"] else "None detected"
    print(f"   Annotation Formats    : {annot_str}")
    print(
        f"   Matching Annotations  : {r['matching_annotations']:,} / {r['num_images']:,} images "
        f"({(r['matching_annotations'] / max(1, r['num_images']) * 100):.1f}%)"
    )

    # 3 Sample file paths
    print("   Sample File Paths     :")
    if r["sample_files"]:
        for sf in r["sample_files"]:
            print(f"     - {sf}")
    else:
        print("     - (No files found)")

    # Example plate-text labels for Indian datasets
    if r["is_indian"]:
        print("   Sample Plate-Text Labels (Indian Dataset):")
        if r["plate_text_samples"]:
            for s in r["plate_text_samples"]:
                print(f"     * {s}")
        elif r["verdict"] == "MISSING":
            print("     * (Dataset not downloaded yet; see download command below)")
        else:
            print("     * (No text labels extracted; bounding boxes only or unparsed format)")


def print_summary_table(results: List[Dict[str, Any]]) -> None:
    """Print the final summary table and training readiness breakdown."""
    print("\n" + "=" * 92)
    print("CITY ANPR DATASET VERIFICATION & READINESS SUMMARY")
    print("=" * 92)
    print(
        f"{'Folder / Dataset Name':<34} | {'Images':<8} | {'Size':<9} | {'Annotations':<13} | {'Matched':<8} | {'Verdict':<8}"
    )
    print("-" * 92)

    ready_count = 0
    partial_count = 0
    missing_count = 0

    for r in results:
        fname = r["folder_name"]
        if len(fname) > 34:
            fname = fname[:31] + "..."

        images_str = f"{r['num_images']:,}"
        size_str = f"{r['total_gb']:.2f} GB"
        annots_str = "/".join(r["annotation_formats"]) if r["annotation_formats"] else "None"
        if len(annots_str) > 13:
            annots_str = annots_str[:11] + ".."
        matched_str = f"{r['matching_annotations']:,}"
        verdict = r["verdict"]

        if verdict == "READY":
            ready_count += 1
        elif verdict == "PARTIAL":
            partial_count += 1
        else:
            missing_count += 1

        print(
            f"{fname:<34} | {images_str:<8} | {size_str:<9} | {annots_str:<13} | {matched_str:<8} | {verdict:<8}"
        )

    print("=" * 92)
    print(f"Summary: {ready_count} READY | {partial_count} PARTIAL | {missing_count} MISSING (Total: {len(results)})")
    print("=" * 92)


def print_training_recommendations(results: List[Dict[str, Any]]) -> None:
    """Print specific analysis of which datasets are enough to start training."""
    ready_datasets = [r for r in results if r["verdict"] == "READY"]

    print("\n" + "#" * 92)
    print("TRAINING READINESS ANALYSIS")
    print("#" * 92)

    if ready_datasets:
        print("\nDatasets READY to start training immediately:")
        for r in ready_datasets:
            meta = r.get("dataset_meta")
            role = meta["role"] if meta else "General Training"
            print(f"  [OK] {r['folder_name']}: {r['num_images']:,} images with annotations -> Ready for: {role}")
    else:
        print("\n[ATTENTION] No datasets currently have the READY verdict.")
        print("To begin model training, the following datasets are recommended:")
        print("  1. Plate Localization / Detection:")
        print("     - 'indian-number-plates-dataset' or 'license-plate-detection' (Kaggle)")
        print("     - CCPD ('ccpd_base' - 200k+ urban vehicle shots)")
        print("  2. Character Recognition (OCR Engine):")
        print("     - 'indian-number-plates-dataset' (contains alphanumeric plate labels)")
        print("     - UFPR-ALPR (character-level bounding box & ground-truth text)")
        print("  3. Multi-Camera City Tracking & Vehicle Re-ID:")
        print("     - CityFlowV2 (synchronized intersection camera videos with tracking IDs)")

    print("\nNext Action to Acquire Missing Datasets:")
    print("  * For the 3 Kaggle Indian Datasets:")
    print("    Run: python data/download_datasets.py")
    print("    (Requires kaggle.json in ~/.kaggle/kaggle.json or KAGGLE_USERNAME / KAGGLE_KEY env vars)")
    print("  * For the Manual Benchmark Datasets (CCPD, UFPR-ALPR, CityFlowV2):")
    print("    Follow the setup guide and download links in: data/raw/README.md")
    print("#" * 92 + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify raw ANPR datasets, annotation formats, matching labels, and training readiness."
    )
    parser.add_argument(
        "--dir",
        type=str,
        default="data/raw",
        help="Path to raw datasets directory (default: data/raw)",
    )
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent.parent
    raw_dir = project_root / args.dir if not Path(args.dir).is_absolute() else Path(args.dir)

    print("=" * 92)
    print("CITY ANPR RAW DATASET INSPECTOR")
    print("=" * 92)
    print(f"Target Directory: {raw_dir.resolve()}")

    if not raw_dir.exists():
        print(f"[INFO] Directory {raw_dir} does not exist yet. Creating directory...")
        raw_dir.mkdir(parents=True, exist_ok=True)

    results = scan_raw_datasets(raw_dir)

    for idx, r in enumerate(results, start=1):
        print_dataset_report(r, idx)

    print_summary_table(results)
    print_training_recommendations(results)

    return 0


if __name__ == "__main__":
    sys.exit(main())
