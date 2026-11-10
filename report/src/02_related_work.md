# 2. RELATED WORK AND THEORETICAL STUDY

## 2.1 License Plate Detection and OCR Techniques

Automated number-plate recognition (ANPR) systems traditionally follow a two-stage computer vision pipeline: first localising the license plate bounding box within a camera frame, and second transcribing the alphanumeric character sequence from the cropped region. Early detection systems relied on handcrafted visual features, including vertical edge density, morphological gradients, colour saliency filters, and Haar-like wavelets classified via AdaBoost or Support Vector Machines. While computationally lightweight, these classical techniques degrade severely under non-uniform illumination, perspective tilt, complex vehicle bodywork, and shadowed backgrounds.

The introduction of convolutional neural networks (CNN) fundamentally transformed object detection. The You Only Look Once (YOLO) framework introduced by Redmon et al. [5] reframed detection as a single-stage spatial regression problem, predicting bounding box coordinates and class probabilities directly from full images in a single forward pass. Subsequent iterations optimized feature pyramid networks, path aggregation, and anchor-free regression heads. In a recent 2025 study published in *Scientific Reports* [2], researchers proposed an improved YOLOv5s architecture coupled with an LPRNet recognition backbone for multi-scene license plate detection and transcription, reporting superior localization accuracy on Chinese and international benchmarks. Concurrently, Ultralytics YOLOv8 [9] introduced an anchor-free split-head architecture with decoupled classification and regression branches, providing state-of-the-art detection accuracy and sub-millisecond edge latency on embedded GPUs and modern multi-core CPUs.

For optical character recognition, early deep architectures employed Connectionist Temporal Classification (CTC) over recurrent neural networks (RNN) or LPRNet [6]. LPRNet eliminates recurrent layers in favour of spatial inception blocks, outputting character probability distributions directly to CTC loss without requiring individual character segmentation. More recently, vision transformers have demonstrated superior character sequence modeling. The Compact Convolutional Transformer (CCT) architecture implemented in `fast-plate-ocr` [10] combines convolutional tokenization with multi-head self-attention mechanisms. By avoiding heavy recurrent gates, CCT models achieve sub-10 ms CPU inference per crop while maintaining robustness against character rotation, dirt smudges, and non-standard typography common in developing countries.

## 2.2 Multi-Object and Multi-Camera Vehicle Tracking

Tracking detected vehicles across consecutive frames is essential for aggregating multi-frame visual information and suppressing transient misclassifications. Single-camera Multi-Object Tracking (MOT) algorithms typically adopt the tracking-by-detection paradigm. Classical approaches, such as SORT and DeepSORT, utilise Kalman filtering to propagate spatial bounding box state vectors across time, associating current detections with existing tracklets using the Hungarian algorithm based on spatial Intersection over Union (IoU) and deep visual appearance embeddings.

However, standard MOT algorithms frequently drop valid tracks during brief vehicle occlusions or when detection confidence scores dip due to motion blur. To resolve this, Zhang et al. [4] introduced ByteTrack, which associates almost every detection box regardless of confidence. Instead of discarding low-scoring detections, ByteTrack partitions detections into high-confidence and low-confidence pools. High-confidence detections are matched first; unmatched tracks are then associated with low-confidence boxes, preserving track continuity through partial occlusions and camera noise without requiring heavy deep Re-ID feature extraction.

Across multi-camera networks (Multi-Target Multi-Camera, or MTMC tracking), spatial continuity breaks down because cameras are non-overlapping. Tran et al. [3] investigated cross-camera tracking by fusing visual Re-ID embeddings with spatial-temporal transition matrices across highway camera networks. However, in dense urban street grids with identical vehicle models, deep appearance vectors exhibit significant ambiguity. In our work, we prioritize definitive alphanumeric license plate identity over visual Re-ID, using physical road network routing and travel-time bounds to validate vehicle transitions across camera networks.

## 2.3 City-Scale Trajectory Reconstruction Datasets

Research in urban traffic flow modeling and intelligent transportation systems relies heavily on large-scale trajectory benchmarks. In 2023, Yu et al. [1] published a landmark benchmark in *Scientific Data* providing city-scale vehicle trajectories collected from Jinan, China. The Jinan dataset documents over 1.18 million vehicle trips and 963,125 unique vehicles traversing a topological road network comprising 8,908 street nodes, of which 1,651 nodes feature surveillance camera sensors.

While the Jinan benchmark provides unprecedented macroscopic scale for urban mobility modeling, it suffers from two major operational constraints for ANPR engineering:
1. **Omission of Alphanumeric Identifiers:** To comply with national privacy regulations, all license plate strings were stripped and replaced with arbitrary synthetic integer identifiers.
2. **Absence of Raw Camera Imagery:** The dataset provides spatial-temporal event tuples but includes no video or image feeds, preventing researchers from studying the coupling between optical vision errors and graph trajectory reconstruction.

To model road network topology programmatically, Boeing [7] developed OSMnx, a Python framework that downloads, constructs, and visualises complex street networks directly from OpenStreetMap (OSM). OSMnx models intersections as graph nodes and road segments as directed edges carrying geographic length, lane counts, and speed limit attributes. In this project, we exploit OSMnx to construct a 5 km radius road network graph of Bangalore, enabling realistic vehicular mobility modeling and Dijkstra-based shortest-path travel time precomputation.

## 2.4 Urban Traffic Flow Analytics and Anomaly Alert Systems

Urban traffic management centres utilize camera observations to compute macroscopic flow parameters defined by the Highway Capacity Manual. Key indicators include segment flow volume ($q$, vehicles per hour), mean transit velocity ($v$, km/h), vehicular density ($k$, vehicles per km), and Level of Service (LOS) ratings ranging from free-flow (LOS A) to severe breakdown (LOS F). Traditional municipal systems compute these metrics from inductive loop sensors embedded in roadway asphalt. However, physical loops cannot track vehicle identities across space, making them incapable of measuring true Origin-Destination (OD) trip distributions.

Surveillance alert systems in intelligent transportation platforms enforce traffic compliance and assist law enforcement. Automated alert rules commonly monitor:
- **Watchlists / Blacklists:** Real-time flagging of stolen vehicles, wanted suspects, or unregistered vehicles against criminal databases.
- **Cloned Plate Anomalies:** Detecting two physical sightings of the same license plate at distant geographic locations within an impossibly short time interval, indicating that one or both vehicles are operating with forged or cloned plates.
- **Access Restrictions:** Enforcing commercial truck curfews in dense residential corridors during night-time hours.
- **Speed Enforcement:** Identifying vehicles exceeding posted corridor speed limits.

Conventional rule engines frequently suffer from high false alarm rates. In high-throughput streaming environments, transient OCR misreads produce spurious plate collisions that mimic cloned vehicles or trigger false blacklist hits. Robust surveillance systems must incorporate sliding-window incident de-duplication, fuzzy string thresholds, and shortest-path road distance verification to prevent operator notification fatigue.

## 2.5 Vehicle Movement Counting Benchmarks

Automated vehicle counting at urban road intersections is critical for optimizing traffic signal cycles and evaluating junction capacity. The IEEE AI City Challenge, organized annually by Naphade et al. [8], established Track 1 as the international standard benchmark for multi-class multi-movement vehicle counting from fixed roadside video streams.

In the AI City Challenge Track 1 benchmark, an intersection is defined by a Region of Interest (ROI) polygon and a set of predefined directional movement trajectories (such as through-movements, left turns, and right turns). Participating systems must count the cumulative number of vehicles completing each specific movement, categorized by vehicle class (cars, trucks, and buses). Vehicles that park, loiter, or enter and exit via the same roadway branch without completing a valid turn must be filtered out.

Most existing literature approaches vehicle counting by manually defining virtual tripwire lines across lane boundaries. However, roadside cameras experience perspective foreshortening, lens distortion, and optical occlusions, causing rigid tripwires to miscount vehicles that deviate slightly from lane centres. In this work, we implement a trajectory assignment algorithm that evaluates the complete vehicle tracklet against calibrated directional movement vectors, demonstrating the vital necessity of empirical centroid calibration.

## 2.6 Theoretical Foundations and Metric Formulations

To ensure rigorous quantitative evaluation, we establish formal mathematical definitions for all computer vision, statistical confidence, and graph routing metrics utilized throughout this report.

### 2.6.1 Precision, Recall, and F1-Score
Binary classification performance across object detection, trajectory matching, and surveillance alerting is evaluated using True Positives ($TP$), False Positives ($FP$), and False Negatives ($FN$):

$$\text{Precision} = \frac{TP}{TP + FP} \tag{2.1}$$

$$\text{Recall} = \frac{TP}{TP + FN} \tag{2.2}$$

The F1-score represents the harmonic mean of precision and recall, providing a balanced single metric that penalises extreme imbalances:

$$F_1 = 2 \cdot \frac{\text{Precision} \cdot \text{Recall}}{\text{Precision} + \text{Recall}} = \frac{2 \cdot TP}{2 \cdot TP + FP + FN} \tag{2.3}$$

### 2.6.2 Mean Average Precision (mAP)
Object detection localisation accuracy is evaluated using Mean Average Precision across Intersection over Union (IoU) thresholds. Given a predicted bounding box $B_p$ and a ground-truth box $B_{gt}$, spatial overlap is computed via the Jaccard index:

$$\text{IoU}(B_p, B_{gt}) = \frac{\text{Area}(B_p \cap B_{gt})}{\text{Area}(B_p \cup B_{gt})} \tag{2.4}$$

A detection is counted as a True Positive if $\text{IoU}(B_p, B_{gt}) \ge \tau$, where $\tau = 0.50$ for standard mAP@50. The Average Precision (AP) corresponds to the area under the interpolated precision-recall curve $p(r)$:

$$\text{AP} = \int_{0}^{1} p(r) \, dr \tag{2.5}$$

The metric mAP@50-95 averages AP scores across 10 evenly spaced IoU thresholds from $\tau = 0.50$ to $\tau = 0.95$ with step size $\Delta \tau = 0.05$.

### 2.6.3 Character-Level and Full-Plate Exact Match Accuracies
Optical character recognition performance is evaluated at both the macroscopic string level and the microscopic character level. Full-plate exact match accuracy measures the percentage of plates where the predicted string $\hat{S}$ identically matches the ground truth string $S$:

$$\text{Acc}_{\text{plate}} = \frac{1}{N} \sum_{i=1}^{N} \mathbb{I}(\hat{S}_i = S_i) \tag{2.6}$$

where $\mathbb{I}(\cdot)$ is the indicator function returning 1 if the strings are identical and 0 otherwise.

Character-level accuracy measures transcription fidelity using the Levenshtein edit distance $\mathcal{L}(\hat{S}, S)$, defined as the minimum number of single-character insertions, deletions, or substitutions required to transform $\hat{S}$ into $S$:

$$\text{Acc}_{\text{char}} = \frac{1}{N} \sum_{i=1}^{N} \max\left(0, 1 - \frac{\mathcal{L}(\hat{S}_i, S_i)}{\max(|S_i|, |\hat{S}_i|)}\right) \tag{2.7}$$

where $|S|$ denotes string character length.

### 2.6.4 Wilson Score Confidence Interval Formulation
When evaluating accuracy over small empirical test sets (such as $N = 20$ video sequences or $N = 57$ counting events), sample proportions $\hat{p} = k/N$ carry significant statistical uncertainty. Standard normal approximation intervals fail near boundary proportions ($\hat{p} \approx 0.90$ or $1.00$). We therefore compute asymmetric two-sided 95% confidence intervals using the Wilson score interval:

$$CI_{95\%} = \frac{\hat{p} + \frac{z^2}{2N} \pm z \sqrt{\frac{\hat{p}(1 - \hat{p})}{N} + \frac{z^2}{4N^2}}}{1 + \frac{z^2}{N}} \tag{2.8}$$

where $z = 1.95996$ corresponds to the standard normal quantile for $\alpha = 0.05$. For 18 successes out of 20 trials ($\hat{p} = 0.90$), Equation (2.8) yields an asymmetric interval of $[69.9\%, 97.2\%]$, rigorously capturing the $\pm 13$ percentage point uncertainty inherent in small-sample evaluations.

### 2.6.5 Temporal Event Matching Metric
In vehicle movement counting evaluation, predicted counting events $e_p = (t_p, m_p, c_p)$ are matched against ground-truth events $e_{gt} = (t_{gt}, m_{gt}, c_{gt})$, where $t$ denotes video frame index, $m$ denotes movement identifier, and $c$ denotes vehicle class. A predicted event is an eligible match for a ground-truth event if they share identical movement and class assignments, and their temporal frame discrepancy falls within a maximum tolerance window $\Delta t_{\max} = 20$ frames:

$$\text{Match}(e_p, e_{gt}) = \mathbb{I}(m_p = m_{gt}) \cdot \mathbb{I}(c_p = c_{gt}) \cdot \mathbb{I}(|t_p - t_{gt}| \le \Delta t_{\max}) \tag{2.9}$$

Eligible pairs are greedily matched in order of minimum absolute frame difference $|t_p - t_{gt}|$, with each ground truth and predicted event matched at most once.

## 2.7 Research Gap and Comparative Analysis

Existing literature in intelligent transportation systems exhibits a persistent bifurcation: computer vision researchers focus on visual detection and tracking over isolated intersection videos without modeling city-wide graph dynamics, while transportation network researchers analyze macroscopic trajectory graphs while treating vehicle identification as a synthetic, error-free abstraction.

Table 2.1 provides a structured comparative analysis contrasting our proposed system against the three foundational base papers identified in the literature review:
1. **Yu et al. (2023) [1]:** Macroscopic vehicle trajectory mining on real-world Jinan city traffic networks.
2. **Scientific Reports (2025) [2]:** Deep-learning license plate detection and LPRNet recognition on static image benchmarks.
3. **Tran et al. (2022) [3]:** Multi-target multi-camera (MTMC) tracking across highway surveillance cameras.

Table 2.1: Comparative Analysis of Base Papers with the Proposed System
| Evaluation Dimension | Yu et al. (2023) [1] | Scientific Reports (2025) [2] | Tran et al. (2022) [3] | Proposed System (This Work) |
| :--- | :--- | :--- | :--- | :--- |
| **Primary Domain** | Macroscopic Trajectory Mining | Optical Plate Detection & OCR | Multi-Camera Vehicle Tracking | Integrated End-to-End ANPR Engine |
| **Perception Input** | None (Tabular Sensor Tuples) | Static Multi-Scene Photographs | Multi-Camera Video Streams | Full Frames, Videos & Synthetic City |
| **Detection Backbone** | Not Applicable | Improved YOLOv5s | Mask R-CNN / ResNet | Ultralytics YOLOv8s (Anchor-Free) |
| **OCR Architecture** | Not Applicable | LPRNet (CNN + CTC Loss) | None (Visual Appearance Only) | Compact Conv Transformer (CCT-s-v2) |
| **Tracking Paradigm** | Spatial Node Traversal | None (Single-Image Only) | Deep Appearance Re-ID (MTMC) | ByteTrack + Positional Consensus Voting |
| **Noise Tolerance** | Assumes Clean Sensor IDs | Evaluated on Static Images | Visual Lighting / Skew Robust | Weighted Levenshtein (Fuzzy Distance 1.0) |
| **Graph Routing** | Empirical Node Sequences | None | Transition Probability Matrix | OpenStreetMap Dijkstra Shortest Paths |
| **Surveillance Alerting** | None | None | Stolen Vehicle Flagging | Multi-Rule Engine (Blacklist, Clones, Curfew) |
| **Vehicle Counting** | Macroscopic Link Volumes | None | Highway Tripwire Counts | Calibrated Directional Movement Assignment |
| **User Interface** | Offline Data Archive | Standalone Evaluation Scripts | Offline Research Benchmark | Interactive Web Dashboard (FastAPI/Leaflet) |
| **Data Realism** | REAL (Jinan, 1.18M Trips) | REAL (Static Plate Datasets) | REAL (Highway CCTV Footage) | REAL (Vision/Counting) + SIMULATED (City) |

As established in Table 2.1, our work bridges these disparate domains into a unified, operational intelligence engine. By integrating real-world visual perception, noise-tolerant fuzzy graph routing, empirical movement calibration, and real-time streaming surveillance into a single architecture, this project provides a reproducible blueprint for metropolitan intelligent transportation governance.

