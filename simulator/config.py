"""Configuration parameters for the City-Wide ANPR Simulator."""

from pathlib import Path
import datetime

# Base paths
ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
DATA_SIM_DIR = DATA_DIR / "sim"
DOCS_DIR = ROOT_DIR / "docs"

# Output artifact paths
GRAPH_PATH = DATA_SIM_DIR / "city.graphml"
CAMERAS_PATH = DATA_SIM_DIR / "cameras.csv"
GROUND_TRUTH_PATH = DATA_SIM_DIR / "ground_truth_events.csv"
EVENTS_PATH = DATA_SIM_DIR / "events.csv"
BLACKLIST_PATH = DATA_SIM_DIR / "blacklist.csv"
ANOMALIES_PATH = DATA_SIM_DIR / "anomalies.csv"
MAP_PATH = DOCS_DIR / "city_map.png"

# ==============================================================================
# Simulation Core Settings
# ==============================================================================
CITY_NAME = "Bangalore, India"       # Target city for OpenStreetMap download
NETWORK_RADIUS_METERS = 5000         # 5 km radius around center
NUM_CAMERAS = 40                     # Number of ANPR camera nodes
MIN_CAMERA_DISTANCE_METERS = 300.0   # Cameras spaced apart by >= 300m
NUM_VEHICLES = 5000                  # Total vehicles in simulation fleet
SIM_DATE = datetime.date(2026, 10, 1) # Simulation target calendar date
RANDOM_SEED = 42                     # Deterministic random seed for reproducibility

# ==============================================================================
# ANPR / OCR Error Model
# ==============================================================================
OCR_MISS_RATE = 0.05                 # 5% probability of camera failing to record event
OCR_CHAR_ERROR_RATE = 0.08           # 8% probability of character confusion per plate

# Visually confusable character substitutions for license plates
CONFUSION_MAP = {
    "O": "0", "0": "O",
    "B": "8", "8": "B",
    "I": "1", "1": "I",
    "S": "5", "5": "S",
    "D": "0", "Z": "2",
    "2": "Z", "G": "6",
}

# ==============================================================================
# Vehicle Types and Speed Models
# ==============================================================================
VEHICLE_TYPES = {
    "car": 0.45,
    "bike": 0.35,
    "bus": 0.10,
    "truck": 0.10,
}

# Free-flow speeds by OpenStreetMap highway classification (km/h)
FREE_FLOW_SPEEDS_KMH = {
    "motorway": 70.0,
    "motorway_link": 50.0,
    "trunk": 55.0,
    "trunk_link": 40.0,
    "primary": 45.0,
    "primary_link": 35.0,
    "secondary": 35.0,
    "secondary_link": 28.0,
    "tertiary": 28.0,
    "tertiary_link": 24.0,
    "residential": 22.0,
    "living_street": 15.0,
    "unclassified": 25.0,
}
DEFAULT_SPEED_KMH = 30.0

# Congestion slowdown multipliers (travel time multiplier = 1 / speed multiplier)
PEAK_HOURS = {
    "morning": {"start": 8, "end": 10, "congestion_factor": 1.65},
    "evening": {"start": 17, "end": 20, "congestion_factor": 1.85},
}
OFF_PEAK_CONGESTION_FACTOR = 1.05

# ==============================================================================
# Surveillance & Alert Rules Settings
# ==============================================================================
WRONG_WAY_ENABLED = False            # Disabled by default; junction cameras see all directions, needs one-way ground truth
RESTRICTED_CAMERAS = ["CAM_001", "CAM_002", "CAM_003"]
RESTRICTED_TIME_WINDOW = ("22:00", "06:00")
RESTRICTED_VEHICLE_TYPES = ["truck"]


