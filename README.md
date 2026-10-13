![](../../workflows/gds/badge.svg) ![](../../workflows/docs/badge.svg) ![](../../workflows/test/badge.svg) ![](../../workflows/fpga/badge.svg)

# Scalable TinyML NPU for Tiny Tapeout (ECG Arrhythmia & CNN/MLP Accelerator)

A parameterized, streaming Neural Processing Unit (NPU) accelerator designed for ultra-low-power TinyML inference on a **single 1x1 tile** (~160x108 µm) for the Tiny Tapeout shuttle (IHP SG13G2 130nm / SkyWater Sky130A / GF180MCU).

- **Documentation**: [docs/info.md](docs/info.md)
- **Top Module**: `tt_um_tinyml_npu_1x1`
- **Tile Footprint**: 1x1 Tile (`tiles: "1x1"`)
- **Clock**: 50.0 MHz synchronous clock domain (`clk`), active-low reset (`rst_n`).

---

## Architecture Overview

The NPU features a parameterized systolic Processing Element (PE) datapath capable of single-cycle signed INT8 Multiply-Accumulate (MAC), bit-exact requantization with half-integer rounding, nonlinear activation functions (ReLU / Saturated Clip), and a multi-class Winner-Take-All ArgMax classifier.

### Key Features
- **1x1 Tile Efficiency**: Synthesizes to 884 standard cells (149 DFFs, 1,571 NAND2 GE, 73.67% cell density), fitting safely within the 1x1 tile boundary.
- **High Throughput**: 50 MMAC/s peak throughput at 50 MHz nominal clock.
- **Micro-Op Instruction Decoder**: Run-time programmable accumulation vector lengths ($K \in [1, 256]$), quantization scaling shifts ($S \in [0, 15]$), bias loading, and activation modes.
- **Architectural Scalability**: Parameterized systolic PE grid (`npu_array.v`), scalable from 1x1 tile up to an $M \times N$ systolic grid (such as a 2x2 grid achieving 200 MMAC/s).
- **Target Workload**: Real-time MIT-BIH ECG arrhythmia detection (Normal, Premature Ventricular Contraction - PVC, Premature Atrial Contraction - PAC), 1D CNN layers, and general dense MLP classifiers.

---

## Pinout Mapping (Tiny Tapeout Standard)

| Pin | Name | Direction | Description |
| :--- | :--- | :--- | :--- |
| `ui_in[7:0]` | `data_in` | Input | Streaming data (weights, activations) or Opcode byte |
| `uo_out[7:0]` | `data_out` | Output | Quantized activation byte or ArgMax winning class / status |
| `uio[0]` | `host_valid` | Input | Host handshake: 1 when `ui_in` is valid |
| `uio[1]` | `npu_ready` | Output | NPU handshake: 1 when ready to accept byte |
| `uio[2]` | `cmd_mode` | Input | 1 = Command/Config byte, 0 = Streaming Data byte |
| `uio[3]` | `weight_stream`| Input | 1 = Incoming data byte is weight, 0 = Activation |
| `uio[4]` | `out_sel` | Input | 0 = Result activation byte, 1 = ArgMax class / status |
| `uio[5]` | `out_valid` | Output | 1 when output computation is valid |
| `uio[6]` | `layer_done` | Output | Pulse when vector dot-product completes |
| `uio[7]` | `npu_busy` | Output | 1 when computation is in progress |

Bidirectional pin direction: `uio_oe = 8'b11100010`.

---

## Verification & Testing

### 1. Standalone Icarus Verilog Simulation
```bash
cd test
iverilog -g2001 -o sim_npu.vvp -I ../src tb_npu_standalone.v ../src/*.v
vvp sim_npu.vvp
```
All 6 directed test phases (Reset, MAC, ReLU clipping, 4-tap dot product, ArgMax, and MIT-BIH PVC ECG inference) pass with 100% bit-exact accuracy.

### 2. Cocotb Testbench
```bash
cd test
make clean
make
```

### 3. Automated GDS Hardening
ASIC hardening is automated via GitHub Actions using [LibreLane](https://www.zerotoasiccourse.com/terminology/librelane/) and `TinyTapeout/tt-gds-action@ttihp26a` targeting the IHP SG13G2 130nm process (`.github/workflows/gds.yaml`).

---

## Attribution & Notice

This project contains a substantially redesigned and parameterized TinyML NPU architecture developed for the Tiny Tapeout shuttle. Portions of the initial project structure and template were derived from open-source Tiny Tapeout project templates; see `LICENSE` for applicable Apache 2.0 licensing terms.
