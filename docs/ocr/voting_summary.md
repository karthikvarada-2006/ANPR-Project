# Multi-Frame Plate Voting Evaluation Report

This report evaluates temporal consensus plate voting across:
1. **Real Video Sequences** from the held-out TEST split (`indian-number-plates-dataset/video_images`).
2. **Synthetic Approaching Clips** generated from held-out TEST split photos (`data/video_events/synthetic/`).

---

## 1. Table 1: Real Video Sequences (`video_images`)

| Metric | All Real Sequences (N=20) | Multi-Frame Only (N=11) | Single-Frame Only (N=9) |
| :--- | :---: | :---: | :---: |
| **Average Frames / Sequence** | 3.80 | 6.09 | 1.00 |
| **Per-Frame Average Exact Match** | 85.24% | 82.25% | 88.89% |
| **Voted Consensus Exact Match** | **90.00%** | **90.91%** | **88.89%** |
| **Exact Match Delta** | **+4.76%** | **+8.66%** | **+0.00%** |
| **Per-Frame Average Char Acc** | 95.95% | 97.19% | 94.44% |
| **Voted Consensus Char Acc** | **97.00%** | **99.09%** | **94.44%** |
| **Character Accuracy Delta** | **+1.05%** | **+1.91%** | **0.00%** |

> [!WARNING]
> **Single-Frame Limitation on Real Sequences:**
> In this test video split, **9 out of 20 sequences (45.0%)** consist of exactly **one frame**.
> Voting fundamentally relies on temporal consensus across multiple independent looks at the vehicle plate. On single-frame detections, voting is an identity operation—it cannot correct errors or resolve consensus because no second reading exists.

---

## 2. Table 2: Synthetic Approaching Video Clips (`synthetic/`)

> [!CAUTION]
> **Optimistic Benchmark Notice:**
> These clips are synthetic and all frames of one clip originate from a single static photo in the TEST split, transformed across 24 frames with zoom, pan, noise, and compression.
> Consequently, multi-frame voting gains on them are **optimistic and must not be reported as real-world results**.

| Metric Scope | Per-Frame Average | Voted Consensus | Delta |
| :--- | :---: | :---: | :---: |
| **Synthetic Clips (Exact Match, N=60)** | 66.87% | **78.33%** | **+11.46%** |
| **Synthetic Clips (Character Accuracy)** | 89.46% | **97.10%** | **+7.63%** |

---

## 3. Detailed Results Preview

| Sequence / Clip | Type | Ground Truth | Frames | Voted Plate | Frame Exact (Avg) | Voted Exact | Frame Char Acc | Voted Char Acc | Margin |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `real_01` | `real` | `MH02EK4399` | 2 | `MH02EK4399` | 100.0% | 100.0% (MATCH) | 100.0% | 100.0% | 1.00 |
| `real_02` | `real` | `MH02EU4884` | 4 | `MH02EU4884` | 100.0% | 100.0% (MATCH) | 100.0% | 100.0% | 1.00 |
| `real_03` | `real` | `MH02DN8718` | 14 | `MH02DN8718` | 100.0% | 100.0% (MATCH) | 100.0% | 100.0% | 1.00 |
| `real_04` | `real` | `MH02BJ2456` | 3 | `MH02BJ2456` | 100.0% | 100.0% (MATCH) | 100.0% | 100.0% | 1.00 |
| `real_05` | `real` | `MH02BR4503` | 1 | `MH02BR4503` | 100.0% | 100.0% (MATCH) | 100.0% | 100.0% | 1.00 |
| `real_06` | `real` | `MH01DP5662` | 1 | `MH01DP5662` | 100.0% | 100.0% (MATCH) | 100.0% | 100.0% | 1.00 |
| `real_07` | `real` | `MH02EN6828` | 1 | `MH022N5` | 0.0% | 0.0% (MISMATCH) | 50.0% | 50.0% | 1.00 |
| `real_08` | `real` | `DL8CN6308` | 7 | `DL8CN63308` | 0.0% | 0.0% (MISMATCH) | 78.6% | 90.0% | 0.71 |
| `real_09` | `real` | `MH47Y0205` | 4 | `MH47Y0205` | 100.0% | 100.0% (MATCH) | 100.0% | 100.0% | 1.00 |
| `real_10` | `real` | `MH02EK5817` | 1 | `MH02EK5817` | 100.0% | 100.0% (MATCH) | 100.0% | 100.0% | 1.00 |
| `synth_001` | `synthetic` | `PB10CQ0006` | 24 | `PB10EQ0006` | 12.5% | 0.0% (MISMATCH) | 85.4% | 90.0% | 0.88 |
| `synth_002` | `synthetic` | `HR26DK0830` | 24 | `HR26DK0830` | 100.0% | 100.0% (MATCH) | 100.0% | 100.0% | 1.00 |
| `synth_003` | `synthetic` | `WB06F9209` | 24 | `MB06F9209` | 20.8% | 0.0% (MISMATCH) | 83.4% | 88.9% | 0.93 |
| `synth_004` | `synthetic` | `TR01N0481` | 24 | `TR01N0481` | 79.2% | 100.0% (MATCH) | 96.2% | 100.0% | 0.99 |
| `synth_005` | `synthetic` | `PB31R8123` | 24 | `PB31R8123` | 91.7% | 100.0% (MATCH) | 97.0% | 100.0% | 1.00 |
| `synth_006` | `synthetic` | `PB02DY7380` | 24 | `PB02DY7380` | 79.2% | 100.0% (MATCH) | 92.5% | 100.0% | 0.95 |
| `synth_007` | `synthetic` | `TN59BE0939` | 24 | `TN59BE0939` | 75.0% | 100.0% (MATCH) | 82.5% | 100.0% | 0.97 |
| `synth_008` | `synthetic` | `CG251612` | 24 | `CO251612` | 12.5% | 0.0% (MISMATCH) | 83.3% | 87.5% | 0.90 |
| `synth_009` | `synthetic` | `MH02EK5817` | 24 | `MH02EK5817` | 70.8% | 100.0% (MATCH) | 87.9% | 100.0% | 0.91 |
| `synth_010` | `synthetic` | `KL54H369` | 24 | `KL54H369` | 87.5% | 100.0% (MATCH) | 94.9% | 100.0% | 1.00 |
