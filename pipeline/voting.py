"""Plate Voting and Track Aggregation Module for City-ANPR Pipeline.

This module provides multi-frame consensus voting for vehicle license plate readings
collected across video tracks.

Key Principles:
1. Temporal Redundancy: When a vehicle moves past a camera, multiple frames capture its
   license plate under varying angles, distances, lighting, and motion blur.
2. Confidence Filtering: Low-confidence OCR predictions (below a configurable threshold)
   are discarded before voting.
3. Positional Consensus: If multiple readings share the same string length, each character
   position undergoes a weighted majority vote weighted by OCR confidence scores. This
   allows the pipeline to correct occasional single-character OCR errors (e.g. B vs 8).
4. Fallback String Sum: If reading lengths vary, the string with the highest summed
   confidence is chosen.
5. Vote Margin: Quantifies consensus strength (1.0 = unanimous agreement, lower = contention).
6. Event Emission: Emits an event dictionary matching `data/sim/events.csv` schema when a
   track ends or is lost for N frames.
"""

from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import cv2
import numpy as np


@dataclass
class PlateReading:
    """Individual frame OCR reading for a tracked plate.
    
    Attributes:
        frame_idx: Video frame index (0-indexed).
        timestamp: ISO timestamp string of the frame.
        crop: Cropped plate image array (BGR).
        text: Normalised alphanumeric plate text (A-Z, 0-9).
        ocr_confidence: Confidence score from OCR recognizer (0.0 to 1.0).
        detector_confidence: Confidence score from YOLO detector (0.0 to 1.0).
        box: Bounding box [x1, y1, x2, y2] in original frame coordinates.
    """
    frame_idx: int
    timestamp: str
    crop: np.ndarray
    text: str
    ocr_confidence: float
    detector_confidence: float
    box: List[float]


class PlateVoting:
    """Multi-frame temporal voting engine for license plate tracks."""

    def __init__(
        self,
        min_confidence: float = 0.35,
        min_readings_for_positional: int = 2,
        length_agreement_ratio: float = 0.5,
    ) -> None:
        """Initialize the voting engine.
        
        Args:
            min_confidence: Minimum OCR confidence threshold. Readings below this
                are discarded as untrusted unless all readings are below threshold.
            min_readings_for_positional: Minimum number of same-length readings
                required to trigger character-position weighted voting.
            length_agreement_ratio: Fraction of valid readings that must share
                the target string length to enable positional voting.
        """
        self.min_confidence = min_confidence
        self.min_readings_for_positional = min_readings_for_positional
        self.length_agreement_ratio = length_agreement_ratio

    def vote(self, readings: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Performs multi-frame voting on a list of track readings.
        
        Args:
            readings: List of reading dicts containing at least:
                'text', 'ocr_confidence', 'detector_confidence', 'crop', 'frame_idx'.
                
        Returns:
            Dict containing:
                - plate: Final consensus plate text string
                - vote_margin: Confidence margin score [0.0, 1.0]
                - ocr_confidence: Aggregated OCR confidence
                - n_frames: Total readings submitted
                - n_valid: Number of readings above confidence threshold
                - best_crop: Crop image with highest confidence
                - best_crop_idx: Index of best reading in input list
                - method: Voting strategy applied ("positional_weighted", "string_sum", or "single")
        """
        if not readings:
            return {
                "plate": "",
                "vote_margin": 0.0,
                "ocr_confidence": 0.0,
                "n_frames": 0,
                "n_valid": 0,
                "best_crop": None,
                "best_crop_idx": -1,
                "method": "none",
            }

        n_frames = len(readings)

        # 1. Filter out readings below confidence threshold
        valid_readings = [
            r for r in readings
            if r.get("ocr_confidence", 0.0) >= self.min_confidence and str(r.get("text", "")).strip()
        ]

        # If all readings were below threshold, fallback to the reading with highest confidence
        if not valid_readings:
            valid_readings = [max(readings, key=lambda r: r.get("ocr_confidence", 0.0))]

        n_valid = len(valid_readings)

        # Find best crop among valid readings (highest OCR confidence)
        best_r = max(valid_readings, key=lambda r: r.get("ocr_confidence", 0.0))
        best_crop = best_r.get("crop")
        best_crop_idx = readings.index(best_r)

        # Single reading case
        if n_valid == 1:
            return {
                "plate": str(valid_readings[0]["text"]).strip().upper(),
                "vote_margin": 1.0,
                "ocr_confidence": float(valid_readings[0].get("ocr_confidence", 0.0)),
                "n_frames": n_frames,
                "n_valid": 1,
                "best_crop": best_crop,
                "best_crop_idx": best_crop_idx,
                "method": "single",
            }

        # 2. Analyze length distribution among valid readings
        length_counts = Counter(len(str(r["text"]).strip()) for r in valid_readings)
        most_common_len, most_common_count = length_counts.most_common(1)[0]

        can_do_positional = (
            most_common_len > 0
            and most_common_count >= self.min_readings_for_positional
            and (most_common_count / n_valid) >= self.length_agreement_ratio
        )

        if can_do_positional:
            # 3A. Character-position weighted vote using OCR confidence
            same_len_readings = [
                r for r in valid_readings
                if len(str(r["text"]).strip()) == most_common_len
            ]
            voted_chars: List[str] = []
            position_margins: List[float] = []

            for pos in range(most_common_len):
                char_weights: Dict[str, float] = defaultdict(float)
                for r in same_len_readings:
                    ch = str(r["text"]).strip().upper()[pos]
                    conf = float(r.get("ocr_confidence", 1.0))
                    char_weights[ch] += conf

                # Sort candidates by accumulated confidence descending
                ranked_chars = sorted(char_weights.items(), key=lambda x: x[1], reverse=True)
                top_char, top_score = ranked_chars[0]
                voted_chars.append(top_char)

                if len(ranked_chars) > 1:
                    second_score = ranked_chars[1][1]
                    margin = (top_score - second_score) / (top_score + 1e-6)
                else:
                    margin = 1.0
                position_margins.append(float(margin))

            final_plate = "".join(voted_chars)
            avg_margin = float(np.mean(position_margins))

            # Real mean confidence of readings that agree with the voted plate
            agreeing_readings = [
                r for r in same_len_readings
                if str(r.get("text", "")).strip().upper() == final_plate
            ]
            if agreeing_readings:
                avg_conf = float(np.mean([float(r.get("ocr_confidence", 0.0)) for r in agreeing_readings]))
            else:
                avg_conf = float(np.mean([float(r.get("ocr_confidence", 0.0)) for r in same_len_readings]))

            return {
                "plate": final_plate,
                "vote_margin": round(avg_margin, 4),
                "ocr_confidence": round(avg_conf, 4),
                "n_frames": n_frames,
                "n_valid": n_valid,
                "best_crop": best_crop,
                "best_crop_idx": best_crop_idx,
                "method": "positional_weighted",
            }

        else:
            # 3B. Fallback: string with the largest summed confidence
            string_scores: Dict[str, float] = defaultdict(float)
            string_counts: Dict[str, int] = defaultdict(int)

            for r in valid_readings:
                txt = str(r["text"]).strip().upper()
                conf = float(r.get("ocr_confidence", 1.0))
                string_scores[txt] += conf
                string_counts[txt] += 1

            ranked_strings = sorted(string_scores.items(), key=lambda x: x[1], reverse=True)
            top_string, top_score = ranked_strings[0]

            if len(ranked_strings) > 1:
                second_score = ranked_strings[1][1]
                margin = (top_score - second_score) / (top_score + 1e-6)
            else:
                margin = 1.0

            # Average confidence of readings matching the chosen string
            chosen_readings = [r for r in valid_readings if str(r["text"]).strip().upper() == top_string]
            avg_conf = float(np.mean([r.get("ocr_confidence", 0.0) for r in chosen_readings]))

            return {
                "plate": top_string,
                "vote_margin": round(float(margin), 4),
                "ocr_confidence": round(avg_conf, 4),
                "n_frames": n_frames,
                "n_valid": n_valid,
                "best_crop": best_crop,
                "best_crop_idx": best_crop_idx,
                "method": "string_sum",
            }


class Track:
    """Manages multi-frame readings and state for a single vehicle track."""

    def __init__(
        self,
        track_id: int,
        camera_id: str,
        initial_reading: Dict[str, Any],
    ) -> None:
        """Initialize track.
        
        Args:
            track_id: Unique integer tracking ID assigned by ByteTrack.
            camera_id: Camera ID string (e.g. 'CAM_01').
            initial_reading: First detected plate reading dictionary.
        """
        self.track_id = track_id
        self.camera_id = camera_id
        self.readings: List[Dict[str, Any]] = [initial_reading]
        self.start_frame = int(initial_reading.get("frame_idx", 0))
        self.last_frame = self.start_frame
        self.start_time = str(initial_reading.get("timestamp", ""))
        self.last_time = self.start_time
        self.is_active = True

    def add_reading(self, reading: Dict[str, Any]) -> None:
        """Appends a new frame reading to the track history."""
        self.readings.append(reading)
        self.last_frame = int(reading.get("frame_idx", self.last_frame))
        self.last_time = str(reading.get("timestamp", self.last_time))

    def to_event(
        self,
        voter: PlateVoting,
        output_crop_dir: Path,
        source_name: str,
        event_id: int = 1,
        default_lane: int = 1,
        source: str = "video",
    ) -> Dict[str, Any]:
        """Resolves consensus plate text and formats the event dictionary.
        
        Matches schema:
            event_id, plate, camera_id, timestamp, source, speed_kmh, heading_degrees, lane,
            ocr_confidence, track_id, n_frames, vote_margin, best_crop_path
            
        Note:
            speed_kmh and heading_degrees are left empty ("") because measuring true
            ground speed and heading requires calibrated extrinsic geometry and multi-point
            camera calibration, which is not available from an uncalibrated single camera.
        """
        voted = voter.vote(self.readings)
        plate_str = voted["plate"]

        # Save best crop to disk
        best_crop_rel_path = ""
        if voted["best_crop"] is not None and isinstance(voted["best_crop"], np.ndarray):
            output_crop_dir.mkdir(parents=True, exist_ok=True)
            crop_filename = f"{source_name}_track{self.track_id}_{plate_str or 'unknown'}.png"
            crop_save_path = output_crop_dir / crop_filename
            cv2.imwrite(str(crop_save_path), voted["best_crop"])
            # Format path with forward slashes for cross-platform consistency
            best_crop_rel_path = str(crop_save_path.as_posix())

        return {
            "event_id": event_id,
            "plate": plate_str,
            "camera_id": self.camera_id,
            "timestamp": self.start_time,
            "source": source,
            # Speed and heading empty: single-camera uncalibrated
            "speed_kmh": "",
            "heading_degrees": "",
            "lane": default_lane,
            "ocr_confidence": voted["ocr_confidence"],
            "track_id": self.track_id,
            "n_frames": voted["n_frames"],
            "vote_margin": voted["vote_margin"],
            "best_crop_path": best_crop_rel_path,
        }
