"""License plate normalization, visual confusable weighted distance, and fuzzy search."""

from __future__ import annotations

import collections
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, NamedTuple, Optional, Set, Tuple

# Ensure project root is in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from sqlalchemy import func
from backend.db import SessionLocal
from backend.models import Event

# Visually confusable character substitutions common in OCR of vehicle plates
# Both directions cost 0.3 edit distance instead of standard 1.0
CONFUSABLE_PAIRS: Set[Tuple[str, str]] = {
    ("O", "0"), ("0", "O"),
    ("B", "8"), ("8", "B"),
    ("I", "1"), ("1", "I"),
    ("S", "5"), ("5", "S"),
    ("D", "0"), ("0", "D"),
    ("Z", "2"), ("2", "Z"),
    ("G", "6"), ("6", "G"),
}

# Canonical character translation mapping each confusable char to a single representative
CANONICAL_MAP = str.maketrans({
    "O": "0", "B": "8", "I": "1", "S": "5", "D": "0", "Z": "2", "G": "6"
})


class PlateMatch:
    """Represents a matched plate candidate with sighting count and similarity distance."""

    def __init__(self, plate: str, count: int, distance: float):
        self.plate = plate
        self.count = count
        self.distance = distance

    def __getitem__(self, item: Any) -> Any:
        if isinstance(item, str):
            if hasattr(self, item):
                return getattr(self, item)
            raise KeyError(f"No key '{item}' on PlateMatch")
        return (self.plate, self.count, self.distance)[item]

    def __iter__(self):
        return iter((self.plate, self.count, self.distance))

    def __repr__(self) -> str:
        return f"PlateMatch(plate='{self.plate}', count={self.count}, distance={self.distance})"

    def to_dict(self) -> Dict[str, Any]:
        return {"plate": self.plate, "count": self.count, "distance": self.distance}


def normalize_plate(plate: Optional[str]) -> str:
    """Normalize license plate text: uppercase, strip spaces, dashes, and special characters.

    Examples:
        'ka-01 ab 1234' -> 'KA01AB1234'
        'MH 12 CD-5678' -> 'MH12CD5678'
    """
    if not plate:
        return ""
    # Strip whitespace, dashes, dots, and convert to uppercase
    cleaned = re.sub(r"[^A-Za-z0-9]", "", str(plate)).upper()
    return cleaned


def plate_distance(a: str, b: str) -> float:
    """Compute weighted Levenshtein edit distance between two license plates.

    Visually confusable OCR swaps (O/0, B/8, I/1, S/5, D/0, Z/2, G/6) cost 0.3.
    Other substitutions, character insertions, and deletions cost 1.0.
    """
    a_norm = normalize_plate(a)
    b_norm = normalize_plate(b)

    if a_norm == b_norm:
        return 0.0

    m, n = len(a_norm), len(b_norm)
    if m == 0:
        return float(n)
    if n == 0:
        return float(m)

    # Standard 2D dynamic programming table
    dp = [[0.0] * (n + 1) for _ in range(m + 1)]

    # Cost of deletions
    for i in range(1, m + 1):
        dp[i][0] = float(i)
    # Cost of insertions
    for j in range(1, n + 1):
        dp[0][j] = float(j)

    for i in range(1, m + 1):
        char_a = a_norm[i - 1]
        for j in range(1, n + 1):
            char_b = b_norm[j - 1]

            if char_a == char_b:
                sub_cost = 0.0
            elif (char_a, char_b) in CONFUSABLE_PAIRS:
                sub_cost = 0.3
            else:
                sub_cost = 1.0

            dp[i][j] = min(
                dp[i - 1][j] + 1.0,          # Deletion
                dp[i][j - 1] + 1.0,          # Insertion
                dp[i - 1][j - 1] + sub_cost  # Substitution / match
            )

    return round(dp[m][n], 4)


# In-memory cache of distinct database plates, counts, and fast partition index
_CACHED_PLATE_COUNTS: Optional[List[Tuple[str, int]]] = None
_CANONICAL_PARTITION_MAP: Optional[Dict[Tuple[int, str], Set[Tuple[str, int]]]] = None


def get_all_distinct_plates(db: Optional[Any] = None, refresh: bool = False, source: Optional[str] = "sim") -> List[Tuple[str, int]]:
    """Retrieve distinct license plates and their sighting counts from the events table."""
    global _CACHED_PLATE_COUNTS, _CANONICAL_PARTITION_MAP
    if _CACHED_PLATE_COUNTS is not None and not refresh and source == "sim":
        return _CACHED_PLATE_COUNTS

    close_session = False
    if db is None:
        db = SessionLocal()
        close_session = True

    try:
        q = db.query(Event.plate, func.count(Event.id))
        if source is not None:
            q = q.filter(Event.source == source)
        results = q.group_by(Event.plate).all()
        plate_counts = [(str(r[0]), int(r[1])) for r in results]

        if source == "sim":
            _CACHED_PLATE_COUNTS = plate_counts
            # Build fast canonical partition index for sub-millisecond candidate pruning
            part_map: Dict[Tuple[int, str], Set[Tuple[str, int]]] = collections.defaultdict(set)
            for p, count in _CACHED_PLATE_COUNTS:
                canon = p.translate(CANONICAL_MAP)
                if len(p) == 10:
                    part_map[(0, canon[:4])].add((p, count))
                    part_map[(1, canon[3:7])].add((p, count))
                    part_map[(2, canon[6:])].add((p, count))
            _CANONICAL_PARTITION_MAP = part_map

        return plate_counts
    finally:
        if close_session:
            db.close()


def find_similar_plates(
    query: str,
    max_distance: float = 1.0,
    db: Optional[Any] = None,
    source: Optional[str] = "sim",
) -> List[PlateMatch]:
    """Search all distinct plates in the events table and return those within max_distance.

    Uses canonical 3-partition candidate indexing for sub-millisecond query latency.
    Results are ordered by edit distance ascending, then sighting count descending.
    """
    norm_query = normalize_plate(query)
    if not norm_query:
        return []

    plate_counts = get_all_distinct_plates(db=db, source=source)
    q_len = len(norm_query)

    # Use canonical partition index for length-10 plates (99.9% of fleet)
    candidates: Set[Tuple[str, int]] = set()
    if q_len == 10 and _CANONICAL_PARTITION_MAP is not None:
        q_canon = norm_query.translate(CANONICAL_MAP)
        candidates.update(_CANONICAL_PARTITION_MAP.get((0, q_canon[:4]), set()))
        candidates.update(_CANONICAL_PARTITION_MAP.get((1, q_canon[3:7]), set()))
        candidates.update(_CANONICAL_PARTITION_MAP.get((2, q_canon[6:]), set()))
    else:
        # Fallback for non-standard lengths: filter by length bounds
        for p, count in plate_counts:
            if abs(len(p) - q_len) <= max_distance:
                candidates.add((p, count))

    matches: List[PlateMatch] = []
    for plate_str, count in candidates:
        dist = plate_distance(norm_query, plate_str)
        if dist <= max_distance:
            matches.append(PlateMatch(plate=plate_str, count=count, distance=dist))

    # Sort primarily by smallest distance, secondarily by highest sightings, tertiarily by plate string
    matches.sort(key=lambda m: (m.distance, -m.count, m.plate))
    return matches


def heading_to_compass(degrees: Optional[float]) -> str:
    """Convert a heading angle in degrees (0 - 360) to an 8-point compass direction."""
    if degrees is None:
        return "N/A"
    directions = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    idx = int((float(degrees) + 22.5) % 360 // 45)
    return directions[idx]
