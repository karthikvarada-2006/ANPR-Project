"""Master Runner for Module 1: City ANPR Event Simulator.

This script executes the entire simulation pipeline in sequence:
  Step 1: Download & build city road network + place ANPR cameras (build_city.py)
  Step 2: Generate realistic daily traffic trips & ground truth events (generate_traffic.py)
  Step 3: Apply ANPR camera occlusions & OCR character noise (add_noise.py)
  Step 4: Inject blacklist surveillance & cloned plate anomalies (inject_scenarios.py)
  Step 5: Render high-resolution city map & vehicle trajectory (visualize.py)
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

# Ensure project root is in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from simulator.build_city import build_city_network
from simulator.generate_traffic import generate_traffic_events
from simulator.add_noise import add_anpr_noise
from simulator.inject_scenarios import inject_scenarios
from simulator.visualize import generate_city_visualization
from simulator.config import (
    ANOMALIES_PATH,
    BLACKLIST_PATH,
    CAMERAS_PATH,
    CITY_NAME,
    EVENTS_PATH,
    GRAPH_PATH,
    GROUND_TRUTH_PATH,
    MAP_PATH,
)


def run_pipeline() -> int:
    t_start = time.time()
    print("=" * 75)
    print(f"CITY-WIDE ANPR SIMULATOR PIPELINE: {CITY_NAME}")
    print("=" * 75)

    # Step 1: Road Network & Cameras
    print("\n[STAGE 1/5] Building Road Network & Placing Virtual Cameras...")
    s1 = time.time()
    build_city_network()
    print(f"-> Stage 1 completed in {time.time() - s1:.2f}s")

    # Step 2: Traffic & Ground Truth Events
    print("\n[STAGE 2/5] Simulating Vehicle Fleet & Generating Ground Truth ANPR Events...")
    s2 = time.time()
    generate_traffic_events()
    print(f"-> Stage 2 completed in {time.time() - s2:.2f}s")

    # Step 3: Noise & OCR Errors
    print("\n[STAGE 3/5] Applying Camera Miss Rates & Optical Character Noise...")
    s3 = time.time()
    add_anpr_noise()
    print(f"-> Stage 3 completed in {time.time() - s3:.2f}s")

    # Step 4: Scenario & Anomaly Injection
    print("\n[STAGE 4/5] Injecting Security Blacklist & Cloned Plate Anomalies...")
    s4 = time.time()
    inject_scenarios()
    print(f"-> Stage 4 completed in {time.time() - s4:.2f}s")

    # Step 5: Map Visualization
    print("\n[STAGE 5/5] Generating High-Resolution City Map & Trajectory Visualization...")
    s5 = time.time()
    generate_city_visualization()
    print(f"-> Stage 5 completed in {time.time() - s5:.2f}s")

    # Summary
    total_time = time.time() - t_start
    print("\n" + "=" * 75)
    print("SIMULATION PIPELINE COMPLETE!")
    print("=" * 75)
    print("Generated Artifacts:")
    print(f"  1. Road Graph:          {GRAPH_PATH}")
    print(f"  2. Camera Registry:     {CAMERAS_PATH}")
    print(f"  3. Ground Truth Events: {GROUND_TRUTH_PATH}")
    print(f"  4. Sensor Events:       {EVENTS_PATH}")
    print(f"  5. Security Blacklist:  {BLACKLIST_PATH}")
    print(f"  6. Cloned Anomalies:    {ANOMALIES_PATH}")
    print(f"  7. City Map Image:      {MAP_PATH}")
    print(f"Total Pipeline Execution Time: {total_time:.2f} seconds")
    print("=" * 75)

    return 0


def main() -> int:
    return run_pipeline()


if __name__ == "__main__":
    sys.exit(main())
