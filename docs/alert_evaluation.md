# City ANPR Real-Time Alert & Surveillance System Evaluation

**Evaluation Date:** 2026-10-01 17:30:07  
**Evaluated Dataset:** `events.csv` (31,244 total camera events)  
**Ground Truth Reference:** `ground_truth_events.csv` (32,813 total events)  

---

## 1. Executive Summary

This report presents an evaluation of the ANPR real-time surveillance alert engine against simulated ground-truth vehicle movements and injected anomaly scenarios, diagnosing previous alert failures with empirical data and verifying subsequent fixes.

### Before vs. After Optimization Summary

#### Cloned-Plate Detection Comparison
| State | Detection Rule Criteria | Injected Detected | Spurious False Alarms | Recall | Precision |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Before Fixes** | Hop speed > 120 km/h; Suppress OCR variants; Simulator no-dwell departures | 3 / 5 | 53 | **60.0%** | **5.4%** (3 / 56) |
| **After Fixes** | Hop speed > 120 km/h; Exact plate match; Conf $\ge 0.70$; Dwell 15–90 min | 5 / 5 | 0 | **100.0%** | **100.0%** (5 / 5) |

#### Blacklist Surveillance Comparison
| State | Blacklist Target Selection | Raw Precision | Raw Recall | Dedup Precision (10m) | Primary Incident Coverage |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Before Fixes** | Sampled from noisy `events.csv` (8/10 OCR artifacts) | **15.8%** (18/114) | **94.7%** (18/19) | **15.7%** (8/51) | **42.1%** (8/19) |
| **After Fixes** | Sampled strictly from true `ground_truth_events.csv` | **100.0%** (88/88) | **93.6%** (88/94) | **100.0%** (35/35) | **37.2%** (35/94) |

---

## 2. Empirical Diagnosis of Previous Alert Failures

### A. Diagnosis of 53 Spurious CLONED_PLATE False Alarms
Every non-injected cloned-plate alert from the prior run was traced back to `ground_truth_events.csv` and classified by root cause:
- **(a) Simulator Overlapping Trips (Confirmed Primary Cause): 50 / 53 (94.3%)**
  - *Mechanism:* In `simulator/generate_traffic.py`, multi-trip vehicles had departure timestamps sampled uniformly at random across the 24-hour simulation window without checking whether the previous trip had concluded. Consequently, a vehicle departed on Trip 2 before Trip 1 reached its destination, causing the vehicle to appear at two distant cameras across the city within seconds.
  - *Fix Applied:* Enforced sequential trips in `generate_traffic.py` where a vehicle's subsequent trip departs strictly after its previous trip arrival plus a random dwell time of 15 to 90 minutes. Trips exceeding 23:59:59 are dropped.
- **(b) OCR Misread Collisions: 3 / 53 (5.7%)**
  - *Mechanism:* An OCR misread on Vehicle A produced the exact plate string of Vehicle B while Vehicle B was driving elsewhere in the city (e.g., true vehicle `KA04DU4058` was misread as `KA03JG7944` at CAM_003 at 09:14:14, colliding with true vehicle `KA03JG7944` at CAM_037 at 09:15:51).
  - *Mitigation:* Require confidence $\ge 0.70$ on both reads and exact plate string equality.
- **(c) Other Causes: 0 / 53 (0.0%)**

### B. Diagnosis of Blacklist Precision Failures
- **Blacklist Target Corruption (Confirmed Root Cause):**
  - An audit of `data/sim/blacklist.csv` revealed that **8 of the 10** blacklisted targets were corrupt OCR strings (`KA4IUM78I5`, `KA02VD19Z0`, `MH120K4639`, `KAS0XD976Z`, `MHI0XR1819`, `KA5OYR2985`, `KA51X06384`, `KAS1UB6231`) that never existed in `ground_truth_events.csv`.
  - *Mechanism:* `simulator/inject_scenarios.py` previously selected plates from noisy `events_df["plate"]` rather than ground truth. Because 80% of the blacklist consisted of OCR corruptions, real vehicles could only trigger alerts via accidental secondary OCR corruptions or loose fuzzy matches, producing 96 false positives.
  - *Fix Applied:* Updated `inject_scenarios.py` to sample blacklist targets strictly from `gt_df["plate"].dropna().unique()`.

### C. Undo "Suppress OCR Variants" Rule
- The prior rule suppressed cloned-plate alerts if a plate looked like an OCR confusable variant of another registered vehicle (`plate_distance <= 0.6`).
- While intended to reduce false alarms, empirical verification showed that this rule suppressed 2 legitimate injected clones (`TN050T8444` and `KA50ES267B`), capping recall at 60.0%.
- This suppression was removed from `check_cloned_plate`. The rule now relies strictly on exact normalized plate matching and confidence $\ge 0.70$ on both sightings. As a result, recall improved to 100.0% (5/5).

---

## 3. Ground Truth Evaluation Definition

To evaluate alerts directly against physical ground truth:
- An `event_id` integer primary key links each noisy observation in `events.csv` to its true sighting in `ground_truth_events.csv`.
- Synthetic injected anomaly observations without ground-truth counterparts are marked with `event_id = None`.
- **Blacklist True Positive Definition:** A blacklist alert is defined as a **true positive if and only if the event's true ground-truth plate is on the blacklist** (`true_plate in blacklist`). If the true vehicle is not on the blacklist, the alert is classified as a false positive (even if OCR noise made the plate text resemble a blacklisted string).

---

## 4. Key Performance Metrics

| Metric Category | Evaluation Metric | Result |
| :--- | :--- | :--- |
| **Cloned Plate Detection** | Anomalies Detected (Recall) | **5 / 5 (100.0%)** |
| **Cloned Plate Precision** | Injected Targets / Total Cloned Alerts | **5 / 5 (100.0%)** |
| **Blacklist Recall (Raw)** | True GT Sightings Detected | **88 / 94 (93.6%)** |
| **Blacklist Precision (Raw)** | True Positives / Total Raw Alerts | **88 / 88 (100.0%)** |
| **Blacklist Precision (Dedup)** | True Positives / Total Dedup Incidents | **35 / 35 (100.0%)** |
| **Incident Coverage (Dedup)** | Primary Incident Dispatches | **35 / 94 (37.2%)** |
| **False-Alarm Rate (All Rules)** | False Alarms per 1,000 Events (Dedup) | **0.000 / 1k events** |
| **False-Alarm Rate (All Rules)** | False Alarms per 1,000 Events (Raw) | **0.000 / 1k events** |
| **Processing Latency** | Average Time Per Event | **0.521 ms** |
| **Throughput** | Real-Time Replay Speed | **1,918 events/sec** |

---

## 5. Blacklist Surveillance Accounting

### A. Raw Alert Accounting (Before De-Duplication)
- **Exact Matches (Severity: HIGH):** 76
- **Fuzzy OCR Confusable Matches (Severity: MEDIUM, Distance $\le 0.6$):** 12
- **Total Raw Blacklist Alerts:** **88** (`exact (76) + fuzzy (12) = 88`)
- **True Positive Alerts:** 88
- **False Positive Alerts:** 0
- **Total True + False Positives:** **88** (`TP (88) + FP (0) = 88`)
- **Raw Precision:** **100.00%** (88 / 88)
- **Raw Recall:** **93.6%** (88 of 94 true sightings)

### B. De-Duplicated Incident Accounting (10-Minute Sliding Window)
- **Exact Match Incidents (Severity: HIGH):** 23
- **Fuzzy OCR Confusable Incidents (Severity: MEDIUM):** 12
- **Total De-duplicated Incidents:** **35** (`exact (23) + fuzzy (12) = 35`)
- **True Positive Incidents:** 35
- **False Positive Incidents:** 0
- **Total True + False Positives:** **35** (`TP (35) + FP (0) = 35`)
- **De-duplicated Precision:** **100.00%** (35 / 35)

---

## 6. Injected Cloned Plate Anomalies

Cloned plate distances and implied speeds are evaluated using shortest-path road network distances from `camera_paths.pkl`:

| Target Plate | Camera 1 | Camera 2 | Road Distance | Time Delta | Implied Speed | Detection Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **DL03NV2244** | CAM_008 | CAM_028 | 6,067 m | 62 s | 352.3 km/h | **DETECTED (HIGH)** |
| **KA53AE1276** | CAM_002 | CAM_036 | 4,484 m | 52 s | 310.4 km/h | **DETECTED (HIGH)** |
| **KA02SJ7165** | CAM_002 | CAM_037 | 5,800 m | 63 s | 331.4 km/h | **DETECTED (HIGH)** |
| **DL08FF1351** | CAM_010 | CAM_023 | 6,723 m | 88 s | 275.0 km/h | **DETECTED (HIGH)** |
| **MH03FD3865** | CAM_030 | CAM_040 | 5,496 m | 65 s | 304.4 km/h | **DETECTED (HIGH)** |

---

## 7. False Alarms Across All Rules

| Rule Type | Total Alerts | True Alerts | False Alarms | False Alarm Source / Note |
| :--- | :--- | :--- | :--- | :--- |
| **BLACKLIST** | 35 | 35 | 0 | Zero false alarms when blacklist targets are true fleet plates |
| **CLONED_PLATE** | 5 | 5 | 0 | Zero spurious alarms after adding sequential trip dwell constraint |
| **OVERSPEED** | 0 | 0 | 0 | No simulated speeds clocked > 80 km/h |
| **RESTRICTED_ZONE** | 4 | 4 | 0 | Commercial truck curfew violations (22:00 - 06:00) |
| **WRONG_WAY** | 0 | 0 | 0 | Disabled by default in config (`WRONG_WAY_ENABLED=False`) |
| **LOITERING** | 0 | 0 | 0 | No vehicle exceeded 3 sightings within 60 minutes |
| **TOTAL** | **44** | **44** | **0** | **0.000 false alarms per 1,000 events** |

---

## 8. Alerts Breakdown by Severity and Type

### Alerts by Severity
| Severity Level | Alert Count | Percentage | Primary Triggers |
| :--- | :--- | :--- | :--- |
| **HIGH** | **28** | 63.6% | Exact Blacklist hits, Cloned Plates (> 120 km/h) |
| **MEDIUM** | **16** | 36.4% | Fuzzy Blacklist hits, Prohibited curfew zone entries |
| **LOW** | **0** | 0.0% | Overspeeding (> 80 km/h), Loitering (> 3 visits / hr) |
| **TOTAL** | **44** | **100.0%** | |

### Alerts by Rule Type
| Alert Type | Count | Status / Description |
| :--- | :--- | :--- |
| **BLACKLIST** | **35** | Active surveillance rule |
| **CLONED_PLATE** | **5** | Active surveillance rule |
| **WRONG_WAY** | **0** | Disabled by default; requires one-way road ground truth |
| **OVERSPEED** | **0** | Active surveillance rule |
| **RESTRICTED_ZONE** | **4** | Active surveillance rule |
| **LOITERING** | **0** | Active surveillance rule |

---

## 9. Real-Time Processing Characteristics

- **Total Events Processed:** 31,244
- **Total Execution Wall Time:** 16.29 seconds
- **Average Processing Latency:** **0.521 milliseconds per event**
- **Sustained Stream Throughput:** **1,918 sightings per second**

---

## 10. Remaining System Limitations

1. **WRONG_WAY Rule Requires Directional Graph Attributes:** The `WRONG_WAY` rule is disabled by default (`WRONG_WAY_ENABLED = False`) because intersection cameras capture vehicles approaching from all four legs of an intersection. Reliably flagging wrong-way traffic requires directed lane geometry or ground-truth one-way road network attributes.
2. **Synthetic Traffic Dwell Model:** Vehicle departures are modeled with uniform 15–90 minute dwell intervals. Real-world urban driver dwell times follow heavy-tailed log-normal distributions (e.g., 8-hour workday parking vs. 10-minute retail stops).
3. **Uniform OCR Error Model:** The current noise model applies independent character substitutions and dropouts. Real ANPR cameras encounter environmental occlusions, severe perspective skew, lighting glare, and physical plate damage.
4. **Overspeeding Threshold Sensitivity:** Simulated speeds did not exceed 80 km/h on urban arterial corridors, resulting in 0 overspeed alerts; in production, speed thresholds must be calibrated per road classification (e.g., 50 km/h for urban streets, 80 km/h for expressways).
