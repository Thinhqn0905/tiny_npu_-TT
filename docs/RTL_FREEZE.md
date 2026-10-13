# RTL Architecture Freeze Specification

**Project:** Scalable TinyML Neural Processing Unit (NPU) for Arrhythmia ECG Detection  
**Target Platform:** Tiny Tapeout Shuttle (IHP SG13G2 130nm / SkyWater Sky130A / GF180MCU)  
**Tile Allocation:** 2x1 Tiles ($320\,\mu\text{m} \times 108\,\mu\text{m}$) or 2x2 Tiles  
**Frozen Top Module:** `tt_um_tinyml_npu_2x2`  
**Core Module:** `npu_top_2x2`  
**Git Baseline Commit:** `906bdcf` (branch `main`)  
**Freeze Status:** **FROZEN FOR PNR HANDOFF**  
**Author:** Thinh Pham  
**Date:** October 13, 2026  

---

## 1. Frozen Architecture Identity

The production tapeout implementation is frozen to the **2x2 Systolic Array NPU Architecture**. The earlier 1x1 single-PE implementation is retained solely as a reference/baseline and is superseded by this 2x2 release.

### Core Architectural Parameters:
- **PE Organization:** 2D Systolic Array Grid, $2 \text{ Rows} \times 2 \text{ Columns}$ ($N_{\text{PE}} = 4$).
- **Data Arithmetic:** Explicit signed two's complement INT8 ($W_{\text{DATA}} = 8\text{ bits}$, range $[-128, +127]$).
- **Accumulator Precision:** 24-bit signed accumulator ($W_{\text{ACC}} = 24\text{ bits}$) per PE, providing $\ge 8\text{ bits}$ of guard headroom over a $16\text{-bit}$ product.
- **Operating Modes:**
  - `SYSTOLIC_MODE = 0`: Fold-SIMD Parallel Broadcast mode for concurrent row/column matrix evaluation.
  - `SYSTOLIC_MODE = 1`: Kung-Leiserson Systolic Wavefront forward chaining mode with registered neighbor propagation.
- **Systolic Forwarding:**
  - Horizontal: Registered activation forward chaining (`data_a_out <= data_a_in`).
  - Vertical: Registered weight forward chaining (`data_b_out <= data_b_in`).
  - Cascade Bus: Vertical partial-sum accumulation cascade (`cascade_acc_in`).
- **Hardware Requantization:**
  - Arithmetic right shift by $S \in [0, 15]$.
  - Half-integer rounding bias offset ($+2^{S-1}$) to eliminate negative DC drift.
  - Saturated clipping hard-bounded to $[-128, +127]$.
- **Activation Functions:** Programmable per-layer via `act_type`:
  - `2'b00`: Linear pass-through.
  - `2'b01`: Rectified Linear Unit (ReLU: $\max(0, x)$).
  - `2'b10`: Signed saturated clipping ($[-128, +127]$).
- **Output Multiplexing:** Multi-channel readout multiplexer (`pe_sel[1:0]`) allowing serialized readout of all 4 PE activations and accumulators, alongside boundary forwarding.
- **Clock Domain:** Single synchronous clock domain (`clk`), nominal target frequency **50.0 MHz** ($T = 20.0\text{ ns}$).
- **Reset Domain:** Single asynchronous or synchronous active-low reset (`rst_n`), fully synchronized internally, zero latches.

---

## 2. Frozen Top-Level Interface (`tt_um_tinyml_npu_2x2`)

The frozen top module implements the standard Tiny Tapeout pinout contract:

| Pin Name | Direction | Width | Functional Description |
| :--- | :---: | :---: | :--- |
| `clk` | Input | 1 | Master System Clock (Nominal 50.0 MHz, rising edge active) |
| `rst_n` | Input | 1 | Master Asynchronous Active-Low Reset |
| `ena` | Input | 1 | Chip Enable (active high, tied to power-on circuit) |
| `ui_in[7:0]` | Input | 8 | Dedicated Data Stream / Opcode configuration byte |
| `uo_out[7:0]` | Output | 8 | Dedicated Result byte (Requantized activation / Status / Class) |
| `uio_in[7:0]` | Input | 8 | Bidirectional Input Port (Control opcodes, handshake) |
| `uio_out[7:0]` | Output | 8 | Bidirectional Output Port (Status flags, telemetry, overflow) |
| `uio_oe[7:0]` | Output | 8 | Pin Output Enable Bus (Frozen constant: `8'b11100010`) |

### Bidirectional Pin Assignment:
- `uio[0]` (Input): `host_valid` — Handshake signal from host MCU.
- `uio[1]` (Output): `npu_ready` — NPU ready signal to host.
- `uio[2]` (Input): `cmd_mode` — Mode control: `1` = Command/Config opcode, `0` = Data stream byte.
- `uio[3]` (Input): `stream_sel` — Sub-stream selector (Activations vs. Weights / Channel select).
- `uio[4]` (Input): `out_sel` — Readout selector: `0` = Selected PE activation, `1` = Status byte.
- `uio[5]` (Output): `out_valid` — Computation complete / output byte valid.
- `uio[6]` (Output): `layer_done` — Pulse signaling dot-product completion.
- `uio[7]` (Output): `npu_busy` — Execution in progress indicator.

---

## 3. Supported and Unsupported Operations

### Supported Operations:
1. Single-cycle signed INT8 Multiply-Accumulate ($P = A \times B + \text{Acc}$).
2. 4-PE parallel vector dot-product with accumulation length $K \in [1, 256]$.
3. $2 \times 2$ Matrix-Matrix Multiplication ($C = A \times B$) in 1 parallel compute phase.
4. Concurrent Dual-Class ECG Heartbeat evaluation (Normal vs. PVC template matching).
5. Signed overflow detection flag with latching.
6. Bit-exact programmable requantization with symmetric half-integer rounding.
7. Multiplexed readout of individual PE accumulators (24-bit) and activations (8-bit).
8. Systolic boundary forwarding for tiling across larger multi-core grids.

### Unsupported Operations (Explicit Out-of-Scope):
1. Floating-point arithmetic (FP32, FP16, BF16).
2. Asymmetric unsigned quantization without zero-point adjustment.
3. Dynamic runtime dimension changes beyond $2 \times 2$ physical grid without host folding.
4. Division, square root, or transcendental activation functions (Softmax, Sigmoid, Tanh).
5. Asynchronous clock crossing (CDC).

---

## 4. Arithmetic Semantics

$$\text{Product} = \text{signed}(A[7:0]) \times \text{signed}(B[7:0]) \quad (\in [-32768, +32767])$$
$$\text{Product}_{\text{sext}} = \{\{8\{\text{Product}[15]\}\}, \text{Product}[15:0]\} \quad (24\text{-bit signed})$$
$$\text{Acc}_{\text{next}} = \text{Acc}_{\text{current}} + \text{Product}_{\text{sext}}$$
$$\text{Overflow} = (\text{Acc}[23] == \text{Product}_{\text{sext}}[23]) \land (\text{Acc}_{\text{next}}[23] \neq \text{Acc}[23])$$
$$\text{Requant}(Acc, S) = \text{clip}\left(\left(\text{Acc} + 2^{S-1}\right) \gg S, -128, +127\right) \quad \text{for } S \ge 1$$

---

## 5. Clock & Reset Assumptions

- Single primary clock domain (`clk`), nominal 50.0 MHz ($20.0\text{ ns}$ period).
- Max clock frequency $F_{\max} > 200\text{ MHz}$ under pre-layout front-end characterization.
- Zero clock gating in datapath; explicit clock enables (`mac_en`, `ena`).
- Synchronous/active-low reset (`rst_n`), deterministic state recovery in $\le 1$ clock cycle.
- Zero inferred latches, zero combinational feedback loops.

---

## 6. Known Limitations

1. **Tile Allocation Requirement:** Requires a 2-tile footprint on Tiny Tapeout (`tiles: "2x1"` or `"2x2"`), as standard cell count (~2,350 cells) exceeds a single $160\,\mu\text{m} \times 108\,\mu\text{m}$ tile.
2. **Host Serialization:** Ingesting 4 parallel operands over an 8-bit input port requires 4 cycles of time-multiplexed host streaming per parallel MAC step.
3. **ArgMax Processing:** Winner-Take-All ArgMax across 4 PEs is performed via host multiplexing or external compare pulse.
