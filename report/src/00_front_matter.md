<!-- FRONT MATTER -->

# FRONT PAGE

<div align="center">

# CITY-WIDE AI ENGINE FOR MULTI-CAMERA ANPR TRAJECTORY TRACKING AND URBAN TRAFFIC ANALYTICS

\
\
*A Project Report Submitted in Partial Fulfilment of the Requirements for the Award of the Degree of*

\
\
**BACHELOR OF TECHNOLOGY**\
*in*\
**COMPUTER SCIENCE AND ENGINEERING**

\
\
*by*

\
\
**[TEAM MEMBERS AND REG. NOS.]**

\
\
*Under the Guidance of*\
**[GUIDE NAME AND DESIGNATION]**

\
\
**DEPARTMENT OF COMPUTER SCIENCE AND ENGINEERING**\
**[INSTITUTION / UNIVERSITY NAME]**\
**[MONTH YEAR]**

</div>

---

# CERTIFICATE

<div align="center">

**DEPARTMENT OF COMPUTER SCIENCE AND ENGINEERING**\
**[INSTITUTION / UNIVERSITY NAME]**

\
\
### CERTIFICATE

</div>

This is to certify that the project entitled **"City-Wide AI Engine for Multi-Camera ANPR Trajectory Tracking and Urban Traffic Analytics"** is a bonafide record of the work carried out by **[TEAM MEMBERS AND REG. NOS.]** in partial fulfilment of the requirements for the award of the degree of **Bachelor of Technology in Computer Science and Engineering** from **[INSTITUTION / UNIVERSITY NAME]** during the academic year 2026–2027.

The results embodied in this report have not been submitted to any other university or institute for the award of any degree or diploma.

\
\
\
\
\
\
\
\

<table width="100%" style="border: none;">
<tr>
<td width="50%" align="left">
<b>[GUIDE NAME AND DESIGNATION]</b><br>
Project Guide<br>
Department of Computer Science and Engineering
</td>
<td width="50%" align="right">
<b>[HOD NAME]</b><br>
Head of the Department<br>
Department of Computer Science and Engineering
</td>
</tr>
</table>

\
\
\
\
**Internal Examiner** \hfill **External Examiner**

---

# ACKNOWLEDGEMENT

We express our sincere gratitude to **[INSTITUTION / UNIVERSITY NAME]** for providing the infrastructure, computing resources, and academic environment required to carry out this final-year B.Tech project.

We convey our profound gratitude and respect to our project guide, **[GUIDE NAME AND DESIGNATION]**, Department of Computer Science and Engineering, for valuable guidance, constructive critique, and constant encouragement throughout the design, implementation, and evaluation of this system.

We also express our sincere thanks to **[HOD NAME]**, Head of the Department of Computer Science and Engineering, for providing necessary administrative facilities and academic support.

We thank our project review coordinators and all faculty members of the Department of Computer Science and Engineering for their insightful feedback and constructive suggestions during project progress reviews.

Finally, we thank our parents, family members, and friends for their enduring support, understanding, and encouragement throughout the course of this work.

\
\
\
\
**[TEAM MEMBERS AND REG. NOS.]**

---

# ABSTRACT

Urban traffic surveillance networks generate millions of video frames daily across distributed road cameras. However, municipal monitoring centres struggle to convert disjoint camera observations into continuous spatial journeys, actionable congestion intelligence, and automated violation alerts without manual operator intervention.

In this work, we design and implement an end-to-end city-wide artificial intelligence engine that connects automated number-plate recognition (ANPR), multi-camera trajectory tracking, and real-time surveillance analytics. The system operates on a dual-pathway architecture. On real video sequences and held-out photographs, an Ultralytics YOLOv8s detector localises license plates with 98.3% precision, 98.1% recall, and 84.3% mAP50-95. A Compact Convolutional Transformer (CCT-s-v2) optical character recogniser, fine-tuned on real Indian plate crops, attains 95.7% character-level accuracy and 76.9% full-plate exact match accuracy. When deployed across multi-frame video clips with ByteTrack and positional confidence-weighted voting, consensus accuracy reaches 90.00% (18 of 20 test sequences), while an automated quality assurance rule flags low-confidence readings (OCR confidence or vote margin below 0.80) for human operator review. 

On a simulated road network of Bangalore (5 km radius, 40 camera nodes, 5,000 vehicles), the spatial database ingests 31,244 noisy sightings (5% miss rate, 8% confusable character error). A graph-theoretic trajectory reconstruction engine with canonical 3-partition fuzzy indexing achieves 99.95% precision, 96.35% recall, and 97.91% F1-score with 15.82 ms average query latency. A multi-rule surveillance engine detects 100% (5 of 5) of injected cloned-plate anomalies through shortest-path speed feasibility analysis (>120 km/h) and achieves 100% precision with 93.6% recall on vehicle blacklist matching. Furthermore, an AI City Challenge vehicle counting prototype demonstrates that calibrating directional ingress/egress centroids improves test movement counting F1-score from 17.9% to 65.1%. All capabilities are served through a unified FastAPI gateway and interactive web dashboard.

\
\
**Keywords:** Automated Number-Plate Recognition, Trajectory Reconstruction, Graph Routing, ByteTrack, Multi-Frame Consensus Voting, Urban Traffic Analytics, Surveillance Alerting.

---

# TABLE OF CONTENTS

- **Certificate** ................................................................................. ii
- **Acknowledgement** ............................................................................ iii
- **Abstract** .................................................................................... iv
- **List of Tables** .............................................................................. vii
- **List of Figures** ............................................................................. viii
- **List of Symbols and Abbreviations** ........................................................... ix

### 1. INTRODUCTION
- 1.1 Introduction ............................................................................. 1
- 1.2 Major Challenges ......................................................................... 2
  - 1.2.1 Real-World License Plate Optical Character Recognition ............................... 2
  - 1.2.2 Tracking and Identity Preservation Across Cameras .................................... 3
  - 1.2.3 Privacy Considerations and Operator Data Protection .................................. 4
  - 1.2.4 Absence of Labelled City-Scale ANPR Trajectory Data .................................. 4
- 1.3 Proposed Solutions and Key Contributions ................................................. 5
- 1.4 Background and Motivation ................................................................ 6
- 1.5 Overview of the Proposed System .......................................................... 8
- 1.6 Objective of the Work .................................................................... 9
- 1.7 Organization of the Report ............................................................... 10

### 2. RELATED WORK AND THEORETICAL STUDY
- 2.1 License Plate Detection and OCR Techniques ............................................... 11
- 2.2 Multi-Object and Multi-Camera Vehicle Tracking ........................................... 13
- 2.3 City-Scale Trajectory Reconstruction Datasets ............................................ 15
- 2.4 Urban Traffic Flow Analytics and Anomaly Alert Systems ................................... 16
- 2.5 Vehicle Movement Counting Benchmarks ..................................................... 18
- 2.6 Theoretical Foundations and Metric Formulations .......................................... 19
  - 2.6.1 Precision, Recall, and F1-Score ...................................................... 19
  - 2.6.2 Mean Average Precision (mAP) ......................................................... 20
  - 2.6.3 Character-Level and Full-Plate Exact Match Accuracies ................................ 21
  - 2.6.4 Wilson Score Confidence Interval Formulation ......................................... 22
  - 2.6.5 Temporal Event Matching Metric ....................................................... 23
- 2.7 Research Gap and Comparative Analysis .................................................... 24

### 3. EXPERIMENTAL STUDY
- 3.1 Requirements and Measurable Engineering Targets ......................................... 26
- 3.2 System Architecture and Execution Pipeline ............................................... 28
- 3.3 Dataset Curation, Deduplication, and Isolation ........................................... 30
- 3.4 Perception Module Design ................................................................. 33
- 3.5 City-Scale Road Simulator ................................................................ 36
- 3.6 Database Design and Persistence Layer .................................................... 38
- 3.7 City Layer: Trajectory Reconstruction and Analytics Engines .............................. 40
- 3.8 Real-Time Surveillance Alert Engine ...................................................... 42
- 3.9 Application Programming Interface (API) and Interactive Dashboard ....................... 43
- 3.10 AI City Vehicle Counting Prototype ...................................................... 45
- 3.11 Experimental Setup and Evaluation Protocol .............................................. 46
- 3.12 Automated Testing Strategy .............................................................. 47

### 4. RESULTS AND DISCUSSIONS
- 4.1 Plate Detector Quantitative Evaluation [REAL] ............................................ 48
- 4.2 Optical Character Recognition Training Progression [REAL] ................................ 50
- 4.3 End-to-End Evaluation on Held-Out Test Photographs [REAL] ................................. 51
- 4.4 Real Video Sequences and Multi-Frame Consensus Voting [REAL & SYNTHETIC] ................. 52
- 4.5 Simulated City Trajectory Reconstruction Performance [SIMULATED] .......................... 54
- 4.6 City Traffic Flow Analytics and Origin-Destination Patterns [SIMULATED] ................... 56
- 4.7 Real-Time Surveillance Alert Engine Performance [SIMULATED] ............................... 57
- 4.8 Quality Assurance REVIEW Flag Evaluation [REAL] .......................................... 58
- 4.9 AI City Vehicle Movement Counting Evaluation (v1 vs. v2) [REAL] .......................... 59
- 4.10 Requirements Traceability and Target Satisfaction Analysis .............................. 61
- 4.11 Qualitative Error Analysis of Unresolved Video Sequences ................................ 62
- 4.12 System Limitations and Threats to Validity .............................................. 63

### 5. CONCLUSIONS AND FUTURE SCOPE
- 5.1 Conclusions .............................................................................. 65
- 5.2 Summary of Engineering Limitations ....................................................... 66
- 5.3 Directions for Future Work ............................................................... 67

### APPENDICES
- Appendix 1: Installation, Setup, and Execution Guide .......................................... 69
- Appendix 2: Complete REST API Endpoint Specification ......................................... 71
- Appendix 3: Selected Core Implementation Excerpts ............................................ 74
- Appendix 4: Automated Test Suite Execution Summary ........................................... 78

### REFERENCES ................................................................................. 80
### LIST OF PUBLICATIONS ....................................................................... 82

---

# LIST OF TABLES

- Table 2.1: Comparative Analysis of Base Papers with the Proposed System ...................... 25
- Table 3.1: System Requirements and Engineering Acceptance Benchmarks ......................... 27
- Table 3.2: Computational Hardware and Software Execution Environment ......................... 28
- Table 3.3: Image and Video Datasets Utilised Across System Modules ........................... 31
- Table 3.4: Relational SQLite Schema Architecture (`data/city_anpr.db`) ........................ 39
- Table 3.5: RESTful API Endpoints and WebSocket Streaming Interface ........................... 44
- Table 3.6: Surveillance Alert Engine Rules, Parameters, and Trigger Thresholds ............... 43
- Table 3.7: Fixed Hyperparameters for the Vehicle Movement Counting Pipeline .................. 45
- Table 4.1: YOLOv8s License Plate Detector Performance on Test Split (N=184) [REAL] ........... 49
- Table 4.2: License Plate Optical Character Recognition Progression Across Regimes [REAL] ..... 50
- Table 4.3: End-to-End System Evaluation on Held-Out Indian Test Photographs (N=167) [REAL] ... 51
- Table 4.4: Video Plate Voting Performance Across Real Sequences and Synthetic Clips ......... 53
- Table 4.5: Qualitative Breakdown of Failed Plate Reads in Video Evaluation [REAL] ............ 54
- Table 4.6: Trajectory Reconstruction Engine Accuracy and Latency Benchmarks [SIMULATED] ...... 55
- Table 4.7: Surveillance Alert Engine Empirical Evaluation and False Alarm Audit [SIMULATED] ... 57
- Table 4.8: Movement Counting Performance on Test Split (frames >= 300) (v1 vs. v2) [REAL] ..... 60
- Table 4.9: Comprehensive Requirements vs. Achieved Performance Audit ......................... 61

---

# LIST OF FIGURES

- Figure 1.1: City-Wide ANPR System Architecture (Block Diagram) ................................ 8
- Figure 1.2: End-to-End System Data Flow Diagram (DFD) ........................................ 9
- Figure 3.1: Video Perception & Plate Recognition Pipeline .................................... 34
- Figure 3.2: Multi-Frame Consensus Voting and Quality Assurance Logic .......................... 35
- Figure 3.3: City-Scale ANPR Simulator Architecture & Event Generation ......................... 37
- Figure 3.4: Relational Entity-Relationship Diagram (SQLite Database Schema) .................. 40
- Figure 3.5: Cross-Camera Trajectory Reconstruction & Fuzzy Search Engine ...................... 41
- Figure 3.6: Multi-Rule Surveillance Alert Engine Evaluation Pipeline .......................... 43
- Figure 3.7: REST API and WebSocket Surveillance Streaming Sequence ............................ 44
- Figure 3.8: Unified Traffic Intelligence Dashboard Interface Layout ........................... 45
- Figure 3.9: AI City Challenge Vehicle Counting & Trajectory Assignment ....................... 46
- Figure 3.10: Schematic Coordinate Map of Camera 5 ROI and 12 Directional Movements ........... 47
- Figure 3.11: Project Repository Hierarchy and Deployment Architecture ......................... 48
- Figure 3.12: Project Implementation Methodology and Milestone Timeline ....................... 48
- Figure 4.1: License Plate Recognition (OCR) Progression Across Training Regimes [REAL] ....... 50
- Figure 4.2: YOLOv8s License Plate Detector Quantitative Evaluation [REAL] ..................... 49
- Figure 4.3: End-to-End Plate Recognition Benchmark on Held-Out Test Photos [REAL] ............. 52
- Figure 4.4: Temporal Consensus Voting Accuracy Across Real & Synthetic Sequences ............. 53
- Figure 4.5: Surveillance Alert Engine Incident Classification & Severity Breakdown [SIMULATED] 58
- Figure 4.6: Cross-Camera Trajectory Reconstruction Performance & Latency Benchmarks [SIMULATED] 55
- Figure 4.7: Vehicle Movement Counting Performance (v1 Visual vs. v2 Calibrated) [REAL] ........ 60

---

# LIST OF SYMBOLS AND ABBREVIATIONS

| Abbreviation / Symbol | Definition |
| :--- | :--- |
| **AICity** | AI City Challenge (IEEE Smart World Congress Benchmark) |
| **ANPR** | Automated Number-Plate Recognition |
| **API** | Application Programming Interface |
| **ASGI** | Asynchronous Server Gateway Interface |
| **ByteTrack** | Multi-Object Tracking by Associating Every Detection Box |
| **CCT** | Compact Convolutional Transformer |
| **CI** | Confidence Interval (Wilson Score formulation at 95% confidence level) |
| **COCO** | Common Objects in Context Benchmark |
| **CORS** | Cross-Origin Resource Sharing |
| **CPU** | Central Processing Unit |
| **CSV** | Comma-Separated Values |
| **DFD** | Data Flow Diagram |
| **dHash** | Difference Hash (Perceptual Image Hash) |
| **Dijkstra** | Dijkstra's Single-Source Shortest-Path Graph Algorithm |
| **ER** | Entity-Relationship (Database Schema) |
| **F1** | Harmonic Mean of Precision and Recall ($2 \cdot P \cdot R / (P + R)$) |
| **FastAPI** | Modern Asynchronous Web Framework for Building RESTful APIs in Python |
| **FN** | False Negative |
| **FP** | False Positive |
| **FPS** | Frames Per Second |
| **GPU** | Graphics Processing Unit |
| **GT** | Ground Truth Reference Observation |
| **HUD** | Heads-Up Display Telemetry |
| **IEEE** | Institute of Electrical and Electronics Engineers |
| **IoU** | Intersection over Union (Jaccard Index between bounding boxes) |
| **JSON** | JavaScript Object Notation |
| **KPI** | Key Performance Indicator |
| **Leaflet** | Open-Source JavaScript Library for Interactive Mobile-Friendly Maps |
| **Levenshtein** | Edit Distance Metric for String Character Insertions, Deletions, and Substitutions |
| **LOS** | Level of Service (Urban Road Traffic Condition Standard) |
| **LPRNet** | License Plate Recognition Deep Neural Network Architecture |
| **mAP** | Mean Average Precision across object detection classes |
| **mAP@50** | Mean Average Precision at an Intersection-over-Union threshold of 0.50 |
| **mAP@50-95** | Mean Average Precision averaged from IoU 0.50 to 0.95 with step size 0.05 |
| **MTMC** | Multi-Target Multi-Camera Vehicle Tracking |
| **OCR** | Optical Character Recognition |
| **OD** | Origin-Destination Traffic Matrix |
| **OMML** | Office Math Markup Language |
| **ONNX** | Open Neural Network Exchange Runtime Format |
| **OSM** | OpenStreetMap Geographic Information Database |
| **OSMnx** | Python Package for Downloading and Modeling Street Networks from OpenStreetMap |
| **P** | Precision ($TP / (TP + FP)$) |
| **P95** | 95th Percentile Query Execution Latency |
| **PK** | Primary Key (Database Constraint) |
| **R** | Recall ($TP / (TP + FN)$) |
| **Re-ID** | Vehicle Re-Identification Across Disjoint Camera Views |
| **REST** | Representational State Transfer Architectural Style |
| **REVIEW** | Low-Confidence Optical Character Recognition Operator Audit Flag |
| **ROI** | Region of Interest Polygon Boundary |
| **SQL** | Structured Query Language |
| **SQLite** | Embedded Self-Contained Serverless Relational Database Engine |
| **TC** | Trade Certificate Motor Vehicle Dealer Registration Plate |
| **TP** | True Positive |
| **Uvicorn** | Lightning-Fast ASGI Web Server Implementation for Python |
| **VOC** | Visual Object Classes (Pascal XML Dataset Annotation Standard) |
| **WebSocket** | Full-Duplex Bidirectional Persistent Network Communication Protocol |
| **Wilson** | Wilson Score Interval for Binomial Confidence Proportions |
| **YOLO** | You Only Look Once (Real-Time Object Detection Framework) |

