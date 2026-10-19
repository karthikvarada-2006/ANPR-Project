"""Entrypoint to launch the City ANPR FastAPI server with Uvicorn.

Starts server locally on http://127.0.0.1:8000.
Interactive API documentation available at:
- Swagger UI: http://127.0.0.1:8000/docs
- ReDoc:      http://127.0.0.1:8000/redoc
"""

import argparse
import sys
from pathlib import Path
import uvicorn

# Ensure project root is in sys.path
ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


def main() -> None:
    parser = argparse.ArgumentParser(description="Start the City ANPR FastAPI Backend.")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Server host IP (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Server port (default: 8000)")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload on code changes")
    args = parser.parse_args()

    print("=" * 80)
    print("STARTING CITY ANPR SURVEILLANCE & TRAFFIC INTELLIGENCE FASTAPI SERVER")
    print("=" * 80)
    print(f"  URL:         http://{args.host}:{args.port}")
    print(f"  Docs:        http://{args.host}:{args.port}/docs")
    print(f"  ReDoc:       http://{args.host}:{args.port}/redoc")
    print(f"  Live Stream: ws://{args.host}:{args.port}/ws/live?speed=200")
    print("=" * 80)

    uvicorn.run("backend.api.main:app", host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()
