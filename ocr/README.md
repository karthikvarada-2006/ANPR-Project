# Module 2: License Plate Detection & OCR (`ocr/`)

The **OCR** module is responsible for detecting vehicle license plates from real camera video frames or static images, extracting characters, and validating plate formats.

## 🎯 Key Objectives

1. **Plate Localization / Detection**:
   - Uses deep learning object detectors (e.g., YOLOv8-nano / YOLOv11 trained on license plates) to detect bounding boxes for vehicles and plates.
2. **Image Preprocessing**:
   - Crops detected license plate regions.
   - Applies perspective transformation to de-skew angled plates.
   - Performs contrast enhancement, grayscale conversion, and adaptive thresholding for poor lighting.
3. **Character Recognition (OCR)**:
   - Uses OCR engines (EasyOCR, Tesseract, or CRNN) to transcribe alphanumeric characters.
   - Extracts character-level confidence scores.
4. **Post-Processing & Validation**:
   - Standardizes plate text (removes whitespace and special characters).
   - Validates regex patterns (e.g., Indian high-security registration plates `^[A-Z]{2}[0-9]{1,2}[A-Z]{1,3}[0-9]{4}$`).
   - Fixes common optical confusion pairs (e.g., `O` vs `0`, `I` vs `1`, `8` vs `B`).

> **Note:** PyTorch, TorchVision, and Ultralytics (YOLO) dependencies will be added during the dedicated Module 2 implementation phase.
