# ECG benchmark provenance and scope

Source model: [CardioEdgeAI](https://github.com/md-rejoyan-islam/CardioEdgeAI),
pinned commit ec36bbc5f96ea42a93274c499a51e3678742ffcf. The deployment header
contains a real TensorFlow Lite FlatBuffer, extracted losslessly as
`models/CardioEdgeAI/ecg_int8.tflite`. Source MIT license and citation remain
in upstream/. SHA-256: `216ae64abccae28fde39da9cb4ec6c0656d71a37ffa8b3acc21ceaee01ff5389`. Size24,352bytes.

Inputs360 samples and four RR timing features; CNN16/32/64 channels and
dense32/3 head; three N/S/V outputs. Logical MAC count1,056,352 per inference
is derived from the serialized convolution/dense tensor shapes, not from
the physical four-PE count. Graph inventory and exact dependencies are saved.

[MIT-BIH1.0.0](https://physionet.org/content/mitdb/1.0.0/) was copied from
E:/ResearchOnWork/data/ecg/mitdb_1.0.0 to dataset/mitbih:144 files across48
records. SHA-256 source/destination checks are in evidence/ecg/. Official
PhysioNet checksum comparison is retained separately; differences must
remain visible rather than silently replacing the user's local data.

Fresh annotated-beat SOFTWARE evaluation: 49293 samples, accuracy
94.733532%, macro-F10.717464. Raw per-sample
predictions, record IDs and annotation sample positions are in predictions.csv.
This is the local evaluated cohort; the upstream50,026 sample report is not
claimed reproduced. See benchmark.json for exclusions, timing and versions.
Records201/202 come from one subject according to PhysioNet, so the upstream
record split must not be described as strictly subject independent.

Inference uses expert annotation peaks, channel0, zero-phase filtering,
full-record z-score and pre/post/local RR features. It is offline
annotated-beat inference, not streaming raw-signal E2E. Host software executes
all CNN layers here. The separate tiny QAT MLP has a passing tensor-to-logits
RTL test; see the front-end review. No clinical or hardware accuracy claim
follows from the software CNN results.

Citation: Moody, G., and Mark, R. MIT-BIH Arrhythmia Database1.0.0, PhysioNet,
2005. DOI10.13026/C2F305. Dataset license/source terms remain available at
the linked resource. Raw files are local and are not added to Git.
