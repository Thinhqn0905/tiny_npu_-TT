# Scalable TinyML NPU 1x1 (ECG & CNN/MLP Accelerator)

A parameterized, streaming neural processing unit designed for ultra-low-power TinyML inference on 130nm ASIC (IHP SG13G2 / SkyWater 130nm) within a **single 1x1 tile** (~160x108 µm).

## How it works

The NPU features a scalable systolic-ready Processing Element (PE) architecture capable of performing single-cycle signed INT8 Multiply-Accumulate (MAC) operations, hardware requantization (arithmetic right-shift with rounding), activation functions (ReLU / Saturated Clip), and Winner-Take-All ArgMax classification.

### Architecture Highlights:
- **1x1 Tile Efficiency**: Synthesizes to ~850 standard cells, fitting comfortably into a 1x1 tile budget.
- **Single-Cycle INT8 Signed MAC**: Operates at 50 MHz.
- **Micro-Op Instruction Decoder**: Run-time programmable accumulation lengths ($K$), quantization scaling shifts ($S=0\dots15$), and activation functions.
- **Scalability**: Parameterized systolic PE grid (`npu_array.v`). Can be scaled from 1 PE (1x1 tile) up to an $M \times N$ systolic array (1x2, 2x2, or multi-tile chips) without architectural changes.
- **Applications**: Real-time MIT-BIH ECG arrhythmia detection (Normal, PVC, PAC), 1D Convolution, keyword spotting, and general dense MLPs.

### Pinout & Interface

| Pin | Name | Direction | Description |
| :--- | :--- | :--- | :--- |
| `ui_in[7:0]` | `data_in` | Input | Streaming data (weights, activations) or Opcode byte |
| `uo_out[7:0]` | `data_out` | Output | Quantized activation byte or ArgMax class / status |
| `uio[0]` | `host_valid` | Input | Host handshake: 1 when `ui_in` is valid |
| `uio[1]` | `npu_ready` | Output | NPU handshake: 1 when ready to accept byte |
| `uio[2]` | `cmd_mode` | Input | 1 = Command/Config byte, 0 = Data byte |
| `uio[3]` | `weight_stream`| Input | 1 = Incoming data byte is weight, 0 = Activation |
| `uio[4]` | `out_sel` | Input | 0 = Result activation byte, 1 = ArgMax class / status |
| `uio[5]` | `out_valid` | Output | 1 when output computation is valid |
| `uio[6]` | `layer_done` | Output | Pulse when vector dot-product completes |
| `uio[7]` | `npu_busy` | Output | 1 when computation is in progress |

### Command Micro-Ops (`cmd_mode = 1`)

When `uio[2] = 1`, `ui_in[7:6]` selects the command:
1. `2'b00` (`CMD_SET_LEN`): Set accumulation vector length $K = ui\_in[5:0] + 1$.
2. `2'b01` (`CMD_SET_POST`): Set quantization shift $S = ui\_in[3:0]$ and activation type $ui\_in[5:4]$ (`00`: Linear, `01`: ReLU, `10`: Signed Clip).
3. `2'b10` (`CMD_ACC_OPS`): Accumulator and ArgMax control:
   - `ui_in[0]`: Clear accumulator
   - `ui_in[1]`: Clear ArgMax
   - `ui_in[2]`: Trigger ArgMax comparison for class index `ui_in[5:4]`
4. `2'b11` (`CMD_LOAD_BIAS`): Load 8-bit signed bias into the 24-bit accumulator.

## How to test

1. **Cocotb Verification**:
   ```bash
   cd test
   make
   ```
2. **Standalone Verilog Simulation**:
   ```bash
   cd test
   iverilog -o sim.vvp ../src/*.v tb_npu_standalone.v
   vvp sim.vvp
   ```
3. **Firmware Integration (RP2040 / RP2350)**:
   Connect GPIOs to `ui_in`, `uo_out`, and `uio`. Stream pre-trained weights and quantized ECG sample windows to identify arrhythmia classifications in real-time.
