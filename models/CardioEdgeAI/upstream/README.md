<div align="center">

# ❤️ CardioEdgeAI

**Lightweight deep learning for real-time ECG arrhythmia detection on edge & wearable devices**

[![License: MIT](https://img.shields.io/badge/License-MIT-007EC7.svg)](LICENSE)
[![Python 3.14](https://img.shields.io/badge/Python-3.14-3776AB?logo=python&logoColor=white)](requirements.txt)
[![TensorFlow 2.22](https://img.shields.io/badge/TensorFlow-2.22-FF6F00?logo=tensorflow&logoColor=white)](requirements.txt)
[![Model](https://img.shields.io/badge/Model-23.8KB_INT8-success)](models/)
[![Accuracy](https://img.shields.io/badge/DS2_accuracy-94.3%25-brightgreen)](docs/RESULTS.md)
[![Macro-F1](https://img.shields.io/badge/Macro--F1-0.712-blue)](docs/RESULTS.md)
[![Docs](https://img.shields.io/badge/docs-passing-brightgreen)](tests/check_docs.py)
[![Tests](https://img.shields.io/badge/e2e_tests-passing-brightgreen)](tests/test_live_pipeline.py)

*A 94 %-accurate arrhythmia classifier that fits in 24 KB and runs beat-by-beat on an ESP32-S3 — no cloud, no PC.*

</div>

---

## 📖 Table of contents

1. 🏆 [Results at a glance](#-results-at-a-glance)
2. ❓ [Problem](#-problem)
3. ⚙️ [How it works](#%EF%B8%8F-how-it-works)
4. 🧠 [Model architecture](#-model-architecture)
5. 🗂️ [Dataset & evaluation protocol](#%EF%B8%8F-dataset--evaluation-protocol)
6. 🔍 [Key research findings](#-key-research-findings)
7. 📁 [Repository structure](#-repository-structure)
8. 📁 [Project documentation](#-project-documentation)
9. 🔁 [Full reproduction guide](#-full-reproduction-guide)
10. 🚀 [Deployment (ESP32-S3 + TFLite Micro)](#-deployment-esp32-s3--tflite-micro)
11. 🫀 [The lab machine](#-the-lab-machine)
12. 🔴 [Live data from the CardioTouch 3000](#-live-data-from-the-cardiotouch-3000)
13. ⚠️ [Limitations & future work](#%EF%B8%8F-limitations--future-work)
14. 🛡️ [Ethics & safety](#%EF%B8%8F-ethics--safety)
15. 📚 [References](#-references)

---

## 🏆 Results at a glance

Evaluation on **MIT-BIH DS2 (inter-patient)** — 50,026 beats from 22 recordings whose patients were **never seen in training**. Primary metric: macro-F1 (classes are ~90 / 3 / 7 % imbalanced).

| # | Model | Params | Size | Acc | Macro-F1 | N F1 | S F1 | V F1 |
|---|---|---|---|---|---|---|---|---|
| 1 | 📐 Logistic Regression (RR + morphology) | — | — | 84.3 % | 0.603 | 0.914 | 0.240 | 0.655 |
| 2 | 🌲 Random Forest (RR + morphology) | — | — | 94.3 % | 0.650 | 0.971 | 0.100 | 0.880 |
| 3 | 🚫 1D CNN, morphology only *(rejected)* | 11,443 | — | 81.1 % | 0.522 | 0.888 | 0.042 | 0.634 |
| 4 | 🧠 1D CNN + RR branch (float32) | 11,571 | 211 KB | 94.4 % | 0.706 | 0.971 | 0.295 | 0.851 |
| 5 | 🧪 v2 float (S-oversampling, not deployed) | 11,571 | 211 KB | 93.7 % | **0.718** | 0.966 | **0.389** | 0.800 |
| 6 | 🏁 **v1, TFLite full-INT8 — deployed** | 11,571 | **23.8 KB** | **94.3 %** | 0.712 | 0.970 | 0.320 | 0.847 |

- 🗜️ INT8 quantization: **8.9× smaller** than the training artifact — with **zero accuracy loss** on the deployed model
- ⚡ Laptop-replay latency: **0.02 ms/beat** (~54,600 beats/s; real time needs 1–2)
- 🎯 Inference-time R-peak detector (NeuroKit): **F1 0.934** vs gold annotations

> 📊 Every number, table and ablation: [`docs/RESULTS.md`](docs/RESULTS.md)

## ❓ Problem

Cardiac arrhythmias are often intermittent, so reliable screening needs **continuous, long-term ECG monitoring**. Cloud-based deep learning is too large and power-hungry for wearable and edge hardware, which has only a few hundred KB of RAM and a battery that must last days. The question this project answers:

> *How small and fast can an accurate arrhythmia detector become — and what accuracy survives aggressive compression on real hardware?*

## ⚙️ How it works

```
ECG signal (MIT-BIH, MLII lead, native 360 Hz)
        │
        ▼
Preprocessing ──── zero-phase 0.5–40 Hz Butterworth bandpass
                   per-record z-score normalization
        │
        ▼
Beat windows ───── R-peak centered: 0.4 s before / 0.6 s after = 360 samples
        │
        ▼
Two-branch model ─ morphology CNN  +  4 RR-timing features
        │
        ▼
INT8 quantization ─ full-integer, stratified calibration
        │
        ▼
Edge deploy ─────── TFLite Micro on ESP32-S3 · watch-folder live demo
        │
        ▼
Profiling ───────── accuracy · latency · RAM · flash · energy
```

## 🧠 Model architecture

**11,571 parameters** (v1, deployed). The morphology branch uses `Conv2D` with `(1, k)` kernels on a `(batch, 1, time, 1)` tensor — mathematically identical to Conv1D, but required because TFLite's integer quantizer cannot calibrate a graph whose first op is Conv1D.

```
beat window (360 × 1)
  → Reshape(1, 360, 1)
  → Conv2D(16, (1,7)) → BN → ReLU → MaxPool(1,2)
  → Conv2D(32, (1,5)) → BN → ReLU → MaxPool(1,2)
  → Conv2D(64, (1,3)) → BN → ReLU → GlobalAvgPool   (64 features)
                                                      \
4 RR-timing scalars ────────────────────────────────→ concat → Dense(32)
                                                     → Dropout(0.3)
                                                     → Dense(3, softmax)
```

RR features (computed identically on the ESP32, fixed physiological normalization mean 0.8 s / std 0.3 s): pre-RR, post-RR, local mean of the 5 preceding RRs, pre/local ratio. Post-RR costs one beat of latency — a documented trade-off for the strongest S-class feature.

<details>
<summary>🔧 Training configuration</summary>

Adam 1e-3 · batch 256 · ≤ 25 epochs · early stopping (patience 8) on four patient-separated validation records (215/220/223/230) · class weights {N:0.6, S:8, V:2} · seed 42 — re-runs are bit-identical.

</details>

## 🗂️ Dataset & evaluation protocol

| Set | Beats | N | S | V |
|---|---|---|---|---|
| 🏋️ DS1 fit (training) | 40,320 | 36,397 | 773 | 3,150 |
| 🛑 DS1 val (early stopping) | 10,250 | 9,442 | 170 | 638 |
| 🧪 DS2 (test) | 50,026 | 44,742 | 1,837 | 3,447 |
| **Σ Total** | **100,596** | **90,581** | **2,780** | **7,235** |

- **Task** — beat classification into AAMI groups **N / S / V** (F and Q excluded in v1, reported as out of scope)
- **Inter-patient splits** (standard DS1/DS2) — no patient appears in both train and test; the honest (much harder) protocol
- **Metrics** — accuracy, macro-F1 (primary), per-class P/R/F1, confusion matrices (`docs/results.json`)
- **Source** — [MIT-BIH Arrhythmia Database](https://physionet.org/content/mitdb/1.0.0/): 48 half-hour records, 360 Hz, cardiologist beat annotations

## 🔍 Key research findings

| # | Finding | Evidence |
|---|---|---|
| 1️⃣ | **Morphology alone cannot detect S beats inter-patient** — supraventricular ectopy is defined by *premature timing*. Adding 4 cheap RR scalars tripled S-F1 (0.10 → 0.30) | `docs/PHASE4.md` |
| 2️⃣ | **The textbook R-detector default is a trap**: Pan-Tompkins scored F1 = 0.63 on filtered signals (missed ~⅓ of beats); NeuroKit's scored 0.93 — the largest end-to-end accuracy fix | `src/evaluation/r_detector_eval.py` |
| 3️⃣ | **Oversampling buys float accuracy and sells quantization robustness** — v2 hit 0.718 float but collapsed under INT8 PTQ under *every* calibration strategy | `docs/RESULTS.md` |
| 4️⃣ | **TFLite cannot integer-quantize Conv1D-first graphs** (`conv.cc input->dims->size != 4`) — the `Conv2D((1,k))` pattern fixes it for free | `docs/PHASE5.md` |
| 5️⃣ | **Quantization acted as a mild regularizer** — INT8 marginally outperformed float on the deployed model | `docs/RESULTS.md` |

## 📓 Colab notebooks

Interactive previews — each link opens directly in Google Colab (no setup needed):

| Notebook | Contents |
|---|---|
| [![Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/md-rejoyan-islam/CardioEdgeAI/blob/main/notebooks/MIT_BIH_Preview_Colab.ipynb) [MIT-BIH Preview](https://colab.research.google.com/github/md-rejoyan-islam/CardioEdgeAI/blob/main/notebooks/MIT_BIH_Preview_Colab.ipynb) | Raw ECG, filtering, R-peaks, N/S/V beat windows, patient table |
| [![Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/md-rejoyan-islam/CardioEdgeAI/blob/main/notebooks/Datasets_Preview_Colab.ipynb) [Datasets Preview](https://colab.research.google.com/github/md-rejoyan-islam/CardioEdgeAI/blob/main/notebooks/Datasets_Preview_Colab.ipynb) | afdb AF episodes, PTB-XL 12-lead ECGs + diagnoses, Chapman-Shaoxing |
| [![Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/md-rejoyan-islam/CardioEdgeAI/blob/main/notebooks/Arrhythmia_Types_Colab.ipynb) [Arrhythmia Graphs](https://colab.research.google.com/github/md-rejoyan-islam/CardioEdgeAI/blob/main/notebooks/Arrhythmia_Types_Colab.ipynb) | ECG graphs of 19 arrhythmia types (self-contained, runs in seconds) |

## 📁 Repository structure

```
CardioEdgeAI/
├── 📂 data/                # raw PhysioNet + processed beats + external (git-ignored)
├── 📂 src/
│   ├── ⚙️ config.py        # all constants: rates, windows, AAMI map, splits, seed
│   ├── 📂 data/            # download · preprocess · visualize · cardiotouch adapter
│   ├── 📂 features/        # Phase 3 classical baselines (RR + morphology)
│   ├── 📂 models/          # v1 CNN · v2 ablation · INT8 quantization
│   └── 📂 evaluation/      # metrics/reports · R-detector evaluation
├── 📂 deploy/
│   ├── 📂 tflite/          # model.h exporter + latency benchmark
│   └── 📂 esp32/           # TFLite Micro firmware + generated model.h
├── 📂 machine/             # the lab ECG machine (photos · manuals · electrodes · protocol)
├── 📂 tools/               # watch-folder classifier · RS-232 capture
├── 📂 tests/               # e2e live-pipeline test · docs checker
├── 📂 docs/                # phase reports · results · live-demo · figures
├── 📄 requirements.txt     # pinned (Python 3.14 · TF 2.22.0rc0)
├── 📄 CITATION.cff · LICENSE (MIT)
```

## 🔁 Full reproduction guide

> 💡 Environment: Python 3.14+, ~2 GB disk, CPU-only. Training the CNN takes **~3 minutes** on a modern laptop.

```bash
git clone https://github.com/md-rejoyan-islam/CardioEdgeAI.git
cd CardioEdgeAI
py -m venv .venv && .venv\Scripts\activate    # or your usual python
pip install -r requirements.txt
```

<details>
<summary>▶️ Run the full pipeline (each step prints its own results)</summary>

```bash
py src/data/download_mitbih.py            # 1️⃣  ~85 MB PhysioNet fetch
py src/data/visualize.py                  # 2️⃣  signal-quality figures
py src/data/preprocess.py                 # 3️⃣  builds the beat dataset
py src/features/classical.py              # 4️⃣  LR + RF baselines
py src/models/cnn.py                      # 5️⃣  v1 model (94.4 % float)
py src/models/cnn_v2.py                   # 6️⃣  ablation model (0.718, float)
py src/evaluation/r_detector_eval.py      # 7️⃣  detector comparison (~10 min)
py src/models/quantize.py                 # 8️⃣  23.8 KB INT8 + interpreter eval
py deploy/tflite/export_model_header.py   # 9️⃣  regenerates ESP32 model.h
py deploy/tflite/benchmark.py             # 🔟  latency benchmark
py tests/test_live_pipeline.py            # ✅  full live-path test (must pass)
```

</details>

Classify any exported recording directly:

```bash
py src/data/cardiotouch.py --file recording.csv       # .csv / .txt / .wav
py src/data/cardiotouch.py --file x.csv --fs 1000     # no time column
```

## 🚀 Deployment (ESP32-S3 + TFLite Micro)

| 🧰 Hardware | Connection |
|---|---|
| ESP32-S3 DevKitC | USB → PC |
| AD8232 front end | OUT → GPIO4, 3V3, GND; electrodes RA/LA/RL |

Software: Arduino IDE + **esp32** board package + **TensorFlowLite_ESP32** library. Upload `deploy/esp32/CardioEdgeAI/CardioEdgeAI.ino`, open Serial Monitor @ 115200 — every detected beat prints `BEAT <N|S|V> conf=… rr_pre=… rr_post=…`.

<details>
<summary>📊 Memory budget & firmware pipeline</summary>

- 23.8 KB model (flash) + 48 KB tensor arena + 14.4 KB rolling buffer ≪ **512 KB** ESP32-S3 SRAM
- Firmware mirrors training exactly: same biquads, 10 s rolling z-score, fixed RR normalization, round-to-nearest int8 (verified equal to the Python eval path)
- Previous beat is classified on each new R peak (post-RR needs the next beat): one-beat latency at 1–2 classifications/s

</details>

Full details: 📄 [`docs/PHASE6.md`](docs/PHASE6.md) · 📄 [`deploy/esp32/README.md`](deploy/esp32/README.md)

## 🫀 The lab machine

The external-validation data source — 📷 photos of the actual unit, its signal chain, ⚡ electrode physics & 12-lead placement, and the complete record-and-export protocol live in [`machine/`](machine/README.md) (includes a 🇧🇩 Bengali practical guide).

| Folder | Contents |
|---|---|
| [`machine/images/`](machine/images/) | Lab-unit photos (HEIC → JPG) |
| [`machine/manuals/`](machine/manuals/) | Practical guide (Bengali docx) |
| [`machine/electrodes/`](machine/electrodes/) | Electrode physics + 12-lead placement |
| [`machine/data-collection/`](machine/data-collection/) | Recording & export protocol |

## 🔴 Live data from the CardioTouch 3000

📄 Full guide: [`docs/LIVE_DEMO.md`](docs/LIVE_DEMO.md)

| Path | What | Status |
|---|---|---|
| **A — watch folder** 📁 | LAN → BMS-Plus → export CSV → auto-classified in ~1 s | ✅ **tested end-to-end** |
| **B — RS-232 capture** 🔌 | `tools/serial_capture.py` logs raw bytes for protocol discovery | 🟡 logger ready |
| **C — continuous wearable** ⌚ | AD8232 + ESP32 firmware | 🟡 firmware written, board pending |

```bash
py tools/watch_folder.py --folder "C:/BMS-Plus/Exports"
```

## ⚠️ Limitations & future work

- **S remains the hard class** (deployed F1 0.32 @ precision 0.43) — consistent with the inter-patient literature. Routes: QAT for the oversampled v2 (float F1 0.39), focal tuning, per-patient calibration
- On-board ESP32 latency/energy **not yet measured** (no board in this session); laptop numbers give 3–4 orders of magnitude headroom
- CardioTouch external validation has **zero recordings yet** — tooling and protocol ready, the lab session produces the data
- The firmware's simple derivative R-detector ≠ the calibrated NeuroKit detector; quantify separately (open item in `docs/PHASE6.md`)
- F/Q AAMI classes excluded in v1; PTB-XL generalization untested

## 🛡️ Ethics & safety

> ⚕️ Human ECG recordings for external validation are collected **under technician/clinician supervision, with informed consent, anonymized before touching this repository** (consent log kept offline). The AD8232 rig must run on battery/isolated power near a person. **This is a research prototype, not a medical device.**

## 📚 References

A curated index of **85 related papers (46 full-text PDFs)** supports this project — LiteNet, ECG-TCN, TinyML arrhythmia classifiers, and the compression literature (Deep Compression, QAT, MCUNet, TFLite Micro). Key anchors:

- Moody & Mark (2001) — *The MIT-BIH Arrhythmia Database*
- de Chazal et al. (2004) — *Automatic classification of heartbeats using ECG morphology and heartbeat interval features* (DS1/DS2 protocol, AAMI grouping)
- Jacob et al. (2018) — *Quantization and training of neural networks for efficient integer-arithmetic-only inference*
- David et al. (2021) — *TensorFlow Lite Micro*

## 📁 Project documentation

| 📄 Document | Contents |
|---|---|
| [`docs/PHASE1.md`](docs/PHASE1.md) | 1️⃣ Environment, dataset download, exploration figures |
| [`docs/PHASE2.md`](docs/PHASE2.md) | 2️⃣ Preprocessing pipeline & design decisions |
| [`docs/PHASE3.md`](docs/PHASE3.md) | 3️⃣ Classical baselines (logistic regression, random forest) |
| [`docs/PHASE4.md`](docs/PHASE4.md) | 4️⃣ CNN v1, the RR-branch finding, v2 addendum |
| [`docs/PHASE5.md`](docs/PHASE5.md) | 5️⃣ INT8 quantization + the Conv1D quantizer bug |
| [`docs/PHASE6.md`](docs/PHASE6.md) | 6️⃣ ESP32 firmware, benchmark, bring-up checklist |
| [`docs/PHASE7.md`](docs/PHASE7.md) | 7️⃣ CardioTouch validation protocol & analysis plan |
| [`docs/RESULTS.md`](docs/RESULTS.md) | 📊 Consolidated results, ablations, detector study |
| [`docs/LIVE_DEMO.md`](docs/LIVE_DEMO.md) | 🔴 Live-data paths A/B/C, verified status |
| [`machine/README.md`](machine/README.md) | 🫀 The lab ECG machine documentation |

---

<div align="center">

**📄 License:** [MIT](LICENSE) · ** cite this repository.**

*Built as a thesis project — Lightweight ML for Real-Time ECG Arrhythmia Detection on Edge/Wearable Devices*

</div>
