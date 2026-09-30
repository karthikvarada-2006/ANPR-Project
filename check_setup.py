"""Setup Verification Script for City-Wide ANPR Project.

This script tests importing every library specified in requirements.txt.
It prints "OK" if all libraries are installed and import successfully,
or lists the names of any libraries that failed to import.
"""

import sys

# Mapping of requirements.txt package names to their python import names
PACKAGES_TO_CHECK = [
    ("numpy", "numpy"),
    ("pandas", "pandas"),
    ("geopandas", "geopandas"),
    ("osmnx", "osmnx"),
    ("networkx", "networkx"),
    ("shapely", "shapely"),
    ("fastapi", "fastapi"),
    ("uvicorn", "uvicorn"),
    ("sqlalchemy", "sqlalchemy"),
    ("psycopg2-binary", "psycopg2"),
    ("geoalchemy2", "geoalchemy2"),
    ("pydantic", "pydantic"),
    ("python-dotenv", "dotenv"),
    ("tqdm", "tqdm"),
    ("matplotlib", "matplotlib"),
    ("pytest", "pytest"),
]

def main() -> int:
    print(f"Python interpreter: {sys.executable}")
    print(f"Python version: {sys.version.split()[0]}\n")
    print("Checking dependencies from requirements.txt...")

    failed = []
    passed = []

    for pkg_name, import_name in PACKAGES_TO_CHECK:
        try:
            module = __import__(import_name)
            version = getattr(module, "__version__", "installed")
            passed.append((pkg_name, import_name, version))
            print(f"  [PASS] {pkg_name} ({version})")
        except ImportError as exc:
            failed.append((pkg_name, str(exc)))
            print(f"  [FAIL] {pkg_name} - Import error: {exc}")

    print("\n" + "=" * 50)
    if not failed:
        print("OK - All dependencies verified successfully!")
        print("=" * 50)
        return 0
    else:
        print(f"FAILED: {len(failed)} package(s) could not be imported:")
        for pkg, err in failed:
            print(f"  - {pkg}: {err}")
        print("=" * 50)
        print("\nTo resolve missing packages, make sure your virtual environment is active and run:")
        print("  pip install -r requirements.txt")
        return 1

if __name__ == "__main__":
    sys.exit(main())
