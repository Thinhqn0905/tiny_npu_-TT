# TinyML NPU 2x2 signed MAC array

Four signed INT8 MAC PEs with24-bit accumulators, saturating requantization
and a TinyTapeout byte interface. **READY FOR PNR:** human Gate5 approved. Complete trained-MLP RTL, reviewed coverage and18/18
sampled mutations pass; see the retained raw evidence and review documents.

Production top: `tt_um_tinyml_npu_2x2`; array2x2; fixed row/column broadcast;
target50MHz; async active-low reset. User-approved planning allocation2x2
uses the IHP profile. Physical fit and routed timing have not been verified.

## Quick start

Run from the repository root in Linux/WSL:

```sh
make help
make regression
make manifest
make manifest-check
```

Requirements: Python3.10+, make, Icarus11, Verilator4.038 or compatible,
Yosys0.9 or compatible, Cocotb2.1.0, and OpenSTA2.0.17. Exact versions and
commands are retained in evidence. `make -n regression` shows tool commands.
Install test packages with `python3 -m pip install -r test/requirements.txt`.

## ECG data and checkpoint

`dataset/mitbih/` contains the copied local MIT-BIH records and is ignored
by Git; `evidence/ecg/dataset_manifest.json` hashes every copied file.
The public trained24,352-byte CardioEdgeAI INT8 artifact, pinned source,
MIT license and citation are retained in `models/CardioEdgeAI/`.
The software benchmark uses annotated beats and is separate from RTL tests.
The frozen hardware does not yet execute the downloaded complete CNN.

## Documentation

- [Front-end signoff review](docs/FRONTEND_SIGNOFF_REVIEW.md)
- [Specification under review](docs/FRONTEND_SPEC.md)
- [Architecture and arithmetic](docs/RTL_FREEZE.md)
- [PnR interface](pnr_handoff/docs/PNR_INTERFACE.md)
- [Handoff manifest](pnr_handoff/HANDOFF_MANIFEST.md)
- [Remaining work](docs/FRONTEND_COMPLETION_PLAN.md)

## Attribution & Notice

The parameterized TinyML NPU architecture was developed for Tiny Tapeout.
Portions of the initial project structure/template derive from open-source
Tiny Tapeout project templates; see LICENSE for Apache2.0 terms. IHP PDK
copyright/license notices remain in the downloaded library. CardioEdgeAI
upstream artifacts retain their MIT license and CITATION.cff. MIT-BIH data
attribution and source are recorded in docs/ECG_BENCHMARK.md.
