"""Plate Reader Module for City-ANPR Pipeline.

This module provides the PlateReader class, which connects:
1. Ultralytics YOLOv8 License Plate Detector (models/plate_detector.pt)
2. fast-plate-ocr Compact Convolutional Transformer Recognizer (models/plate_ocr/)

Pipeline Flow:
1. Detects vehicle license plates in the input image with YOLOv8.
2. Expands bounding boxes by 5% padding on each side (matching training pipeline).
3. Crops the padded plate region and passes it to fast-plate-ocr.
4. Returns bounding box, detector confidence, cropped image, normalised plate text,
   and OCR confidence derived from character-level prediction probabilities.
"""

import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import cv2
import numpy as np
from PIL import Image

# Library imports verified against installed package versions
from ultralytics import YOLO
from fast_plate_ocr import LicensePlateRecognizer

logger = logging.getLogger(__name__)

# Named constants for default OCR model and configuration
OCR_ONNX_PATH = Path("models/plate_ocr/cct_s_v2_finetuned_indian.onnx")
OCR_CONFIG_PATH = Path("models/plate_ocr/cct_s_v2_global_plate_config.yaml")


class PlateReader:
    """End-to-end License Plate Reader combining YOLO detection and fast-plate-ocr recognition.
    
    Attributes:
        detector_path: Path to the YOLO .pt model weights.
        ocr_dir: Path to directory containing the ONNX model and YAML config.
        conf_thresh: Minimum detector confidence threshold for filtering plate proposals.
        device: Target execution device ('auto', 'cpu', or 'cuda').
    """

    def __init__(
        self,
        detector_path: Union[str, Path] = "models/plate_detector.pt",
        ocr_dir: Union[str, Path] = "models/plate_ocr",
        conf_thresh: float = 0.25,
        device: str = "auto",
        padding_ratio: float = 0.05,
    ) -> None:
        """Initialize detector and OCR recognizer.
        
        Args:
            detector_path: Path to YOLO plate detector checkpoint (plate_detector.pt).
            ocr_dir: Path to directory containing ONNX plate recognizer and YAML config.
            conf_thresh: Confidence threshold for YOLO bounding box detections.
            device: Inference device ('auto', 'cpu', or 'cuda').
            padding_ratio: Fractional bounding box padding (0.05 = 5%, matching training).
        """
        self.detector_path = Path(detector_path)
        self.ocr_dir = Path(ocr_dir)
        self.conf_thresh = conf_thresh
        self.device = device
        self.padding_ratio = padding_ratio

        # 1. Load YOLO plate detector
        if not self.detector_path.exists():
            raise FileNotFoundError(
                f"YOLO detector checkpoint not found at: {self.detector_path.resolve()}\n"
                f"Please verify models/plate_detector.pt exists."
            )
        logger.info("Loading YOLO detector from %s...", self.detector_path)
        self.detector = YOLO(str(self.detector_path))

        # 2. Discover custom ONNX model and config in models/plate_ocr/
        if not self.ocr_dir.exists() or not self.ocr_dir.is_dir():
            raise FileNotFoundError(
                f"OCR model directory not found at: {self.ocr_dir.resolve()}\n"
                f"Expected directory with .onnx model and .yaml plate config."
            )

        self.onnx_path, self.plate_config_path = self._locate_ocr_assets(self.ocr_dir)
        logger.info(
            "Loading custom fast-plate-ocr model:\n  ONNX:   %s\n  Config: %s",
            self.onnx_path,
            self.plate_config_path,
        )

        # 3. Initialize fast-plate-ocr recognizer using the supported custom model API
        self.recognizer = LicensePlateRecognizer(
            onnx_model_path=str(self.onnx_path),
            plate_config_path=str(self.plate_config_path),
            device=self.device,
        )
        logger.info("PlateReader initialized successfully on device: %s", self.recognizer.providers)

    @staticmethod
    def _locate_ocr_assets(ocr_dir: Path) -> Tuple[Path, Path]:
        """Locates the ONNX weights file and YAML plate config in the given directory.
        
        Prefers fine-tuned / best weights if multiple models exist.
        """
        all_onnx = sorted(list(ocr_dir.glob("*.onnx")))
        if not all_onnx:
            raise FileNotFoundError(f"No .onnx file found in {ocr_dir.resolve()}!")

        # Prioritize fine-tuned model names over base models
        chosen_onnx = all_onnx[0]
        for p in all_onnx:
            stem = p.stem.lower()
            if "finetun" in stem or "best" in stem:
                chosen_onnx = p
                break

        all_yaml = sorted(list(ocr_dir.glob("*.yaml")) + list(ocr_dir.glob("*.yml")))
        if not all_yaml:
            raise FileNotFoundError(f"No .yaml config file found in {ocr_dir.resolve()}!")

        # Prioritize plate config YAML
        chosen_yaml = all_yaml[0]
        for y in all_yaml:
            if "plate_config" in y.name.lower():
                chosen_yaml = y
                break

        return chosen_onnx, chosen_yaml

    @staticmethod
    def normalize_text(raw_text: str) -> str:
        """Normalises plate text: converts to uppercase and keeps only A-Z and 0-9.
        
        Args:
            raw_text: Raw string decoded from OCR or ground truth.
            
        Returns:
            Normalised alphanumeric string with all whitespace and special characters stripped.
        """
        if not raw_text:
            return ""
        # Convert to uppercase and retain only A-Z, 0-9
        return re.sub(r"[^A-Z0-9]", "", str(raw_text).upper()).strip()

    def read_image(
        self,
        image: Union[str, Path, np.ndarray, Image.Image],
        is_bgr: bool = True,
    ) -> List[Dict[str, Any]]:
        """Detects plates and recognizes their text in a single image.
        
        Args:
            image: Input image as a file path (str or Path), numpy array (BGR or RGB),
                   or PIL Image.
            is_bgr: Whether numpy array input is in BGR format (True, default for cv2)
                    or RGB format (False, default for PIL/matplotlib).
                   
        Returns:
            A list of dictionary objects, one per detected plate:
                - 'box': [x1, y1, x2, y2] bounding box with 5% padding clamped to image bounds.
                - 'raw_box': [xmin, ymin, xmax, ymax] original unpadded detector box.
                - 'detector_confidence': float confidence from YOLO (e.g. 0.88).
                - 'crop': numpy RGB image array of the cropped plate.
                - 'text': normalised plate string (A-Z and 0-9 only, uppercase).
                - 'raw_text': raw string directly returned by fast-plate-ocr.
                - 'ocr_confidence': float average confidence over plate characters (from char_probs).
                - 'char_probs': list of float probabilities per character position.
        """
        # Convert input into standardized numpy arrays: image_bgr (for YOLO) & image_rgb (for OCR)
        image_bgr, image_rgb = self._standardize_image(image, is_bgr=is_bgr)
        h_img, w_img = image_bgr.shape[:2]

        # 1. Run YOLO detector
        det_results = self.detector.predict(image_bgr, conf=self.conf_thresh, verbose=False)[0]
        boxes = det_results.boxes
        if len(boxes) == 0:
            return []

        detections: List[Dict[str, Any]] = []

        # 2. Process each detected plate box
        for box in boxes:
            xyxy = box.xyxy[0].cpu().numpy()
            det_conf = float(box.conf[0].cpu().numpy())
            xmin, ymin, xmax, ymax = xyxy

            # Compute 5% padding exactly as used in data preparation (ocr/prepare_ocr_data.py)
            bw = xmax - xmin
            bh = ymax - ymin
            pad_x = self.padding_ratio * bw
            pad_y = self.padding_ratio * bh

            x1 = max(0, int(round(xmin - pad_x)))
            y1 = max(0, int(round(ymin - pad_y)))
            x2 = min(w_img, int(round(xmax + pad_x)))
            y2 = min(h_img, int(round(ymax + pad_y)))

            if x2 <= x1 or y2 <= y1:
                continue

            # Extract 5% padded crop (in RGB format expected by fast-plate-ocr)
            crop_rgb = image_rgb[y1:y2, x1:x2]
            if crop_rgb.size == 0:
                continue

            # 3. Run OCR inference with per-character confidence scores
            # Note: fast_plate_ocr exposes per-character probabilities via return_confidence=True
            ocr_preds = self.recognizer.run(crop_rgb, return_confidence=True)
            if not ocr_preds:
                continue

            pred_item = ocr_preds[0]
            raw_text = pred_item.plate if hasattr(pred_item, "plate") else str(pred_item)
            norm_text = self.normalize_text(raw_text)

            # Extract per-character confidence probabilities
            char_probs = pred_item.char_probs
            if char_probs is not None and len(raw_text) > 0:
                char_probs_list = [float(p) for p in char_probs[: len(raw_text)]]
                ocr_conf = float(np.mean(char_probs_list))
            else:
                char_probs_list = []
                ocr_conf = 0.0

            detections.append({
                "box": [x1, y1, x2, y2],
                "raw_box": [float(xmin), float(ymin), float(xmax), float(ymax)],
                "detector_confidence": det_conf,
                "crop": crop_rgb,
                "text": norm_text,
                "raw_text": raw_text,
                "ocr_confidence": ocr_conf,
                "char_probs": char_probs_list,
            })

        return detections

    @staticmethod
    def _standardize_image(
        image: Union[str, Path, np.ndarray, Image.Image],
        is_bgr: bool = True,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Converts diverse image inputs into (image_bgr, image_rgb) uint8 numpy arrays."""
        if isinstance(image, (str, Path)):
            path_str = str(image)
            if not Path(path_str).exists():
                raise FileNotFoundError(f"Input image not found: {path_str}")
            image_bgr = cv2.imread(path_str)
            if image_bgr is None:
                raise ValueError(f"cv2.imread failed to load image: {path_str}")
            image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
            return image_bgr, image_rgb

        if isinstance(image, Image.Image):
            rgb_pil = image.convert("RGB")
            image_rgb = np.array(rgb_pil)
            image_bgr = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2BGR)
            return image_bgr, image_rgb

        if isinstance(image, np.ndarray):
            if image.ndim == 2:
                # Grayscale to 3-channel
                image_bgr = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
                image_rgb = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
                return image_bgr, image_rgb
            if image.ndim == 3 and image.shape[2] == 3:
                if is_bgr:
                    image_bgr = image
                    image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
                else:
                    image_rgb = image
                    image_bgr = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
                return image_bgr, image_rgb
            raise ValueError(f"Unsupported numpy image array shape: {image.shape}")

        raise TypeError(f"Unsupported image type: {type(image)}")
