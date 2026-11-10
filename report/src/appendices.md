# APPENDICES

## APPENDIX 1: INSTALLATION AND EXECUTION GUIDE

This appendix provides the complete, step-by-step instructions for establishing the computational development environment, installing software dependencies, initializing the database, and running the system services.

### A1.1 Hardware and Environment Prerequisites
- **Operating System:** Microsoft Windows 10/11 (64-bit), Ubuntu Linux 22.04 LTS, or macOS 13+.
- **Python Version:** Python 3.11.9 (64-bit).
- **GPU Acceleration (Optional):** NVIDIA GPU with CUDA 11.8+ for deep learning model training. CPU execution is supported for inference.

### A1.2 Virtual Environment Setup and Dependency Installation
Clone the project repository and create an isolated Python virtual environment:

```bash
# Clone the repository
git clone https://github.com/project-repo/city-anpr.git
cd city-anpr

# Create virtual environment
python -m venv .venv

# Activate virtual environment (Windows PowerShell)
.venv\Scripts\Activate.ps1

# Activate virtual environment (Linux / macOS)
source .venv/bin/activate

# Upgrade pip and install core requirements
pip install --upgrade pip
pip install -r requirements.txt
```

### A1.3 Database Initialization and Read-Only Verification
The spatial repository resides at `data/city_anpr.db`. To safeguard against accidental overwrites during analytical evaluation, the database can be connected in read-only mode using SQLite URI parameters:

```python
import sqlite3

# Connect to the SQLite database in strict read-only mode
conn = sqlite3.connect("file:data/city_anpr.db?mode=ro", uri=True)
cursor = conn.cursor()

# Verify event counts
cursor.execute("SELECT source, COUNT(*) FROM events GROUP BY source;")
print(cursor.fetchall())
# Expected: [('sim', 31244), ('video', 20)]
conn.close()
```

### A1.4 Launching the REST API and Streaming Gateway
To launch the FastAPI backend server with Uvicorn:

```bash
# Start FastAPI server on port 8000
python -m uvicorn backend.api.main:app --host 0.0.0.0 --port 8000 --reload
```

Once the server initializes, the services become accessible at:
- **Interactive API Documentation (Swagger UI):** `http://localhost:8000/docs`
- **Municipal Command Dashboard:** Open `frontend/index.html` in any modern web browser (Google Chrome, Mozilla Firefox, or Microsoft Edge).
- **Live Surveillance WebSocket Stream:** `ws://localhost:8000/ws/live`

### A1.5 Executing the Automated Test Suite
To verify system integrity and run all 101 automated unit and integration tests:

```bash
# Run pytest across the entire test suite
pytest -v tests/
```

---

## APPENDIX 2: COMPLETE API ENDPOINT SPECIFICATIONS

This appendix provides detailed schema definitions and parameter payloads for the 13 primary RESTful and WebSocket endpoints exposed by `backend/api/main.py`.

### A2.1 Health Check and Spatial Camera Registry
- `GET /api/health`
  - **Description:** Verifies API server health and database connectivity.
  - **Response Payload:** `{"status": "ok", "database": "connected"}`
- `GET /api/cameras`
  - **Description:** Retrieves all 41 registered surveillance cameras.
  - **Response Payload:** Array of camera objects:
    ```json
    [
      {
        "camera_id": "CAM_001",
        "name": "MG Road / Brigade Rd Junction",
        "lat": 12.9752,
        "lon": 77.6068,
        "node_id": 182749102
      }
    ]
    ```

### A2.2 Trajectory Reconstruction and Evidence Export
- `GET /api/trajectory/{plate}?fuzzy=true`
  - **Path Parameter:** `plate` (string) — vehicle license plate query string.
  - **Query Parameter:** `fuzzy` (boolean, default: true) — enables 3-partition fuzzy string index.
  - **Response Payload:**
    ```json
    {
      "query_plate": "TN11YD7305",
      "matched_plates": ["TN11YD7305", "TN11YD730S"],
      "total_sightings": 17,
      "trips": [
        {
          "trip_id": 1,
          "start_time": "2026-10-01T08:14:22",
          "end_time": "2026-10-01T08:42:15",
          "camera_sequence": ["CAM_012", "CAM_008", "CAM_003"],
          "total_distance_m": 4210.5,
          "mean_speed_kmh": 32.4,
          "route_geojson": { "type": "LineString", "coordinates": [...] }
        }
      ]
    }
    ```
- `GET /api/trajectory/{plate}/export`
  - **Path Parameter:** `plate` (string).
  - **Description:** Generates a downloadable CSV containing chronological sightings, sanitizing all cells using `escape_csv_cell()` to prevent spreadsheet formula injection.

### A2.3 Traffic Analytics and Macroscopic Flow
- `GET /api/analytics/overview`
  - **Description:** Returns executive dashboard metrics (total vehicles: 4,296; active cameras: 41; peak hour volume: 4,277 at 09:00; total alerts: 44).
- `GET /api/analytics/hourly-volume`
  - **Description:** Returns 24-hour array of hourly sighting counts for trend plotting.
- `GET /api/analytics/busiest-cameras?limit=10`
  - **Description:** Returns top $N$ cameras ranked by total vehicle observations.
- `GET /api/analytics/heatmap`
  - **Description:** Returns geographic points with spatial intensity weights for Leaflet heatmap rendering.

### A2.4 Surveillance Watchlists and Real-Time Streaming
- `GET /api/alerts?limit=50&severity=HIGH`
  - **Description:** Retrieves persistent security alert records filtered by severity or alert type.
- `POST /api/blacklist`
  - **Request Body:** `{"plate": "KA01AB9999", "reason": "Suspected Stolen Vehicle"}`
  - **Description:** Registers a new target vehicle on the active surveillance watchlist.
- `POST /api/plates/read`
  - **Request Body:** Multipart image file.
  - **Response Payload:** Detected bounding boxes, cropped image base64, transcribed string, confidence, and `REVIEW` quality flag.
- `WS /ws/live?multiplier=5.0`
  - **Description:** Full-duplex WebSocket stream replaying historical sightings and pushing real-time alert notifications.

---

## APPENDIX 3: CORE CODE EXCERPTS

This appendix provides verbatim code excerpts of the three foundational algorithmic implementations developed in this project.

### A3.1 Positional Confidence-Weighted Multi-Frame Voting (`pipeline/voting.py`)
```python
def vote_plate_sequence(track_frames: list[dict]) -> tuple[str, float, float, str]:
    """
    Computes character-position weighted consensus across consecutive video frames.
    Returns: (voted_plate, consensus_confidence, consensus_margin, status)
    """
    if not track_frames:
        return "", 0.0, 0.0, "REVIEW"

    # Single-frame shortcut
    if len(track_frames) == 1:
        f = track_frames[0]
        plate = f["plate"].strip()
        conf = float(f.get("confidence", 0.0))
        status = "VERIFIED" if conf >= 0.80 else "REVIEW"
        return plate, conf, 1.0, status

    # Determine maximum plate length
    max_len = max(len(f["plate"].strip()) for f in track_frames)
    total_weight = sum(float(f.get("confidence", 0.5)) for f in track_frames)

    voted_chars = []
    slot_confidences = []
    slot_margins = []

    for pos in range(max_len):
        char_weights = {}
        for f in track_frames:
            plate = f["plate"].strip()
            conf = float(f.get("confidence", 0.5))
            char = plate[pos] if pos < len(plate) else ""
            char_weights[char] = char_weights.get(char, 0.0) + conf

        # Rank winning characters
        sorted_chars = sorted(char_weights.items(), key=lambda x: x[1], reverse=True)
        winner_char, winner_wt = sorted_chars[0]
        second_wt = sorted_chars[1][1] if len(sorted_chars) > 1 else 0.0

        if winner_char != "":
            voted_chars.append(winner_char)
            slot_confidences.append(winner_wt / total_weight)
            slot_margins.append((winner_wt - second_wt) / total_weight)

    voted_plate = "".join(voted_chars)
    mean_conf = sum(slot_confidences) / len(slot_confidences) if slot_confidences else 0.0
    mean_margin = sum(slot_margins) / len(slot_margins) if slot_margins else 0.0

    # Automated Quality Assurance Gating
    status = "VERIFIED" if (mean_conf >= 0.80 and mean_margin >= 0.80) else "REVIEW"
    return voted_plate, mean_conf, mean_margin, status
```

### A3.2 Canonical 3-Partition Fuzzy Matcher (`backend/trajectory.py`)
```python
def find_fuzzy_candidates(query_plate: str, cursor, max_distance: float = 1.0) -> list[str]:
    """
    Retrieves matching plates using 3-partition pigeonhole indexing
    and discounted Levenshtein distance for optically confusable characters.
    """
    clean_query = query_plate.replace(" ", "").upper()
    n = len(clean_query)
    if n < 6:
        return [clean_query]

    # Partition string into 3 disjoint substrings
    p1 = clean_query[: n // 3]
    p2 = clean_query[n // 3 : 2 * n // 3]
    p3 = clean_query[2 * n // 3 :]

    # Indexed candidate retrieval
    query = """
        SELECT DISTINCT plate FROM events
        WHERE plate LIKE ? OR plate LIKE ? OR plate LIKE ?
    """
    cursor.execute(query, (f"{p1}%", f"%{p2}%", f"%{p3}"))
    raw_candidates = [row[0] for row in cursor.fetchall()]

    # Confusable substitution map with discounted penalty
    confusables = {
        ('O', '0'), ('0', 'O'), ('B', '8'), ('8', 'B'),
        ('I', '1'), ('1', 'I'), ('S', '5'), ('5', 'S'),
        ('D', '0'), ('Z', '2'), ('G', '6')
    }

    verified_matches = []
    for cand in raw_candidates:
        dist = weighted_levenshtein(clean_query, cand, confusables, discount=0.3)
        if dist <= max_distance:
            verified_matches.append(cand)

    return verified_matches
```

### A3.3 Speed-Feasibility Cloned-Plate Validation (`backend/alerts/engine.py`)
```python
def check_cloned_plate(event: dict, history: list[dict], road_graph) -> dict | None:
    """
    Evaluates physical transit feasibility between consecutive camera sightings.
    Triggers HIGH severity alert if implied shortest-path road speed > 120 km/h.
    """
    plate = event["plate"]
    current_cam = event["camera_id"]
    current_time = event["timestamp"]

    for prev in reversed(history):
        if prev["plate"] == plate and prev["camera_id"] != current_cam:
            dt_seconds = (current_time - prev["timestamp"]).total_seconds()
            if 0 < dt_seconds < 3600:  # Within 1 hour
                # Retrieve Dijkstra shortest-path road distance in metres
                road_dist = road_graph.get_shortest_distance(prev["camera_id"], current_cam)
                implied_speed_kmh = (road_dist / dt_seconds) * 3.6

                if implied_speed_kmh > 120.0:  # Physically impossible urban velocity
                    return {
                        "alert_type": "CLONED_PLATE",
                        "severity": "HIGH",
                        "plate": plate,
                        "camera_id": current_cam,
                        "timestamp": current_time,
                        "details": {
                            "prev_camera": prev["camera_id"],
                            "implied_speed_kmh": round(implied_speed_kmh, 1),
                            "shortest_road_dist_m": round(road_dist, 1),
                            "time_delta_seconds": round(dt_seconds, 1)
                        }
                    }
    return None
```

---

## APPENDIX 4: AUTOMATED TEST SUITE SUMMARY

This appendix provides a summary of the 101 unit and integration test cases executed via `pytest`, all of which passed with 100% success (`101 passed`).

Table A4.1: Automated Test Suite Structure and Execution Coverage
| Test Module | Primary Verification Scope | Test Cases | Execution Status |
| :--- | :--- | :--- | :--- |
| `tests/test_detector.py` | Bounding box tensors, NMS threshold $\tau_{\text{det}} = 0.25$, 5% padding logic | 12 tests | 12 Passed |
| `tests/test_ocr.py` | CCT-s-v2 ONNX character dictionary mapping, tensor shapes, CPU inference latency | 14 tests | 14 Passed |
| `tests/test_voting.py` | Multi-frame consensus weighting, single-frame passthrough, `REVIEW` gating | 16 tests | 16 Passed |
| `tests/test_database.py` | SQLite schema integrity, foreign keys, index coverage, read-only mode (`mode=ro`)| 15 tests | 15 Passed |
| `tests/test_trajectory.py` | 3-partition fuzzy matching, 30-min trip splitting, Dijkstra route assembly | 18 tests | 18 Passed |
| `tests/test_alerts.py` | Blacklist matching, clone speed validation, 10-min de-duplication window | 12 tests | 12 Passed |
| `tests/test_api.py` | REST endpoints, WebSocket streaming, formula injection sanitization | 8 tests | 8 Passed |
| `tests/test_counting.py` | AI City ROI point test, frame duration $\ge 10$, displacement $\ge 60\text{ px}$ | 6 tests | 6 Passed |
| **Total Test Suite** | **System-Wide End-to-End Verification Across All Tiers** | **101 tests** | **101 Passed [F8]** |

