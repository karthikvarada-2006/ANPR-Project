# FACTS.md — Ground-Truth Facts for the Project Report
> All facts below are sourced from project files, the live database (read-only), or
> existing evaluation documents. Invented numbers are forbidden; use [FILL] instead.
> Every fact carries an ID (F1, F2, …) used in TRACE.md to link report text to sources.

---

## ENVIRONMENT (F1–F10)

| ID   | Fact | Source |
|------|------|--------|
| F1   | OS: Windows; Python 3.11.9; virtual environment `.venv` | `README.md`, `requirements.txt` |
| F2   | Database: SQLite at `data/city_anpr.db` (15,507,456 bytes as of backup 2026-10-31) | DB backup |
| F3   | Key packages: ultralytics 8.4.171, fast-plate-ocr[onnx] 1.1.0, onnxruntime 1.30.0, opencv-python 5.0.0.93, torch 2.14.1, torchvision 0.29.1, fastapi, uvicorn, numpy, pandas, geopandas, osmnx, networkx, shapely, sqlalchemy, pydantic, pytest | `requirements.txt` |
| F4   | OCR model: `cct_s_v2_finetuned_indian.onnx` (fast-plate-ocr Compact Convolutional Transformer small v2, fine-tuned on Indian plates) | `pipeline/plate_reader.py`, `models/plate_ocr/` |
| F5   | Vehicle detector: `models/plate_detector.pt` (YOLOv8s, fine-tuned on Indian plate dataset) | `backend/api/main.py` |
| F6   | Tracker: Ultralytics ByteTrack (`bytetrack.yaml`, `persist=True`) | `pipeline/video_pipeline.py` |
| F7   | Training: Google Colab T4 GPU | FACTS prompt (F7) |
| F8   | Last reported test run: 101 tests passed | FACTS prompt |
| F9   | API host: FastAPI + Uvicorn on `0.0.0.0:8000` | `.env.example`, `backend/api/main.py` |
| F10  | Dashboard: plain HTML/JS (no React/Node required); libraries Leaflet, Chart.js | `frontend/index.html` (confirmed — no React build) |

> **Note on README vs reality (MISMATCH-1):** The README describes the frontend as "React & Leaflet/MapLibre" and lists a `frontend/` React build. In practice, `frontend/index.html` is a standalone HTML/JS file with no React — no `package.json` or build step exists. List in TODO.md.

---

## SYSTEM ARCHITECTURE (F11–F20)

| ID   | Fact | Source |
|------|------|--------|
| F11  | Real path: photos/video → YOLOv8s detector → ByteTrack (persist=True) + fine-tuned OCR → plate voting + REVIEW flag | `pipeline/video_pipeline.py`, `pipeline/voting.py` |
| F12  | Simulated path: OSM Bangalore city graph → 5,000 vehicles → 40 cameras → noisy events | `simulator/config.py` |
| F13  | Both paths write to SQLite `events` table (tagged `source='sim'` or `source='video'`) | `backend/models.py`, DB inspection |
| F14  | Shared downstream: trajectory engine → analytics engine → alert engine → FastAPI → dashboard | `backend/trajectory.py`, `backend/analytics.py`, `backend/alerts/engine.py` |
| F15  | Plate Reader tab calls `POST /api/plates/read` (detector + OCR directly via API) | `backend/api/main.py` |
| F16  | 6 dashboard tabs: Overview, Trajectory Search, Traffic Heatmap, Live Alerts, Blacklist, Plate Reader | `frontend/index.html` |
| F17  | Dashboard has NO counting tab: `COUNTING_TAB_BUILT = NO` | `frontend/index.html` (confirmed absent) |
| F18  | WebSocket endpoint: `ws://host/ws/live` (replays `events.csv` through AlertEngine) | `backend/api/main.py` |
| F19  | CSV export for trajectory uses `escape_csv_cell()` to prevent formula injection | `backend/plate_utils.py`, `backend/api/main.py` |
| F20  | WRONG_WAY rule disabled by default (`WRONG_WAY_ENABLED = False` in `simulator/config.py`) | `simulator/config.py`, `backend/alert_rules.py` |

---

## SIMULATED CITY (F21–F35)

| ID   | Fact | Source |
|------|------|--------|
| F21  | City: Bangalore, India; radius 5 km around centre | `simulator/config.py` |
| F22  | NUM_CAMERAS = 40; minimum camera spacing 300 m; RANDOM_SEED = 42 | `simulator/config.py` |
| F23  | NUM_VEHICLES = 5,000; simulation date 2026-10-01 | `simulator/config.py` |
| F24  | OCR miss rate 5%; character confusion rate 8% per character | `simulator/config.py` |
| F25  | Confusion map: O↔0, B↔8, I↔1, S↔5, D→0, Z→2, G→6 (weighted distance 0.3) | `simulator/config.py`, `backend/plate_utils.py` |
| F26  | Total sim events in DB: 31,244 (source='sim') | DB inspection |
| F27  | Total events in DB (all sources): 31,264 (31,244 sim + 20 video) | DB inspection |
| F28  | Distinct sim plates in DB: 10,729 | DB inspection |
| F29  | 10 blacklist plates; 5 injected clones | DB inspection (10 blacklist rows), `docs/alert_evaluation.md` |
| F30  | Alerts total: 44 (BLACKLIST 35, CLONED_PLATE 5, RESTRICTED_ZONE 4, OVERSPEED 0) | DB inspection, `docs/alert_evaluation.md` |
| F31  | RESTRICTED cameras: CAM_001, CAM_002, CAM_003; restricted time 22:00–06:00; restricted vehicle type: truck | `simulator/config.py` |
| F32  | Peak hours: morning 08:00–10:00 (congestion 1.65×), evening 17:00–20:00 (1.85×) | `simulator/config.py` |
| F33  | Top hour by event count: 09:00 (4,277 events) | DB inspection |
| F34  | Alert engine throughput: 1,918 sightings/second; avg latency 0.521 ms/event; 16.29 s total | `docs/alert_evaluation.md` |
| F35  | Unique vehicles shown in analytics: 4,296 (FACTS prompt — not independently verified from DB; note F28 gives 10,729 distinct plates which is larger) | FACTS prompt [MISMATCH-2: verify] |

> **MISMATCH-2:** FACTS prompt states "Unique vehicles shown 4,296" but DB shows 10,729 distinct sim plates. The 4,296 figure likely refers to vehicles shown in the dashboard analytics (which default to `source='sim'` with a rolling window filter). Flagged in TODO.md.

---

## TRAJECTORY ENGINE (F36–F41)

| ID   | Fact | Source |
|------|------|--------|
| F36  | Evaluation: 200 randomly selected journeys vs. ground truth (seed 42) | `docs/trajectory_evaluation.md` |
| F37  | Trajectory precision 99.95%; recall 96.35%; F1 97.91% | `docs/trajectory_evaluation.md` |
| F38  | Average query latency 15.82 ms; median 20.47 ms; P95 24.00 ms | `docs/trajectory_evaluation.md` |
| F39  | Cloned plate detection: 5/5 (100%) on injected scenarios | `docs/trajectory_evaluation.md` |
| F40  | Speed threshold for clone detection: implied speed > 120 km/h between cameras | `backend/alert_rules.py` |
| F41  | Journey CSV export: 17 rows for TN11YD7305 (fuzzy matcher joins OCR-noisy variants) | FACTS prompt |

> **Note on latency (MISMATCH-3):** FACTS prompt states "about 15 ms per query" but evaluation doc gives average 15.82 ms and median 20.47 ms. The 15 ms figure matches average but not median. Report both; prefer the document values.

---

## REAL DETECTOR (F42–F46)

| ID   | Fact | Source |
|------|------|--------|
| F42  | Dataset: `indian-number-plates-dataset` + `license-plate-detection` + `indian-vehicle-dataset` | `docs/data_report.md` |
| F43  | Detector split: 1,467 train (79.9%), 184 val (10.0%), 184 test (10.0%); total 1,835 images | `docs/data_report.md` |
| F44  | Detector results (test split): precision 98.3%, recall 98.1%, mAP50 98.3%, mAP50-95 84.3%, F1 98.2% (computed from P and R) | FACTS prompt |
| F45  | Split isolation: group-based (perceptual hash Hamming ≤ 4); no frame leakage between splits | `docs/data_report.md` |
| F46  | Detector confidence threshold in API: conf_thresh = 0.25; padding_ratio = 0.05 | `pipeline/plate_reader.py`, `backend/api/main.py` |

---

## REAL OCR (F47–F54)

| ID   | Fact | Source |
|------|------|--------|
| F47  | OCR dataset: 1,360 train + 168 val + 167 test real crops; 10,400 synthetic train-only; total 12,095 | `docs/data_report.md` |
| F48  | Synthetic crops strictly in train/ only (no test leakage) | `docs/data_report.md` |
| F49  | OCR model fine-tuning: Google Colab T4 GPU | FACTS prompt |
| F50  | OCR progression (plate-level / character-level): scratch 29.4% / [FILL char], zero-shot 25.2% / [FILL char], zero-shot + syntax rules 37.1% / [FILL char], fine-tuned (unseen crops) 76.9% / 95.7% | FACTS prompt; char-level breakdown for early stages not found in docs |
| F51  | End-to-end test (167 held-out photos): detection recall 100%, detection precision 98.8%, plate exact match 80.84%, character accuracy 96.30%, avg latency ~307 ms/image on CPU | FACTS prompt; `docs/ocr/end_to_end_results.csv` (sample confirms ≈300 ms) |
| F52  | REVIEW threshold: REVIEW_CONFIDENCE_THRESHOLD = 0.80 (fixed, not tuned) | `backend/plate_utils.py` |
| F53  | REVIEW status triggered by: OCR confidence < 0.80 OR vote_margin < 0.80 | `backend/plate_utils.py` |
| F54  | 2 of 20 video events flagged REVIEW: DL8CN63308 (conf 61.1%, margin 71.1%) and MH022N5 (conf 70.4%, margin 100%) | DB inspection (lowest conf video events) |

---

## REAL VIDEO SEQUENCES (F55–F63)

| ID   | Fact | Source |
|------|------|--------|
| F55  | 20 real video sequences tested; 9 single-frame, 11 multi-frame; avg 3.80 frames/sequence | `docs/ocr/voting_summary.md` |
| F56  | Per-frame plate accuracy: 85.24%; voted consensus: 90.00% (18/20 correct) | `docs/ocr/voting_summary.md` |
| F57  | 95% confidence interval for 18/20 (n=20): approximately 68% to 99% (Wilson interval) | Computed: Wilson CI for p=0.9, n=20 |
| F58  | Per-frame char accuracy: 95.95%; voted char accuracy: 97.00% | `docs/ocr/voting_summary.md` |
| F59  | Wrong read 1: GT=DL8CN6308, voted=DL8CN63308, conf 61.1%, margin 71.1%, 7 frames | `docs/ocr/voting_results.csv` |
| F60  | Wrong read 2: GT=MH02EN6828, voted=MH022N5, conf 70.4%, margin 100%, 1 frame (single-frame) | `docs/ocr/voting_results.csv` |
| F61  | Both wrong reads had the lowest OCR confidence of the 20 sequences | DB inspection / voting_results.csv |
| F62  | SYNTHETIC clips (NOT real-world): 60 clips, 24 frames each; per-frame 66.87%, voted 78.33% (OPTIMISTIC — all frames from one photo) | `docs/ocr/voting_summary.md` |
| F63  | Voting method used: positional_weighted (character-position weighted) for multi-frame; identity for single-frame | `docs/ocr/voting_results.csv` |

---

## VIDEO INGESTION INTO DATABASE (F64–F68)

| ID   | Fact | Source |
|------|------|--------|
| F64  | 20 source='video' events in DB (20 distinct plates) | DB inspection |
| F65  | Demo camera: CAM_VIDEO_01, name "ANPR Video Pipeline Demo Camera", lat 12.9716, lon 77.5946 (placeholder Bangalore coordinates) | DB inspection |
| F66  | Total cameras in DB: 41 (40 sim + 1 demo video camera) | DB inspection |
| F67  | Analytics default filter: `source='sim'` (video events excluded from city-level analytics) | `backend/analytics.py` (inferred from FACTS prompt) |
| F68  | Video event timestamps: 2026-10-05 10:00:00 to 10:19:00 (placeholder timestamps) | DB inspection |

---

## DATABASE SCHEMA (F69–F77)

| ID   | Fact | Source |
|------|------|--------|
| F69  | Tables: alerts, blacklist, camera_window_stats, cameras, congestion, events, od_matrix, route_density, trajectories | DB inspection |
| F70  | events columns: id, plate, camera_id, timestamp, speed_kmh, heading_degrees, lane, ocr_confidence, source, track_id, n_frames, vote_margin, best_crop_path | DB inspection |
| F71  | alerts columns: id, alert_type, plate, camera_id, timestamp, details (JSON), created_at, severity | DB inspection |
| F72  | cameras columns: camera_id, name, lat, lon, node_id | DB inspection |
| F73  | trajectories table: 0 rows (pre-computed trajectories not persisted; computed on-demand) | DB inspection |
| F74  | camera_window_stats: 2,795 rows; congestion: 463 rows; od_matrix: 64 rows; route_density: 3,194 rows | DB inspection |
| F75  | Overspeed threshold: 80 km/h (check_overspeed); clone speed threshold: 120 km/h (check_cloned_plate) | `backend/alert_rules.py` |
| F76  | Overspeed = 0 alerts because simulated speeds never exceeded 80 km/h on urban corridors | `docs/alert_evaluation.md` |
| F77  | LOITERING rule: ≥ 3 visits at same camera within 60 minutes; 0 alerts triggered | `docs/alert_evaluation.md` |

---

## API ENDPOINTS (F78–F90)

| ID   | Fact | Source |
|------|------|--------|
| F78  | GET /api/health | `backend/api/main.py` |
| F79  | GET /api/cameras | `backend/api/main.py` |
| F80  | GET /api/trajectory/{plate} | `backend/api/main.py` |
| F81  | GET /api/trajectory/{plate}/export (CSV with formula injection escaping) | `backend/api/main.py` |
| F82  | GET /api/plates/search | `backend/api/main.py` |
| F83  | GET /api/analytics/overview (alias: /api/analytics/summary) | `backend/api/main.py` |
| F84  | GET /api/analytics/hourly-volume (alias: /api/analytics/flow-trend) | `backend/api/main.py` |
| F85  | GET /api/analytics/busiest-cameras (alias: /api/analytics/camera-stats) | `backend/api/main.py` |
| F86  | GET /api/analytics/congestion; GET /api/analytics/od-matrix; GET /api/analytics/route-density; GET /api/analytics/heatmap | `backend/api/main.py` |
| F87  | GET /api/alerts; GET/POST/DELETE /api/blacklist; DELETE /api/blacklist/{plate} | `backend/api/main.py` |
| F88  | POST /api/plates/read (upload image → detect + OCR → return results) | `backend/api/main.py` |
| F89  | GET /api/plates/sample-images; GET /api/events | `backend/api/main.py` |
| F90  | WebSocket /ws/live (replay events.csv through AlertEngine with speed multiplier) | `backend/api/main.py` |

---

## ALERT RULES (F91–F97)

| ID   | Fact | Source |
|------|------|--------|
| F91  | BLACKLIST: exact match → HIGH severity; fuzzy confusable match (distance ≤ 0.6) → MEDIUM severity | `backend/alert_rules.py` |
| F92  | CLONED_PLATE: implied road speed > 120 km/h between two camera sightings → HIGH severity | `backend/alert_rules.py` |
| F93  | WRONG_WAY: heading differs > 135° from dominant camera heading → MEDIUM; disabled by default | `backend/alert_rules.py` |
| F94  | OVERSPEED: instantaneous speed > 80 km/h → LOW severity | `backend/alert_rules.py` |
| F95  | LOITERING: ≥ 3 visits same camera within 60 min → LOW; 0 triggers in sim | `backend/alert_rules.py`, `docs/alert_evaluation.md` |
| F96  | RESTRICTED_ZONE: truck at CAM_001/002/003 between 22:00–06:00 → MEDIUM; 4 alerts triggered | `simulator/config.py`, `docs/alert_evaluation.md` |
| F97  | Deduplication window: 10 minutes (AlertEngine parameter) | `backend/api/main.py` |

---

## BLACKLIST PRECISION/RECALL (F98–F100)

| ID   | Fact | Source |
|------|------|--------|
| F98  | Blacklist precision 100% (35/35 de-duplicated incidents, all true); recall 93.6% (88/94 raw true sightings matched) | `docs/alert_evaluation.md` |
| F99  | Cloned plate detection: 5/5 (100%); zero false alarms after fixes | `docs/alert_evaluation.md` |
| F100 | Before-fixes state: blacklist precision 15.8%, recall 94.7%; clone recall 60%, precision 5.4% | `docs/alert_evaluation.md` |

---

## COUNTING PROTOTYPE (F101–F120)

| ID   | Fact | Source |
|------|------|--------|
| F101 | Dataset: AI City Challenge 2021 Track 1; camera 5 example clip | FACTS prompt, counting scripts |
| F102 | Video: 1280×960, 10 fps, 60 s, 600 frames | `counting/track_clip.py` output |
| F103 | Ground truth: 96 events (M11: 37 car+1 truck; M5: 23+2; M3: 13; M4: 10; M2: 5; M10: 2; M1: 1; M7: 1; M12: 1) | `counting/evaluate_counts.py` output |
| F104 | Tracking: pretrained YOLOv8s (COCO weights, not fine-tuned plate detector), ByteTrack, conf 0.25, imgsz 960 | `counting/track_clip.py` |
| F105 | Tracking run: 342 total track IDs; 271.02 s CPU time | previous session output |
| F106 | Constants (fixed before evaluation): MIN_FRAMES_IN_ROI=10, MIN_DISPLACEMENT_PX=60, MAX_ASSIGN_SCORE=300 | `counting/count_clip.py` |
| F107 | Match tolerance: 20 frames between predicted exit frame and GT frame_id | `counting/evaluate_counts.py` |
| F108 | v1 pipeline stages: 342 all → 162 in-ROI → 117 long enough → 103 moving → 19 assigned | `counting/count_clip.py` output |
| F109 | v1 overall (all 96 GT): P 73.7%, R 14.6%, F1 24.3%; TP 14, FP 5, FN 82 | `counting/evaluate_counts.py` output |
| F110 | Calibration (frames < 300): 39 GT events; 36 matched to tracks within ±10 frames; 3 unmatched | `counting/calibrate_movements.py` output |
| F111 | Calibrated movements (v2): M2, M3, M4, M11 from track medians; M1, M5, M6, M7, M8, M9, M10, M12 kept from v1 visual | `counting/movements_cam5_v2.json` |
| F112 | v2 test split (frames ≥ 300): 57 GT events | `counting/evaluate_counts_v2.py` output |
| F113 | v1 on frames ≥ 300: P 60.0%, R 10.5%, F1 17.9%; TP 6, FP 4, FN 51 | `counting/evaluate_counts_v2.py` output |
| F114 | v2 on frames ≥ 300: P 96.6%, R 49.1%, F1 65.1%; TP 28, FP 1, FN 29 | `counting/evaluate_counts_v2.py` output |
| F115 | v2 ignoring class (frames ≥ 300): P 100.0%, R 50.9%, F1 67.4%; TP 29, FP 0, FN 28 | `counting/evaluate_counts_v2.py` output |
| F116 | Movement 11 (v2): 22 of 26 cars found (recall 84.6%) | `counting/evaluate_counts_v2.py` output |
| F117 | Movement 5 (v2): 5 of 23 found (recall 21.7%); M5 had 0 calibration events (all in second half) | `counting/evaluate_counts_v2.py` output, `counting/calibrate_movements.py` output |
| F118 | Movement 4 (v2): 0 of 3 found; lost calibrated zone (M4 calibrated to wrong cluster) | `counting/evaluate_counts_v2.py` output |
| F119 | Counting uncertainty: single clip, n=57 GT in test half; ±13 pp uncertainty (approx 95% CI) | Computed: z√(p(1-p)/n) ≈ 0.13 at p=0.5, n=57 |
| F120 | v2 revised after seeing v1 results (calibrated on same video's first half) — honest disclosure required | FACTS prompt |

---

## REAL JINAN DATA (F121–F127)

| ID   | Fact | Source |
|------|------|--------|
| F121 | Source: Yu et al. 2023 Scientific Data — city-scale vehicle trajectories from Jinan, China | FACTS prompt |
| F122 | Raw dataset: 1,184,417 trips; 963,125 vehicles; 8,908 OSM nodes; 1,651 nodes with cameras | FACTS prompt |
| F123 | No plates; no real dates (placeholder 2026-03-01) | FACTS prompt |
| F124 | After 1-in-20 sampling + deduplication: 460,145 events; 56,941 trips; 48,157 vehicles; 1,579 cameras; 2,444 duplicate rows removed | FACTS prompt |
| F125 | Kept as future work; not in dashboard (analytics default to source='sim') | FACTS prompt |
| F126 | Real-time loader available (`backend/load_data.py`) but not invoked | `backend/load_data.py` exists |
| F127 | Loader uses 1-in-20 subsampling to fit SQLite | FACTS prompt |

---

## OPEN ITEMS / KNOWN BUGS (F128–F133)

| ID   | Fact | Source |
|------|------|--------|
| F128 | Cloned-plate trajectory click: HTTP 500 status [FILL: fixed or still present] | FACTS prompt |
| F129 | Live Alerts card padding issue [FILL: resolved or still present] | FACTS prompt |
| F130 | Overspeed = 0 alerts: cause is that simulated urban speeds never exceeded 80 km/h (confirmed in eval doc) | `docs/alert_evaluation.md` |
| F131 | WRONG_WAY disabled: intersection cameras see all directions; requires one-way lane ground truth | `simulator/config.py`, `docs/alert_evaluation.md` |
| F132 | trajectories table: 0 rows (pre-computed trajectories not persisted to DB) | DB inspection |
| F133 | Counting dashboard tab: NOT built (COUNTING_TAB_BUILT = NO) | `frontend/index.html` inspection |

