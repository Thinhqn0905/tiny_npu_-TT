# Verification

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
