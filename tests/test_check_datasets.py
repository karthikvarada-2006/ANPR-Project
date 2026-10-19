"""Tests for data/check_datasets.py verification script."""

import json
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from data.check_datasets import (
    extract_plate_text_samples,
    inspect_dataset_folder,
    scan_raw_datasets,
)


@pytest.fixture
def mock_raw_dir(tmp_path):
    """Create a temporary mock data/raw directory structure with sample datasets."""
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()

    # 1. Mock Indian Number Plates dataset (READY: images + VOC XML with plate text)
    inp_dir = raw_dir / "indian-number-plates-dataset"
    inp_dir.mkdir()
    for i in range(25):
        img_file = inp_dir / f"car_{i:03d}.jpg"
        img_file.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 100)  # Dummy JPEG bytes

        xml_file = inp_dir / f"car_{i:03d}.xml"
        plate_str = f"KA0{i % 9 + 1}AB{1000 + i}"
        root = ET.Element("annotation")
        fn = ET.SubElement(root, "filename")
        fn.text = img_file.name
        obj = ET.SubElement(root, "object")
        name = ET.SubElement(obj, "name")
        name.text = "number_plate"
        ptext = ET.SubElement(obj, "number_plate_text")
        ptext.text = plate_str
        tree = ET.ElementTree(root)
        tree.write(str(xml_file))

    # 2. Mock Indian Vehicle dataset (READY: images + JSON lines with plate text)
    iv_dir = raw_dir / "indian-vehicle-dataset"
    iv_dir.mkdir()
    json_lines = []
    for i in range(25):
        img_file = iv_dir / f"veh_{i:03d}.png"
        img_file.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
        plate_str = f"DL03NV{2000 + i}"
        json_lines.append(
            json.dumps({
                "content": img_file.name,
                "annotation": [{"label": ["number_plate"], "notes": plate_str}],
            })
        )
    (iv_dir / "Indian_Number_Plates.json").write_text("\n".join(json_lines), encoding="utf-8")

    # 3. Mock License Plate Detection dataset (PARTIAL: images without annotations)
    lpd_dir = raw_dir / "license-plate-detection"
    lpd_dir.mkdir()
    for i in range(5):
        (lpd_dir / f"sample_{i}.jpg").write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 50)

    # 4. Mock CCPD dataset (READY: CCPD filename-embedded annotations)
    ccpd_dir = raw_dir / "ccpd"
    ccpd_dir.mkdir()
    for i in range(60):
        ccpd_name = f"025-95_113-154&383_386&473-386&473_177&454_154&383_363&402-0_0_22_27_27_33_{i:02d}-37-15.jpg"
        (ccpd_dir / ccpd_name).write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 50)

    return raw_dir


def test_inspect_dataset_folder_ready_xml(mock_raw_dir):
    """Check that dataset with images and XML files gets READY verdict."""
    folder = mock_raw_dir / "indian-number-plates-dataset"
    meta = {
        "key": "indian_number_plates",
        "category": "indian",
        "min_images": 20,
    }
    info = inspect_dataset_folder(folder, dataset_meta=meta)
    assert info["verdict"] == "READY"
    assert info["num_images"] == 25
    assert info["matching_annotations"] == 25
    assert "XML" in info["annotation_formats"]
    assert len(info["plate_text_samples"]) > 0
    assert any("KA0" in s for s in info["plate_text_samples"])


def test_inspect_dataset_folder_ready_ccpd(mock_raw_dir):
    """Check that CCPD dataset with filename-embedded annotations gets READY verdict."""
    folder = mock_raw_dir / "ccpd"
    meta = {
        "key": "ccpd",
        "category": "benchmark",
        "min_images": 50,
    }
    info = inspect_dataset_folder(folder, dataset_meta=meta)
    assert info["verdict"] == "READY"
    assert info["num_images"] == 60
    assert info["matching_annotations"] == 60
    assert "FILENAME_EMBEDDED" in info["annotation_formats"]


def test_inspect_dataset_folder_partial(mock_raw_dir):
    """Check that dataset with few files or no annotations gets PARTIAL verdict."""
    folder = mock_raw_dir / "license-plate-detection"
    meta = {
        "key": "license_plate_detection",
        "category": "indian",
        "min_images": 20,
    }
    info = inspect_dataset_folder(folder, dataset_meta=meta)
    assert info["verdict"] == "PARTIAL"
    assert info["num_images"] == 5
    assert info["matching_annotations"] == 0


def test_inspect_dataset_folder_missing(mock_raw_dir):
    """Check that non-existent folder gets MISSING verdict."""
    folder = mock_raw_dir / "ufpr_alpr"
    meta = {
        "key": "ufpr_alpr",
        "category": "benchmark",
        "min_images": 50,
    }
    info = inspect_dataset_folder(folder, dataset_meta=meta)
    assert info["verdict"] == "MISSING"
    assert info["num_images"] == 0


def test_scan_raw_datasets_all_recognized(mock_raw_dir):
    """Check that scan_raw_datasets recognizes all 6 datasets."""
    results = scan_raw_datasets(mock_raw_dir)
    assert len(results) >= 6
    names = [r["folder_name"] for r in results]
    assert "ccpd" in names
    assert "ufpr_alpr" in names
    assert "cityflowv2" in names
    assert "indian-number-plates-dataset" in names
    assert "indian-vehicle-dataset" in names
    assert "license-plate-detection" in names


def test_check_datasets_cli_run(mock_raw_dir):
    """Check that running python data/check_datasets.py via CLI succeeds with exit code 0."""
    script_path = ROOT_DIR / "data" / "check_datasets.py"
    res = subprocess.run(
        [sys.executable, str(script_path), "--dir", str(mock_raw_dir)],
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0
    assert "CITY ANPR RAW DATASET INSPECTOR" in res.stdout
    assert "CITY ANPR DATASET VERIFICATION & READINESS SUMMARY" in res.stdout
    assert "TRAINING READINESS ANALYSIS" in res.stdout
    assert "[READY]" in res.stdout
    assert "[PARTIAL]" in res.stdout
    assert "[MISSING]" in res.stdout
