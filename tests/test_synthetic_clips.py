"""Unit Tests for Synthetic Video Clips and Ground-Truth Integrity.

Verifies:
1. Synthetic clip filenames start with 'synthetic_'.
2. Every synthetic video clip has a corresponding row in ground_truth.csv.
3. Synthetic clips ONLY use photos from the TEST split of indian-number-plates-dataset
   (verified against data/processed/split_groups.json; zero train or val photos).
"""

import json
from pathlib import Path
import pandas as pd
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SYNTHETIC_DIR = PROJECT_ROOT / "data" / "video_events" / "synthetic"
SPLIT_GROUPS_PATH = PROJECT_ROOT / "data" / "processed" / "split_groups.json"
GROUND_TRUTH_CSV = SYNTHETIC_DIR / "ground_truth.csv"


def test_synthetic_clip_filenames_start_with_prefix():
    """Verify all generated video clips in data/video_events/synthetic/ start with 'synthetic_'."""
    assert SYNTHETIC_DIR.exists(), f"Synthetic directory does not exist: {SYNTHETIC_DIR}"

    clips = list(SYNTHETIC_DIR.glob("*.mp4"))
    assert len(clips) >= 60, f"Expected at least 60 synthetic clips, found {len(clips)}"

    for clip in clips:
        assert clip.name.startswith("synthetic_"), (
            f"Clip '{clip.name}' does not start with prefix 'synthetic_'"
        )


def test_every_clip_has_ground_truth_row():
    """Verify that every generated video clip has a matching entry in ground_truth.csv."""
    assert GROUND_TRUTH_CSV.exists(), f"Ground truth CSV not found: {GROUND_TRUTH_CSV}"

    df_gt = pd.read_csv(GROUND_TRUTH_CSV)
    assert "clip_name" in df_gt.columns
    assert "true_plate" in df_gt.columns
    assert "n_frames" in df_gt.columns

    gt_clip_names = set(df_gt["clip_name"].tolist())
    clips = list(SYNTHETIC_DIR.glob("*.mp4"))

    for clip in clips:
        assert clip.name in gt_clip_names, (
            f"Clip '{clip.name}' is missing from ground_truth.csv"
        )
        row = df_gt[df_gt["clip_name"] == clip.name].iloc[0]
        assert pd.notna(row["true_plate"]) and str(row["true_plate"]).strip() != "", (
            f"Clip '{clip.name}' has empty ground truth plate text"
        )
        assert row["n_frames"] == 24, f"Expected 24 frames, got {row['n_frames']}"


def test_clips_only_use_test_split_photos():
    """Strictly verify that clips ONLY use photos assigned to the TEST split.
    
    Cross-checks each source photo in ground_truth.csv against split_groups.json.
    Must never use train or val photos.
    """
    assert SPLIT_GROUPS_PATH.exists(), f"split_groups.json not found: {SPLIT_GROUPS_PATH}"
    assert GROUND_TRUTH_CSV.exists(), f"ground_truth.csv not found: {GROUND_TRUTH_CSV}"

    with open(SPLIT_GROUPS_PATH, "r", encoding="utf-8") as f:
        split_meta = json.load(f)

    image_to_split = split_meta.get("image_to_split", {})
    df_gt = pd.read_csv(GROUND_TRUTH_CSV)

    assert "source_image" in df_gt.columns, "ground_truth.csv missing 'source_image' column"

    for _, row in df_gt.iterrows():
        source_rel = str(row["source_image"]).replace("\\", "/")
        source_basename = Path(source_rel).name

        # Look up split by full path or basename
        assigned_split = image_to_split.get(source_basename)
        if assigned_split is None:
            # Check if any key ends with this basename
            matching = [v for k, v in image_to_split.items() if k.endswith(source_basename)]
            if matching:
                assigned_split = matching[0]

        assert assigned_split is not None, (
            f"Photo '{source_basename}' was not found in split_groups.json"
        )
        assert assigned_split == "test", (
            f"LEAKAGE DETECTED: Photo '{source_basename}' is assigned to '{assigned_split}', NOT 'test'!"
        )
