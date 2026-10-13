# Front-end signoff review

Date: 2026-10-13 (Asia/Bangkok). Final decision: **READY FOR PNR**.
Functional diagnostics and the complete trained INT8 MLP pass after two
narrow fixes. Coverage exclusions have explicit user approval; raw metrics
are preserved. Human Gate5 and final package review are approved.

## 1. Design identity

Repository: tiny_npu_-TT, working directory ttihp26a-inferenceFCNN-16h3,
branch main, remote https://github.com/Thinhqn0905/tiny_npu_-TT.git.
Exact initial commit `d020f70630e1c9feacf9fd79206d7a9e2874afed`; the concurrent editor finished at `c0ef2520c1a76f5730e6c716403ca77bc42194e9`.
Those commits are preserved in `evidence/history/`. Test run identities hash
the actual frozen source bytes; they do not claim a nonexistent final commit.

## 2. Frozen architecture

| Claim | RTL Evidence | Verified Value | PASS/FAIL | Notes |
|---|---|---|---|---|
| Top / ports | `tt_um_tinyml_npu_2x2.v:module` | standard 8 buses/control interface | PASS | Frozen defaults only |
| PE count / dimensions | `npu_top_2x2.v:u_array_2x2` | 4 PEs; ROWS=2,COLS=2 | PASS | Frozen defaults only |
| Precision | `npu_pe.v:prod,prod_sext,acc_reg` | signed INT8 x INT8; 16-bit product; 24-bit sum | PASS | Frozen defaults only |
| Forward registers | `npu_pe.v:always` | A east/B south advance on ena, independent of mac_en | PASS | Frozen defaults only |
| Production mode | `npu_array.v:gen_broadcast_in; top parameter omission` | SYSTOLIC_MODE=0; row/column broadcast | PASS | Frozen defaults only |
| Generic neighbor mode | `npu_array.v:gen_systolic_in` | compile-time mode 1; externally skewed; no valid controller | PASS | Frozen defaults only |
| Fold-SIMD | `wrapper sequencer; array broadcast` | host temporal reuse only; no autonomous fold scheduler | PASS | Frozen defaults only |
| Activations | `npu_activation.v:case act_type` | signed saturation all modes; mode 1 ReLU | PASS | Frozen defaults only |
| Requantization | `npu_activation.v:acc_rounded,shifted` | 25-bit round add, arithmetic shift0..15, ties to +infinity | PASS | Frozen defaults only |
| Post-processing channels | `npu_top_2x2.v:u_act_00..11` | 4 parallel combinational units | PASS | Frozen defaults only |
| Output | `wrapper:uo_out; top:mux_act` | selected quantized signed byte or status; no raw-acc external readout | PASS | Frozen defaults only |
| Reset | `PE/wrapper:posedge clk or negedge rst_n` | async active-low; no internal synchronizer | PASS | Frozen defaults only |
| Handshake | `wrapper:npu_ready,state` | ready iff rst_n && ena && IDLE; valid/done at final MAC | PASS | Frozen defaults only |
| Bias | `array:pe_bias_in; wrapper:CMD_LOAD_BIAS` | 24-bit core cascade snapshot; opcode encodes -64..-1 at wrapper | PASS | Frozen defaults only |

Architecture details and cycle table: `../../../docs/RTL_FREEZE.md`. The production
top is fixed to four PEs and broadcast mode. Generic width parameters are
not a qualification of arbitrary widths: only DATA_WIDTH=8, ACC_WIDTH=24
and the tested 1x1/2x2 dimensions are supported by this review.

## 3. RTL hierarchy

tt_um_tinyml_npu_2x2 -> npu_top_2x2 -> npu_array -> 4 x npu_pe;
npu_top_2x2 also instantiates 4 x npu_activation. There is no production
npu_controller or npu_argmax instance. The older 1x1 top remains reference
code, excluded from `pnr_handoff/filelist.f` and `info.yaml`.

## 4. Interfaces

See `pnr_handoff/docs/PNR_INTERFACE.md` and `docs/FRONTEND_SPEC.md` for exact
ports, opcode encoding and state handshake. K is 1..64, not 256. Tuple
ordering is r0 activation, r1 activation, c0 weight, c1 weight. Reserved
control bit3 is ignored. Host supplies all scheduling and model data.

## 5. Arithmetic contract

Actual products span [-16256,16384], explicitly signed 16-bit, sign-extended
before wrapping 24-bit accumulation. Safe universal length from zero is
511; repeated maximum-negative products allow 516; repeated 127*127 allow
520. Bias-dependent bound and rounding examples are in RTL_FREEZE.md.
The rounding add now uses 25 bits. Both fixes were checked against an
independent Python integer oracle. Overflow is latest-MAC status, not sticky.

## 6. Clock/reset contract

One clk domain; 50 MHz / 20 ns is a target. Async low reset, no synchronizer.
Reset works independently of ena; state and pulses freeze while ena=0.
External reset release and synchronous host timing are assumptions. SDC
removes the old false path on functional ena. No timing exceptions remain.

## 7. Dataflow

Production uses four outer-product MACs per enabled MAC edge. Byte streaming
requires four acceptance edges plus a POST_MAC edge per tuple, and a FINISH
edge per vector. Generic neighbor mode requires skew, zero fill/drain and
externally determined validity. Consecutive operation clearing/flush and
randomized cycle-by-cycle partial sums are exercised by test_arithmetic.py.

## 8. Verification evidence

| Test | Count | Passed | Failed | Evidence Path |
|---|---:|---:|---:|---|
| arithmetic | 3 | 3 | 0 | `evidence/review/final/arithmetic.log` |
| release | 5 | 5 | 0 | `evidence/review/final/release.log` |
| existing | 4 | 4 | 0 | `evidence/review/final/existing.log` |
| legacy | 6 | 6 | 0 | `evidence/review/final/legacy.log` |
| tb_npu_standalone | 6 | 6 | 0 | `evidence/review/final/tb_npu_standalone.log` |
| tb_npu_2x2_standalone | 6 | 6 | 0 | `evidence/review/final/tb_npu_2x2_standalone.log` |
| tb_tt_um_2x2 | 8 | 8 | 0 | `evidence/review/final/tb_tt_um_2x2.log` |
| Verilator lint | 1 | 1 | 0 | `evidence/review/final/verilator.log` |
| TC-TRAINED-E2E | 6 | 6 | 0 | `evidence/review/final/trained_network.log` |

Seed: 784736294 (0x2EC62026). Raw logs and XML are retained. Arithmetic
checks include all 65,536 INT8 operand pairs, randomized/boundary wrapping
MACs, shift0..15, all activation modes, rounding/saturation thresholds,
random broadcasts and skewed wavefronts. Protocol tests cover continuous
ready/valid streams, random stalls, back-to-back vectors, idle/partial/pending
reset, ena stalls, cascade snapshots and readout. Legacy synthetic tests are
retained without treating their ECG labels as clinical/network evidence.

Negative controls in `evidence/review/negative_controls/` show the unchanged
rounding failure (8388607,S=1 -> -128 instead of127) and ready incorrectly
asserted during POST_MAC. Failures are not erased by later passing logs.
One legacy harness run failed because the concurrent editor removed new
test copies; this is a harness failure, not a DUT functional failure.

Fresh native Verilator coverage: line30/33, branch16/16, toggle1650/1672.
The user approved exactly3 unreachable line points and22 constant/out-of-range
toggle points in `docs/COVERAGE_REVIEW.md`. Eligible results are30/30,16/16
and1650/1650, each100%; raw databases and unfiltered metrics remain retained.
Mutation tests detected18/18 compiled faults,3 per requirement. These are
sampled fault-detection results, not formal equivalence or exhaustive proof.
Gate1/3a/3b have explicit user approval; Gate5 is approved.

## 9. ECG/workload evidence

The old 1x1 tests perform three one-tap synthetic scores. The maintained
2x2 ECG-named test performs two handcrafted dot products of length two.
The model utility constructs analytic templates, not learned weights, and
its unsigned hidden-activation semantics differ from the production signed
output. Legacy firmware implements the old protocol and is not a 2x2 driver.

The added 45-element dual-dot demo uses 90 useful logical MACs, 180 physical
PE MAC updates, and 226 stream/completion edges; 233 including three setup
commands and four read selections. At the 50 MHz target this is 4.52 us
stream/completion, 4.66 us including the documented setup/readout boundary.
Useful throughput is 19.9115 MMAC/s over the 226-cycle interval, utilization
90/(4*226)=9.9558%. Peak internal ceiling is 200 MMAC/s; the byte protocol
ceiling with four useful outputs is 40 MMAC/s before setup/finish overhead.
There is no measured 4x application speedup.

A public trained CardioEdgeAI INT8 artifact was downloaded at pinned commit
ec36bbc5f96ea42a93274c499a51e3678742ffcf; MIT license/source notices retained.
It is 24,352 bytes, input 360 samples plus four RR features, three N/S/V
outputs, and 1,056,352 logical MACs per inference. SHA-256 and graph inventory
are in `models/CardioEdgeAI/PROVENANCE.json` and `evidence/ecg/`.
MIT-BIH raw files were copied from E:/ResearchOnWork/data/ecg/mitdb_1.0.0:
48 records, 144 files, 93,857,066 bytes, with source/destination hashes.

Fresh SOFTWARE evaluation: 49,293 eligible beats on 22 DS2
records, accuracy 94.733532%, macro-F1 0.717464.
Every prediction has a record ID, annotation sample and quantized output in
`evidence/ecg/predictions.csv`. This is annotated-beat software inference:
gold R peaks, offline whole-record normalization and next-beat RR are used.
It is not raw E2E or RTL inference. Upstream support counts differ and are
not presented as reproduced. The upstream split separates records 201/202,
which PhysioNet identifies as the same subject; subject independence is not
certified. Original source-reported metrics are retained only under upstream/.

The frozen wrapper lacks the model's affine scaling, general bias loading,
pooling/mean/concatenation/softmax and automated layer/memory scheduling.
That downloaded CNN is SOFTWARE ONLY. A separately trained compatible
20->8 ReLU->3 INT8 MLP executes all neural layers on RTL, without biases.
`TC-TRAINED-E2E` compares66 hidden/final values across6 real held-out beats
and feeds actual RTL hidden outputs into the second RTL layer. It passes
1104 useful MACs in1585 cycles across3 two-sample batches (529/528/528).
Steady two-sample batch time is10.56us at the assumed50MHz target.
`models/tiny_ecg_qat/network.json` retains weights, scales, sample IDs and
training provenance. Software evaluation on47,159 DS2 beats, excluding202
because training includes the same subject's record201, gives85.790623%
accuracy and0.595989 macro-F1. Low minority-class F1 remains a limitation.
Host operations are offline annotated segmentation/filtering/features,
quantization, byte scheduling and optional ArgMax. No host neural layer is
used in the RTL test. This is tensor-to-logits E2E, not raw streaming or clinical evidence.

## 10. Synthesis evidence

Tool: Yosys 0.9 (git sha1 1979e0b). Fresh synthesis reads only pnr_handoff/filelist.f.
Generic total 6094 primitives, 279
DFF bits, 5815 combinational primitives.
Generic hierarchy keeps forwarding ports: array164 DFF bits + wrapper115.
Flattened IHP mapped netlist: 4091 standard cells,
215 sequential cells,
3876 combinational cells;
Liberty cell area 49527.9414 um2. Counts differ because
flattening/mapping optimizes the production connectivity. No NAND2-equivalent
estimate is asserted. Zero latches, memories, unresolved modules or unmapped
generic cells are present in the fresh structural checks.

Raw generic/mapped logs, JSON netlists and scripts are packaged. Generic
synthesis reports zero warnings. Mapped synthesis reports four distinct
unsupported scan-cell function warnings (36 occurrences); none of those
scan cells is instantiated. They are explicitly reviewed rather than hidden.
The historical raw generic log supports 5,822 primitives and 280 DFFs for
the old source, but provides no mapped ~2,350-cell result. It is superseded.

## 11. Timing evidence

OpenSTA2.0.17, pinned IHP typ_1p20V_25C Liberty, ideal clock and library
wire-load estimate, no extracted routing/CTS. **PRE-LAYOUT / SYNTHESIS ESTIMATE**.
Target20 ns, worst reported setup slack approximately+4.3904 ns. The limiting
register-to-output data arrival is11.1096 ns; output budget4 ns and uncertainty
0.5 ns consume the rest. Algebraic 20-slack=15.6096 ns gives approximately
64.063 MHz under these same budgets, not 1/11.1096 as an overall Fmax claim.
Raw evidence: pnr_handoff/reports/timing_est.rpt. Constant uio_oe[7:0] and
uio_out[0,2,3,4] are the12 unconstrained endpoints; they are tied outputs,
not hidden sequential paths. Hold/recovery/removal diagnostics are retained.

The historical script printed4.20 ns, +15.30 ns and238.1 MHz as literal text;
it did not run STA. These values are unsupported and mutually inconsistent:
20-15.30=4.70 ns ->212.8 MHz. They are withdrawn, not corrected by guessing.
Routed setup/hold/CTS closure and silicon Fmax: **NOT VERIFIED**.

## 12. TinyTapeout integration

info.yaml selects only the five production files and correct2x2 top, clock
target50MHz, planning tiles2x2. User approval for the tile change is recorded
in this session. Pinned official support-tools geometry419.52x313.74 um is
used; no cell-count limit, physical fit or universal package frequency is
inferred. Structural wrapper/metadata checks and official documentation
validation are separate from physical precheck/GDS, which are not run here.

## 13. PnR handoff contents

Only current production RTL/config/constraints/docs/reports are in handoff.
Historical packages and failed runs remain outside it under evidence/.
The manifest includes relative paths, sizes and64-hex SHA-256 values, checks
duplicate/missing paths, and deliberately excludes its own self hash.
Both Python generation and independent PowerShell checking are required.
Scripts and original license notices remain available for reproduction.

## 14. Known limitations

Production mode is fixed broadcast. Raw accumulators are not available at
external pins. Bias encoding is limited. No hardware ArgMax or autonomous
network engine exists. Non-default widths and arbitrary array shapes are
not qualified. Complete trained-MLP inference, coverage and sampled mutation
evidence are retained with their declared scopes.

## 15. Open risks

The complete trained-MLP RTL test passes. Reviewed production coverage meets
the100% eligible-point target; raw coverage remains visible. Human Gate5
is approved explicitly in the approval ledger. The selected standalone
overlay has not been executed by LibreLane; PDK/shuttle revision integration,
pad timing budgets and external reset release must be confirmed by PnR.
Physical fit, multi-corner STA, CTS, DRC, LVS and final GDS are downstream.

## 16. Final release decision

| Gate | Status | Basis |
|---|---|---|
| RTL | PASS | Functional directed/random arithmetic and protocol diagnostics |
| VERIFICATION | PASS | Complete trained MLP, reviewed coverage and18/18 mutations pass; user Gate5 approved |
| SYNTHESIS | PASS | Fresh generic and IHP mapping with reviewed library warnings |
| CONSTRAINTS | PASS | Parsed by OpenSTA; explicit assumptions; only constant endpoints untimed |
| TINYTAPEOUT INTEGRATION | PASS (front-end) | Pinned official metadata/docs and structural checks; physical full flow/precheck NOT VERIFIED |
| PNR HANDOFF | PASS | Front-end package reviewed; physical PnR is downstream |

**READY FOR PNR — human Gate5 review approved.** No physical
PnR was run. Release commit/push is authorized under the original conditional
release rule. This report does not waive missing project requirements.
