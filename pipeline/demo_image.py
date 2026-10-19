"""Demo Script to Read License Plates and Visualize Detections on an Image.

Usage:
    python -m pipeline.demo_image <path_to_image>
    python pipeline/demo_image.py <path_to_image>

Outputs:
    Saves annotated image with bounding boxes, plate text, and confidence scores
    to docs/demo/<image_name>_demo.jpg.
"""

import argparse
import logging
import os
import sys
import time
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from pipeline.plate_reader import PlateReader

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def annotate_image(
    image_bgr: np.ndarray,
    detections: list,
) -> np.ndarray:
    """Draws bounding boxes, plate text, and confidence badges on the image."""
    annotated = image_bgr.copy()
    h_img, w_img = annotated.shape[:2]

    for det in detections:
        x1, y1, x2, y2 = [int(round(v)) for v in det["box"]]
        text = det["text"]
        det_conf = det["detector_confidence"]
        ocr_conf = det["ocr_confidence"]

        # Draw green bounding box around license plate
        box_color = (34, 197, 94)  # BGR Vibrant Green (#22c55e)
        cv2.rectangle(annotated, (x1, y1), (x2, y2), box_color, 3)

        # Build label string
        label = f"{text} (Det:{det_conf:.0%} OCR:{ocr_conf:.0%})"

        # Font configuration
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = max(0.45, min(0.8, w_img / 1200.0))
        thickness = 2
        (tw, th), baseline = cv2.getTextSize(label, font, font_scale, thickness)

        # Badge position (above box, or below if near top of image)
        tag_y2 = y1 - 4 if (y1 - th - baseline - 8) > 0 else y2 + th + baseline + 8
        tag_y1 = tag_y2 - th - baseline - 6
        tag_x1 = max(0, x1)
        tag_x2 = min(w_img, x1 + tw + 12)

        # Draw filled dark background tag
        tag_color = (15, 23, 42)  # BGR Dark Slate (#0f172a)
        cv2.rectangle(annotated, (tag_x1, tag_y1), (tag_x2, tag_y2), tag_color, -1)
        # Border around tag
        cv2.rectangle(annotated, (tag_x1, tag_y1), (tag_x2, tag_y2), box_color, 1)

        # Text inside tag
        text_origin = (tag_x1 + 6, tag_y2 - baseline - 3)
        cv2.putText(
            annotated,
            label,
            text_origin,
            font,
            font_scale,
            (255, 255, 255),
            thickness,
            cv2.LINE_AA,
        )

    return annotated


def run_demo(
    image_path: str,
    detector_path: str = "models/plate_detector.pt",
    ocr_dir: str = "models/plate_ocr",
    conf_thresh: float = 0.25,
    out_dir: str = "docs/demo",
) -> Optional[Path]:
    """Runs PlateReader on a single image, annotates detections, and saves output."""
    img_p = Path(image_path)
    if not img_p.exists():
        raise FileNotFoundError(f"Input image not found: {img_p.resolve()}")

    out_folder = Path(out_dir)
    out_folder.mkdir(parents=True, exist_ok=True)

    logger.info("Initializing PlateReader pipeline...")
    reader = PlateReader(
        detector_path=detector_path,
        ocr_dir=ocr_dir,
        conf_thresh=conf_thresh,
        device="auto",
    )

    logger.info("Running detection and OCR on %s...", img_p.name)
    t0 = time.perf_counter()
    detections = reader.read_image(img_p)
    t1 = time.perf_counter()
    latency_ms = (t1 - t0) * 1000.0

    logger.info("Inference completed in %.1f ms. Found %d plate(s):", latency_ms, len(detections))
    for i, det in enumerate(detections, 1):
        logger.info(
            "  [%d] Plate: %-12s | Detector Conf: %5.1f%% | OCR Conf: %5.1f%% | Box: %s",
            i,
            det["text"],
            det["detector_confidence"] * 100.0,
            det["ocr_confidence"] * 100.0,
            det["box"],
        )

    # Load original image for visualization
    orig_bgr = cv2.imread(str(img_p))
    if orig_bgr is None:
        raise ValueError(f"Could not load image: {img_p}")

    annotated = annotate_image(orig_bgr, detections)

    # Output filename
    save_path = out_folder / f"{img_p.stem}_demo.jpg"
    cv2.imwrite(str(save_path), annotated)
    logger.info("Saved annotated demo image to: %s", save_path.resolve())

    return save_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="City-ANPR Plate Reader Single Image Demo.")
    parser.add_argument("image", type=str, help="Path to input image file.")
    parser.add_argument("--detector", type=str, default="models/plate_detector.pt", help="Path to detector weights.")
    parser.add_argument("--ocr-dir", type=str, default="models/plate_ocr", help="Directory with OCR ONNX & config.")
    parser.add_argument("--conf", type=float, default=0.25, help="Detector confidence threshold.")
    parser.add_argument("--out-dir", type=str, default="docs/demo", help="Directory to save annotated image.")
    args = parser.parse_args()

    run_demo(
        image_path=args.image,
        detector_path=args.detector,
        ocr_dir=args.ocr_dir,
        conf_thresh=args.conf,
        out_dir=args.out_dir,
    )
