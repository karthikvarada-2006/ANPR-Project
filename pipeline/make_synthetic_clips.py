"""Synthetic Video Clip Generator for Multi-Frame ANPR Evaluation.

Builds short synthetic video clips ONLY from photos in the TEST split of
`indian-number-plates-dataset` (verified strictly against `data/processed/split_groups.json`).
NEVER uses training or validation split photos.

Clip Generation Protocol:
1. Selects 60 unique test-split photos with valid XML ground-truth annotations.
2. For each photo, synthesizes a 24-frame video clip (1280x720) simulating a vehicle
   approaching a camera:
   - Smooth zoom progression from 60% to 100% scale
   - Small random pans mimicking camera jitter and vehicle steering
   - Realistic perceptual artifacts: motion blur, Gaussian sensor noise, brightness
     fluctuations, and JPEG compression compression artifacts.
3. Uses a fixed random seed (default: 42) for total reproducibility.
4. Saves MP4 clips to `data/video_events/synthetic/` with filename prefix `synthetic_`.
5. Saves `ground_truth.csv` (and `synthetic_ground_truth.csv`) with columns:
   `clip_name`, `true_plate`, `n_frames`, `source_image`.
"""

import argparse
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np
import pandas as pd

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from pipeline.plate_reader import PlateReader


def apply_motion_blur(frame: np.ndarray, k: int = 7, angle: float = 0.0) -> np.ndarray:
    """Applies realistic directional motion blur simulating vehicle or camera movement."""
    k = max(3, k if k % 2 == 1 else k + 1)
    kernel = np.zeros((k, k), dtype=np.float32)
    kernel[k // 2, :] = 1.0 / k
    # Optional slight rotation for angled motion
    if abs(angle) > 1e-3:
        M = cv2.getRotationMatrix2D((k / 2.0, k / 2.0), angle, 1.0)
        kernel = cv2.warpAffine(kernel, M, (k, k))
        kernel /= (kernel.sum() + 1e-6)
    return cv2.filter2D(frame, -1, kernel)


def apply_gaussian_noise(frame: np.ndarray, sigma: float = 10.0, rng: Optional[np.random.RandomState] = None) -> np.ndarray:
    """Adds zero-mean Gaussian sensor noise."""
    if rng is None:
        noise = np.random.normal(0, sigma, frame.shape).astype(np.float32)
    else:
        noise = rng.normal(0, sigma, frame.shape).astype(np.float32)
    noisy = np.clip(frame.astype(np.float32) + noise, 0, 255)
    return noisy.astype(np.uint8)


def apply_brightness_change(frame: np.ndarray, factor: float = 1.1) -> np.ndarray:
    """Simulates exposure or sunlight glare adjustments."""
    adjusted = np.clip(frame.astype(np.float32) * factor, 0, 255)
    return adjusted.astype(np.uint8)


def apply_jpeg_compression(frame: np.ndarray, quality: int = 40) -> np.ndarray:
    """Simulates video streaming compression artifacts."""
    q = max(10, min(95, int(quality)))
    _, enc = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, q])
    return cv2.imdecode(enc, cv2.IMREAD_COLOR)


def load_test_split_photos(
    raw_dataset_dir: Path,
    split_groups_path: Path,
    seed: int = 42,
    num_photos: int = 60,
) -> List[Tuple[Path, str]]:
    """Discovers and validates photos strictly belonging to the TEST split.
    
    Guarantees:
        - NEVER returns photos assigned to 'train' or 'val'.
        - Checks XML annotation existence and parses ground-truth plate text.
        - Uses deterministic sampling using the provided seed.
    """
    if not split_groups_path.exists():
        raise FileNotFoundError(f"split_groups.json not found at: {split_groups_path.resolve()}")
    if not raw_dataset_dir.exists():
        raise FileNotFoundError(f"Dataset directory not found at: {raw_dataset_dir.resolve()}")

    with open(split_groups_path, "r", encoding="utf-8") as f:
        meta = json.load(f)

    image_to_split = meta.get("image_to_split", {})

    # Build set of approved TEST basenames
    test_basenames = set()
    for img_key, split_val in image_to_split.items():
        if split_val == "test":
            test_basenames.add(Path(img_key).name)

    # Scan raw dataset files
    candidates: List[Tuple[Path, str]] = []
    seen_stems = set()

    for p in sorted(raw_dataset_dir.rglob("*")):
        if p.suffix.lower() not in (".jpg", ".jpeg", ".png"):
            continue
        if p.name not in test_basenames:
            continue

        # Strictly assert that it is NOT in train or val
        if image_to_split.get(p.name) != "test" and image_to_split.get(str(p)) != "test":
            continue

        xml_path = p.with_suffix(".xml")
        if not xml_path.exists():
            continue

        try:
            tree = ET.parse(xml_path)
            root = tree.getroot()
            objs = root.findall("object")
            if not objs:
                continue

            raw_text = objs[0].find("name")
            if raw_text is None or not raw_text.text:
                continue

            clean_plate = PlateReader.normalize_text(raw_text.text)
            if len(clean_plate) >= 4 and clean_plate not in seen_stems:
                candidates.append((p, clean_plate))
                seen_stems.add(clean_plate)
        except Exception:
            continue

    if len(candidates) < num_photos:
        # If unique plate count was smaller, relax plate deduplication while keeping unique image paths
        seen_paths = set()
        candidates = []
        for p in sorted(raw_dataset_dir.rglob("*")):
            if p.suffix.lower() not in (".jpg", ".jpeg", ".png"):
                continue
            if p.name not in test_basenames:
                continue
            xml_path = p.with_suffix(".xml")
            if not xml_path.exists() or p in seen_paths:
                continue
            try:
                tree = ET.parse(xml_path)
                objs = tree.getroot().findall("object")
                if not objs:
                    continue
                raw_text = objs[0].find("name")
                if raw_text is None or not raw_text.text:
                    continue
                clean_plate = PlateReader.normalize_text(raw_text.text)
                if len(clean_plate) >= 4:
                    candidates.append((p, clean_plate))
                    seen_paths.add(p)
            except Exception:
                continue

    if len(candidates) < num_photos:
        raise RuntimeError(f"Found only {len(candidates)} valid test photos, but {num_photos} requested.")

    # Deterministic selection with fixed random seed
    rng = np.random.RandomState(seed)
    selected_indices = rng.choice(len(candidates), size=num_photos, replace=False)
    selected = [candidates[i] for i in selected_indices]

    # Verification: assert 100% of chosen photos belong to test split
    for path, _ in selected:
        split_assigned = image_to_split.get(path.name)
        if split_assigned != "test":
            raise ValueError(f"CRITICAL: Non-test photo selected! {path.name} is in '{split_assigned}'")

    return selected


def render_approaching_clip(
    image_path: Path,
    output_path: Path,
    n_frames: int = 24,
    width: int = 1280,
    height: int = 720,
    fps: int = 12,
    seed: int = 42,
) -> None:
    """Synthesizes a 24-frame clip simulating vehicle approach with zoom, pan, and noise."""
    im = cv2.imread(str(image_path))
    if im is None:
        raise ValueError(f"Could not read image: {image_path}")

    h_orig, w_orig = im.shape[:2]

    # Fit image onto a base 1280x720 canvas preserving aspect ratio
    scale_factor = min(width / w_orig, height / h_orig)
    new_w = int(round(w_orig * scale_factor))
    new_h = int(round(h_orig * scale_factor))
    resized = cv2.resize(im, (new_w, new_h), interpolation=cv2.INTER_LINEAR)

    pad_top = (height - new_h) // 2
    pad_bottom = height - new_h - pad_top
    pad_left = (width - new_w) // 2
    pad_right = width - new_w - pad_left

    base_frame = cv2.copyMakeBorder(
        resized,
        pad_top,
        pad_bottom,
        pad_left,
        pad_right,
        cv2.BORDER_REPLICATE,
    )

    # Initialize video writer
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(output_path), fourcc, float(fps), (width, height))
    if not writer.isOpened():
        # Fallback to MJPG container if platform lacks mp4v
        fallback_path = output_path.with_suffix(".avi")
        fourcc_fb = cv2.VideoWriter_fourcc(*"MJPG")
        writer = cv2.VideoWriter(str(fallback_path), fourcc_fb, float(fps), (width, height))
        if not writer.isOpened():
            raise RuntimeError(f"Could not initialize VideoWriter for {output_path}")

    rng = np.random.RandomState(seed)

    center_x = width / 2.0
    center_y = height / 2.0

    try:
        for t in range(n_frames):
            # 1. Smooth zoom from 60% (t=0) to 100% (t=n_frames - 1)
            t_ratio = float(t) / max(1.0, float(n_frames - 1))
            current_zoom = 0.60 + (1.00 - 0.60) * t_ratio

            # 2. Small random pan (camera shake / vehicle drift)
            pan_x = float(rng.uniform(-6.0, 6.0))
            pan_y = float(rng.uniform(-4.0, 4.0))

            # Affine zoom and pan transformation
            M = cv2.getRotationMatrix2D((center_x, center_y), angle=0.0, scale=current_zoom)
            M[0, 2] += pan_x
            M[1, 2] += pan_y

            frame = cv2.warpAffine(
                base_frame,
                M,
                (width, height),
                borderMode=cv2.BORDER_REPLICATE,
                flags=cv2.INTER_LINEAR,
            )

            # 3. Probabilistic realism augmentations on selected frames
            # Motion blur on ~25% of frames
            if rng.rand() < 0.25:
                blur_k = int(rng.choice([5, 7, 9]))
                angle = float(rng.uniform(-10.0, 10.0))
                frame = apply_motion_blur(frame, k=blur_k, angle=angle)

            # Gaussian noise on ~35% of frames
            if rng.rand() < 0.35:
                sigma = float(rng.uniform(6.0, 14.0))
                frame = apply_gaussian_noise(frame, sigma=sigma, rng=rng)

            # Brightness adjustments on ~40% of frames
            if rng.rand() < 0.40:
                bright_factor = float(rng.uniform(0.82, 1.22))
                frame = apply_brightness_change(frame, factor=bright_factor)

            # JPEG compression degradation on ~30% of frames
            if rng.rand() < 0.30:
                quality = int(rng.uniform(30, 60))
                frame = apply_jpeg_compression(frame, quality=quality)

            writer.write(frame)

    finally:
        writer.release()


def make_synthetic_clips(
    split_groups_path: Path = Path("data/processed/split_groups.json"),
    raw_dataset_dir: Path = Path("data/raw/indian-number-plates-dataset"),
    output_dir: Path = Path("data/video_events/synthetic"),
    num_clips: int = 60,
    n_frames: int = 24,
    seed: int = 42,
    fps: int = 12,
) -> Path:
    """Generates 60 synthetic 24-frame approaching video clips and ground_truth.csv."""
    output_dir.mkdir(parents=True, exist_ok=True)

    print("\n" + "=" * 80)
    print("=== GENERATING SYNTHETIC TEST VIDEO CLIPS ===")
    print("=" * 80)
    print(f"Dataset Source:      {raw_dataset_dir.resolve()}")
    print(f"Split Verification:  {split_groups_path.resolve()} (TEST split only)")
    print(f"Clips to Generate:   {num_clips}")
    print(f"Frames per Clip:     {n_frames} (approx. 1280x720 @ {fps} FPS)")
    print(f"Random Seed:         {seed}")
    print(f"Destination:         {output_dir.resolve()}")
    print("-" * 80)

    selected_photos = load_test_split_photos(
        raw_dataset_dir=raw_dataset_dir,
        split_groups_path=split_groups_path,
        seed=seed,
        num_photos=num_clips,
    )

    print(f"Successfully selected {len(selected_photos)} verified TEST split photos.")

    records = []

    for idx, (img_path, true_plate) in enumerate(selected_photos, 1):
        clip_filename = f"synthetic_clip_{idx:03d}.mp4"
        clip_path = output_dir / clip_filename

        # Render clip
        render_approaching_clip(
            image_path=img_path,
            output_path=clip_path,
            n_frames=n_frames,
            width=1280,
            height=720,
            fps=fps,
            seed=seed + idx * 37,
        )

        rel_source = str(img_path.resolve().relative_to(PROJECT_ROOT.resolve())).replace("\\", "/")
        records.append({
            "clip_name": clip_filename,
            "true_plate": true_plate,
            "n_frames": n_frames,
            "source_image": rel_source,
        })

        if idx % 10 == 0 or idx == num_clips:
            print(f"Rendered {idx:>2}/{num_clips} clips... (Latest: {clip_filename} -> '{true_plate}')")

    # Save ground_truth.csv
    df_gt = pd.DataFrame(records)
    gt_csv_path = output_dir / "ground_truth.csv"
    df_gt.to_csv(gt_csv_path, index=False)

    # Also save with prefix synthetic_ground_truth.csv for unambiguous naming
    synthetic_gt_csv_path = output_dir / "synthetic_ground_truth.csv"
    df_gt.to_csv(synthetic_gt_csv_path, index=False)

    print("\n" + "=" * 80)
    print("=== SYNTHETIC CLIPS GENERATION COMPLETE ===")
    print(f"Total Clips Generated:   {len(records)}")
    print(f"Clips Directory:         {output_dir.resolve()}")
    print(f"Ground Truth CSV Saved:  {gt_csv_path.resolve()}")
    print("=" * 80)

    return gt_csv_path


def main():
    parser = argparse.ArgumentParser(description="Generate synthetic vehicle approach clips from test split photos.")
    parser.add_argument("--split-groups", type=str, default="data/processed/split_groups.json")
    parser.add_argument("--raw-dataset", type=str, default="data/raw/indian-number-plates-dataset")
    parser.add_argument("--output-dir", type=str, default="data/video_events/synthetic")
    parser.add_argument("--num-clips", type=int, default=60, help="Number of clips to generate (default: 60).")
    parser.add_argument("--frames", type=int, default=24, help="Frames per clip (default: 24).")
    parser.add_argument("--seed", type=int, default=42, help="Fixed random seed (default: 42).")
    parser.add_argument("--fps", type=int, default=12, help="Playback frame rate (default: 12).")
    args = parser.parse_args()

    make_synthetic_clips(
        split_groups_path=Path(args.split_groups),
        raw_dataset_dir=Path(args.raw_dataset),
        output_dir=Path(args.output_dir),
        num_clips=args.num_clips,
        n_frames=args.frames,
        seed=args.seed,
        fps=args.fps,
    )


if __name__ == "__main__":
    main()
