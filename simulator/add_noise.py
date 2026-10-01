"""Module 1: ANPR Sensor & OCR Noise Injection.

This script transforms perfect ground truth events into realistic noisy ANPR readings:
1. Drops events at OCR_MISS_RATE (simulating camera occlusions or bad angles).
2. Corrupts license plate characters at OCR_CHAR_ERROR_RATE using optical confusion pairs:
   (O <-> 0, B <-> 8, I <-> 1, S <-> 5, D <-> 0, Z <-> 2).
3. Adds an ocr_confidence score (lower for corrupted readings, high for clean reads).
4. Saves noisy observations to data/sim/events.csv.
"""

from __future__ import annotations

import random
import sys
from pathlib import Path
from typing import Tuple

import pandas as pd

from simulator.config import (
    CONFUSION_MAP,
    EVENTS_PATH,
    GROUND_TRUTH_PATH,
    OCR_CHAR_ERROR_RATE,
    OCR_MISS_RATE,
    RANDOM_SEED,
)


def corrupt_plate_text(
    plate: str, error_rate: float, rnd: random.Random
) -> Tuple[str, bool]:
    """Corrupt license plate characters using visual optical confusion swaps."""
    chars = list(plate)
    corrupted = False

    for i, c in enumerate(chars):
        if rnd.random() < error_rate:
            upper_c = c.upper()
            if upper_c in CONFUSION_MAP:
                chars[i] = CONFUSION_MAP[upper_c]
                corrupted = True
            elif upper_c.isdigit():
                # Swap with confusable letter if available
                digit_to_char = {"0": "O", "1": "I", "5": "S", "8": "B", "2": "Z"}
                if upper_c in digit_to_char:
                    chars[i] = digit_to_char[upper_c]
                    corrupted = True

    return "".join(chars), corrupted


def add_anpr_noise() -> pd.DataFrame:
    """Read ground truth events and produce noisy camera observation records."""
    if not GROUND_TRUTH_PATH.exists():
        raise FileNotFoundError(
            f"Ground truth events file not found at {GROUND_TRUTH_PATH}. "
            "Please run generate_traffic.py first."
        )

    rnd = random.Random(RANDOM_SEED)

    print(f"Reading ground truth events from: {GROUND_TRUTH_PATH} ...")
    gt_df = pd.read_csv(GROUND_TRUTH_PATH)
    total_true_events = len(gt_df)
    print(f"Total ground truth events: {total_true_events:,}")

    noisy_records = []
    dropped_count = 0
    corrupted_count = 0

    for _, row in gt_df.iterrows():
        # 1. Simulate missed camera detection
        if rnd.random() < OCR_MISS_RATE:
            dropped_count += 1
            continue

        true_plate = str(row["plate"])

        # 2. Simulate OCR character confusion
        observed_plate, was_corrupted = corrupt_plate_text(
            true_plate, OCR_CHAR_ERROR_RATE, rnd
        )

        # 3. Assign realistic confidence score
        if was_corrupted:
            corrupted_count += 1
            # Lower confidence when corrupted: 0.45 - 0.78
            confidence = round(rnd.uniform(0.45, 0.78), 3)
        else:
            # High confidence for clean reads: 0.88 - 0.99
            confidence = round(rnd.uniform(0.88, 0.99), 3)

        noisy_records.append(
            {
                "event_id": row.get("event_id"),
                "plate": observed_plate,
                "camera_id": row["camera_id"],
                "timestamp": row["timestamp"],
                "speed_kmh": row["speed_kmh"],
                "heading_degrees": row["heading_degrees"],
                "lane": row["lane"],
                "ocr_confidence": confidence,
            }
        )

    noisy_df = pd.DataFrame(noisy_records)
    # Ensure chronological order
    noisy_df = noisy_df.sort_values(by="timestamp").reset_index(drop=True)

    noisy_df.to_csv(EVENTS_PATH, index=False)

    print(f"Processed noisy ANPR observations:")
    print(f"  - Original true events: {total_true_events:,}")
    print(f"  - Dropped (miss rate {OCR_MISS_RATE*100:.1f}%): {dropped_count:,}")
    print(f"  - Character corrupted ({OCR_CHAR_ERROR_RATE*100:.1f}%): {corrupted_count:,}")
    print(f"  - Saved observations: {len(noisy_df):,} -> {EVENTS_PATH}")

    return noisy_df


def main() -> int:
    add_anpr_noise()
    return 0


if __name__ == "__main__":
    sys.exit(main())
