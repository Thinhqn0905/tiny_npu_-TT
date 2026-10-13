# VLSIT Gate 3b property review

Golden sources: FE-REVIEW-20261013 specification and verification contract,
explicitly approved at Gate1/3a. File: `src/sva/npu_protocol_properties.sv`.
The properties observe only public ports at stable falling-edge points.
They are simulation assertions, not a claim of formal proof.
The monitor ignores only the simulator's time-zero X-to-zero clock event.
Reset-driving tests keep reset transitions away from observation edges so
asynchronous-reset nonblocking assignments settle before checks.
The user approved the six property meanings at Gate3b on 2026-10-13.

| Property | Requirement | Expected behavior |
|---|---|---|
| PROP-TT-001 | REQ-NPU-006 | uio_oe always0xE2 |
| PROP-TT-002 | REQ-NPU-006 | uio_out bits0/2/3/4 are zero |
| PROP-PROTO-003 | REQ-NPU-003 | out_valid equals layer_done |
| PROP-RESET-004 | REQ-NPU-006 | reset clears busy, ready and completion flags |
| PROP-PROTO-005 | REQ-NPU-003 | no ready while disabled or reset |
| PROP-TT-006 | REQ-NPU-006 | no unknown bits on visible outputs |

Arithmetic and full byte-stream conservation are checked separately by
the independent integer oracle/testbench; these six assertions alone do
not establish full RTL correctness or full-network inference. Assertion
failures terminate simulation with nonzero status.
