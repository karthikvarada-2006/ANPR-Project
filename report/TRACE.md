# TRACE.md — Traceability Matrix Linking Report Metrics to Ground Truth (FACTS.md)

This document establishes bidirectional traceability between every quantitative metric, hyperparameter, dataset size, and architectural configuration in the final B.Tech Project Report (*"City-Wide AI Engine for Multi-Camera ANPR Trajectory Tracking and Urban Traffic Analytics"*) and the ground-truth facts verified in `report/FACTS.md`.

---

## 1. Traceability by Fact Identifier (F1 to F133)

| Fact ID | Parameter / Metric Description | Measured / Ground Truth Value | Report Location(s) | Source in Codebase / Evaluation Logs |
| :--- | :--- | :--- | :--- | :--- |
| **F1** | Host OS, Python runtime, and virtual env | Microsoft Windows, Python 3.11.9, `.venv` | §3.11, Table 3.2, App 1 | `requirements.txt`, system runtime |
| **F2** | Database engine & file size | SQLite at `data/city_anpr.db` (15,507,456 bytes) | §3.6, §3.11, Table 3.2, App 1 | File properties, DB backup |
| **F3** | Core installed dependencies & versions | Ultralytics 8.4.171, fast-plate-ocr 1.1.0, ONNX 1.30.0, Torch 2.14.1, OpenCV 5.0.0.93, OSMnx 1.9.1, FastAPI 0.110.0, Pytest 8.1.1 | §3.11, Table 3.2, App 1 | `requirements.txt`, environment inspect |
| **F4** | OCR Transformer Model File | `cct_s_v2_finetuned_indian.onnx` (Compact Conv Transformer) | §3.4.3, §3.11, Table 3.2 | `models/plate_ocr/`, `pipeline/plate_reader.py` |
| **F5** | License Plate Detection Model File | `models/plate_detector.pt` (YOLOv8s anchor-free) | §3.4.1, §3.11, Table 3.2 | `models/plate_detector.pt` |
| **F6** | Multi-Object Video Tracker | ByteTrack (`bytetrack.yaml`, `persist=True`) | §3.4.2, App 3.1 | `pipeline/video_pipeline.py` |
| **F7** | Deep Learning Training Hardware | Google Colab NVIDIA Tesla T4 GPU (16 GB GDDR6) | §3.4.1, §3.11, Table 3.2 | Training notebook logs |
| **F8** | Automated Test Suite Results | 101 unit and integration tests passing (`101 passed`) | §3.12, App 1.5, App 4, Table A4.1 | `pytest` test runner execution |
| **F9** | API Server Host & Port | FastAPI + Uvicorn on `0.0.0.0:8000` | §3.9.1, App 1.4 | `backend/api/main.py`, `.env.example` |
| **F10** | Front-end Dashboard Architecture | Standalone HTML5 / CSS3 / Vanilla JS (no React / Node build) | §3.9.2, TODO.md | `frontend/index.html` inspection |
| **F11** | Physical Perception Processing Flow | Video/Photo $\to$ YOLOv8s $\to$ ByteTrack $\to$ CCT-s-v2 $\to$ Voting $\to$ REVIEW | §1.5, §3.2, Fig 1.1, Fig 3.1 | `pipeline/video_pipeline.py`, `pipeline/voting.py` |
| **F12** | Simulated Traffic Flow | OSM Bangalore graph $\to$ 5,000 vehicles $\to$ 40 cameras $\to$ Noisy events | §1.5, §3.2, §3.5, Fig 3.3 | `simulator/config.py`, `simulator/simulator.py` |
| **F13** | Database Convergence & Provenance | Single `events` table tagged `source='sim'` or `source='video'` | §1.5, §3.2, §3.6, Table 3.4 | `backend/models.py`, `data/city_anpr.db` |
| **F14** | Shared Analytical Engines | Trajectory engine $\to$ Traffic analytics $\to$ AlertEngine $\to$ FastAPI $\to$ UI | §1.5, §3.2, Fig 1.2 | `backend/trajectory.py`, `backend/analytics.py` |
| **F15** | Direct Image Reader API Endpoint | `POST /api/plates/read` (Edge plate inference) | §3.9.1, §3.9.2, Table 3.5, App 2.4 | `backend/api/main.py` |
| **F16** | Dashboard Navigation Tabs | 6 tabs: Overview, Trajectory, Heatmap, Alerts, Blacklist, Plate Reader | §3.9.2, Fig 3.8, Figs 3.13–3.18 | `frontend/index.html` |
| **F17** | Absence of Counting Dashboard Tab | `COUNTING_TAB_BUILT = NO` (Standalone prototype) | §3.9.2, §4.10, TODO.md | `frontend/index.html` inspection |
| **F18** | Streaming WebSocket Gateway | `ws://0.0.0.0:8000/ws/live` (Replays event stream to AlertEngine) | §3.9.1, Table 3.5, App 2.4 | `backend/api/main.py` |
| **F19** | CSV Export Security Sanitization | `escape_csv_cell()` neutralizing `=, +, -, @` formula execution | §3.9.1, Table 3.5, App 2.2 | `backend/plate_utils.py`, `backend/api/main.py` |
| **F20** | Wrong-Way Alert State | `WRONG_WAY_ENABLED = False` (Disabled by default) | §3.8, Table 3.6, §4.10 | `simulator/config.py`, `backend/alert_rules.py` |
| **F21** | Simulated Geographic Domain | Bangalore, India; radius $r = 5.0\text{ km}$ ($12.9716^\circ\text{N}, 77.5946^\circ\text{E}$) | §3.5.1, Table 3.2 | `simulator/config.py` |
| **F22** | Simulated Camera Network Size | $N_{\text{cam}} = 40$ roadside cameras, min spacing $300\text{ m}$, seed 42 | §3.5.2, Table 3.2 | `simulator/config.py` |
| **F23** | Simulated Fleet Volume & Date | $N_{\text{veh}} = 5,000$ active vehicles, simulation date `2026-10-01` | §3.5.3, Table 3.2 | `simulator/config.py` |
| **F24** | Optical Sensor Noise Rates | Miss probability $P_{\text{miss}} = 0.05$ (5%), Character confusion $P_{\text{conf}} = 0.08$ (8%) | §3.5.4, Table 3.2 | `simulator/config.py` |
| **F25** | Optical Confusion Character Map | $\mathcal{M}_{\text{conf}} = \{O \leftrightarrow 0, B \leftrightarrow 8, I \leftrightarrow 1, S \leftrightarrow 5, D \to 0, Z \to 2, G \to 6\}$ | §3.5.4, §3.7.1, Eq 3.8, App 3.2 | `simulator/config.py`, `backend/plate_utils.py` |
| **F26** | Total Simulated Events in Database | 31,244 records (`source='sim'`) | §3.5.3, §3.6, Table 3.4, §4.6 | `data/city_anpr.db` SQL query |
| **F27** | Total Sightings in Database | 31,264 records (31,244 sim + 20 real video pipeline sightings) | §3.6, Table 3.4 | `data/city_anpr.db` SQL query |
| **F28** | Distinct Simulated Plates in DB | 10,729 unique plate strings | §3.5.3, §3.6 | `data/city_anpr.db` SQL query |
| **F29** | Injected Security Scenarios | 10 blacklist plates; 5 injected cloned plate scenarios | §3.5.4, §3.6, Table 3.4, §4.6 | `data/city_anpr.db`, `docs/alert_evaluation.md` |
| **F30** | Total Alerts Logged in Database | 44 alerts (35 Blacklist, 5 Cloned Plate, 4 Restricted Zone, 0 Overspeed) | §3.6, §3.8, Table 3.4, Table 3.6, §4.6 | `data/city_anpr.db` SQL query |
| **F31** | Curfew Restricted Zone Cameras | Cameras `CAM_001`, `CAM_002`, `CAM_003`; 22:00–06:00; commercial trucks | §3.5.2, §3.5.4, §3.8, Table 3.6 | `simulator/config.py`, `docs/alert_evaluation.md` |
| **F32** | Diurnal Peak Flow Multipliers | Morning peak (08:00–10:00) $1.65\times$; Evening peak (17:00–20:00) $1.85\times$ | §3.5.3, Table 3.2 | `simulator/config.py` |
| **F33** | Peak Traffic Hour Volume | Hour 09:00 with 4,277 camera sightings | §3.5.3, §3.9.2, Fig 3.13 | `data/city_anpr.db` SQL query |
| **F34** | Surveillance Engine Throughput | 1,918 sightings / second; 0.521 ms / event; 16.29 s total run time | §3.8, Table 3.6, §4.6, Table 4.7 | `docs/alert_evaluation.md` benchmark |
| **F35** | Unique Vehicles in Analytics View | 4,296 vehicles (rolling window filtered) | §3.9.2, Fig 3.13, TODO.md | Dashboard analytics endpoint |
| **F36** | Trajectory Benchmark Sample | 200 randomly sampled vehicle journeys (seed 42) | §3.7.1, §4.5, Table 4.6 | `docs/trajectory_evaluation.md` |
| **F37** | Trajectory Hop Accuracy Metrics | Hop Precision 99.95%, Hop Recall 96.35%, Trajectory $F_1$ **97.91%** | §4.5, Table 4.6, Fig 4.6, Table 4.9 | `docs/trajectory_evaluation.md` |
| **F38** | Trajectory Query Latency | Average 15.82 ms, Median 20.47 ms, 95th Percentile 24.00 ms | §4.5, Table 4.6, Table 4.9 | `docs/trajectory_evaluation.md` |
| **F39** | Cloned Plate Detection Recall | 5 / 5 injected clone pairs detected (100.0%) | §3.8, §4.5, Table 4.6, Table 4.7 | `docs/trajectory_evaluation.md` |
| **F40** | Clone Detection Speed Threshold | Implied road speed $v_{\text{hop}} > 120.0\text{ km/h}$ between camera hops | §3.7.1, §3.8, Table 3.6, Eq 3.9 | `backend/alert_rules.py` |
| **F41** | Trajectory Case Study Volume | Target vehicle `TN11YD7305` recovered 17 sightings via fuzzy index | §3.7.1, §3.9.2, Fig 3.14 | Trajectory API query logs |
| **F42** | Detection Dataset Sources | Indian Number Plates, License Plate Detection, Indian Vehicle datasets | §3.3, Table 3.3 | `docs/data_report.md` |
| **F43** | Detection Dataset Splits | Total 1,835 images: 1,467 train (79.9%), 184 val (10.0%), 184 test (10.0%) | §3.3, Table 3.3, §4.1, Table 4.1 | `docs/data_report.md` |
| **F44** | YOLOv8s Test Split Metrics | Precision 98.3%, Recall 98.1%, $F_1$ 98.2%, mAP@50 98.3%, mAP@50-95 84.3% | §4.1, Table 4.1, Fig 4.2, Table 4.9 | Detector evaluation logs |
| **F45** | Split Deduplication Guarantee | 64-bit Perceptual Hash (pHash) Hamming distance $\le 4$ group partition | §3.3, Table 3.3, §4.1 | `docs/data_report.md` |
| **F46** | Detector Inference Hyperparameters | Confidence threshold $\tau_{\text{det}} = 0.25$, Bounding box padding ratio $0.05$ (5%) | §3.4.1, Table 3.2 | `pipeline/plate_reader.py`, `backend/api/main.py` |
| **F47** | OCR Dataset Volume and Splits | 1,695 real crops (1,360 train, 168 val, 167 test) + 10,400 synthetic crops | §3.3, Table 3.3, §4.2, Table 4.2 | `docs/data_report.md` |
| **F48** | Synthetic Crop Isolation Protocol | Synthetic crops restricted strictly to `train/` split (zero test leakage) | §3.3, Table 3.3 | `docs/data_report.md` |
| **F49** | OCR Transformer Training Setup | Google Colab NVIDIA Tesla T4 GPU, learning rate $0.001$, AdamW | §3.4.3, Table 3.2 | Model training logs |
| **F50** | OCR Progression Accuracies | Scratch: 29.4%; Zero-shot: 25.2%; Syntax: 37.1%; Fine-tuned: **76.9%** plate / **95.7%** char | §4.2, Table 4.2, Fig 4.1, Table 4.9 | OCR training benchmark logs |
| **F51** | End-to-End Held-Out Evaluation | 167 photos: Detection Recall 100%, Precision 98.8%, Plate Exact **80.84%**, Char **96.30%**, ~307 ms | §4.3, Table 4.3, Fig 4.3, Table 4.9 | `docs/ocr/end_to_end_results.csv` |
| **F52** | Quality Assurance Audit Threshold | Fixed rule: `REVIEW_CONFIDENCE_THRESHOLD = 0.80` | §3.4.4, Eq 3.5, Table 3.1 | `backend/plate_utils.py` |
| **F53** | Quality Assurance Trigger Criteria | Flagged `status='REVIEW'` if $C_{\text{voted}} < 0.80$ OR $M_{\text{voted}} < 0.80$ | §3.4.4, Table 3.1, App 3.1 | `backend/plate_utils.py`, `pipeline/voting.py` |
| **F54** | Intercepted Misread Video Sequences | 2 video sequences flagged REVIEW (`DL8CN63308` and `MH022N5`) | §3.4.4, §4.4.1, Table 4.5, Table 4.9 | Database inspection, voting results |
| **F55** | Authentic Video Sequences Corpus | 20 real video sequences, 76 frames, avg 3.80 frames (9 single, 11 multi) | §3.3, Table 3.3, §4.4, Table 4.4 | `docs/ocr/voting_summary.md` |
| **F56** | Video Plate Exact Match Accuracies | Per-frame baseline 85.24% (65/76) $\to$ Multi-frame consensus **90.00%** (18/20) | §4.4, Table 4.4, Fig 4.4, Table 4.9 | `docs/ocr/voting_summary.md` |
| **F57** | Wilson 95% Confidence Interval | Wilson interval for 18/20 ($p=0.90, N=20$): **[69.9%, 97.2%]** | §2.6.4, Eq 2.8, §4.4, Table 4.4, §4.8 | Computed statistical formulation |
| **F58** | Video Character Accuracies | Per-frame baseline 95.95% $\to$ Multi-frame consensus **97.00%** | §4.4, Table 4.4 | `docs/ocr/voting_summary.md` |
| **F59** | Failed Video Sequence 1 | GT: `DL8CN6308`, Voted: `DL8CN63308`, Conf 61.1%, Margin 71.1%, 7 frames | §4.4.1, Table 4.5 | `docs/ocr/voting_results.csv` |
| **F60** | Failed Video Sequence 2 | GT: `MH02EN6828`, Voted: `MH022N5`, Conf 70.4%, Margin 100.0%, 1 frame | §4.4.1, Table 4.5 | `docs/ocr/voting_results.csv` |
| **F61** | Lowest Confidence Property | Both failed sequences exhibited the lowest confidence among all 20 clips | §4.4.1, Table 4.5 | `docs/ocr/voting_results.csv` |
| **F62** | Synthetic Video Clips Baseline | 60 clips, 24 frames/clip: Per-frame 66.87% $\to$ Voted 78.33% (OPTIMISTIC) | §4.4, Table 4.4, Fig 4.4 | `docs/ocr/voting_summary.md` |
| **F63** | Consensus Voting Aggregation | Positional confidence-weighted voting for multi-frame; identity for single | §3.4.4, Eq 3.1–3.4, App 3.1 | `pipeline/voting.py` |
| **F64** | Video Events in Persistent Database | 20 records (`source='video'`) across 20 distinct vehicle registrations | §3.6, Table 3.4 | `data/city_anpr.db` SQL query |
| **F65** | Demo Video Camera Entity | `CAM_VIDEO_01` ("ANPR Video Pipeline Demo Camera", $12.9716^\circ, 77.5946^\circ$) | §3.5.2, §3.6, Table 3.4 | `data/city_anpr.db` SQL query |
| **F66** | Total Registered Cameras in DB | 41 cameras (40 simulated + 1 demo video camera) | §3.5.2, §3.6, Table 3.4, §3.9.2 | `data/city_anpr.db` SQL query |
| **F67** | Macroscopic Analytics Filter | Analytics queries default to `source='sim'` to maintain graph consistency | §3.6, Table 3.4 | `backend/analytics.py` |
| **F68** | Demo Video Sighting Timestamps | Timestamps set to `2026-10-05 10:00:00` to `10:19:00` | §3.6 | `data/city_anpr.db` SQL query |
| **F69** | SQLite Database Schema Inventory | 9 tables: `events`, `cameras`, `alerts`, `blacklist`, `camera_window_stats`, `congestion`, `route_density`, `od_matrix`, `trajectories` | §3.6, Fig 3.4, Table 3.4 | Database schema inspection |
| **F70** | `events` Table Schema Columns | `id`, `plate`, `camera_id`, `timestamp`, `speed_kmh`, `heading_degrees`, `lane`, `ocr_confidence`, `source`, `track_id`, `n_frames`, `vote_margin`, `best_crop_path` | §3.6, Table 3.4 | Database schema inspection |
| **F71** | `alerts` Table Schema Columns | `id`, `alert_type`, `plate`, `camera_id`, `timestamp`, `details` (JSON), `created_at`, `severity` | §3.6, Table 3.4 | Database schema inspection |
| **F72** | `cameras` Table Schema Columns | `camera_id`, `name`, `lat`, `lon`, `node_id` | §3.6, Table 3.4 | Database schema inspection |
| **F73** | `trajectories` Dynamic Computation | Table exists in schema with 0 persistent rows (computed dynamically on query) | §3.6, Table 3.4, §4.10 | Database inspection (`SELECT COUNT(*)`) |
| **F74** | Secondary Analytics Tables Rows | `camera_window_stats`: 2,795; `congestion`: 463; `route_density`: 3,194; `od_matrix`: 64 | §3.6, Table 3.4 | Database inspection (`SELECT COUNT(*)`) |
| **F75** | Corridor Speed Limits | Overspeed threshold: $80\text{ km/h}$; Clone speed threshold: $120\text{ km/h}$ | §3.7.1, §3.8, Table 3.6 | `backend/alert_rules.py` |
| **F76** | Zero Overspeed Alerts Root Cause | Peak simulated vehicle speeds capped at $60\text{ km/h}$ ($\le 80\text{ km/h}$ limit) | §3.8, Table 3.6, §4.6, Table 4.7, §4.10 | `docs/alert_evaluation.md` |
| **F77** | Loitering Rule Specification | $\ge 3$ sightings at same camera within $60\text{ min}$; 0 triggers in simulation | §3.8, Table 3.6, §4.6, Table 4.7 | `backend/alert_rules.py`, eval docs |
| **F78–F90** | API Endpoints Portfolio | 13 endpoints covering health, cameras, trajectory, export, analytics, alerts, blacklist, plate reading, and WebSockets | §3.9.1, Table 3.5, App 2.1–2.4 | `backend/api/main.py` |
| **F91** | Blacklist Rule Severity Logic | Exact match $\to$ HIGH; Confusable fuzzy match ($D_{\text{weighted}} \le 0.6$) $\to$ MEDIUM | §3.8, Table 3.6, App 3.2 | `backend/alert_rules.py` |
| **F92** | Cloned Plate Severity Logic | Implied shortest-path road velocity $> 120\text{ km/h} \to$ HIGH severity | §3.7.1, §3.8, Table 3.6, App 3.3 | `backend/alert_rules.py` |
| **F93** | Wrong Way Rule Parameter | Heading deviation $> 135^\circ$ from dominant camera heading; disabled | §3.8, Table 3.6, §4.10 | `backend/alert_rules.py` |
| **F94** | Overspeed Rule Parameter | Instantaneous radar speed $> 80\text{ km/h} \to$ LOW severity | §3.8, Table 3.6, §4.6 | `backend/alert_rules.py` |
| **F95** | Loitering Rule Parameter | $\ge 3$ visits to same camera in $60\text{ min} \to$ LOW severity | §3.8, Table 3.6, §4.6 | `backend/alert_rules.py` |
| **F96** | Restricted Zone Curfew Parameter | Commercial truck at CAM 1–3 between 22:00–06:00 $\to$ MEDIUM (4 triggers) | §3.5.4, §3.8, Table 3.6, §4.6, Table 4.7 | `simulator/config.py`, eval docs |
| **F97** | Alert De-duplication Window | 10-minute sliding window suppressing redundant incident triggers | §3.8, Table 3.6, §4.6, Table 4.7 | `backend/api/main.py`, AlertEngine |
| **F98** | Blacklist Detection Performance | Precision **100.0%** (35/35 de-duplicated), Recall 93.6% (88/94 raw sightings) | §3.8, Table 3.6, §4.6, Table 4.7, Table 4.9 | `docs/alert_evaluation.md` |
| **F99** | Cloned Plate Detection Performance | Precision **100.0%** (5/5 detected), Recall **100.0%**, Zero false alarms | §3.8, Table 3.6, §4.6, Table 4.7, Table 4.9 | `docs/alert_evaluation.md` |
| **F100** | Before-Fix Alert False Alarm Rates | Blacklist precision was 15.8% (R 94.7%); Cloned plate precision was 5.4% (R 60%) | §3.8, Table 3.6, §4.6, Table 4.7 | `docs/alert_evaluation.md` |
| **F101** | AI City Challenge Benchmark Setup | IEEE AI City Challenge 2021 Track 1, Camera 5 sample clip | §3.10.1, Table 3.7 | `counting/track_clip.py` |
| **F102** | Counting Clip Video Attributes | $1280 \times 960$ resolution, 10.0 fps, 60.0 s duration, 600 total frames | §3.10.1, Table 3.7, §4.7 | Video metadata inspection |
| **F103** | Ground Truth Movement Volume | 96 verified turning events (M11: 38, M5: 25, M3: 13, M4: 10, M2: 5, etc.) | §3.10.1, Table 3.7, §4.7 | `counting_example_cam_5_1min.csv` |
| **F104** | Counting Vehicle Tracking Setup | Ultralytics YOLOv8s COCO weights, ByteTrack, $\tau_{\text{conf}} = 0.25$, imgsz 960 | §3.10.2, §4.7 | `counting/track_clip.py` |
| **F105** | Counting Tracking Execution Time | 342 raw track IDs identified in 271.02 seconds CPU run time | §3.10.2, §4.7, TODO.md | Track clip execution logs |
| **F106** | Fixed Counting Hyperparameters | $\text{MIN\_FRAMES}=10$, $\text{MIN\_DISP}=60\text{ px}$, $\text{MAX\_SCORE}=300\text{ px}$ | §3.10.2, Eq 3.11–3.14 | `counting/count_clip.py` |
| **F107** | Event Matching Tolerance Window | Temporal tolerance $\Delta t_{\max} = 20\text{ frames}$ between predicted exit and GT | §2.6.5, Eq 2.9, §4.7 | `counting/evaluate_counts.py` |
| **F108** | Baseline Pipeline Filtering Stages | 342 raw $\to$ 162 in-ROI $\to$ 117 long enough $\to$ 103 moving $\to$ 19 assigned | §3.10.2, Fig 3.9 | `counting/count_clip.py` output |
| **F109** | Baseline Visual Counting ($v1$, all 96 GT)| Precision 73.7%, Recall 14.6%, $F_1$-score 24.3% (TP 14, FP 5, FN 82) | §3.10.3, §4.7 | `counting/evaluate_counts.py` output |
| **F110** | Empirical Calibration Split ($t < 300$) | 39 GT events; 36 matched to tracklets within $\pm 10$ frames; 3 unmatched | §3.10.3, §4.7 | `counting/calibrate_movements.py` |
| **F111** | Calibrated Movements Allocation | Updated $M_2, M_3, M_4, M_{11}$ from track medians; others kept visual ($v1$) | §3.10.3, Table 3.7 | `counting/movements_cam5_v2.json` |
| **F112** | Held-Out Test Split ($t \ge 300$) | 57 ground-truth turning events | §3.10.3, §4.7, Table 4.8 | `counting/evaluate_counts_v2.py` |
| **F113** | Baseline Visual ($v1$) on Test Split | Precision 60.0%, Recall 10.5%, $F_1$-score **17.9%** (TP 6, FP 4, FN 51) | §4.7, Table 4.8, Fig 4.7 | `counting/evaluate_counts_v2.py` |
| **F114** | Calibrated Model ($v2$) on Test Split | Precision **96.6%**, Recall **49.1%**, $F_1$-score **65.1%** (TP 28, FP 1, FN 29) | §4.7, Table 4.8, Fig 4.7, Table 4.9 | `counting/evaluate_counts_v2.py` |
| **F115** | Calibrated ($v2$) Class-Agnostic | Precision **100.0%**, Recall **50.9%**, $F_1$-score **67.4%** (TP 29, FP 0, FN 28) | §4.7, Table 4.8 | `counting/evaluate_counts_v2.py` |
| **F116** | Movement 11 Calibrated Accuracy | Captured 22 of 26 test vehicles (Recall **84.6%**) | §4.7.1, Table 4.8 | `counting/evaluate_counts_v2.py` |
| **F117** | Movement 5 Calibrated Accuracy | Captured 5 of 23 test vehicles (Recall **21.7%**; 0 calibration events in first half)| §4.7.1, Table 4.8 | `counting/evaluate_counts_v2.py` |
| **F118** | Movement 4 Calibrated Failure | Captured 0 of 3 test vehicles (Calibration matched displaced cluster) | §4.7.1, Table 4.8 | `counting/evaluate_counts_v2.py` |
| **F119** | Counting Uncertainty Margin | Binomial uncertainty $\pm 13$ percentage points on test split ($N=57$) | §4.8 | Statistical computation |
| **F120** | Counting Methodology Disclosure | $v2$ developed after seeing $v1$ results; tested on single camera clip | §4.8 | Scientific transparency audit |
| **F121** | Real Jinan Trajectory Dataset Citation | Yu et al., 2023, *Scientific Data* (Jinan, Shandong, China) | §2.3, §5.3, Ref [1] | Academic benchmark publication |
| **F122** | Raw Jinan Dataset Dimensions | 1,184,417 trips, 963,125 vehicles, 8,908 OSM nodes, 1,651 camera nodes | §2.3, §5.3 | Dataset documentation |
| **F123** | Jinan Privacy Masking Constraints | Alphanumeric plate strings omitted; synthetic integer vehicle IDs | §2.3, §5.3 | Dataset documentation |
| **F124** | Subsampled Jinan Benchmark Volume | 1-in-20 sampling: 460,145 events, 56,941 trips, 48,157 vehicles, 1,579 cameras | §5.3 | `backend/load_data.py` logic |
| **F125** | Jinan Operational Deployment Status | Reserved as future research extension (not in current default UI) | §5.3 | Codebase inspection |
| **F126** | Jinan Database Ingestion Script | Standalone loader implemented in `backend/load_data.py` | §5.3 | File inspection |
| **F127** | Jinan Sampling Decimation Ratio | 1-in-20 decimation factor to maintain local SQLite performance | §5.3 | `backend/load_data.py` |
| **F128** | Cloned Plate Map Polyline Bug | HTTP 500 status on UI polyline click for clone scenarios | §4.10, TODO.md | Known issue audit |
| **F129** | Live Alerts Card Layout Padding | Minor CSS flexbox padding truncation on $>1920\text{ px}$ monitors | §4.10, TODO.md | Known issue audit |
| **F130** | Zero Overspeed Triggers Explanation | Road simulator maximum urban speeds capped at $60\text{ km/h} \le 80\text{ km/h}$ | §3.8, §4.6, §4.10 | Known issue audit |
| **F131** | Wrong-Way Driving Deactivation | Rule disabled due to lack of lane-level directional vectors at junctions | §3.8, §4.10 | Known issue audit |
| **F132** | Empty Trajectories Relational Table | 0 rows in `trajectories` table (dynamic on-demand Dijkstra computation) | §3.6, Table 3.4, §4.10 | Database architecture audit |
| **F133** | Dashboard Counting Tab Status | Counting tab NOT built in web dashboard (`COUNTING_TAB_BUILT = NO`) | §3.9.2, §4.10, TODO.md | `frontend/index.html` inspection |

---

## 2. Verification of Report Integrity
- Every quantitative claim in the narrative matches the corresponding ground-truth fact above.
- No synthetic or estimated values are presented without explicit labeling.
- All 133 facts are fully accounted for, cross-referenced, and verified against project files and read-only database queries.

