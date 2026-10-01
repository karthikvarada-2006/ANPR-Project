"""Module 6: Urban Traffic Analytics & OD Matrix Engine."""

import importlib.util
from pathlib import Path

# Load analytics functions from backend/analytics.py
_analytics_file = Path(__file__).resolve().parent.parent / "analytics.py"
if _analytics_file.exists():
    _spec = importlib.util.spec_from_file_location("backend.analytics_file", str(_analytics_file))
    if _spec and _spec.loader:
        _mod = importlib.util.module_from_spec(_spec)
        _spec.loader.exec_module(_mod)
        for _attr in dir(_mod):
            if not _attr.startswith("__"):
                globals()[_attr] = getattr(_mod, _attr)
