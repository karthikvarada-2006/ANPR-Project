# City-Wide AI Engine for Multi-Camera ANPR Trajectory Tracking and Urban Traffic Analytics

[![Python Version](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/downloads/)
[![Architecture](https://img.shields.io/badge/Architecture-Modular%20Pipeline-green.svg)](#system-architecture)
[![License](https://img.shields.io/badge/license-MIT-lightgrey.svg)](LICENSE)

An intelligent, city-scale traffic monitoring and surveillance system that captures vehicle license plates across a distributed camera network, reconstructs full travel trajectories across urban road graphs, and provides real-time traffic flow analytics and automated incident alerts.

---

## 📖 Project Overview

Modern urban traffic management requires real-time situational awareness across dozens or hundreds of distributed cameras. This project implements an end-to-end AI pipeline:

1. **Simulates or ingests city-scale road networks and camera feeds.**
2. **Detects and reads vehicle license plates with OCR and tracking.**
3. **Reconstructs complete vehicle trajectories across multiple cameras.**
4. **Computes traffic analytics** (speeds, density, congestion bottlenecks, Origin-Destination matrices).
5. **Detects anomalies & triggers automated alerts** (speed violations, watchlist vehicles, wrong-way travel).
6. **Visualizes the live city state on an interactive web dashboard.**

---

## 🏛️ System Architecture: The 9 Modules

The project is structured into **9 distinct, modular subsystems**:

```
city-anpr/
├── data/            # Datasets, road cache, synthetic event logs
├── simulator/       # Module 1: Road network simulation + fake ANPR event generator
├── ocr/             # Module 2: License plate detection + recognition (YOLO + EasyOCR)
├── tracking/        # Module 3: Single-camera object tracking + multi-frame plate voting
├── backend/         # Modules 4-8: Spatial DB, trajectory, analytics, alerts, API
│   ├── database/    # Module 4: PostgreSQL + PostGIS spatial persistence layer
│   ├── trajectory/  # Module 5: Cross-camera graph trajectory reconstruction
│   ├── analytics/   # Module 6: Traffic flow, speed, congestion & OD matrix engine
│   ├── alerts/      # Module 7: Real-time rules engine (speeding, watchlist, anomalies)
│   └── api/         # Module 8: FastAPI REST & WebSocket streaming server
├── frontend/        # Module 9: Interactive React & Leaflet/MapLibre dashboard
├── tests/           # Unit, integration, and end-to-end tests (pytest)
└── docs/            # Architecture diagrams, specifications, and reports
```

### Module Breakdown

| Module | Directory | Description | Key Technologies |
| :--- | :--- | :--- | :--- |
| **Module 1: City Road Simulator** | `simulator/` | Fetches real OpenStreetMap street graphs and generates realistic multi-vehicle traffic with timestamped ANPR sightings. | OSMnx, NetworkX, GeoPandas |
| **Module 2: Plate Detection & OCR** | `ocr/` | Detects vehicle license plates in camera frames, crops bounding boxes, corrects perspective, and extracts plate characters. | YOLO, EasyOCR / Tesseract, OpenCV |
| **Module 3: Single-Camera Tracking & Voting** | `tracking/` | Assigns persistent tracking IDs across video frames and aggregates multi-frame OCR predictions using confidence-weighted voting. | ByteTrack / DeepSORT, Pandas |
| **Module 4: Database Layer** | `backend/` | High-performance database schemas for camera nodes, plate sightings, vehicle metadata, and trajectories. | SQLite (default) / PostgreSQL, SQLAlchemy |
| **Module 5: Trajectory Reconstruction** | `backend/trajectory/` | Reconnects sparse sightings from disjoint cameras into topologically valid vehicle paths using shortest-path graph algorithms. | NetworkX, Shapely, GeoPandas |
| **Module 6: Urban Traffic Analytics** | `backend/analytics/` | Computes average link speeds, segment density, level-of-service (LOS), congestion bottlenecks, and Origin-Destination (OD) matrices. | NumPy, Pandas, SciPy |
| **Module 7: Alerts & Anomaly Engine** | `backend/alerts/` | Evaluates real-time events against watchlists (stolen/wanted vehicles), speed limit thresholds, and irregular travel patterns. | Python, Pydantic, WebSockets |
| **Module 8: API Gateway Server** | `backend/api/` | Exposes REST endpoints for querying history, analytics, and cameras, alongside WebSockets for streaming live sightings and alerts. | FastAPI, Uvicorn, Pydantic |
| **Module 9: Interactive Dashboard** | `frontend/` | Web-based command center featuring live city map overlays, trajectory inspection, congestion heatmaps, and alert notifications. | React, Mapbox/Leaflet, Recharts |

---

## 🚀 Quick Start Guide

### 1. Prerequisites
- **Python 3.11**
- **Git**
- **Node.js** (v18+ for frontend dashboard)
- *(Database runs out-of-the-box on SQLite with zero setup; Docker/PostgreSQL is optional)*

### 2. Environment Setup (PowerShell on Windows)

```powershell
# 1. Activate the virtual environment
.\.venv\Scripts\Activate.ps1

# 2. Run simulation pipeline (Module 1)
python -m simulator.run_all

# 3. Initialize database tables & load data (Module 4)
python backend/init_db.py
python backend/load_data.py
python backend/check_db.py

# 4. Run automated test suite
pytest -v
```

### 3. Configuration
Copy the template configuration and customize as needed:
```powershell
cp .env.example .env
```

---

## 🧪 Testing

Run test suites using `pytest`:
```powershell
pytest -v
```

---

## 📜 License
This project is open-source under the MIT License.
