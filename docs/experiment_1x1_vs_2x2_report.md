# Reference architecture comparison

The retained 1x1 top is a historical reference with a different protocol
and ArgMax unit. Production uses a 2x2 broadcast array and no ArgMax.
Both standalone reference tests are rerun; this is functional evidence,
not a matched area/power/latency experiment. No application speedup or
energy scaling factor is qualified. Historical comparison numbers are
preserved only in evidence/history/d020f70_original.zip.

Current quantitative evidence is in FRONTEND_SIGNOFF_REVIEW.md and
benchmark_report.md. A controlled comparison must use identical workload,
I/O boundaries, PDK/library/corner, clock and source/configuration identity.
