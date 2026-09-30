# Module 3: Single-Camera Tracking & Plate Voting (`tracking/`)

The **Tracking** module maintains vehicle identity across consecutive video frames within a single camera's field of view and combines multiple OCR reads into a high-confidence consensus result.

## 🎯 Key Objectives

1. **Multi-Object Tracking (MOT)**:
   - Tracks detected vehicles across video frames using algorithms like **ByteTrack** or **DeepSORT**.
   - Maintains continuous track IDs using Kalman filtering and bounding-box IoU (Intersection-over-Union) matching.
2. **Track-to-Plate Association**:
   - Associates detected license plates with their parent vehicle bounding boxes.
   - Handles occlusion, entry, and exit from camera scenes.
3. **Multi-Frame Plate Voting**:
   - An OCR reading from a single frame may suffer from motion blur, glare, or partial occlusion.
   - Collects OCR candidates across all frames in a tracklet (e.g., 15–30 frames).
   - Uses **confidence-weighted majority voting** or character-level Levenshtein consensus to deduce the true plate number.
4. **Consolidated Event Emission**:
   - Once a vehicle exits the camera frame, generates a single canonical sighting record:
     `{track_id, camera_id, consensus_plate, first_seen, last_seen, mean_confidence, vehicle_class}`.
