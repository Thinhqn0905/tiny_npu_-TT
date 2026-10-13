# Failed instrumentation attempt — not a mutation qualification result

This retained attempt predates the explicit Cocotb2.1 `GPI_USERS` bootstrap.
The twelve Cocotb simulations did not execute their tests. Their zero
detection entries are harness failures, not surviving RTL mutants or valid
mutation scores. The six standalone SystemVerilog simulations did run.

The corrected, compiled, executed18-mutant campaign and per-requirement
detection evidence are in `../mutation/`. No failed attempt closes a gate.
