# TinyML NPU 2x2 MAC array

## How it works

Four signed INT8 MACs accumulate in signed24-bit registers. Production
uses row/column broadcast, byte-serialized ingress and selected signed
8-bit requantized output. Runtime K=1..64, shift0..15, signed saturation
and ReLU are supported. The generic array has an independently tested
neighbor-forwarding mode; that mode is not exposed by this wrapper.

This front-end candidate is READY FOR PNR after human Gate5 approval.
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
