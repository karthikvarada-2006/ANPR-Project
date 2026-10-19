"""Unit and Integration Tests for ANPR Data Preparation Pipeline.

Verifies:
1. No overlap of groups between splits (zero data leakage).
2. Every YOLO label line has 5 numbers within 0 to 1.
3. Every OCR crop image has a corresponding ground-truth label in labels.csv.
4. No synthetic path or crop appears in val or test splits.
5. data.yaml is valid and configured with class 0: plate.
"""

import json
from pathlib import Path
import pandas as pd
import pytest
import yaml

PROCESSED_DIR = Path("data/processed")
DETECTOR_DIR = PROCESSED_DIR / "detector"
OCR_DIR = PROCESSED_DIR / "ocr"


def test_split_groups_json_exists():
    """Verify split metadata was created."""
    meta_path = PROCESSED_DIR / "split_groups.json"
    assert meta_path.exists(), "split_groups.json must exist in data/processed/"


def test_no_group_overlap_between_splits():
    """Verify that train, val, and test group sets are strictly disjoint."""
    meta_path = PROCESSED_DIR / "split_groups.json"
    assert meta_path.exists(), "split_groups.json missing"

    with open(meta_path, "r", encoding="utf-8") as f:
        meta = json.load(f)

    group_splits = meta.get("group_splits", {})
    assert len(group_splits) > 0, "group_splits must not be empty"

    train_groups = {g for g, s in group_splits.items() if s == "train"}
    val_groups = {g for g, s in group_splits.items() if s == "val"}
    test_groups = {g for g, s in group_splits.items() if s == "test"}

    assert len(train_groups) > 0, "train_groups is empty"
    assert len(val_groups) > 0, "val_groups is empty"
    assert len(test_groups) > 0, "test_groups is empty"

    # Zero intersection between any pair of splits
    train_val_overlap = train_groups.intersection(val_groups)
    train_test_overlap = train_groups.intersection(test_groups)
    val_test_overlap = val_groups.intersection(test_groups)

    assert len(train_val_overlap) == 0, f"Group overlap between train and val: {train_val_overlap}"
    assert len(train_test_overlap) == 0, f"Group overlap between train and test: {train_test_overlap}"
    assert len(val_test_overlap) == 0, f"Group overlap between val and test: {val_test_overlap}"


def test_yolo_labels_validity():
    """Verify every YOLO label line has 5 numbers within 0 to 1."""
    labels_dir = DETECTOR_DIR / "labels"
    assert labels_dir.exists(), "detector/labels directory missing"

    total_checked_files = 0
    total_checked_lines = 0

    for split in ["train", "val", "test"]:
        split_dir = labels_dir / split
        assert split_dir.exists(), f"detector/labels/{split} missing"

        label_files = list(split_dir.glob("*.txt"))
        assert len(label_files) > 0, f"No label files in {split}"

        for lbl_file in label_files:
            total_checked_files += 1
            lines = [l.strip() for l in lbl_file.read_text(encoding="utf-8").splitlines() if l.strip()]
            assert len(lines) > 0, f"Empty label file: {lbl_file}"

            for line_idx, line in enumerate(lines, 1):
                total_checked_lines += 1
                parts = line.split()
                assert len(parts) == 5, (
                    f"Invalid line format in {lbl_file}:{line_idx} - expected 5 tokens, got {len(parts)}: '{line}'"
                )

                # Class id must be integer 0
                cls_id = int(parts[0])
                assert cls_id == 0, f"Invalid class_id {cls_id} in {lbl_file}:{line_idx} (expected 0)"

                # Coordinates xc, yc, w, h
                xc, yc, w, h = [float(x) for x in parts[1:5]]

                assert 0.0 <= xc <= 1.0, f"xc out of bounds [0, 1]: {xc} in {lbl_file}"
                assert 0.0 <= yc <= 1.0, f"yc out of bounds [0, 1]: {yc} in {lbl_file}"
                assert 0.0 < w <= 1.0, f"width out of bounds (0, 1]: {w} in {lbl_file}"
                assert 0.0 < h <= 1.0, f"height out of bounds (0, 1]: {h} in {lbl_file}"

    assert total_checked_files >= 1800, f"Expected >= 1800 label files, checked {total_checked_files}"
    assert total_checked_lines >= 1800, f"Expected >= 1800 label lines, checked {total_checked_lines}"


def test_ocr_crops_have_labels():
    """Verify that every OCR crop image on disk has a corresponding label."""
    # 1. Real OCR crops
    real_labels_file = OCR_DIR / "real" / "labels.csv"
    review_labels_file = OCR_DIR / "real" / "labels_review.csv"
    assert real_labels_file.exists(), "ocr/real/labels.csv missing"

    df_real = pd.read_csv(real_labels_file)
    known_real_paths = set(df_real["path"].tolist())
    known_real_filenames = {Path(p).name for p in known_real_paths}

    if review_labels_file.exists():
        df_rev = pd.read_csv(review_labels_file)
        rev_paths = set(df_rev["path"].tolist())
        known_real_paths.update(rev_paths)
        known_real_filenames.update({Path(p).name for p in rev_paths})

    for split in ["train", "val", "test"]:
        crop_dir = OCR_DIR / "real" / split
        assert crop_dir.exists(), f"ocr/real/{split} directory missing"
        crop_files = list(crop_dir.glob("*.png"))
        assert len(crop_files) > 0, f"No crop images in ocr/real/{split}"

        for cf in crop_files:
            rel_path = f"real/{split}/{cf.name}"
            assert (rel_path in known_real_paths) or (cf.name in known_real_filenames), (
                f"Crop image {cf} has no matching entry in labels.csv or labels_review.csv"
            )

    # 2. Synthetic OCR crops
    synth_labels_file = OCR_DIR / "synthetic" / "labels.csv"
    assert synth_labels_file.exists(), "ocr/synthetic/labels.csv missing"
    df_synth = pd.read_csv(synth_labels_file)
    known_synth_paths = set(df_synth["path"].tolist())
    known_synth_filenames = {Path(p).name for p in known_synth_paths}

    synth_crop_files = list((OCR_DIR / "synthetic" / "train").glob("*.png"))
    assert len(synth_crop_files) == 10400, f"Expected 10400 synthetic crops, found {len(synth_crop_files)}"

    for cf in synth_crop_files[:500]:  # Sample test 500
        rel_path = f"synthetic/train/{cf.name}"
        assert (rel_path in known_synth_paths) or (cf.name in known_synth_filenames), (
            f"Synthetic crop {cf.name} missing from synthetic labels.csv"
        )


def test_no_synthetic_in_val_or_test():
    """Verify that synthetic plate crops NEVER appear in val or test splits."""
    # Check directory structure
    synth_val_dir = OCR_DIR / "synthetic" / "val"
    synth_test_dir = OCR_DIR / "synthetic" / "test"

    if synth_val_dir.exists():
        assert len(list(synth_val_dir.glob("*"))) == 0, "ocr/synthetic/val must be empty"
    if synth_test_dir.exists():
        assert len(list(synth_test_dir.glob("*"))) == 0, "ocr/synthetic/test must be empty"

    # Check unified labels.csv
    unified_labels = OCR_DIR / "labels.csv"
    if unified_labels.exists():
        df = pd.read_csv(unified_labels)
        synth_rows = df[df["source"] == "synthetic"]

        for _, row in synth_rows.iterrows():
            path_str = str(row["path"]).replace("\\", "/")
            assert "/val/" not in path_str, f"Synthetic image in val split: {path_str}"
            assert "/test/" not in path_str, f"Synthetic image in test split: {path_str}"
            assert "train" in path_str, f"Synthetic image not in train split: {path_str}"

    # Check detector images
    for split in ["val", "test"]:
        detector_imgs = list((DETECTOR_DIR / "images" / split).glob("*.*"))
        for img in detector_imgs:
            assert not img.name.startswith("KA 0"), f"Synthetic plate crop leaked into detector {split}: {img.name}"


def test_detector_data_yaml():
    """Verify that detector data.yaml exists and is valid YAML."""
    yaml_file = DETECTOR_DIR / "data.yaml"
    assert yaml_file.exists(), "detector/data.yaml missing"

    with open(yaml_file, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    assert "train" in data, "train split missing in data.yaml"
    assert "val" in data, "val split missing in data.yaml"
    assert "test" in data, "test split missing in data.yaml"
    assert "names" in data, "names missing in data.yaml"
    assert data["names"] == {0: "plate"} or data["names"] == ["plate"], f"Invalid names mapping: {data['names']}"
