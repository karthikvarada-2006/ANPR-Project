"""Prepare YOLO License Plate Detection Dataset.

Processes raw datasets:
1. data/raw/license-plate-detection/
2. data/raw/indian-number-plates-dataset/
3. data/raw/indian-vehicle-dataset/

Outputs:
data/processed/detector/
    ├── images/ {train, val, test}
    ├── labels/ {train, val, test}
    └── data.yaml
and data/processed/split_groups.json (shared group split mapping).
"""

import argparse
import json
import os
import re
import shutil
import sys
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import numpy as np
from PIL import Image, ImageOps


class UnionFind:
    """Disjoint Set Union (DSU) to group connected frames/images."""

    def __init__(self):
        self.parent: Dict[str, str] = {}

    def find(self, x: str) -> str:
        if x not in self.parent:
            self.parent[x] = x
            return x
        if self.parent[x] != x:
            self.parent[x] = self.find(self.parent[x])
        return self.parent[x]

    def union(self, x: str, y: str):
        root_x = self.find(x)
        root_y = self.find(y)
        if root_x != root_y:
            self.parent[root_y] = root_x


def compute_dhash(img_path: Path, hash_size: int = 8) -> Optional[int]:
    """Compute 64-bit difference hash (dHash) for fast perceptual deduplication."""
    try:
        with Image.open(img_path) as im:
            im = im.convert("L").resize((hash_size + 1, hash_size), Image.Resampling.BILINEAR)
            pixels = np.asarray(im)
            diff = pixels[:, 1:] > pixels[:, :-1]
            val = 0
            for b in diff.flatten():
                val = (val << 1) | int(b)
            return val
    except Exception:
        return None


def hamming_distance(h1: int, h2: int) -> int:
    """Compute Hamming distance between two 64-bit hashes."""
    return bin(h1 ^ h2).count("1")


def get_video_group(filename: str) -> str:
    """Extract group prefix from video frame filenames."""
    # Match video series: video10_1060.jpg -> vid_video10
    m1 = re.match(r"^(video\d+)", filename, re.IGNORECASE)
    if m1:
        return f"vid_{m1.group(1).lower()}"

    # Match car series: car-wbs-MH01DE2780_00000.png -> vid_car-wbs-MH01DE2780
    m2 = re.match(r"^(car-[a-zA-Z0-9]+-[A-Z0-9]+)_\d+", filename, re.IGNORECASE)
    if m2:
        return f"vid_{m2.group(1).lower()}"

    # General prefix before trailing _number
    m3 = re.match(r"^([A-Za-z0-9_-]+)_\d+\.[a-zA-Z0-9]+$", filename)
    if m3:
        return f"vid_{m3.group(1).lower()}"

    return f"vid_{Path(filename).stem}"


class DetectorDataPreparer:
    def __init__(
        self,
        raw_dir: Path,
        processed_dir: Path,
        max_size: int = 1280,
        train_ratio: float = 0.80,
        val_ratio: float = 0.10,
        test_ratio: float = 0.10,
        seed: int = 42,
    ):
        self.raw_dir = Path(raw_dir)
        self.processed_dir = Path(processed_dir)
        self.detector_dir = self.processed_dir / "detector"
        self.max_size = max_size
        self.train_ratio = train_ratio
        self.val_ratio = val_ratio
        self.test_ratio = test_ratio
        self.seed = seed

        self.removed_items: List[Dict[str, str]] = []
        self.all_candidates: List[Dict] = []
        self.dhash_map: Dict[str, int] = {}
        self.image_groups: Dict[str, str] = {}
        self.image_to_split: Dict[str, str] = {}

    def collect_license_plate_detection(self):
        """Source 1: data/raw/license-plate-detection/ (YOLO txt format)."""
        src_dir = self.raw_dir / "license-plate-detection"
        img_dir = src_dir / "images"
        lbl_dir = src_dir / "labels"

        if not img_dir.exists():
            print(f"Warning: {img_dir} does not exist!")
            return

        lbl_files = {f.stem: f for f in lbl_dir.glob("*.txt")}
        all_imgs = sorted([f for f in img_dir.glob("*") if f.suffix.lower() in (".jpg", ".jpeg", ".png")])

        missing_labels = []
        for img in all_imgs:
            if img.stem not in lbl_files:
                missing_labels.append(img.name)
                self.removed_items.append({
                    "path": str(img.relative_to(self.raw_dir)),
                    "filename": img.name,
                    "source": "license-plate-detection",
                    "reason": "Missing label file",
                })
                continue

            lbl_file = lbl_files[img.stem]
            try:
                with Image.open(img) as im:
                    w_img, h_img = im.size
            except Exception as e:
                self.removed_items.append({
                    "path": str(img.relative_to(self.raw_dir)),
                    "filename": img.name,
                    "source": "license-plate-detection",
                    "reason": f"Corrupted image: {e}",
                })
                continue

            # Read YOLO boxes
            lines = [l.strip().split() for l in lbl_file.read_text().splitlines() if l.strip()]
            valid_boxes = []
            for parts in lines:
                if len(parts) < 5:
                    continue
                xc, yc, bw, bh = [float(x) for x in parts[1:5]]
                area = bw * bh

                # Sanity checks
                if area > 0.40:
                    self.removed_items.append({
                        "path": str(img.relative_to(self.raw_dir)),
                        "filename": img.name,
                        "source": "license-plate-detection",
                        "reason": f"Box area > 40% ({area*100:.1f}%) - plate crop",
                    })
                    continue

                if bw < 0.01 or bh < 0.01 or (bw * w_img < 10) or (bh * h_img < 10) or (area < 0.0002):
                    self.removed_items.append({
                        "path": str(img.relative_to(self.raw_dir)),
                        "filename": img.name,
                        "source": "license-plate-detection",
                        "reason": f"Tiny box (w={bw:.3f}, h={bh:.3f})",
                    })
                    continue

                if not (0 <= xc <= 1 and 0 <= yc <= 1):
                    self.removed_items.append({
                        "path": str(img.relative_to(self.raw_dir)),
                        "filename": img.name,
                        "source": "license-plate-detection",
                        "reason": f"Center out of bounds (xc={xc:.3f}, yc={yc:.3f})",
                    })
                    continue

                # Clamp box boundaries to [0, 1]
                xmin = max(0.0, xc - bw / 2)
                ymin = max(0.0, yc - bh / 2)
                xmax = min(1.0, xc + bw / 2)
                ymax = min(1.0, yc + bh / 2)
                bw_clamped = xmax - xmin
                bh_clamped = ymax - ymin
                xc_clamped = (xmin + xmax) / 2
                yc_clamped = (ymin + ymax) / 2

                valid_boxes.append((0, xc_clamped, yc_clamped, bw_clamped, bh_clamped))

            if not valid_boxes:
                # If all boxes were excluded (e.g. tight plate crops covering >40% of image)
                self.removed_items.append({
                    "path": str(img.relative_to(self.raw_dir)),
                    "filename": img.name,
                    "source": "license-plate-detection",
                    "reason": "No valid boxes remaining after sanity checks",
                })
                continue

            self.all_candidates.append({
                "source": "license-plate-detection",
                "img_path": img,
                "boxes": valid_boxes,
                "orig_size": (w_img, h_img),
                "rel_path": str(img.relative_to(self.raw_dir)),
                "group_hint": f"lpd_{img.stem}",
            })

        print(f"[license-plate-detection] Total images: {len(all_imgs)}")
        print(f"  Excluded without label file: {len(missing_labels)}")
        if missing_labels:
            print(f"  Sample excluded without label: {missing_labels[:5]}")
        print(f"  Accepted candidates with valid boxes: {sum(1 for c in self.all_candidates if c['source'] == 'license-plate-detection')}")

    def collect_indian_number_plates_dataset(self):
        """Source 2: data/raw/indian-number-plates-dataset/ (Pascal VOC XML)."""
        src_dir = self.raw_dir / "indian-number-plates-dataset"
        if not src_dir.exists():
            print(f"Warning: {src_dir} does not exist!")
            return

        all_imgs = sorted([f for f in src_dir.rglob("*") if f.suffix.lower() in (".jpg", ".jpeg", ".png")])
        count_accepted = 0

        for img in all_imgs:
            # Find matching XML file
            cand1 = img.with_suffix(img.suffix + ".xml")
            cand2 = img.with_suffix(".xml")
            xml_file = cand1 if cand1.exists() else (cand2 if cand2.exists() else None)

            if not xml_file:
                self.removed_items.append({
                    "path": str(img.relative_to(self.raw_dir)),
                    "filename": img.name,
                    "source": "indian-number-plates-dataset",
                    "reason": "Missing XML annotation",
                })
                continue

            try:
                with Image.open(img) as im:
                    w_img, h_img = im.size
            except Exception as e:
                self.removed_items.append({
                    "path": str(img.relative_to(self.raw_dir)),
                    "filename": img.name,
                    "source": "indian-number-plates-dataset",
                    "reason": f"Corrupted image: {e}",
                })
                continue

            try:
                root = ET.parse(xml_file).getroot()
            except Exception as e:
                self.removed_items.append({
                    "path": str(img.relative_to(self.raw_dir)),
                    "filename": img.name,
                    "source": "indian-number-plates-dataset",
                    "reason": f"Corrupted XML: {e}",
                })
                continue

            valid_boxes = []
            for obj in root.findall("object"):
                bnd = obj.find("bndbox")
                if bnd is None:
                    continue
                try:
                    raw_xmin = float(bnd.find("xmin").text)
                    raw_ymin = float(bnd.find("ymin").text)
                    raw_xmax = float(bnd.find("xmax").text)
                    raw_ymax = float(bnd.find("ymax").text)
                except Exception:
                    continue

                if raw_xmax <= raw_xmin or raw_ymax <= raw_ymin:
                    self.removed_items.append({
                        "path": str(img.relative_to(self.raw_dir)),
                        "filename": img.name,
                        "source": "indian-number-plates-dataset",
                        "reason": f"Inverted box coordinates ({raw_xmin}, {raw_ymin}, {raw_xmax}, {raw_ymax})",
                    })
                    continue

                # Clamp to image dimensions
                xmin = max(0.0, min(raw_xmin, w_img))
                ymin = max(0.0, min(raw_ymin, h_img))
                xmax = max(0.0, min(raw_xmax, w_img))
                ymax = max(0.0, min(raw_ymax, h_img))

                bw = xmax - xmin
                bh = ymax - ymin
                area = (bw * bh) / (w_img * h_img)

                if area > 0.40:
                    self.removed_items.append({
                        "path": str(img.relative_to(self.raw_dir)),
                        "filename": img.name,
                        "source": "indian-number-plates-dataset",
                        "reason": f"Box area > 40% ({area*100:.1f}%)",
                    })
                    continue

                if bw < 10 or bh < 10 or (bw * bh) < 100:
                    self.removed_items.append({
                        "path": str(img.relative_to(self.raw_dir)),
                        "filename": img.name,
                        "source": "indian-number-plates-dataset",
                        "reason": f"Tiny box ({bw:.1f}x{bh:.1f} px)",
                    })
                    continue

                # YOLO normalized coords
                xc = (xmin + xmax) / (2.0 * w_img)
                yc = (ymin + ymax) / (2.0 * h_img)
                w_norm = bw / w_img
                h_norm = bh / h_img
                valid_boxes.append((0, xc, yc, w_norm, h_norm))

            if not valid_boxes:
                self.removed_items.append({
                    "path": str(img.relative_to(self.raw_dir)),
                    "filename": img.name,
                    "source": "indian-number-plates-dataset",
                    "reason": "No valid boxes remaining after sanity checks",
                })
                continue

            # Group hint
            sub = img.relative_to(src_dir).parts[0]
            if sub == "video_images":
                group_hint = get_video_group(img.name)
            elif sub == "State-wise_OLX":
                state = img.relative_to(src_dir).parts[1] if len(img.relative_to(src_dir).parts) > 1 else "misc"
                group_hint = f"olx_{state}"
            else:
                group_hint = f"google_{img.stem}"

            self.all_candidates.append({
                "source": "indian-number-plates-dataset",
                "img_path": img,
                "boxes": valid_boxes,
                "orig_size": (w_img, h_img),
                "rel_path": str(img.relative_to(self.raw_dir)),
                "group_hint": group_hint,
            })
            count_accepted += 1

        print(f"[indian-number-plates-dataset] Total images: {len(all_imgs)}, Accepted: {count_accepted}")

    def collect_indian_vehicle_dataset(self):
        """Source 3: data/raw/indian-vehicle-dataset/ (Pascal VOC XML, box only)."""
        src_dir = self.raw_dir / "indian-vehicle-dataset"
        if not src_dir.exists():
            print(f"Warning: {src_dir} does not exist!")
            return

        all_imgs = sorted([f for f in src_dir.rglob("*") if f.suffix.lower() in (".jpg", ".jpeg", ".png")])
        all_xmls = {x.stem: x for x in src_dir.rglob("*.xml")}
        count_accepted = 0

        for img in all_imgs:
            xml_file = all_xmls.get(img.stem)
            if not xml_file:
                self.removed_items.append({
                    "path": str(img.relative_to(self.raw_dir)),
                    "filename": img.name,
                    "source": "indian-vehicle-dataset",
                    "reason": "Missing XML annotation",
                })
                continue

            try:
                with Image.open(img) as im:
                    w_img, h_img = im.size
            except Exception as e:
                self.removed_items.append({
                    "path": str(img.relative_to(self.raw_dir)),
                    "filename": img.name,
                    "source": "indian-vehicle-dataset",
                    "reason": f"Corrupted image: {e}",
                })
                continue

            try:
                root = ET.parse(xml_file).getroot()
            except Exception as e:
                self.removed_items.append({
                    "path": str(img.relative_to(self.raw_dir)),
                    "filename": img.name,
                    "source": "indian-vehicle-dataset",
                    "reason": f"Corrupted XML: {e}",
                })
                continue

            valid_boxes = []
            for obj in root.findall("object"):
                bnd = obj.find("bndbox")
                if bnd is None:
                    continue
                try:
                    raw_xmin = float(bnd.find("xmin").text)
                    raw_ymin = float(bnd.find("ymin").text)
                    raw_xmax = float(bnd.find("xmax").text)
                    raw_ymax = float(bnd.find("ymax").text)
                except Exception:
                    continue

                if raw_xmax <= raw_xmin or raw_ymax <= raw_ymin:
                    continue

                xmin = max(0.0, min(raw_xmin, w_img))
                ymin = max(0.0, min(raw_ymin, h_img))
                xmax = max(0.0, min(raw_xmax, w_img))
                ymax = max(0.0, min(raw_ymax, h_img))

                bw = xmax - xmin
                bh = ymax - ymin
                area = (bw * bh) / (w_img * h_img)

                if area > 0.40:
                    self.removed_items.append({
                        "path": str(img.relative_to(self.raw_dir)),
                        "filename": img.name,
                        "source": "indian-vehicle-dataset",
                        "reason": f"Box area > 40% ({area*100:.1f}%)",
                    })
                    continue

                if bw < 10 or bh < 10 or (bw * bh) < 100:
                    continue

                xc = (xmin + xmax) / (2.0 * w_img)
                yc = (ymin + ymax) / (2.0 * h_img)
                w_norm = bw / w_img
                h_norm = bh / h_img
                valid_boxes.append((0, xc, yc, w_norm, h_norm))

            if not valid_boxes:
                self.removed_items.append({
                    "path": str(img.relative_to(self.raw_dir)),
                    "filename": img.name,
                    "source": "indian-vehicle-dataset",
                    "reason": "No valid boxes remaining after sanity checks",
                })
                continue

            self.all_candidates.append({
                "source": "indian-vehicle-dataset",
                "img_path": img,
                "boxes": valid_boxes,
                "orig_size": (w_img, h_img),
                "rel_path": str(img.relative_to(self.raw_dir)),
                "group_hint": f"ivd_{img.parent.name}",
            })
            count_accepted += 1

        print(f"[indian-vehicle-dataset] Total images: {len(all_imgs)}, Accepted: {count_accepted}")

    def deduplicate_with_dhash(self) -> List[Dict]:
        """Compute dHash and remove exact (dist=0) and near duplicates (dist<=2)."""
        print(f"\nComputing perceptual hashes for {len(self.all_candidates)} candidates...")
        # Compute hashes concurrently
        def _get_hash(item):
            h = compute_dhash(item["img_path"])
            return item["rel_path"], h

        with ThreadPoolExecutor(max_workers=8) as ex:
            results = list(ex.map(_get_hash, self.all_candidates))

        for rel_path, h in results:
            if h is not None:
                self.dhash_map[rel_path] = h

        # Prioritize keeping indian-number-plates-dataset (has plate text for OCR)
        def _priority(c):
            if c["source"] == "indian-number-plates-dataset":
                return 0
            if c["source"] == "indian-vehicle-dataset":
                return 1
            return 2

        sorted_candidates = sorted(self.all_candidates, key=_priority)
        kept_candidates: List[Dict] = []
        kept_hashes: List[Tuple[int, Dict]] = []

        exact_dups = 0
        near_dups = 0

        for cand in sorted_candidates:
            h = self.dhash_map.get(cand["rel_path"])
            if h is None:
                kept_candidates.append(cand)
                continue

            # Compare against already kept
            is_dup = False
            for kept_h, kept_cand in kept_hashes:
                dist = hamming_distance(h, kept_h)
                if dist == 0:
                    exact_dups += 1
                    is_dup = True
                    self.removed_items.append({
                        "path": cand["rel_path"],
                        "filename": cand["img_path"].name,
                        "source": cand["source"],
                        "reason": f"Exact perceptual duplicate of {kept_cand['img_path'].name}",
                    })
                    break
                elif dist <= 2:
                    near_dups += 1
                    is_dup = True
                    self.removed_items.append({
                        "path": cand["rel_path"],
                        "filename": cand["img_path"].name,
                        "source": cand["source"],
                        "reason": f"Near perceptual duplicate of {kept_cand['img_path'].name} (dist={dist})",
                    })
                    break

            if not is_dup:
                kept_candidates.append(cand)
                kept_hashes.append((h, cand))

        print(f"Deduplication complete: removed {exact_dups} exact duplicates, {near_dups} near duplicates.")
        print(f"Remaining unique candidates: {len(kept_candidates)}")
        return kept_candidates

    def cluster_and_split_groups(self, items: List[Dict]) -> Dict[str, List[Dict]]:
        """Cluster video series and visually close frames, then split by group."""
        uf = UnionFind()

        # Step A: Register group hints
        for it in items:
            uf.find(it["group_hint"])

        # Step B: Union video frames if their perceptual hash distance is <= 4
        video_items = [it for it in items if "vid_" in it["group_hint"]]
        for i in range(len(video_items)):
            h1 = self.dhash_map.get(video_items[i]["rel_path"])
            if h1 is None:
                continue
            for j in range(i + 1, min(i + 15, len(video_items))):
                h2 = self.dhash_map.get(video_items[j]["rel_path"])
                if h2 is not None and hamming_distance(h1, h2) <= 4:
                    uf.union(video_items[i]["group_hint"], video_items[j]["group_hint"])

        # Assign final canonical group ID to each item
        group_to_items = defaultdict(list)
        for it in items:
            canonical_group = uf.find(it["group_hint"])
            it["group_id"] = canonical_group
            self.image_groups[it["rel_path"]] = canonical_group
            group_to_items[canonical_group].append(it)

        print(f"\nGroup clustering: {len(items)} images clustered into {len(group_to_items)} groups.")

        # Step C: Deficit-ratio greedy knapsack split (80/10/10)
        import random
        random.seed(self.seed)

        total_items = len(items)
        targets = {
            "train": total_items * self.train_ratio,
            "val": total_items * self.val_ratio,
            "test": total_items * self.test_ratio,
        }
        current = {"train": 0, "val": 0, "test": 0}
        group_splits = {}
        split_items: Dict[str, List[Dict]] = {"train": [], "val": [], "test": []}

        # Sort groups descending by count, with random tie-breaker
        sorted_groups = sorted(
            group_to_items.keys(),
            key=lambda g: (-len(group_to_items[g]), random.random()),
        )

        for g in sorted_groups:
            g_items = group_to_items[g]
            cnt = len(g_items)

            # Assign to split with highest relative deficit
            best_split = max(
                ["train", "val", "test"],
                key=lambda s: (targets[s] - current[s]) / (targets[s] if targets[s] > 0 else 1.0),
            )
            group_splits[g] = best_split
            current[best_split] += cnt
            split_items[best_split].extend(g_items)

            for it in g_items:
                self.image_to_split[it["rel_path"]] = best_split
                # Also store filename and stem for easy matching
                self.image_to_split[it["img_path"].name] = best_split
                self.image_to_split[it["img_path"].stem] = best_split

        print("Split distribution:")
        for s in ["train", "val", "test"]:
            cnt = len(split_items[s])
            pct = cnt / total_items * 100 if total_items > 0 else 0
            n_grp = sum(1 for g, sp in group_splits.items() if sp == s)
            print(f"  {s:5s}: {cnt:4d} images ({pct:5.1f}%), {n_grp:4d} groups")

        # Save metadata for prepare_ocr_data and make_data_report
        meta = {
            "image_to_split": self.image_to_split,
            "group_splits": group_splits,
            "image_groups": self.image_groups,
            "removed_items": self.removed_items,
        }
        meta_path = self.processed_dir / "split_groups.json"
        meta_path.parent.mkdir(parents=True, exist_ok=True)
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)
        print(f"Saved split metadata to: {meta_path}")

        return split_items

    def resize_and_save_dataset(self, split_items: Dict[str, List[Dict]]):
        """Resize images to max 1280 px and save YOLO images and labels."""
        print(f"\nResizing images (max_size={self.max_size}px) and writing YOLO dataset...")

        for s in ["train", "val", "test"]:
            (self.detector_dir / "images" / s).mkdir(parents=True, exist_ok=True)
            (self.detector_dir / "labels" / s).mkdir(parents=True, exist_ok=True)

        counts_per_source_split = defaultdict(lambda: Counter())

        def _process_item(it, split):
            src_p = it["img_path"]
            source = it["source"]

            # Unique filename prefix per source to avoid any collision
            pfx = "lpd" if source == "license-plate-detection" else ("inp" if source == "indian-number-plates-dataset" else "ivd")
            base_name = f"{pfx}_{src_p.stem}{src_p.suffix.lower()}"
            lbl_name = f"{pfx}_{src_p.stem}.txt"

            dst_img = self.detector_dir / "images" / split / base_name
            dst_lbl = self.detector_dir / "labels" / split / lbl_name

            # Resize if max dimension > max_size
            try:
                with Image.open(src_p) as im:
                    im = ImageOps.exif_transpose(im)
                    im = im.convert("RGB")
                    w, h = im.size
                    if max(w, h) > self.max_size:
                        scale = self.max_size / float(max(w, h))
                        new_w = int(round(w * scale))
                        new_h = int(round(h * scale))
                        im = im.resize((new_w, new_h), Image.Resampling.LANCZOS)
                    im.save(dst_img, "JPEG", quality=92)
            except Exception as e:
                print(f"Error saving {src_p}: {e}")
                return False

            # Write YOLO label lines: 0 xc yc w h
            lines = [f"{cls_id} {xc:.6f} {yc:.6f} {w:.6f} {h:.6f}" for cls_id, xc, yc, w, h in it["boxes"]]
            dst_lbl.write_text("\n".join(lines) + "\n", encoding="utf-8")

            counts_per_source_split[source][split] += 1
            return True

        tasks = []
        for split, items in split_items.items():
            for it in items:
                tasks.append((it, split))

        with ThreadPoolExecutor(max_workers=8) as ex:
            ex.map(lambda p: _process_item(p[0], p[1]), tasks)

        # Write data.yaml
        data_yaml = (
            f"path: ../detector\n"
            f"train: images/train\n"
            f"val: images/val\n"
            f"test: images/test\n\n"
            f"names:\n"
            f"  0: plate\n"
        )
        yaml_path = self.detector_dir / "data.yaml"
        yaml_path.write_text(data_yaml, encoding="utf-8")
        print(f"Created YOLO config: {yaml_path}")

        # Print summary per split and source
        print("\n=== Detector Dataset Summary ===")
        print(f"{'Source':<35} | {'Train':<7} | {'Val':<7} | {'Test':<7} | {'Total':<7}")
        print("-" * 72)
        total_train = total_val = total_test = 0
        for src in ["license-plate-detection", "indian-number-plates-dataset", "indian-vehicle-dataset"]:
            tr = counts_per_source_split[src]["train"]
            va = counts_per_source_split[src]["val"]
            te = counts_per_source_split[src]["test"]
            tot = tr + va + te
            total_train += tr
            total_val += va
            total_test += te
            print(f"{src:<35} | {tr:<7} | {va:<7} | {te:<7} | {tot:<7}")
        print("-" * 72)
        print(f"{'TOTAL':<35} | {total_train:<7} | {total_val:<7} | {total_test:<7} | {total_train+total_val+total_test:<7}\n")

    def run(self):
        """Execute full detector data preparation pipeline."""
        print("=== Step 1: Preparing Detector Dataset ===")
        self.collect_license_plate_detection()
        self.collect_indian_number_plates_dataset()
        self.collect_indian_vehicle_dataset()

        unique_items = self.deduplicate_with_dhash()
        split_items = self.cluster_and_split_groups(unique_items)
        self.resize_and_save_dataset(split_items)
        print("Detector data preparation completed successfully!")


def main():
    parser = argparse.ArgumentParser(description="Prepare YOLO License Plate Detector Dataset")
    parser.add_argument("--raw-dir", type=str, default="data/raw", help="Path to raw data directory")
    parser.add_argument("--processed-dir", type=str, default="data/processed", help="Path to processed data directory")
    parser.add_argument("--max-size", type=int, default=1280, help="Max image dimension")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for splitting")
    args = parser.parse_args()

    preparer = DetectorDataPreparer(
        raw_dir=Path(args.raw_dir),
        processed_dir=Path(args.processed_dir),
        max_size=args.max_size,
        seed=args.seed,
    )
    preparer.run()


if __name__ == "__main__":
    main()
