# Module 1: Road Network Simulator (`simulator/`)

The **Simulator** module generates synthetic city-scale traffic and simulated ANPR camera sighting events without requiring physical hardware or high-bandwidth video streams.

## 🎯 Key Objectives

1. **City Road Network Ingestion**: Uses `OSMnx` to download and parse drivable road networks from OpenStreetMap (OSM) for any target city (e.g., Bengaluru, London, New York).
2. **Camera Network Placement**: Automatically places virtual ANPR cameras at key graph intersections, arterial roads, and highway choke points.
3. **Traffic Simulation**:
   - Generates realistic vehicle trips with random or gravity-modeled Origin-Destination (OD) pairs.
   - Calculates routes across the street graph using `NetworkX` shortest path algorithms.
   - Computes vehicle movement over time steps using speed limits and road segment lengths.
4. **ANPR Event Emission**:
   - Generates timestamped camera passage logs: `(timestamp, camera_id, plate_number, vehicle_type, speed, confidence)`.
   - Injects realistic noise (intermittent missed detections, character substitutions, optical occlusions).
   - Writes events to CSV/Parquet or streams them directly to the backend database/Kafka/FastAPI endpoints.

## 📁 Module Contents

- `network.py`: Downloads, caches, and simplifies OSMnx street graphs.
- `cameras.py`: Defines camera placement algorithms and camera metadata schemas.
- `traffic.py`: Simulates vehicle movements and Origin-Destination trip generation.
- `generator.py`: Orchestrates the simulation and emits synthetic ANPR events.
