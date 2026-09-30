# Test Suite (`tests/`)

This directory contains automated unit, integration, and performance tests for all modules in the project.

## 📂 Test Organization

```
tests/
├── conftest.py              # Pytest shared fixtures (mock data, DB sessions, road graphs)
├── test_simulator.py        # Tests for road network download and event generation
├── test_ocr.py              # Tests for plate detection, OCR parsing, and regex validation
├── test_tracking.py         # Tests for Kalman filter, ByteTrack association, and plate voting
├── test_trajectory.py       # Tests for shortest path routing and multi-camera path matching
├── test_analytics.py        # Tests for speed, density, and OD matrix calculations
├── test_alerts.py           # Tests for watchlist rules and speed violation alerts
└── test_api.py              # Tests for FastAPI endpoints and WebSocket message streaming
```

## 🧪 Running Tests

Execute the test suite using `pytest`:

```powershell
# Run all tests
pytest -v

# Run tests with code coverage report
pytest --cov=backend --cov=simulator --cov=ocr --cov=tracking
```
