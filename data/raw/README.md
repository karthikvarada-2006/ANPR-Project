# Raw Datasets Directory (`data/raw/`)

This folder contains raw benchmark datasets for license plate detection, optical character recognition (OCR), multi-object tracking, and multi-camera city vehicle re-identification.

---

## 📥 Datasets Overview

| Dataset | Acquisition Method | Target Folder | Purpose in Project |
| :--- | :--- | :--- | :--- |
| **Indian Vehicle Dataset** | Automatic (`download_datasets.py`) | `data/raw/indian-vehicle-dataset/` | Vehicle classification & localization |
| **Indian Number Plates** | Automatic (`download_datasets.py`) | `data/raw/indian-number-plates-dataset/` | Indian plate detection & OCR training |
| **License Plate Detection** | Automatic (`download_datasets.py`) | `data/raw/license-plate-detection/` | Plate bounding box detector training |
| **CCPD** | Manual Download | `data/raw/ccpd/` | Large-scale license plate benchmark |
| **UFPR-ALPR** | Manual Download | `data/raw/ufpr_alpr/` | Multi-frame vehicle & plate video sequences |
| **CityFlowV2** | Manual Download | `data/raw/cityflowv2/` | Multi-Camera Multi-Target (MC-MT) tracking & Re-ID |

---

## 🛠️ Manual Datasets Setup

Due to size (>10 GB) and licensing/registration requirements, the following three datasets must be downloaded manually and extracted into their respective directories:

### 1. CCPD (Chinese City Parking Dataset)
* **Description:** Over 250,000 images captured under diverse urban conditions (angles, weather, blurs). Annotations are embedded directly in the image filenames.
* **Source:** [GitHub - detectRecog/CCPD](https://github.com/detectRecog/CCPD) or official Google Drive / Baidu Wangpan links.
* **Target Location:** Place the unzipped contents into `data/raw/ccpd/`.
* **Expected Folder Structure:**
  ```
  data/raw/ccpd/
  ├── ccpd_base/            # Standard clear urban shots
  ├── ccpd_blur/            # Motion blur images
  ├── ccpd_challenge/       # Difficult lighting and angles
  ├── ccpd_db/              # Dark / night shots
  ├── ccpd_fn/              # Far / near distance variation
  ├── ccpd_np/              # Vehicles without front plates
  ├── ccpd_rotate/          # Rotated plates (20-50 degrees)
  ├── ccpd_tilt/            # Tilted plates (horizontal/vertical)
  └── ccpd_weather/         # Rain, snow, fog conditions
  ```
  *(Note: At minimum, `ccpd_base/` is required for baseline experiments).*

* **How to Verify CCPD:**
  Open PowerShell in the project root and run:
  ```powershell
  python -c "from pathlib import Path; p = Path('data/raw/ccpd'); imgs = list(p.rglob('*.jpg')); print(f'CCPD Loaded: {len(imgs):,} images found') if imgs else print('CCPD NOT FOUND')"
  ```
  **Expected:** Prints `CCPD Loaded: >0 images found`.

---

### 2. UFPR-ALPR Dataset
* **Description:** 4,500 video frames of cars and motorcycles with comprehensive ground-truth annotations (bounding boxes, plate characters, vehicle makes/models).
* **Source:** [UFPR-ALPR Official Page](https://virserv.com.br/datasets/ufpr-alpr/) (requires short request form).
* **Target Location:** Place the unzipped dataset into `data/raw/ufpr_alpr/`.
* **Expected Folder Structure:**
  ```
  data/raw/ufpr_alpr/
  ├── testing/
  │   ├── track0001/
  │   │   ├── track0001[01].png
  │   │   ├── track0001[01].txt
  │   │   └── ...
  ├── training/
  └── validation/
  ```

* **How to Verify UFPR-ALPR:**
  Open PowerShell in the project root and run:
  ```powershell
  python -c "from pathlib import Path; p = Path('data/raw/ufpr_alpr'); tracks = list(p.glob('*/*')); print(f'UFPR-ALPR Loaded: {len(tracks)} tracks found') if tracks else print('UFPR-ALPR NOT FOUND')"
  ```
  **Expected:** Prints `UFPR-ALPR Loaded: 150 tracks found` (or non-zero tracks).

---

### 3. CityFlowV2 (AI City Challenge Benchmark)
* **Description:** Multi-camera video tracking dataset covering multiple road intersections and synchronized camera streams for vehicle re-identification and trajectory reconstruction.
* **Source:** [AI City Challenge](https://www.aicitychallenge.org/) / [CityFlow GitHub](https://github.com/VehicleReId/CityFlow).
* **Target Location:** Place the unzipped contents into `data/raw/cityflowv2/`.
* **Expected Folder Structure:**
  ```
  data/raw/cityflowv2/
  ├── train/
  │   ├── S01/               # Scenario 1
  │   │   ├── c001/          # Camera 1 (vdo.avi, gt/gt.txt, calibration.txt)
  │   │   ├── c002/          # Camera 2
  │   │   └── ...
  │   ├── S03/
  │   └── S04/
  ├── validation/
  └── test/
  ```

* **How to Verify CityFlowV2:**
  Open PowerShell in the project root and run:
  ```powershell
  python -c "from pathlib import Path; p = Path('data/raw/cityflowv2'); cams = list(p.glob('*/*/*')); print(f'CityFlowV2 Loaded: {len(cams)} camera feeds found') if cams else print('CityFlowV2 NOT FOUND')"
  ```
  **Expected:** Prints `CityFlowV2 Loaded: >0 camera feeds found`.

---

## 🔍 Automated Verification Script

You can verify all manual and downloaded datasets in one go using:

```powershell
python -c "
from pathlib import Path

datasets = {
    'CCPD': Path('data/raw/ccpd'),
    'UFPR-ALPR': Path('data/raw/ufpr_alpr'),
    'CityFlowV2': Path('data/raw/cityflowv2'),
    'Indian Vehicles': Path('data/raw/indian-vehicle-dataset'),
    'Indian Number Plates': Path('data/raw/indian-number-plates-dataset'),
    'License Plate Detection': Path('data/raw/license-plate-detection'),
}

print('=' * 60)
print('DATASET INVENTORY STATUS')
print('=' * 60)
for name, path in datasets.items():
    if path.exists() and any(path.iterdir()):
        files = list(path.rglob('*.*'))
        print(f'  [FOUND] {name:<25} ({len(files):,} files in {path})')
    else:
        print(f'  [MISSING] {name:<25} (Expected at: {path})')
print('=' * 60)
"
```
