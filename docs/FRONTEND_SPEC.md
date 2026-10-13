# Front-end specification under review

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
