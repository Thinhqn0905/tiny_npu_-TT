`timescale 1ns/1ps
// Verification-only public-interface assertions from FE-REVIEW-20261013.
// Excluded from production filelist. Immediate assertions run at stable
// falling-edge observation points; these are simulation checks, not formal proof.
module npu_protocol_properties (
    input wire clk, rst_n, ena,
    input wire [7:0] uo_out, uio_out, uio_oe
);
    always @(negedge clk) begin
        // Ignore only the simulator's time-zero X->0 clock initialization,
        // before asynchronous-reset nonblocking assignments have settled.
        if ($time > 0) begin
        // REQ-NPU-006 / PROP-TT-001: fixed pad directions.
        assert (uio_oe === 8'he2) else $fatal(1,"PROP-TT-001 output enable");
        // REQ-NPU-006 / PROP-TT-002: unused output bits are deterministic.
        assert ((uio_out & 8'h1d) === 8'h00) else $fatal(1,"PROP-TT-002 reserved outputs");
        // REQ-NPU-003 / PROP-PROTO-003: one common completion event.
        assert (uio_out[5] === uio_out[6]) else $fatal(1,"PROP-PROTO-003 completion flags");
        // REQ-NPU-006 / PROP-RESET-004: reset clears visible busy/completion.
        if (!rst_n)
            assert ((uio_out & 8'he2) === 8'h00) else $fatal(1,"PROP-RESET-004 reset status");
        // REQ-NPU-003 / PROP-PROTO-005: disabled/reset design accepts no bytes.
        if (!ena || !rst_n)
            assert (uio_out[1] === 1'b0) else $fatal(1,"PROP-PROTO-005 disabled ready");
        // REQ-NPU-006 / PROP-TT-006: no unresolved externally visible bits.
        assert ((^{uo_out,uio_out,uio_oe}) !== 1'bx) else $fatal(1,"PROP-TT-006 unknown output");
        end
    end
endmodule
