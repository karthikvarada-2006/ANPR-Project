"""Module 5: Multi-Camera Trajectory Reconstruction Engine."""

import importlib.util
from pathlib import Path

# Re-export legacy reconstructor class if needed
try:
    from backend.trajectory.reconstructor import (
        TrajectoryReconstructor,
        TRIP_INACTIVITY_THRESHOLD_SECONDS,
    )
except ImportError:
    pass

# Load trajectory functions from backend/trajectory.py
_traj_file = Path(__file__).resolve().parent.parent / "trajectory.py"
if _traj_file.exists():
    _spec = importlib.util.spec_from_file_location("backend.trajectory_file", str(_traj_file))
    if _spec and _spec.loader:
        _mod = importlib.util.module_from_spec(_spec)
        _spec.loader.exec_module(_mod)
        for _attr in dir(_mod):
            if not _attr.startswith("__"):
                globals()[_attr] = getattr(_mod, _attr)
