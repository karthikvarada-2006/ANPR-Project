"""Dataset Downloader for City-Wide ANPR System.

This script uses the Kaggle API to automatically download and extract:
1. saisirishan/indian-vehicle-dataset -> data/raw/indian-vehicle-dataset/
2. dataclusterlabs/indian-number-plates-dataset -> data/raw/indian-number-plates-dataset/
3. sunrajbishnolia/license-plate-detection -> data/raw/license-plate-detection/

If a dataset folder already exists and is not empty, downloading is skipped.
A summary of image count and disk usage is printed at completion.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Dict, List, Tuple

# Supported image extensions
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff"}

# Dataset registry
DATASETS = [
    {
        "slug": "saisirishan/indian-vehicle-dataset",
        "folder_name": "indian-vehicle-dataset",
        "title": "Indian Vehicle Dataset",
    },
    {
        "slug": "dataclusterlabs/indian-number-plates-dataset",
        "folder_name": "indian-number-plates-dataset",
        "title": "Indian Number Plates Dataset",
    },
    {
        "slug": "sunrajbishnolia/license-plate-detection",
        "folder_name": "license-plate-detection",
        "title": "License Plate Detection Dataset",
    },
]


def format_bytes(size_bytes: int) -> str:
    """Format byte size into human-readable string (KB, MB, GB)."""
    val = float(size_bytes)
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if val < 1024.0:
            return f"{val:.2f} {unit}"
        val /= 1024.0
    return f"{val:.2f} PB"


def check_kaggle_credentials() -> bool:
    """Check if Kaggle credentials file or environment variables exist."""
    home_dir = Path.home()
    default_kaggle_json = home_dir / ".kaggle" / "kaggle.json"
    default_access_token = home_dir / ".kaggle" / "access_token"
    env_config_dir = os.environ.get("KAGGLE_CONFIG_DIR")

    custom_kaggle_json = (
        Path(env_config_dir) / "kaggle.json" if env_config_dir else None
    )

    has_file = (
        default_kaggle_json.exists()
        or default_access_token.exists()
        or (custom_kaggle_json and custom_kaggle_json.exists())
    )
    has_env = bool(
        os.environ.get("KAGGLE_USERNAME") and os.environ.get("KAGGLE_KEY")
    ) or bool(os.environ.get("KAGGLE_API_TOKEN"))

    return has_file or has_env


def inspect_folder(folder_path: Path) -> Tuple[int, int, int]:
    """Inspect folder and return (image_count, total_file_count, total_bytes)."""
    image_count = 0
    total_file_count = 0
    total_bytes = 0

    if not folder_path.exists():
        return 0, 0, 0

    for item in folder_path.rglob("*"):
        if item.is_file():
            total_file_count += 1
            try:
                total_bytes += item.stat().st_size
            except OSError:
                pass
            if item.suffix.lower() in IMAGE_EXTENSIONS:
                image_count += 1

    return image_count, total_file_count, total_bytes


def download_all_datasets(raw_dir: Path) -> int:
    """Download and unzip datasets using Kaggle API."""
    print("=" * 70)
    print("City-Wide ANPR Dataset Downloader")
    print("=" * 70)
    print(f"Target raw directory: {raw_dir.resolve()}\n")

    raw_dir.mkdir(parents=True, exist_ok=True)

    # 1. Verify credentials
    if not check_kaggle_credentials():
        print("[ERROR] Kaggle credentials not found!")
        print("Please ensure your 'kaggle.json' is located at:")
        print(f"  {Path.home() / '.kaggle' / 'kaggle.json'}")
        print("\nOr set environment variables:")
        print("  $env:KAGGLE_USERNAME = 'your_username'")
        print("  $env:KAGGLE_KEY = 'your_key'")
        return 1

    # 2. Initialize Kaggle API
    try:
        from kaggle.api.kaggle_api_extended import KaggleApi

        api = KaggleApi()
        api.authenticate()
        print("[AUTH] Successfully authenticated with Kaggle API.\n")
    except Exception as exc:
        print(f"[ERROR] Failed to authenticate with Kaggle: {exc}")
        print("Please check that your kaggle.json is valid and contains your API token.")
        return 1

    # 3. Download / Skip each dataset
    results = []

    for item in DATASETS:
        slug = item["slug"]
        folder_name = item["folder_name"]
        title = item["title"]
        target_dir = raw_dir / folder_name

        print("-" * 70)
        print(f"Dataset: {title} ({slug})")

        # Check if already exists and contains files
        if target_dir.exists() and any(target_dir.iterdir()):
            print(f"  [STATUS] Folder '{folder_name}' already exists and is not empty.")
            print("  [ACTION] Skipping download.")
        else:
            target_dir.mkdir(parents=True, exist_ok=True)
            print(f"  [ACTION] Downloading and unzipping into: {target_dir.name}/ ...")
            try:
                api.dataset_download_files(
                    slug,
                    path=str(target_dir),
                    unzip=True,
                    quiet=False,
                )
                print("  [DONE] Download & unzip completed.")
            except Exception as err:
                print(f"  [ERROR] Failed to download {slug}: {err}")

        # Compute stats
        img_count, file_count, byte_size = inspect_folder(target_dir)
        results.append(
            {
                "title": title,
                "folder": folder_name,
                "images": img_count,
                "files": file_count,
                "size_str": format_bytes(byte_size),
                "bytes": byte_size,
            }
        )

    # 4. Print Summary
    print("\n" + "=" * 70)
    print("DATASET INVENTORY SUMMARY")
    print("=" * 70)
    print(f"{'Dataset Folder':<32} | {'Images':<10} | {'Total Files':<12} | {'Size':<10}")
    print("-" * 70)

    total_all_images = 0
    total_all_bytes = 0

    for r in results:
        print(
            f"{r['folder']:<32} | {r['images']:<10,d} | {r['files']:<12,d} | {r['size_str']:<10}"
        )
        total_all_images += r["images"]
        total_all_bytes += r["bytes"]

    print("-" * 70)
    print(
        f"{'TOTAL':<32} | {total_all_images:<10,d} | {'':<12} | {format_bytes(total_all_bytes):<10}"
    )
    print("=" * 70)

    # Reminder about manual datasets
    manual_datasets = ["ccpd", "ufpr_alpr", "cityflowv2"]
    missing_manual = [d for d in manual_datasets if not (raw_dir / d).exists()]
    if missing_manual:
        print("\n[REMINDER] Manual datasets still required:")
        for d in missing_manual:
            print(f"  - data/raw/{d}/")
        print("See data/raw/README.md for download instructions and structure.")

    return 0


def main() -> int:
    # Project root is parent of 'data' directory
    current_file = Path(__file__).resolve()
    project_root = current_file.parent.parent
    raw_dir = project_root / "data" / "raw"

    return download_all_datasets(raw_dir)


if __name__ == "__main__":
    sys.exit(main())
