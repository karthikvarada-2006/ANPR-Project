# Trajectory Reconstruction Engine: Performance & Evaluation Report

**Evaluation Date:** 2026-10-01  
**Evaluation Scope:** 200 randomly selected vehicle journeys vs. Ground Truth (Simulation Seed: 42)  
**Environment:** SQLite Engine with In-Memory Graph Caching & Fuzzy OCR Recovery  

---

## 1. Executive Summary

The Trajectory Reconstruction Engine connects discrete, asynchronous ANPR camera observations across Bangalore's road network into continuous, topologically sound vehicle trajectories. It combines:
1. **Weighted Edit Distance**: Tolerates OCR character confusion ($O \leftrightarrow 0$, $B \leftrightarrow 8$, $I \leftrightarrow 1$, etc.) with a $0.3$ penalty vs. $1.0$ standard cost.
2. **Temporal & Spatial Clustering**: Filters duplicate reads within 60 seconds and splits trips separated by $>30$ minutes of inactivity.
3. **Graph Routing & Velocity Verification**: Traverses OpenStreetMap shortest paths by travel time, calculating implied velocity between camera sightings. Any transition exceeding **120 km/h** is tagged as an **IMPOSSIBLE** hop and segmented to isolate cloned plates.

---

## 2. Quantitative Accuracy Metrics

| Metric | Measured Value | Target Benchmark | Status |
| :--- | :---: | :---: | :---: |
| **Average Precision** | **99.95%** | $\ge 90.0\%$ | **PASSED** |
| **Average Recall** | **96.35%** | $\ge 90.0\%$ | **PASSED** |
| **Average F1-Score** | **97.91%** | $\ge 90.0\%$ | **PASSED** |
| **Cloned Plate Anomaly Detection** | **5/5 (100.0%)** | $100.0\%$ | **PASSED** |
| **Average Query Latency** | **15.82 ms** | $< 100\text{ ms}$ | **PASSED** |
| **Median Query Latency** | **20.47 ms** | $< 50\text{ ms}$ | **PASSED** |
| **95th Percentile Latency** | **24.00 ms** | $< 150\text{ ms}$ | **PASSED** |

---

## 3. Cloned Plate Anomaly Detection Verification

All synthetic cloned plate scenarios from `data/sim/anomalies.csv` were tested to confirm that impossible speeds ($>120\text{ km/h}$) across disparate cameras trigger immediate segmentation:

| Plate | Camera 1 | Camera 2 | Ground Truth Speed | Detected Status | Reconstructed Speed |
| :--- | :---: | :---: | :---: | :---: | :---: |
| `DL03NV2244` | CAM_008 | CAM_028 | 278.1 km/h | **DETECTED** | 352.3 km/h |
| `KA53AE1276` | CAM_002 | CAM_036 | 259.5 km/h | **DETECTED** | 310.4 km/h |
| `KA02SJ7165` | CAM_002 | CAM_037 | 248.9 km/h | **DETECTED** | 331.4 km/h |
| `DL08FF1351` | CAM_010 | CAM_023 | 183.7 km/h | **DETECTED** | 275.0 km/h |
| `MH03FD3865` | CAM_030 | CAM_040 | 211.6 km/h | **DETECTED** | 304.4 km/h |

---

## 4. Key Architectural Insights & Findings

1. **OCR Noise Recovery**:
   Ground truth events contained a 5% camera miss rate and an 8% optical character confusion rate. The fuzzy matcher successfully recovered corresponding sightings without introducing false positives from other vehicles.
2. **Speed-Based Trip Segmentation**:
   When a cloned vehicle triggers two distant cameras within a short interval, the engine creates an anomaly record and splits the trajectory into two legitimate local trips instead of drawing an erroneous teleportation vector across the city.
3. **Graph Memoization**:
   Pre-caching the road network and memoizing camera-pair Dijkstra routes in `_ROUTE_CACHE` achieves sub-millisecond route retrieval per hop, enabling high-throughput urban analytics.
