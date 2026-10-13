# Coverage exclusion review — FE-REVIEW-20261013

Baseline: Verilator 4.038, `make coverage-baseline`, seed 784736294.
The five production files in `pnr_handoff/filelist.f` are the DUT scope.
Testbench and assertions are excluded. Native hierarchical points are merged
by Verilator; the original `h` field and every uncovered point are retained in
`evidence/review/coverage/summary.json` and `merged.dat`.

Raw metrics: line/block 30/33 (90.909091%), branch 16/16 (100%), toggle
1650/1672 (98.684211%). No DUT exclusions are currently applied.
The public-pin independent integer test passed 3,748,355 checks over
1,046,832 cycles. This measurement covers the production broadcast hierarchy;
the generic systolic configuration has separate functional regression evidence.

The following **25 native points** are proposed for exclusion. This proposal
requires user review; it changes neither RTL nor the mandatory 100% target.

| Points | Count | Evidence of unreachability under the approved contract |
|---|---:|---|
| Wrapper line 139 opcode default | 1 line | All four binary values of the two-bit opcode are explicitly handled. Four-state unknown inputs are outside the legal protocol and not representable by this two-state coverage simulator. |
| Wrapper line 163 byte-index default | 1 line | All four binary values of the two-bit index are explicitly handled. |
| Wrapper lines 187–188 FSM default | 1 line | Reset initializes IDLE; legal transitions are IDLE→POST_MAC→IDLE/FINISH→IDLE. There is no assignment to the fourth two-bit state. Enable only holds state. Fault injection into internal state is outside the public protocol. |
| `npu_activation.v:30`, `round_offset[15..24]` | 10 toggle | Four-bit shift is 0..15. The offset is zero for shift 0, otherwise 1<<(shift−1), so the largest set bit is 14. |
| `npu_top_2x2.v:42`, `out_acc_sel` | 1 toggle | Production wrapper ties this core input to zero; no external raw-accumulator selection exists. |
| Wrapper line 18, `uio_out[0,2,3,4]` | 4 toggle | Explicit constant-zero assignments; approved assertions check their values. |
| Wrapper line 19, `uio_oe[0,2,3,4]` | 4 toggle | Fixed output-enable mask E2 makes these bits constant zero; approved assertion checks the mask. |
| Wrapper line 70, `cfg_vector_len[7]` | 1 toggle | Configuration assigns zero-extended six-bit value plus one, range 1..64. Reset assigns 1. |
| Wrapper line 71, `mac_count[6,7]` | 2 toggle | Reset/clear assigns zero. In POST_MAC the counter increments only when count+1<K; otherwise it resets. For K≤64 its maximum stored value is 63. |

No internal forcing, coverage suppression pragmas, or RTL edits are proposed.
With exactly these reviewed exclusions, the eligible denominators would be
line 30/30, branch 16/16, toggle 1650/1650. Raw results remain visible.
This is simulation coverage, not formal reachability proof or physical signoff.
Gate 5 remains open pending review and the complete final regression.
