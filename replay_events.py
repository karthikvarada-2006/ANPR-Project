"""Root runner for ANPR event replayer."""

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.replay_events import main

if __name__ == "__main__":
    sys.exit(main())
