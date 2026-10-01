"""Root runner for ANPR surveillance alert evaluation."""

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.evaluate_alerts import main

if __name__ == "__main__":
    sys.exit(main())
