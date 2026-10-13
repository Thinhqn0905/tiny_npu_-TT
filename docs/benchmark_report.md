# Verified benchmark boundaries

Fresh evidence: [front-end review](FRONTEND_SIGNOFF_REVIEW.md).
Four physical MACs at the target50MHz give a theoretical200MMAC/s ceiling.
The 45-element synthetic dual-dot case uses90 useful MACs and226 wrapper
cycles, or19.9115MMAC/s useful throughput and4.52us at the target frequency.
Including setup and four PE reads:233 cycles /4.66us. This is not an ECG
neural network or a measured silicon performance result.

The downloaded CardioEdgeAI trained INT8 network has1,056,352 logical MACs.
Local software-only benchmark: 49293 annotated MIT-BIH beats,
accuracy 94.733532%, macro-F1 0.717464. Hardware
mapping of that downloaded CNN is NOT VERIFIED. The separately trained
20->8->3 INT8 MLP passes the complete RTL test on6 held-out inputs,1104
useful MACs in1585 cycles over3 batches; steady two-sample batch528 cycles
or10.56us at the target50MHz. See `evidence/ecg/benchmark.json` for CNN
scope, preprocessing, record list, confusion matrix and host runtime limits.

Synthesis: 6094 generic primitives and
4091 IHP mapped cells; these are different units.
Timing is PRE-LAYOUT / SYNTHESIS ESTIMATE only. Power, energy, battery life,
routed utilization and application speedup are NOT VERIFIED. The old PPA
report is preserved in `evidence/history/d020f70_original.zip` and must not be reused as signoff.
