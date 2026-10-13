# RTL-to-PnR Formal Handoff Manifest

**Project Title:** Scalable TinyML Neural Processing Unit (2x2 Systolic Array)  
**Target Platform:** Tiny Tapeout Shuttle (IHP SG13G2 130nm / SkyWater Sky130A)  
**Top Module:** `tt_um_tinyml_npu_2x2`  
**Core Module:** `npu_top_2x2`  
**Tile Allocation:** 2x1 Tiles ($320\,\mu\text{m} \times 108\,\mu\text{m}$)  
**Target Clock:** 50.0 MHz ($T = 20.0\,\text{ns}$)  
**Author:** Thinh Pham  
**Handoff Date:** October 13, 2026  
**Git Baseline Commit:** `906bdcf`  
**Release Gate Status:** **READY FOR PNR (FORMALLY SIGNED OFF)**  

---

## Section A: Executive Summary & Project Identification

This package represents the formal, frozen RTL-to-PnR handoff release for the **2x2 Systolic Array TinyML Neural Processing Unit (NPU)**. The core is tailored for edge real-time biomedical signal processing, specifically automated ECG arrhythmia classification (MIT-BIH Arrhythmia Database template matching) as well as general 1D/2D Convolutional and Multi-Layer Perceptron (MLP) neural inference.

The frontend design phase is officially closed. All microarchitectural explorations have been finalized and frozen. The implementation comprises 4 signed INT8 Processing Elements arranged in a $2 \times 2$ grid, featuring concurrent Fold-SIMD broadcasting and Kung-Leiserson systolic wavefront propagation, integrated bit-exact arithmetic requantization with symmetric rounding bias, and complete single-clock synchronous control. The entire package is self-contained within the `pnr_handoff/` hierarchy, requiring zero parameter inference or architectural assumptions by the Physical Design (PnR) engineering team.

---

## Section B: Handoff Package File Inventory & SHA256 Checksums

Every file included in this production release has been hashed using SHA-256 to ensure cryptographic integrity across handoff transitions:

| Relative Path | Size (Bytes) | SHA-256 Checksum | Description |
| :--- | :---: | :--- | :--- |
| `filelist.f` | 925 | `742C165613C1F3A083BF8AE6B803ABA1876454836E0BEA1A9023B6394A891BB7` | Dependency-ordered synthesis RTL filelist |
| `config/config.json` | 567 | `6AEBD62C3ED920DCD91CE7AE1D525734678ADFFCC1A8C6A047B9A29AF80F5408` | OpenLane/LibreLane PnR configuration file |
| `constraints/design.sdc` | 2,756 | `17A249FA25BFDE78CFECDFA7F0924B210A64DF9BFD653C340DC14734511A6985` | SDC timing constraints (50 MHz, I/O budgets) |
| `docs/PNR_INTERFACE.md` | 4,286 | `4F471E8F999777A307783157759ED2F492F17182BDF80E91AD4238DCF53787C7` | Physical design interface contract & rules |
| `reports/cell_count.rpt` | 1,872 | `F1739AB05F513194C5B142C7BC703CC3E8225AD1FFBCA0CE3600C5DD589EFED4` | Synthesis gate-level primitive breakdown |
| `reports/latch_check.rpt` | 2,267 | `93E85CE5BF4DEA838E4AE034E49505E94A38C33FE22C0EA888F8C72D4BC2B78C` | Zero-latch verification sign-off report |
| `reports/sequential_dff.rpt` | 3,470 | `5F64626E136BFDDD6B86207BAC3579BCFCA662D8B7B7D07C8AB23BBF53922239` | Sequential storage & DFF register report |
| `reports/synth_netlist.v` | 147,745 | `57712C0CCAAEFAB8BF45AF0CFF2CC28DE81F8A4BE6BA6DE37DFC872F53215D57` | Post-synthesis gate-level Verilog netlist |
| `reports/synth_stat.rpt` | 2,864 | `90BA856F0C912E4DCB80CB1291846DCDE29B19169AB1972C0FA43972B865BE31` | Full Yosys synthesis statistics report |
| `reports/timing_est.rpt` | 973 | `A8DD993621D46CF819BEFBF37B09AAA1CF2D07C7521AC09D2AD1F4FA54994EED` | Pre-layout timing & logic depth report |
| `reports/yosys_synth.log` | 96,403 | `C7CBA1D37C839ED3522EFBF6DCF3FC86B7DA0CF0F76704049A25173589E2FCB7` | Complete raw Yosys execution log |
| `rtl/npu_activation.v` | 3,248 | `A6DD1A7C1DB17F10F5E1C10DD4FCDB2323FD4D125B16B374515DE781EBF5680F` | Hardware requantizer & activation unit |
| `rtl/npu_array.v` | 5,618 | `5635EC7E2C1CAD12A8443BC386009BE30618709921EFD7FE11CCB4BAD05FF6D8` | 2D Systolic Array grid (ROWS=2, COLS=2) |
| `rtl/npu_pe.v` | 3,922 | `CC50D98C113715A54A14C8BB4377E6A49B7E4524F9143E6E9F1D512D7E8B431D` | Processing Element (INT8 MAC + 24-bit Acc) |
| `rtl/npu_top_2x2.v` | 6,554 | `4056A209EBFCEECFD32828BB30E125CE3FF3C08FE4B109771C7DA5BC8DB05DE3` | 2x2 Core Datapath & parallel requantizers |
| `rtl/tt_um_tinyml_npu_2x2.v` | 8,924 | `61346303590F2AD9B1A3828E633B42A0AFD8EDF26950A6670DA70C13C153DCBE` | Frozen Tiny Tapeout top wrapper |

---

## Section C: Target Architecture & Microarchitecture Specifications

1. **Processing Element Array:**
   - 4 PEs structured in a $2 \text{ rows} \times 2 \text{ columns}$ topology.
   - Datapath Precision: Signed INT8 operands ($W_{\text{DATA}} = 8$), range $[-128, +127]$.
   - Accumulator Headroom: 24-bit signed accumulator ($W_{\text{ACC}} = 24$), range $[-8388608, +8388607]$.
   - Internal Forwarding: Horizontal systolic activation propagation (`data_a_out <= data_a_in`) and vertical weight propagation (`data_b_out <= data_b_in`).
   - Cascade Bus: Vertical partial-sum accumulation bus (`cascade_acc_in`).

2. **Requantization & Activation Engine:**
   - Four parallel requantization channels operating on PE00, PE01, PE10, and PE11 accumulators.
   - Symmetrical Half-Integer Rounding: Adds $2^{S-1}$ prior to arithmetic right shift by $S \in [0, 15]$.
   - Saturation: Clamping hard-limited to $[-128, +127]$.
   - Activation Functions: Linear pass-through (`00`), ReLU (`01`), Signed Clip (`10`).

3. **Throughput & Performance:**
   - Peak Arithmetic Throughput: 4 MACs/cycle $\times$ 50 MHz = **200 MMAC/s** ($0.2\text{ GMAC/s}$).
   - Classification Latency: Evaluates dual-template 45-sample ECG windows in $\sim 180\text{ clock cycles}$ ($3.6\,\mu\text{s}$ core latency).

---

## Section D: Physical Design Contract & Pinout Specification

- **Module Name:** `tt_um_tinyml_npu_2x2`
- **Tile Footprint:** 2x1 Tiles ($320\,\mu\text{m} \times 108\,\mu\text{m}$).
- **Target Density:** 55% placement density.

### Tiny Tapeout 24-Pin Assignment:
- `ui_in[7:0]` (Input): Dedicated streaming operand ingestion and micro-op command bus.
- `uo_out[7:0]` (Output): Dedicated output bus (Selected PE activation or status byte).
- `uio_oe[7:0]` (Output): Fixed constant `8'b11100010`.
- `uio_in[0]` (Input): `host_valid` strobe.
- `uio_out[1]` (Output): `npu_ready` flow control flag.
- `uio_in[2]` (Input): `cmd_mode` selector (1 = opcode, 0 = operand).
- `uio_in[3]` (Input): `stream_sel` channel selector.
- `uio_in[4]` (Input): `out_sel` readout mux (0 = activation, 1 = status byte).
- `uio_out[5]` (Output): `out_valid` completion strobe.
- `uio_out[6]` (Output): `layer_done` vector dot-product pulse.
- `uio_out[7]` (Output): `npu_busy` status flag.
- `clk` (Input): Master 50 MHz clock.
- `rst_n` (Input): Master active-low reset.
- `ena` (Input): Chip enable.

---

## Section E: Clock, Reset, and Timing Budget

1. **Clock Contract:**
   - Single synchronous domain: `clk`
   - Period: $20.000\,\text{ns}$ ($f_{\text{clk}} = 50.0\,\text{MHz}$)
   - Setup Uncertainty: $0.500\,\text{ns}$
   - Hold Uncertainty: $0.250\,\text{ns}$
   - Max Transition / Slew: $0.200\,\text{ns}$

2. **I/O Delay Assumptions:**
   - Input delay (`ui_in`, `uio_in`, `rst_n`): Max $4.000\,\text{ns}$, Min $1.000\,\text{ns}$ ($20\%$ clock period).
   - Output delay (`uo_out`, `uio_out`, `uio_oe`): Max $4.000\,\text{ns}$, Min $1.000\,\text{ns}$ ($20\%$ clock period).
   - Output Load: $50\,\text{fF}$ external pad capacitance.

3. **Reset Contract:**
   - Active-low asynchronous reset (`rst_n`), fully synchronized internally.
   - Zero recovery/removal timing hazards; recovers in $\le 1$ cycle.

---

## Section F: Synthesis Baseline & Gate-Level Complexity Evidence

Directly synthesized via Yosys 0.9 from `pnr_handoff/filelist.f`:
- **Total Primitive Logic Cells:** 5,822 cells
- **Estimated Standard Cells:** $\sim 2,350$ standard cells
- **Sequential Storage:** 280 Flip-Flops (164 in 2x2 Array, 116 in top wrapper)
- **Inferred Latches:** **0** (Verified via `check -assert`)
- **Inferred Memories:** **0** (100% digital standard cell logic, zero SRAM macros)
- **Multiplexers:** 1,353 cells
- **Combinational Logic:** 5,542 cells (AND, OR, XOR, XNOR, AOI, OAI compound gates)

---

## Section G: Static Timing Analysis & Critical Path Evidence

- **Pre-Layout Estimated Critical Path:** $\sim 4.20\,\text{ns}$
- **Logic Depth:** 18 – 22 gate levels across the $8\times 8$ Wallace/Booth tree multiplier, 24-bit sign extension, accumulator adder, and requantizer barrel shifter.
- **Setup Slack:** $+15.30\,\text{ns}$ at $50.0\,\text{MHz}$ ($T = 20.0\,\text{ns}$).
- **Estimated Maximum Frequency ($F_{\max}$):** $\sim 238.1\,\text{MHz}$ ( $> 4.7\times$ nominal operating frequency).
- **Timing Exceptions:** Zero false paths on functional logic; zero multicycle path exceptions.

---

## Section H: Functional Verification & Regression Sign-off Evidence

1. **Standalone RTL Regression (`tb_tt_um_2x2.v`):**
   - Phase 1: Reset behavior and ready/busy handshake (`TC1_RESET`) — **PASS**
   - Phase 2: Runtime micro-op configuration ($K=1$, $S=0$, Linear) — **PASS**
   - Phase 3: 4-PE Concurrent MAC verification (PE00=72, PE01=40, PE10=63, PE11=35) — **PASS**
   - Phase 4: Serialized 4-channel PE readout multiplexer — **PASS**
   - Phase 5: Requantization arithmetic shift ($S=2$) with rounding bias — **PASS**
   - Phase 6: ReLU negative clamping ($\le 0 \rightarrow 0$) on PE00/PE01 — **PASS**
   - Phase 7: Saturated positive clipping on PE10/PE11 — **PASS**
   - Total Verification Errors: **0**

2. **Lint & Synthesizability Audit:**
   - Verilator 5.x `-Wall`: **0 Warnings** (Zero CASEINCOMPLETE, zero UNUSED).
   - Yosys `check -assert`: **PASS** (Zero undriven nets, zero combinational loops).

---

## Section I: Physical Invariants & PnR Team Invariant Rules

The Physical Design team MUST NOT alter:
1. Top module entity name (`tt_um_tinyml_npu_2x2`) or port list.
2. Hardwired pin output enable bus (`uio_oe = 8'b11100010`).
3. Signed INT8 datapath width or 24-bit accumulator precision.
4. Systolic forwarding registers (retiming across boundary forwarding is forbidden).
5. Asynchronous clock domain crossings (must remain single synchronous domain `clk`).

---

## Section J: Formal Release Gate Sign-off

```
================================================================================
                    OFFICIAL FRONTEND SIGN-OFF CERTIFICATE
================================================================================
Release Target:        tt_um_tinyml_npu_2x2 (2x2 Systolic Array NPU)
Target Platform:       Tiny Tapeout Shuttle (IHP SG13G2 / SkyWater Sky130A)
Tile Allocation:       2x1 Tiles (320 um x 108 um)
Master Clock:          50.0 MHz (20.0 ns)
Synthesis Filelist:    pnr_handoff/filelist.f
Verification Suite:    test/tb_tt_um_2x2.v (PASS, 0 Errors)
Lint / Latch Audit:    PASS (0 Lint Warnings, 0 Inferred Latches, 0 Memories)
Timing Closure Margin: +15.30 ns Setup Slack at 50 MHz (Fmax ~238 MHz)

RELEASE GATE VERDICT:  [ READY FOR PNR ]
Sign-Off Lead:         Thinh Pham
Date of Sign-Off:      October 13, 2026
================================================================================
```
