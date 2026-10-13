# Scalable TinyML NPU 2x2 Systolic Array (ECG & CNN/MLP Accelerator)

A parameterized, streaming 2D systolic neural processing unit designed for ultra-low-power TinyML inference on 130nm ASIC (IHP SG13G2 / SkyWater Sky130A) allocating **2x1 tiles** ($320\,\mu\text{m} \times 108\,\mu\text{m}$) on the Tiny Tapeout shuttle.

## How it works

The NPU features a 4-PE 2D Systolic Array grid ($2 \times 2$) capable of executing concurrent signed INT8 Multiply-Accumulate (MAC) operations, hardware requantization (arithmetic right-shift with rounding), programmable activation functions (Linear, ReLU, Saturated Clip), and multi-channel readout multiplexing.

### Architecture Highlights:
- **2x1 Tile Footprint**: Synthesizes to ~2,350 standard cells (5,822 primitive logic gates), fitting comfortably in a 2x1 tile allocation.
- **Concurrent 4-PE Parallel Throughput**: Delivers up to 200 MMAC/s peak throughput at nominal 50.0 MHz.
- **Dual Dataflow Execution**:
  - `SYSTOLIC_MODE = 0`: Fold-SIMD Parallel Broadcast for concurrent matrix dot products.
  - `SYSTOLIC_MODE = 1`: Kung-Leiserson Systolic Wavefront chaining with registered neighbor forwarding.
- **Bit-Exact Requantization**: Arithmetic right shift $S \in [0, 15]$ with half-integer symmetric rounding bias ($+2^{S-1}$) and saturated $[-128, +127]$ clipping.
- **Zero Latches**: 100% synchronous design, verified with 0 inferred latches and single clock domain (`clk`).
- **Target Application**: Real-time MIT-BIH ECG arrhythmia detection (Normal vs. PVC template classification), 1D/2D CNNs, and dense MLPs.

### Pinout & Interface (`tt_um_tinyml_npu_2x2`)

| Pin | Name | Direction | Description |
| :--- | :--- | :---: | :--- |
| `ui_in[7:0]` | `data_in` | Input | Streaming data byte (activations, weights) or command opcode |
| `uo_out[7:0]` | `data_out` | Output | Quantized activation byte or status byte (selected via `out_sel`) |
| `uio[0]` | `host_valid` | Input | Host handshake: 1 when `ui_in` byte is valid |
| `uio[1]` | `npu_ready` | Output | NPU flow control: 1 when ready to receive byte |
| `uio[2]` | `cmd_mode` | Input | 1 = Command/Config opcode, 0 = Streaming operand data byte |
| `uio[3]` | `stream_sel` | Input | Streaming channel select / reserved control |
| `uio[4]` | `out_sel` | Input | Readout mux: 0 = Selected PE activation, 1 = Status byte |
| `uio[5]` | `out_valid` | Output | Computation complete pulse |
| `uio[6]` | `layer_done` | Output | Pulse when vector dot-product completes |
| `uio[7]` | `npu_busy` | Output | 1 when computation or ingestion in progress |

### Command Micro-Ops (`cmd_mode = 1`)

When `uio[2] = 1`, `ui_in[7:6]` selects the micro-op command:
1. `2'b00` (`CMD_SET_LEN`): Set accumulation vector length $K = ui\_in[5:0] + 1$.
2. `2'b01` (`CMD_SET_POST`): Set quantization shift $S = ui\_in[3:0]$ and activation function $ui\_in[5:4]$ (`00`: Linear, `01`: ReLU, `10`: Signed Clip).
3. `2'b10` (`CMD_ACC_OPS`):
   - `ui_in[0]`: Clear all 4 accumulators (`acc_clear`).
   - `ui_in[1]`: Load bias into column accumulators.
   - `ui_in[5:4]`: Select readout PE (`00`: PE00, `01`: PE01, `10`: PE10, `11`: PE11).
4. `2'b11` (`CMD_LOAD_BIAS`): Broadcast 8-bit signed bias to columns C0 and C1.

## How to test

### Standalone Verilog Verification (Icarus Verilog):
```bash
# Test 2x2 Top Module testbench (8/8 test phases)
iverilog -o sim_2x2.vvp src/npu_pe.v src/npu_activation.v src/npu_array.v src/npu_top_2x2.v src/tt_um_tinyml_npu_2x2.v test/tb_tt_um_2x2.v
vvp sim_2x2.vvp
```

### Full PnR Synthesis Regression:
```bash
# Clean Yosys gate-level synthesis using pnr_handoff filelist
./scripts/run_pnr_handoff_synth.sh
```
