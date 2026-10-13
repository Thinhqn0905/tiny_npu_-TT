# Locally trained compatible ECG network

This is a separately trained 20→8 ReLU→3 linear, bias-free INT8 MLP,
not the downloaded CardioEdgeAI CNN. It has184 weights/useful MACs per beat.
`network.json` is the frozen trained checkpoint, scales, training provenance
and six real held-out fixtures. `training_history.json` retains model selection.

Reproduce with `make tiny-features tiny-train` after installing the isolated
benchmark dependencies and PyTorch2.5.1. Training uses deterministic seed
784736294 and DS1 training/validation records. DS2 evaluation excludes202,
because record201 in DS1 belongs to the same subject. Validation, not DS2,
selects the checkpoint. See the scripts and JSON for exact record lists.

Held-out software evaluation:47,159 beats, accuracy85.790623%, macro-F1
0.595989. Minority-class performance is limited; this is not clinical validation.

`make generate-network-test trained-network` executes both neural layers on
RTL and compares all66 hidden/output bytes for six held-out beats. Actual
RTL hidden bytes feed the next RTL layer. The independent integer oracle
uses the approved rounding, saturation and signed arithmetic contract.
The host supplies offline annotated, filtered, normalized feature tensors,
quantization and byte scheduling; ArgMax is external. There is no host neural
layer in the RTL test and no streaming raw-signal claim.

The complete test takes1585 cycles across three two-sample batches:
529 first,528 subsequent. At the assumed50MHz target, a steady batch is
10.56µs; this is simulated wrapper execution, not measured silicon latency.
