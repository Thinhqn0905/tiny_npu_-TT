"""Reconcile review documents from retained evidence. Does not run EDA tools."""
import json, hashlib, re, zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
def write(path,text):
    p=ROOT/path; p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(text.strip()+'\n',encoding='utf-8')
def load(path): return json.loads((ROOT/path).read_text(encoding='utf-8-sig'))
def js(path,value): write(path,json.dumps(value,indent=2))

def main():
    approval_file=ROOT/'schemas/review_approvals.json'
    approvals=load('schemas/review_approvals.json') if approval_file.exists() else {}
    approved=lambda gate: approvals.get(gate,{}).get('approved',False)
    synth=load('pnr_handoff/reports/summary.json')
    timing=load('pnr_handoff/reports/timing_summary.json')
    bench=load('evidence/ecg/benchmark.json')
    tests=load('evidence/review/final/verification.json')
    network=load('evidence/review/final/rtl_e2e.json')
    coverage=load('evidence/review/coverage/summary.json')
    mutation=load('evidence/review/mutation/summary.json')
    base='d020f70630e1c9feacf9fd79206d7a9e2874afed'
    resumed='c0ef2520c1a76f5730e6c716403ca77bc42194e9'
    # Keep the original package, including its unsupported claims, immutable.
    history='evidence/history/d020f70_original.zip'
    config={
        'DESIGN_NAME':'tt_um_tinyml_npu_2x2',
        'VERILOG_FILES':['dir::../rtl/'+p for p in ['npu_pe.v','npu_activation.v','npu_array.v','npu_top_2x2.v','tt_um_tinyml_npu_2x2.v']],
        'CLOCK_PORT':'clk','CLOCK_PERIOD':20,
        'PNR_SDC_FILE':'dir::../constraints/design.sdc',
        'DIE_AREA':[0,0,419.52,313.74],'FP_SIZING':'absolute',
        'PL_TARGET_DENSITY_PCT':55,'RUN_LINTER':True}
    js('pnr_handoff/config/config.json',config)
    write('pnr_handoff/config/README.md','''# Configuration boundary

`config.json` is a design overlay for the TinyTapeout IHP flow, with paths
relative to this directory. Invoke the official flow with PDK `ihp-sg13g2`
and its `sg13g2_stdcell` profile. The flow must supply official power nets,
pin placement, PDN and shuttle defaults. This overlay has not been hardened.

The user approved planning allocation `2x2` on 2026-10-13. The bounding box
is 419.52 x 313.74 um in the pinned official support-tools profile
01d5d2814fa9dd61e9d211e0b235a4a592a9316a. This is not a routed fit claim.

The Liberty file is from IHP Open PDK, with its Apache 2.0 notices intact.
`library_provenance.json` records the upstream revision and URL. It is used
for a reproducible typical-corner front-end synthesis/STA diagnostic, not
as a replacement for the shuttle's pinned signoff PDK/corners.
''')
    write('pnr_handoff/filelist.f','''# Frozen production RTL; paths relative to pnr_handoff/.
# Top: tt_um_tinyml_npu_2x2; 2 rows x 2 columns; SYSTOLIC_MODE=0.
rtl/npu_pe.v
rtl/npu_activation.v
rtl/npu_array.v
rtl/npu_top_2x2.v
rtl/tt_um_tinyml_npu_2x2.v
''')
    spec='''# Front-end specification under review

Revision: FE-REVIEW-20261013. Approval history is in schemas/review_approvals.json. This specification
records the implemented compute/protocol contract without waiving the
project's requirement for a complete trained, quantized network test.

| Requirement | Contract |
|---|---|
| REQ-NPU-001 | Four signed INT8 multipliers, 16-bit products, signed 24-bit wrapping accumulators; clear > bias load > MAC priority |
| REQ-NPU-002 | Production 2x2 row-activation/column-weight broadcast; generic array also supports externally skewed registered neighbor propagation |
| REQ-NPU-003 | Enabled rising-edge ready/valid acceptance; four-byte tuples r0,r1,c0,c1; K=1..64; one internal MAC edge per tuple and one finish edge per vector |
| REQ-NPU-004 | Widen before rounding; floor((acc + (S>0 ? 2**(S-1) : 0))/2**S); signed clamp [-128,127]; ReLU [0,127]; S=0..15 |
| REQ-NPU-005 | A complete trained quantized network must execute through hardware-supported layers to final results, with all host neural operations identified; evidence: TC-TRAINED-E2E |
| REQ-NPU-006 | Standard TinyTapeout ports, uio_oe=0xE2, one clk domain, async active-low reset; external synchronous reset-release assumption |

## Protocol

The host holds ui_in and controls stable before a rising clk edge and
transfers a byte only when host_valid and npu_ready are both high. ena must
also be high. ready is low during reset, disable, POST_MAC and FINISH.
Commands are issued at transaction boundaries; partial tuples are aborted
by reset. Configuration commands must not interrupt an in-progress vector.
All 4 accumulators persist after completion; the host explicitly clears
before an independent operation. ena freezes state and pending pulses.

| ui_in[7:6] | Meaning |
|---|---|
| 00 | K=ui_in[5:0]+1; resets MAC/byte counters, does not clear accumulators |
| 01 | shift=ui_in[3:0], act_type=ui_in[5:4] |
| 10 | bit0 clear, bit1 cascade load, bits5:4 PE read selector; bits3:2 ignored |
| 11 | signed full opcode byte loads top-row column biases: only -64..-1 are encodable; lower row snapshots previous top-row accumulators |

Bias/cascade load is a simultaneous snapshot, not an all-row broadcast.
At core interface the two column bias inputs are signed 24-bit values.
The external wrapper cannot directly load arbitrary 24-bit or arbitrary
signed 8-bit bias. There is no production ArgMax, pooling, general scaling
multiplier, zero-point correction, model store, or autonomous layer scheduler.

Signed production outputs for act_type 00,10,11 all clamp to [-128,127].
Only 01 adds ReLU. The generic activation module's unsigned side output
clamps to [0,255], but it is disconnected at the production wrapper.

## Review-only changes

Correct ready backpressure and extend rounding addition to 25 bits. No PE
count, accumulator width, pin assignment or compute-mode redesign.
Tile planning allocation is 2x2, explicitly approved by the user. Area fit,
routed timing, CTS, DRC, LVS and GDS remain physical-design responsibilities.
'''
    write('docs/FRONTEND_SPEC.md',spec)
    architecture='''# Frozen architecture review

This candidate is `tt_um_tinyml_npu_2x2`, with four signed INT8 MAC PEs in
two rows and two columns, each with a signed 24-bit accumulator. Production
uses row activation / column weight broadcast (`SYSTOLIC_MODE=0`).
The generic `npu_array` additionally supports registered activation-east /
weight-south forwarding (`SYSTOLIC_MODE=1`), with host-supplied skew and drain.
It has no valid-wavefront controller. Neither mode is selectable at runtime
through the production wrapper. Host-controlled temporal reuse is possible;
there is no hardware Fold-SIMD scheduler. We use these precise descriptions
instead of asserting a named Kung-Leiserson implementation.

```mermaid
flowchart LR
    H[Host byte stream] --> W[TinyTapeout wrapper and operand registers]
    W --> A[2x2 broadcast array: four signed INT8 MACs]
    A --> Q[Four combinational requantizers]
    Q --> M[PE selector: one signed byte]
    M --> O[uo_out]
    W --> S[Status mux]
    S --> O
```

## Arithmetic contract

INT8 operands lie in [-128,127]. Actual product range is [-16256,16384],
within a signed 16-bit result. -128*-128=16384; -128*127=-16256;
127*127=16129. Product bits are explicitly sign-extended to 24 bits.
The 24-bit accumulator addition wraps modulo 2**24. Overflow flags describe
the most recent enabled MAC, not a sticky history; clear/load reset them.

From zero bias, 511 repeated maximum-positive products are safe;
512*16384=8388608 overflows. 516 repeated maximum-negative products are
safe; 517*(-16256)=-8404352 overflows. 520 repeated 127*127 products are
safe; the 521st overflows. The universal bound for arbitrary signed INT8
terms is 511, not a heuristic count of guard bits.

With initial bias B in [-8388608,8388607], a universal safe length is
min(floor((8388607-B)/16384), floor((8388608+B)/16256)). A boundary bias
can leave zero headroom. The K=1..64 wrapper is safe from zero for one
vector, but repeated vectors do not automatically clear accumulators.

Requantization adds a nonnegative rounding offset in signed 25-bit precision
before arithmetic right shift. This prevents the old positive-to-negative
wrap bug at acc=8388607, S=1. The exact rule rounds ties toward positive
infinity: -3/2 -> -1 and -1/2 -> 0. It is not symmetric/unbiased rounding.
There are four parallel combinational post-processors. At the production
port, all modes except ReLU share signed clipping; mode 11 is not unsigned
readout. Accumulator and forwarding outputs are available at core ports,
but the TinyTapeout wrapper exposes only quantized bytes and status.

## Neighbor-forwarding example (generic array only)

A=[[2,3],[4,5]], B=[[6,7],[8,9]]. Each table entry is the operands consumed
on that enabled MAC edge. Clear and zero the boundaries before the schedule.

| Edge | West A(r0,r1) | North B(c0,c1) | PE00 | PE01 | PE10 | PE11 |
|---|---|---|---|---|---|---|
| 0 | 2,0 | 6,0 | 2*6 | 0 | 0 | 0 |
| 1 | 3,4 | 8,7 | 3*8 | 2*7 | 4*6 | 0 |
| 2 | 0,5 | 0,9 | 0 | 3*9 | 5*8 | 4*7 |
| 3 | 0,0 | 0,0 | 0 | 0 | 0 | 5*9 |

Final row-major accumulators: [36,41,64,73]. PE(r,c) consumes term k at
edge k+r+c. A 2x2 product with inner dimension K needs K+2 enabled MAC
edges including the fill/drain wavefront. Forwarding registers advance on
every ena edge even with mac_en=0, and freeze with ena=0. Zero padding,
global MAC gating, operation clearing and completion timing are supplied
externally. The array has no output-valid signal. Production broadcast
instead consumes all four useful outer-product contributions on each MAC
edge; its byte wrapper cannot feed a useful MAC every clock.
'''
    write('docs/RTL_FREEZE.md',architecture)
    interface='''# PnR interface contract

Top: `tt_um_tinyml_npu_2x2`. Four signed INT8 MACs, signed 24-bit accumulators,
production broadcast mode. Read [architecture](../../docs/RTL_FREEZE.md) and
the packaged [front-end review](FRONTEND_SIGNOFF_REVIEW.md).

| Port | Direction | Width | Meaning |
|---|---|---|---|
| clk | input | 1 | Rising-edge functional clock, target 20 ns |
| rst_n | input | 1 | Async active-low assertion; no internal release synchronizer |
| ena | input | 1 | Synchronous state enable; not an external package GPIO |
| ui_in | input | 8 | Command or tuple byte |
| uo_out | output | 8 | Selected signed quantized byte or status |
| uio_in | input | 8 | Valid bit0, cmd bit2, reserved bit3, out-select bit4 |
| uio_out | output | 8 | Ready bit1, valid bit5, done bit6, busy bit7; others zero |
| uio_oe | output | 8 | Fixed 0xE2 |

The standard interface represents 26 physical digital signals: 8 input,
8 output, 8 bidirectional, clk and reset. The uio input/output/enable RTL
buses represent the same eight physical bidirectional pads.

Status byte = {overflow, busy, valid, done, byte_idx[1:0], pe_sel[1:0]}.
out_sel=0 reads selected PE activation; out_sel=1 reads status. No external
raw 24-bit accumulator serialization or ArgMax is implemented. Results
persist until another accumulator/configuration operation, but valid/done
are one enabled-cycle completion indications, not a read-response handshake.

SDC: period 20 ns, waveform {0 10}, setup uncertainty 0.5 ns, hold 0.25 ns,
clock slew 0.2 ns. Synchronous I/O budgets max 4/min 1 ns and output load
0.050 pF are engineering assumptions, not measured board specifications.
ena is timed normally. No functional false paths, multicycle paths or
max/min-delay overrides exist. Reset recovery/removal is analyzed under
the external-release assumptions. Constant output endpoints can appear
as unconstrained in STA; they must match the netlist's tied bits exactly.

The user approved 2x2 tile planning on 2026-10-13. Official pinned IHP
support-tools geometry is 419.52 x 313.74 um. Placement density target is
55%, not measured utilization. No hard cell-count limit is asserted.
Use the official shuttle flow to supply pin placement, PDK, power nets,
PDN, electrical limits and corner definitions. Do not copy SKY130 settings.

Preserve the port contract, signed arithmetic, round/clamp equation,
ready/valid semantics and cycle behavior. Any physical optimization must
retain equivalence and rerun functional/gate-level verification. PnR owns
CTS, routed setup/hold, fit, DRC, LVS and GDS; none is signed off here.
'''
    write('pnr_handoff/docs/PNR_INTERFACE.md',interface)
    rows=[]
    claims=[
        ('Top / ports','tt_um_tinyml_npu_2x2.v:module','standard 8 buses/control interface'),
        ('PE count / dimensions','npu_top_2x2.v:u_array_2x2','4 PEs; ROWS=2,COLS=2'),
        ('Precision','npu_pe.v:prod,prod_sext,acc_reg','signed INT8 x INT8; 16-bit product; 24-bit sum'),
        ('Forward registers','npu_pe.v:always','A east/B south advance on ena, independent of mac_en'),
        ('Production mode','npu_array.v:gen_broadcast_in; top parameter omission','SYSTOLIC_MODE=0; row/column broadcast'),
        ('Generic neighbor mode','npu_array.v:gen_systolic_in','compile-time mode 1; externally skewed; no valid controller'),
        ('Fold-SIMD','wrapper sequencer; array broadcast','host temporal reuse only; no autonomous fold scheduler'),
        ('Activations','npu_activation.v:case act_type','signed saturation all modes; mode 1 ReLU'),
        ('Requantization','npu_activation.v:acc_rounded,shifted','25-bit round add, arithmetic shift0..15, ties to +infinity'),
        ('Post-processing channels','npu_top_2x2.v:u_act_00..11','4 parallel combinational units'),
        ('Output','wrapper:uo_out; top:mux_act','selected quantized signed byte or status; no raw-acc external readout'),
        ('Reset','PE/wrapper:posedge clk or negedge rst_n','async active-low; no internal synchronizer'),
        ('Handshake','wrapper:npu_ready,state','ready iff rst_n && ena && IDLE; valid/done at final MAC'),
        ('Bias','array:pe_bias_in; wrapper:CMD_LOAD_BIAS','24-bit core cascade snapshot; opcode encodes -64..-1 at wrapper')]
    for claim,ev,value in claims: rows.append(f'| {claim} | `{ev}` | {value} | PASS | Frozen defaults only |')
    test_table='\n'.join(f"| {t['test']} | {t['count']} | {t['passed']} | {t['failed']} | `{t.get('evidence','evidence/review/final/')}` |" for t in tests)
    review=f'''# Front-end signoff review

Date: 2026-10-13 (Asia/Bangkok). Final decision: **NOT READY FOR PNR**.
Functional diagnostics and the complete trained INT8 MLP pass after two
narrow fixes. Coverage exclusions have explicit user approval; raw metrics
are preserved. Human Gate5 and final package review remain pending.

## 1. Design identity

Repository: tiny_npu_-TT, working directory ttihp26a-inferenceFCNN-16h3,
branch main, remote https://github.com/Thinhqn0905/tiny_npu_-TT.git.
Exact initial commit `{base}`; the concurrent editor finished at `{resumed}`.
Those commits are preserved in `evidence/history/`. Test run identities hash
the actual frozen source bytes; they do not claim a nonexistent final commit.

## 2. Frozen architecture

| Claim | RTL Evidence | Verified Value | PASS/FAIL | Notes |
|---|---|---|---|---|
{chr(10).join(rows)}

Architecture details and cycle table: `docs/RTL_FREEZE.md`. The production
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
{test_table}

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
Gate1/3a/3b have explicit user approval; Gate5 remains pending.

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

Fresh SOFTWARE evaluation: {bench['count']:,} eligible beats on 22 DS2
records, accuracy {bench['accuracy']:.6%}, macro-F1 {bench['macro_f1']:.6f}.
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

Tool: {synth['tool']}. Fresh synthesis reads only pnr_handoff/filelist.f.
Generic total {synth['generic_primitives']} primitives, {synth['sequential_bits']}
DFF bits, {synth['combinational_primitives']} combinational primitives.
Generic hierarchy keeps forwarding ports: array164 DFF bits + wrapper115.
Flattened IHP mapped netlist: {synth['mapped_standard_cells']} standard cells,
{synth['mapped_sequential_cells']} sequential cells,
{synth['mapped_combinational_cells']} combinational cells;
Liberty cell area {synth['mapped_cell_area_um2']:.4f} um2. Counts differ because
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
is still required and is not inferred from passing tests. The selected standalone
overlay has not been executed by LibreLane; PDK/shuttle revision integration,
pad timing budgets and external reset release must be confirmed by PnR.
Physical fit, multi-corner STA, CTS, DRC, LVS and final GDS are downstream.

## 16. Final release decision

| Gate | Status | Basis |
|---|---|---|
| RTL | PASS | Functional directed/random arithmetic and protocol diagnostics |
| VERIFICATION | PENDING REVIEW | Complete trained MLP, reviewed coverage and18/18 mutations pass; human Gate5 pending |
| SYNTHESIS | PASS | Fresh generic and IHP mapping with reviewed library warnings |
| CONSTRAINTS | PASS | Parsed by OpenSTA; explicit assumptions; only constant endpoints untimed |
| TINYTAPEOUT INTEGRATION | PASS (front-end) | Pinned official metadata/docs and structural checks; physical full flow/precheck NOT VERIFIED |
| PNR HANDOFF | FAIL | Verification and human review blockers remain |

**NOT READY FOR PNR — human Gate5 review remains open.** No physical
PnR was run. Release commit/push is held under the original conditional
release rule. This report does not waive missing project requirements.
'''
    write('docs/FRONTEND_SIGNOFF_REVIEW.md',review)
    write('pnr_handoff/docs/FRONTEND_SIGNOFF_REVIEW.md',review.replace('`docs/RTL_FREEZE.md`','`../../../docs/RTL_FREEZE.md`'))
    write('docs/benchmark_report.md',f'''# Verified benchmark boundaries

Fresh evidence: [front-end review](FRONTEND_SIGNOFF_REVIEW.md).
Four physical MACs at the target50MHz give a theoretical200MMAC/s ceiling.
The 45-element synthetic dual-dot case uses90 useful MACs and226 wrapper
cycles, or19.9115MMAC/s useful throughput and4.52us at the target frequency.
Including setup and four PE reads:233 cycles /4.66us. This is not an ECG
neural network or a measured silicon performance result.

The downloaded CardioEdgeAI trained INT8 network has1,056,352 logical MACs.
Local software-only benchmark: {bench['count']} annotated MIT-BIH beats,
accuracy {bench['accuracy']:.6%}, macro-F1 {bench['macro_f1']:.6f}. Hardware
mapping of that downloaded CNN is NOT VERIFIED. The separately trained
20->8->3 INT8 MLP passes the complete RTL test on6 held-out inputs,1104
useful MACs in1585 cycles over3 batches; steady two-sample batch528 cycles
or10.56us at the target50MHz. See `evidence/ecg/benchmark.json` for CNN
scope, preprocessing, record list, confusion matrix and host runtime limits.

Synthesis: {synth['generic_primitives']} generic primitives and
{synth['mapped_standard_cells']} IHP mapped cells; these are different units.
Timing is PRE-LAYOUT / SYNTHESIS ESTIMATE only. Power, energy, battery life,
routed utilization and application speedup are NOT VERIFIED. The old PPA
report is preserved in `{history}` and must not be reused as signoff.
''')
    write('docs/experiment_1x1_vs_2x2_report.md','''# Reference architecture comparison

The retained 1x1 top is a historical reference with a different protocol
and ArgMax unit. Production uses a 2x2 broadcast array and no ArgMax.
Both standalone reference tests are rerun; this is functional evidence,
not a matched area/power/latency experiment. No application speedup or
energy scaling factor is qualified. Historical comparison numbers are
preserved only in evidence/history/d020f70_original.zip.

Current quantitative evidence is in FRONTEND_SIGNOFF_REVIEW.md and
benchmark_report.md. A controlled comparison must use identical workload,
I/O boundaries, PDK/library/corner, clock and source/configuration identity.
''')
    write('docs/info.md','''# TinyML NPU 2x2 MAC array

## How it works

Four signed INT8 MACs accumulate in signed24-bit registers. Production
uses row/column broadcast, byte-serialized ingress and selected signed
8-bit requantized output. Runtime K=1..64, shift0..15, signed saturation
and ReLU are supported. The generic array has an independently tested
neighbor-forwarding mode; that mode is not exposed by this wrapper.

This front-end candidate is NOT READY FOR PNR pending human Gate5 review.
Trained-MLP RTL, reviewed coverage and sampled mutation tests pass. Planning allocation
2x2 was approved by the user; physical fit is not established.

## How to test

Use `make help` at repository root. `make regression` runs the documented
front-end diagnostics; `make ecg-benchmark` runs the separate software ECG
evaluation when its dependencies and local dataset are available.

Read [protocol/specification](FRONTEND_SPEC.md),
[architecture](RTL_FREEZE.md), and [review](FRONTEND_SIGNOFF_REVIEW.md).

## External hardware

A synchronous host supplies four bytes per tuple in r0,r1,c0,c1 order.
uio0=valid, uio2=command, uio4=output mux; uio3 is ignored.
uio1=ready, uio5=valid completion, uio6=done, uio7=busy.
uio_oe=0xE2. The host honors ready and supplies reset release away from
clock edges. No board, clinical classification or silicon evidence is claimed.
''')
    write('README.md','''# TinyML NPU 2x2 signed MAC array

Four signed INT8 MAC PEs with24-bit accumulators, saturating requantization
and a TinyTapeout byte interface. **NOT READY FOR PNR:** human Gate5 review
remains pending. Complete trained-MLP RTL, reviewed coverage and18/18
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
''')
    write('test/README.md','''# Verification

`make regression` from repository root is the canonical command. The
original `test/Makefile` remains the Cocotb simulator integration layer.
Root recipes show each compiler/simulator invocation and archive logs/XML.

`test_arithmetic.py` compares exhaustive signed products, random/boundary
MACs, requantization and both dataflows against `oracle.py` integer math.
`test_release.py` checks the production byte protocol and synthetic workload.
`test.py` is the maintained four-case production smoke suite. The three
standalone Verilog benches are retained, including the historical1x1 top.
Their ECG-named synthetic score cases are not trained-model inference.

Specification/contract Gate1/3a and assertion Gate3b have user approval.
The complete trained MLP passes on RTL. Production coverage meets100% after
exactly25 user-reviewed exclusions; raw metrics remain visible. Sampled
mutation detection is18/18. Human final Gate5 remains open.
''')
    write('docs/ECG_BENCHMARK.md',f'''# ECG benchmark provenance and scope

Source model: [CardioEdgeAI](https://github.com/md-rejoyan-islam/CardioEdgeAI),
pinned commit ec36bbc5f96ea42a93274c499a51e3678742ffcf. The deployment header
contains a real TensorFlow Lite FlatBuffer, extracted losslessly as
`models/CardioEdgeAI/ecg_int8.tflite`. Source MIT license and citation remain
in upstream/. SHA-256: `{bench['model_sha256']}`. Size24,352bytes.

Inputs360 samples and four RR timing features; CNN16/32/64 channels and
dense32/3 head; three N/S/V outputs. Logical MAC count1,056,352 per inference
is derived from the serialized convolution/dense tensor shapes, not from
the physical four-PE count. Graph inventory and exact dependencies are saved.

[MIT-BIH1.0.0](https://physionet.org/content/mitdb/1.0.0/) was copied from
E:/ResearchOnWork/data/ecg/mitdb_1.0.0 to dataset/mitbih:144 files across48
records. SHA-256 source/destination checks are in evidence/ecg/. Official
PhysioNet checksum comparison is retained separately; differences must
remain visible rather than silently replacing the user's local data.

Fresh annotated-beat SOFTWARE evaluation: {bench['count']} samples, accuracy
{bench['accuracy']:.6%}, macro-F1{bench['macro_f1']:.6f}. Raw per-sample
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
''')
    write('docs/FRONTEND_COMPLETION_PLAN.md','''# Remaining front-end completion plan

1. Completed: user-approved Gate1/3a/3b and exactly25 coverage exclusions;
   preserve the approval ledger and the dual-mode generic array capability.
2. Completed: locally trained20->8->3 INT8 QAT model with real MIT-BIH
   provenance; six held-out tensor-to-logits RTL tests compare66 values.
   The downloaded CardioEdgeAI CNN remains a separate software benchmark.
3. Completed: actual coverage databases and18 compiled mutation detections;
   keep raw metrics separate from the100% eligible-point result.
4. Final package review: complete canonical regression, frozen-copy hashes,
   generic/IHP synthesis, pre-layout STA and official local metadata checks.
5. Pending: explicit human Gate5 signoff on the concrete evidence package.
   After approval regenerate documents/manifest, independently verify hashes,
   show diff/stat, commit intended files and ordinary push to origin/main.
6. Downstream: PnR owns2x2 fit, routing, CTS, multi-corner STA, DRC/LVS/GDS.
   GDS workflow is manual-only so a front-end push does not run physical PnR.

No physical PnR is authorized in this task. No high-value reusable skill
update was identified from two distinct design contexts; workflow skills
are left unchanged.
''')
    # Replace stale approval/coverage/PPA JSON rather than carrying false PASS fields.
    requirements=[dict(id=f'REQ-NPU-00{i}',title=t) for i,t in enumerate([
        'Signed four-PE MAC arithmetic','Broadcast and generic neighbor dataflow',
        'Byte protocol and configuration','Requantization and activation',
        'Complete trained quantized network','TinyTapeout clock/reset/ports'],1)]
    js('schemas/structured_spec.json',dict(ip_name='tt_um_tinyml_npu_2x2',version='FE-REVIEW-20261013',
        spec_ref='docs/FRONTEND_SPEC.md',gate_1_approved=approved('gate_1'),approval_status='PASS' if approved('gate_1') else 'NOT VERIFIED',requirements=requirements))
    js('schemas/final_config.json',dict(ip_name='tt_um_tinyml_npu_2x2',version='FE-REVIEW-20261013',
        gate_2_approved=approved('gate_2'),parameters=dict(ROWS=2,COLS=2,DATA_WIDTH=8,ACC_WIDTH=24,SYSTOLIC_MODE=0),
        clock_period_ns=20,pdk='ihp-sg13g2',tiles='2x2',tile_user_approved=True,
        rtl_rule_source='workspace Tiny_NPU/TinyTapeout_CNN_Tapeout_Spec/03_RTL_Design_Rules.md',
        style_note='Preserve existing Verilog names/interfaces; no unrelated VLSIT-style rewrite',
        physical_fit='NOT VERIFIED'))
    js('schemas/verification_contract.json',dict(ip_name='tt_um_tinyml_npu_2x2',
        contract_version='FE-REVIEW-20261013',gate_3a_approved=approved('gate_3a'),
        golden_sources=['docs/FRONTEND_SPEC.md','schemas/final_config.json'],
        independent_integer_oracle='test/oracle.py',
        behavioral_oracles=dict(mac='signed24(acc + signed8(a)*signed8(b))',
            requant='clamp(floor((acc + (shift ? 2**(shift-1) : 0))/2**shift))',
            ready='rst_n && ena && transaction accepts a byte',bias='top-row bias; lower row prior-top snapshot'),
        complete_network_status=network['status'],human_review='explicit approval ledger in schemas/review_approvals.json'))
    js('schemas/selected_testplan.json',dict(ip_name='tt_um_tinyml_npu_2x2',gate_4_approved=approved('gate_4'),
        baseline_evidence='evidence/review/final/verification.json',
        test_cases=[dict(tc_id=t['test'],file='test/',status=t['status'],evidence=t.get('evidence')) for t in tests],
        coverage_closure=dict(test_cases=[],target_percent=100,review='docs/COVERAGE_REVIEW.md'),
        additional_cases=[dict(tc_id='TC-TRAINED-E2E',file='src/tb/tests/tc_trained_network.sv',req_ids=['REQ-NPU-001','REQ-NPU-003','REQ-NPU-004','REQ-NPU-005']),
            dict(tc_id='TC-COVERAGE-BASE',file='src/tb/tests/tc_coverage_baseline.sv',driver='test/coverage_driver.cpp',req_ids=['REQ-NPU-001','REQ-NPU-003','REQ-NPU-004','REQ-NPU-006'])],
        unresolved=['coverage exclusion review','human Gate5']))
    js('schemas/verification_report.json',dict(ip_name='tt_um_tinyml_npu_2x2',gate_5_approved=False,
        gate_status='FAIL',functional_diagnostics=tests,source_identity='evidence/review/final/run_identity.json',
        gate_3b_approved=approved('gate_3b'),code_coverage=coverage,
        mutation=mutation,
        full_network=network,
        signoff='pending explicit human approval; no previous percentages reused'))
    js('schemas/synth_report.json',dict(synth,source_identity='evidence/review/final/run_identity.json',
        timing=timing,pdk='ihp-sg13g2',tiles='2x2',physical_fit='NOT VERIFIED',routed_timing='NOT VERIFIED'))
    js('schemas/rtm.json',dict(ip_name='tt_um_tinyml_npu_2x2',gate_5_approved=False,
        traceability_matrix=[dict(req_id=r['id'],title=r['title'],
            status='PASS',
            evidence='evidence/review/final/rtl_e2e.json' if r['id']=='REQ-NPU-005' else 'evidence/review/final/',
            human_signoff='Gate5 pending',mutation_score=mutation['per_requirement'][r['id']]['score']) for r in requirements]))
    write('docs/CHANGELOG.md','''# Unreleased front-end review

- Correct wrapper ready backpressure and widened rounding addition.
- Add independent arithmetic/protocol tests and preserve negative controls.
- Replace hardcoded PPA output with reproducible generic/mapped synthesis
  and explicit pre-layout STA evidence; retain original packages.
- Update planning allocation to user-approved2x2 and remove ena false path.
- Download/hash a public trained ECG INT8 checkpoint and copy/hash local
  MIT-BIH files; keep software CNN benchmark distinct from trained-MLP RTL E2E.
- Reconcile architecture, interface, benchmark and machine-readable reports.
- Record actual human approvals, measured coverage and complete trained-MLP
  RTL evidence; final human Gate5 remains pending.
''')
    wrapper='''#!/usr/bin/env python3
"""Compatibility entry point. Canonical EDA invocations are visible in Makefile."""
import os,sys
from pathlib import Path
os.chdir(Path(__file__).resolve().parents[1])
args=['make']
if '--synth-only' in sys.argv:
    args+=['preflight','synthesis','timing']
elif '--baseline' in sys.argv:
    raise SystemExit('Original negative controls are immutable under evidence/review/negative_controls; do not overwrite them with corrected RTL.')
else:
    args+=['regression']
os.execvp(args[0],args)
'''
    write('scripts/frontend_review.py',wrapper)
    write('scripts/run_frontend_benchmarks.py',wrapper)
    write('scripts/run_pnr_handoff_synth.sh','''#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
exec make preflight synthesis timing "$@"
''')
    write('firmware/README.md','''# Firmware boundary

`reference_1x1/` preserves the historical1x1 illustrative driver. It is
not compatible with the production2x2 tuple protocol and is not validated
MCU firmware. It must not be used as evidence of real ECG hardware inference.
The canonical2x2 protocol is documented in docs/FRONTEND_SPEC.md.
''')
    write('model/README.md','''# Historical model utility

`ecg_tinyml_model.py` constructs analytic synthetic templates; it does not
load trained weights. Its original unsigned hidden values are incompatible
with the production signed-output contract. It is retained as historical
reference only. Real downloaded and locally trained model artifacts are
kept under models/, with source/training provenance and distinct benchmarks.
''')
    write('scripts/reference/README.md','''# Historical utilities

The preserved DOCX conversion utility has workspace-specific paths and can
delete input documents. It is not part of the canonical front-end build and
has not been executed during this review. Original attribution is retained.
''')
    write('evidence/history/README.md','''# Immutable historical evidence

Original Git archives preserve the old RTL/docs/reports, including claims
that are unsupported. Old synthesis logs are retained for comparison only.
Current signoff evidence is under evidence/review/final and pnr_handoff/reports.
No historical cell/power/timing/accuracy number is automatically current.
''')
    write('pnr_handoff/docs/RTL_FREEZE.md',architecture)
    write('pnr_handoff/docs/FRONTEND_SPEC.md',spec)

    # Human Gate5 is the final decision; never infer it from test success.
    if approved('gate_5'):
        assert all(t['status']=='PASS' for t in tests)
        assert network['status']==mutation['status']==synth['status']==timing['status']=='PASS'
        assert coverage['status']=='target_met'
        assert 'PASS:' in (ROOT/'evidence/review/final/tinytapeout_metadata.log').read_text()
        replacements={
            'NOT READY FOR PNR — human Gate5 review remains open.':'READY FOR PNR — human Gate5 review approved.',
            'NOT READY FOR PNR pending human Gate5 review.':'READY FOR PNR after human Gate5 approval.',
            '**NOT READY FOR PNR:** human Gate5 review\nremains pending.':'**READY FOR PNR:** human Gate5 approved.',
            '**NOT READY FOR PNR**':'**READY FOR PNR**',
            'Human Gate5 and final package review remain pending.':'Human Gate5 and final package review are approved.',
            'Gate5 remains pending.':'Gate5 is approved.',
            'Human final Gate5 remains open.':'Human final Gate5 is approved.',
            'is still required and is not inferred from passing tests.':'is approved explicitly in the approval ledger.',
            '| VERIFICATION | PENDING REVIEW | Complete trained MLP, reviewed coverage and18/18 mutations pass; human Gate5 pending |':'| VERIFICATION | PASS | Complete trained MLP, reviewed coverage and18/18 mutations pass; user Gate5 approved |',
            '| PNR HANDOFF | FAIL | Verification and human review blockers remain |':'| PNR HANDOFF | PASS | Front-end package reviewed; physical PnR is downstream |',
            'Release commit/push is held under the original conditional\nrelease rule.':'Release commit/push is authorized under the original conditional\nrelease rule.',
            'Pending: explicit human Gate5 signoff on the concrete evidence package.':'Completed: explicit human Gate5 signoff on the concrete evidence package.',
            'final human Gate5 remains pending.':'final human Gate5 is approved.',
        }
        paths=[ROOT/'README.md',*list((ROOT/'docs').glob('*.md')),*list((ROOT/'pnr_handoff/docs').glob('*.md'))]
        for path in paths:
            text=path.read_text()
            for old,new in replacements.items(): text=text.replace(old,new)
            path.write_text(text)
        for path in ['schemas/verification_report.json','schemas/rtm.json']:
            data=load(path); data['gate_5_approved']=True
            if 'gate_status' in data: data.update(gate_status='PASS',signoff='Explicit user Gate5 approval in schemas/review_approvals.json')
            for row in data.get('traceability_matrix',[]): row['human_signoff']='user Gate5 approved'
            js(path,data)
        data=load('schemas/selected_testplan.json'); data['unresolved']=[]; js('schemas/selected_testplan.json',data)

if __name__=='__main__': main()
