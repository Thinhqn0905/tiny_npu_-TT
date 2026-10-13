# PnR interface contract

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
