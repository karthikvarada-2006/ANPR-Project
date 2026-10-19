"""Unit and Integration Tests for ANPR Pipeline and PlateReader.

Verifies:
1. PlateReader initializes cleanly with default detector and OCR paths.
2. PlateReader detects and reads plate text correctly on a known test image.
3. PlateReader returns an empty list for an image without plates (e.g. blank image).
4. PlateReader normalises text to uppercase alphanumeric (A-Z and 0-9 only).
5. PlateReader accepts both file paths, numpy arrays, and PIL Images.
"""

from pathlib import Path
import numpy as np
import pytest
from PIL import Image

from pipeline.plate_reader import PlateReader, OCR_ONNX_PATH, OCR_CONFIG_PATH

PROJECT_ROOT = Path(__file__).resolve().parent.parent
KNOWN_TEST_IMG = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "indian-number-plates-dataset"
    / "google_images"
    / "00b42b2c-f193-4863-b92c-0245cbc816da___3e7fd381-0ae5-4421-8a70-279ee0ec1c61_Nissan-Terrano-Petrol-Review-Images-Black-Front-Angle.jpg"
)


@pytest.fixture(scope="module")
def reader():
    """Shared PlateReader fixture for test suite."""
    return PlateReader(
        detector_path=PROJECT_ROOT / "models" / "plate_detector.pt",
        ocr_dir=PROJECT_ROOT / "models" / "plate_ocr",
        conf_thresh=0.25,
        device="auto",
    )


def test_reader_initialization(reader):
    """Verify PlateReader loads detector and OCR recognizer without errors."""
    assert reader.detector is not None, "YOLO detector failed to load"
    assert reader.recognizer is not None, "fast-plate-ocr recognizer failed to load"
    assert reader.onnx_path.exists(), "ONNX model path does not exist"
    assert reader.plate_config_path.exists(), "Plate config YAML path does not exist"
    assert reader.onnx_path.name == OCR_ONNX_PATH.name, f"Expected {OCR_ONNX_PATH.name}, got {reader.onnx_path.name}"


def test_reader_detects_plate_on_known_test_image(reader):
    """Verify the reader returns plate text and metadata for a known real test photo."""
    assert KNOWN_TEST_IMG.exists(), f"Known test image not found at: {KNOWN_TEST_IMG}"

    detections = reader.read_image(KNOWN_TEST_IMG)

    # 1. Must detect at least one plate
    assert len(detections) >= 1, "Expected at least 1 plate detection on known test image"

    first_det = detections[0]

    # 2. Check required dictionary keys
    expected_keys = {
        "box",
        "raw_box",
        "detector_confidence",
        "crop",
        "text",
        "raw_text",
        "ocr_confidence",
        "char_probs",
    }
    assert expected_keys.issubset(first_det.keys()), f"Missing keys in detection dict: {expected_keys - set(first_det.keys())}"

    # 3. Check values
    assert first_det["detector_confidence"] > 0.5, f"Detector confidence too low: {first_det['detector_confidence']}"
    assert first_det["ocr_confidence"] > 0.5, f"OCR confidence too low: {first_det['ocr_confidence']}"
    assert first_det["crop"].ndim == 3, "Crop must be a 3D image array"
    assert first_det["crop"].shape[0] > 0 and first_det["crop"].shape[1] > 0, "Crop has zero dimensions"

    # 4. Check plate text content
    text = first_det["text"]
    assert text == "TN21AT0492", f"Expected plate 'TN21AT0492', got '{text}'"
    assert text.isalnum(), "Plate text must be alphanumeric"
    assert text.isupper(), "Plate text must be uppercase"


def test_reader_returns_empty_list_for_image_without_plates(reader):
    """Verify the reader returns an empty list [] for an image without license plates."""
    # Create plain black image
    blank_image = np.zeros((640, 640, 3), dtype=np.uint8)

    detections = reader.read_image(blank_image)
    assert isinstance(detections, list), "Expected list return type"
    assert len(detections) == 0, f"Expected 0 detections on blank image, got: {len(detections)}"

    # Create random noise image without plates
    np.random.seed(42)
    noise_image = np.random.randint(0, 256, (480, 640, 3), dtype=np.uint8)
    detections_noise = reader.read_image(noise_image)
    assert len(detections_noise) == 0, f"Expected 0 detections on noise image, got: {len(detections_noise)}"


def test_reader_normalises_text():
    """Verify PlateReader.normalize_text strips special characters, spaces, and uppercases."""
    # Test cases: (input, expected)
    test_cases = [
        ("dl 01 ab 1234", "DL01AB1234"),
        ("ka-18-p-2987", "KA18P2987"),
        ("mh.20/cs_1941", "MH20CS1941"),
        ("!@#TN$$21%%AT^^0492&&", "TN21AT0492"),
        ("  hr 26 dk 8337  ", "HR26DK8337"),
        ("wb-06-f-9209\n", "WB06F9209"),
        ("", ""),
        ("   ", ""),
    ]

    for raw_inp, expected in test_cases:
        actual = PlateReader.normalize_text(raw_inp)
        assert actual == expected, f"Failed for '{raw_inp}': expected '{expected}', got '{actual}'"
        if actual:
            assert actual.isalnum(), f"Result '{actual}' is not alphanumeric"
            assert actual.isupper(), f"Result '{actual}' is not uppercase"


def test_reader_accepts_pil_and_numpy_inputs(reader):
    """Verify read_image works transparently with PIL Image and numpy array inputs."""
    import cv2

    # 1. Load via PIL Image
    with Image.open(KNOWN_TEST_IMG) as pil_im:
        dets_pil = reader.read_image(pil_im)
        assert len(dets_pil) >= 1, "Failed detection with PIL Image input"
        assert dets_pil[0]["text"] == "TN21AT0492"

    # 2. Load via OpenCV BGR numpy array (default for cv2.imread)
    im_bgr = cv2.imread(str(KNOWN_TEST_IMG))
    dets_bgr = reader.read_image(im_bgr, is_bgr=True)
    assert len(dets_bgr) >= 1, "Failed detection with OpenCV BGR numpy array"
    assert dets_bgr[0]["text"] == "TN21AT0492"

    # 3. Load via RGB numpy array (e.g. from PIL or matplotlib)
    im_rgb = np.array(Image.open(KNOWN_TEST_IMG))
    dets_rgb = reader.read_image(im_rgb, is_bgr=False)
    assert len(dets_rgb) >= 1, "Failed detection with RGB numpy array"
    assert dets_rgb[0]["text"] == "TN21AT0492"

