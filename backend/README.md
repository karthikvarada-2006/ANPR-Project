# Backend Subsystems (`backend/`)

The **Backend** houses the core analytical brain, spatial data storage, path reconstruction algorithms, real-time alert engine, and public REST/WebSocket APIs (covering Modules 4 through 8).

## 📂 Submodule Architecture

```
backend/
├── database/     # Module 4: Database models, schemas, PostGIS spatial queries
├── trajectory/   # Module 5: Multi-camera path reconstruction & road-graph mapping
├── analytics/    # Module 6: Traffic flow, segment speeds, bottlenecks & OD matrix
├── alerts/       # Module 7: Rule engine, watchlist matching & anomaly detector
└── api/          # Module 8: FastAPI server, routers, dependencies & WebSockets
```

### Module 4: Spatial Database & Storage (`backend/database/`)
- Relational and spatial data layer powered by **PostgreSQL** and **PostGIS**.
- Uses **SQLAlchemy ORM** and **GeoAlchemy2** to store camera locations (Points), vehicle sightings, and reconstructed trajectories (LineStrings).
- Manages high-throughput ingestion of ANPR camera sighting streams.

### Module 5: Multi-Camera Trajectory Reconstruction (`backend/trajectory/`)
- Solves the cross-camera vehicle re-identification and tracking problem.
- Takes sequential sightings of plate $P$ at cameras $C_1, C_2, \dots, C_n$.
- Matches sightings against the city road graph using shortest-path (Dijkstra / A*) algorithms and travel-time feasibility checks.
- Generates continuous, timestamped spatial trajectory geometries.

### Module 6: Urban Traffic Analytics (`backend/analytics/`)
- Computes macroscopic and microscopic traffic metrics:
  - Average travel time and speed per road corridor.
  - Road segment traffic density and Level of Service (LOS A–F).
  - Identification of congestion hotspots and bottlenecks.
  - City-wide Origin-Destination (OD) flow matrices.

### Module 7: Alerts & Anomaly Engine (`backend/alerts/`)
- Evaluates real-time events against critical triggers:
  - **Watchlist Matching**: Stolen vehicles, expired permits, or vehicles of interest.
  - **Speeding Violations**: Section-control speed calculation between successive cameras.
  - **Route Anomalies**: U-turns, wrong-way travel, or unexpected detours.
- Dispatches alert payloads immediately via WebSockets to the frontend dashboard.

### Module 8: Unified API Server (`backend/api/`)
- High-performance asynchronous API built on **FastAPI** and **Uvicorn**.
- Provides REST endpoints for historical queries, stats, and camera configurations.
- Houses WebSocket endpoints for real-time live map streaming and instant alerts.
