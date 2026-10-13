`timescale 1ns/1ps
// TC-COVERAGE-BASE / REQ-NPU-001/003/004/006.
// Verification-only adapter; stimulus/checks are in test/coverage_driver.cpp.
// The C++ driver uses only this approved public interface and integer contract.
module coverage_top (
    input wire [7:0] ui_in, output wire [7:0] uo_out,
    input wire [7:0] uio_in, output wire [7:0] uio_out,uio_oe,
    input wire ena,clk,rst_n
);
    tt_um_tinyml_npu_2x2 dut(ui_in,uo_out,uio_in,uio_out,uio_oe,ena,clk,rst_n);
    npu_protocol_properties u_properties(clk,rst_n,ena,uo_out,uio_out,uio_oe);
endmodule
