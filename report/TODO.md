# TODO.md — Outstanding Items Before Report Submission

Items marked **[FILL]** must be resolved by the team before Stage 6 finalises the report.
Items marked **[VERIFY]** are reference citations to be checked online.
Items marked **[MISMATCH]** are discrepancies between the FACTS prompt and measured values.
Items marked **[SCREENSHOT]** are dashboard screenshots still to be taken.

---

## [FILL] — Required from the Team

| # | Location in Report | What is Needed |
|---|---|---|
| FILL-1 | Ch 1 / Front page | Team members' names and registration numbers — `[TEAM MEMBERS AND REG. NOS.]` |
| FILL-2 | Certificate page | Guide's name and designation — `[GUIDE NAME AND DESIGNATION]` |
| FILL-3 | Certificate page | Head of Department name — `[HOD NAME]` |
| FILL-4 | Certificate page | Month and year of submission — `[MONTH YEAR]` |
| FILL-5 | §3 OCR progression table | Character-level accuracy for: from-scratch, zero-shot, and zero-shot+syntax-rules stages (FACTS prompt gives plate-level only: 29.4%, 25.2%, 37.1%) |
| FILL-6 | §4 Open bugs | Confirm whether the HTTP 500 on cloned-plate trajectory click is fixed or still present (F128) |
| FILL-7 | §4 Open bugs | Confirm whether the Live Alerts card padding issue is fixed or still present (F129) |
| FILL-8 | §4 Counting tab | Update `COUNTING_TAB_BUILT` flag if the counting dashboard tab is added before submission (F133) |
| FILL-9 | §3 reference files | Place `Main_Project_Guidelines_and_Report_2026-27.docx` in `report/reference/` |
| FILL-10 | §3 reference files | Place `MiniPro.pdf` in `report/reference/` |
| FILL-11 | List of Publications | Provide any publications, or confirm "Nil" |
| FILL-12 | §2 Related Work Table 2.1 | Full citation details for base paper on "Improved YOLOv5s + LPRNet plate recognition, Scientific Reports, 2025" — authors, title, volume, pages |
| FILL-13 | §2 Related Work Table 2.1 | Full citation for Tran et al. 2022 multi-camera vehicle tracking — venue, volume, pages |

---

## [MISMATCH] — Discrepancies to Resolve

| # | FACTS Prompt Says | Measured/Found | Action |
|---|---|---|---|
| MISMATCH-1 | README says frontend is "React & Leaflet/MapLibre" | `frontend/index.html` is plain HTML/JS; no React or Node build | Report the actual tech (HTML/JS) in the report. Note in Ch 3. |
| MISMATCH-2 | "Unique vehicles shown 4,296" | DB shows 10,729 distinct sim plates | 4,296 likely refers to a windowed analytics view. Report both: 10,729 total distinct plates in DB; 4,296 shown in dashboard analytics window. Verify by querying analytics endpoint. |
| MISMATCH-3 | "about 15 ms per query" for trajectory | eval doc: avg 15.82 ms, median 20.47 ms | Report both values from the evaluation doc (F38). |
| MISMATCH-4 | "219.27 s CPU" for tracking run (FACTS prompt) | counting session measured 271.02 s | Report 271.02 s (measured); note FACTS prompt figure may be from a different machine/run. |
| MISMATCH-5 | FACTS prompt states 95% CI "about 70 to 97%" for 18/20 | Wilson interval for 18/20, n=20: 68.4%–98.8% | Use the computed Wilson CI (68% to 99%); state method in the text. |

---

## [VERIFY] — References to Check Online

| # | Reference (as given) | What to Verify |
|---|---|---|
| REF-1 | Yu et al., 2023, Scientific Data, city-scale vehicle trajectories | Verify exact title, volume, pages, DOI |
| REF-2 | Improved YOLOv5s + LPRNet plate recognition, Scientific Reports, 2025 | Verify authors, exact title, volume, pages, DOI |
| REF-3 | Tran et al., 2022, multi-camera vehicle tracking | Verify authors, title, venue, pages |
| REF-4 | Y. Zhang et al., "ByteTrack: Multi-object tracking by associating every detection box," ECCV 2022 | Verify exact title, proceedings, pages |
| REF-5 | J. Redmon et al., "You only look once: Unified, real-time object detection," CVPR 2016 | Verify page numbers |
| REF-6 | S. Zherzdev and A. Gruzdev, "LPRNet: License plate recognition via deep neural networks," arXiv:1806.10447, 2018 | Verify arXiv ID and date |
| REF-7 | G. Boeing, OSMnx, Computers, Environment and Urban Systems, vol. 65, pp. 126-139, 2017 | Verify DOI and year |
| REF-8 | M. Naphade et al., AI City Challenge 2021 | Verify exact title, venue (CVPR Workshop), year |
| REF-9 | Ultralytics YOLOv8 — software citation | Verify URL, version (8.4.171 confirmed installed), year |
| REF-10 | fast-plate-ocr — software citation | Verify PyPI URL, version (1.1.0 confirmed) |
| REF-11 | FastAPI — software citation | Verify URL and version |
| REF-12 | Leaflet — software citation | Verify URL and version |
| REF-13 | Chart.js — software citation | Verify URL and version |

---

## [SCREENSHOT] — Dashboard Screenshots to Capture

The API cannot be started safely from the sandbox. The following screenshots must be
taken manually by running `python -m uvicorn backend.api.main:app` and opening
`http://127.0.0.1:8000` in a browser. Blur any real plate numbers before inserting.

| # | Tab / View | Screenshot Name |
|---|---|---|
| SS-1 | Overview tab (KPIs, map, congestion table) | `report/assets/ss_overview.png` |
| SS-2 | Trajectory Search tab (search result for TN11YD7305) | `report/assets/ss_trajectory.png` |
| SS-3 | Traffic Heatmap tab | `report/assets/ss_heatmap.png` |
| SS-4 | Live Alerts tab (showing the 44 simulated alerts) | `report/assets/ss_alerts.png` |
| SS-5 | Blacklist tab (showing the 10 blacklisted plates) | `report/assets/ss_blacklist.png` |
| SS-6 | Plate Reader tab (after uploading a sample image) — blur plate | `report/assets/ss_plate_reader.png` |

Until screenshots are taken, the report will contain clearly labelled placeholder boxes:
> "SCREENSHOT TO BE INSERTED: [tab name]"

---

## [DIAGRAM] — Diagrams to Generate in Stage 2

All diagrams generated from code; no AI-generated images. List here for tracking.

| # | Diagram | Script / Method | Output |
|---|---|---|---|
| D-1 | System block diagram | matplotlib | `report/assets/fig_system_block.png` |
| D-2 | Data flow diagram | graphviz or matplotlib | `report/assets/fig_data_flow.png` |
| D-3 | Perception pipeline flowchart | matplotlib | `report/assets/fig_perception_pipeline.png` |
| D-4 | Plate voting & REVIEW flowchart | matplotlib | `report/assets/fig_voting_review.png` |
| D-5 | Simulator flowchart | matplotlib | `report/assets/fig_simulator.png` |
| D-6 | ER diagram (real SQLite schema) | Read from DB; draw with matplotlib | `report/assets/fig_er_diagram.png` |
| D-7 | Trajectory engine flowchart (with fuzzy matcher) | matplotlib | `report/assets/fig_trajectory_engine.png` |
| D-8 | Alert engine flowchart | matplotlib | `report/assets/fig_alert_engine.png` |
| D-9 | API + WebSocket sequence diagram | matplotlib | `report/assets/fig_api_sequence.png` |
| D-10 | Dashboard tab layout schematic | matplotlib | `report/assets/fig_dashboard_layout.png` |
| D-11 | Counting pipeline flowchart | matplotlib | `report/assets/fig_counting_pipeline.png` |
| D-12 | Cam_5 ROI + 12 movement arrows (from coordinates) | matplotlib | `report/assets/fig_cam5_roi_movements.png` |
| D-13 | Project folder & deployment diagram | matplotlib | `report/assets/fig_folder_deployment.png` |
| D-14 | Methodology & timeline diagram | matplotlib flowchart LR | `report/assets/fig_methodology_timeline.png` |
| D-15 | OCR progression bar chart | matplotlib | `report/assets/fig_ocr_progression.png` |
| D-16 | Detector metrics bar chart | matplotlib | `report/assets/fig_detector_metrics.png` |
| D-17 | End-to-end results chart | matplotlib | `report/assets/fig_end_to_end.png` |
| D-18 | Per-frame vs. voted accuracy chart | matplotlib | `report/assets/fig_voting_accuracy.png` |
| D-19 | Alert breakdown chart | matplotlib | `report/assets/fig_alert_breakdown.png` |
| D-20 | Trajectory metrics chart | matplotlib | `report/assets/fig_trajectory_metrics.png` |
| D-21 | Counting v1 vs. v2 comparison chart | matplotlib | `report/assets/fig_counting_v1_v2.png` |

