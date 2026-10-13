# Physical Design (PnR) Interface Specification

**Project:** Scalable TinyML Neural Processing Unit (2x2 Systolic Array)  
**Top Module:** `tt_um_tinyml_npu_2x2`  
**Core Datapath:** `npu_top_2x2`  
**Target Platform:** Tiny Tapeout Shuttle (IHP SG13G2 130nm / SkyWater Sky130A)  
**Tile Allocation:** 1x2 Tiles ($202\,\mu\text{m} \times 314\,\mu\text{m}$)  
**Target Clock:** 50.0 MHz ($T = 20.0\,\text{ns}$)  
**Sign-off Status:** **FROZEN FOR PNR**  

---

## 1. Top-Level Pin Interface & Direction Contract

The module `tt_um_tinyml_npu_2x2` conforms strictly to the standard Tiny Tapeout 24-pin digital interface.

| Pin Name | Type | Width | Active State | Description |
| :--- | :---: | :---: | :---: | :--- |
| `clk` | Input | 1 | Rising edge | Master Synchronous Clock (Nominal 50.0 MHz) |
| `rst_n` | Input | 1 | Active Low | Asynchronous / Synchronous Master Reset |
| `ena` | Input | 1 | Active High | Module Enable (held high during normal operation) |
| `ui_in[7:0]` | Input | 8 | Logic | Dedicated Input Stream (Opcode / Activations / Weights) |
| `uo_out[7:0]` | Output | 8 | Logic | Dedicated Output Port (Requantized Result / Status) |
| `uio_in[7:0]` | Input | 8 | Logic | Bidirectional Ingest Bus (Control flags, handshake) |
| `uio_out[7:0]` | Output | 8 | Logic | Bidirectional Output Bus (Status telemetry, flags) |
| `uio_oe[7:0]` | Output | 8 | Active High | Output Enable Driver for Bidirectional Pins |

### Bidirectional Pin Direction Contract:
- `uio_oe` is hardwired to **`8'b11100010`**:
  - `uio[0]`: Input (`host_valid` strobe from host MCU)
  - `uio[1]`: Output (`npu_ready` flow control flag)
  - `uio[2]`: Input (`cmd_mode` selector: 1 = opcode, 0 = operand data)
  - `uio[3]`: Input (`stream_sel` channel selector)
  - `uio[4]`: Input (`out_sel` readout mux selector: 0 = activation, 1 = status)
  - `uio[5]`: Output (`out_valid` pulse)
  - `uio[6]`: Output (`layer_done` pulse)
  - `uio[7]`: Output (`npu_busy` status flag)

---

## 2. Clocking and Reset Architecture

1. **Clock Distribution:**
   - Single global clock net: `clk`.
   - Frequency: Nominal 50.0 MHz ($T = 20.0\,\text{ns}$, 50% duty cycle).
   - Clock uncertainty budget: 0.500 ns setup, 0.250 ns hold.
   - Zero clock-gating cells inside datapath (all clock gating replaced by explicit register enables).
   - Maximum transition time: 0.200 ns.

2. **Reset Distribution:**
   - Active-low global asynchronous reset: `rst_n`.
   - Synchronously released internally; requires standard recovery and removal timing checks in STA.
   - Guarantees deterministic state recovery across all sequential DFFs within 1 clock cycle.
   - **Zero latches inferred:** All control and datapath state machines have fully specified default branches.

---

## 3. Physical Design & Floorplan Rules

1. **Tile Allocation & Footprint:**
   - Shuttle Allocation: **1x2 Tiles** (standard vertical 2-tile allocation on Tiny Tapeout shuttle).
   - Bounding Box Dimensions: $X = 202.08\,\mu\text{m}$, $Y = 313.74\,\mu\text{m}$.
   - Pin placement conforms to the standardized Tiny Tapeout frame.

2. **Standard Cell & Macro Budget:**
   - Standard Cell Gate Count: ~4,867 primitive logic gates (~2,350 mapped standard cells).
   - Sequential Flip-Flops: 164 DFF instances.
   - Hard Macro Blocks: **None** (zero SRAM, zero analog IP, 100% synthesizable digital standard cell logic).
   - Target Placement Density: 50% – 60% to avoid routing congestion across the systolic matrix.

3. **Power Grid:**
   - Core Power Net: `vccd1` (1.2V for core logic).
   - Core Ground Net: `vssd1`.

---

## 4. Invariant Rules (What PnR MUST NOT Change)

To maintain bit-exact functional equivalence and shuttle integration compliance, the physical design team must adhere to these strict invariants:

1. **Interface Contract Invariance:**
   - NEVER alter module name (`tt_um_tinyml_npu_2x2`), pin names, port widths, or signal directions.
   - NEVER modify `uio_oe` value (`8'b11100010`).

2. **Datapath Bitwidth & Arithmetic Invariance:**
   - NEVER alter accumulator widths (24 bits) or multiplier width (8-bit signed $\times$ 8-bit signed $\rightarrow$ 16-bit).
   - NEVER change the requantization rounding bias ($+2^{S-1}$) or saturation clipping logic ($[-128, +127]$).

3. **Pipeline Invariance:**
   - NEVER retime or insert registers across the systolic forwarding paths (`act_in` $\rightarrow$ `act_out`, `weight_in` $\rightarrow$ `weight_out`) without running the post-layout gate-level regression (`test/tb_tt_um_2x2.v`), as cycle-count contracts will break.

4. **Timing Exception Policy:**
   - NO false paths permitted on functional datapath nets.
   - NO multicycle path exceptions on multiplier or accumulator trees.
   - Only `ena` may be marked as a static false path if necessary.

---

## 5. PnR Sign-Off Criteria

The physical handoff is considered closed and tapeout-ready when the following sign-off checks pass:

- [ ] **LVS:** Clean (0 errors, 100% netlist matching layout).
- [ ] **DRC:** Clean (0 design rule violations under IHP SG13G2 / SkyWater Sky130 PDK).
- [ ] **STA Setup:** Positive slack at 50.0 MHz ($WNS \ge 0.00\,\text{ns}$) across worst-case PVT corner.
- [ ] **STA Hold:** Positive hold slack ($WHS \ge 0.00\,\text{ns}$) across best-case PVT corner.
- [ ] **Antenna:** Clean (0 antenna diode violations).
- [ ] **Gate-Level Simulation:** `tb_tt_um_2x2.v` passes bit-exact comparison against post-PnR SDF back-annotated netlist.
