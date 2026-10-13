# GitHub Actions scope

Pushing code and passing CI are separate outcomes. Commit `bbc94e0` reached
`origin/main`, but its test workflow failed before running RTL tests:
Ubuntu24.04 had no installation candidate for the requested `opensta` package.
The docs workflow passed. Failure evidence is available in
[the original run](https://github.com/Thinhqn0905/tiny_npu_-TT/actions/runs/38403468431).

The RTL test workflow now installs Icarus and Verilator and invokes
`make REPORTS=work/ci-results rtl-preflight lint tb-compile arithmetic release existing legacy standalone generate-network-test sva-compile contract-shell-compile trained-network`.
`rtl-preflight` validates frozen sources/configuration and prepares artifacts
without requiring synthesis or STA tools. `make preflight` and the complete
`make regression` still require Yosys and OpenSTA; their checks are preserved.

CI logs/XML are written to `work/ci-results`, so summaries and uploaded
artifacts cannot accidentally reuse committed local PASS results if CI stops
early. These RTL-only checks do not requalify synthesis, STA or coverage on
the hosted runner. Physical GDS/PnR remains manual-only.
