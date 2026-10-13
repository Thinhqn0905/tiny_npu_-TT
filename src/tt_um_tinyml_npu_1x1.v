`default_nettype none
`timescale 1ns/1ps

//==============================================================================
// Module:      tt_um_tinyml_npu_1x1
// Project:     Scalable TinyML NPU for 1x1 Tile (ECG & CNN/MLP Accelerator)
// Author:      Thinh Pham
// Description: Tiny Tapeout Top Wrapper for the Scalable 1x1 NPU.
//              Fits within 1x1 tile budget (<1,000 std cells).
//==============================================================================

module tt_um_tinyml_npu_1x1 (
    input  wire [7:0] ui_in,    // Dedicated inputs: Data stream / Opcode
    output wire [7:0] uo_out,   // Dedicated outputs: Result byte or Class
    input  wire [7:0] uio_in,   // Bidirectional inputs
    output wire [7:0] uio_out,  // Bidirectional outputs
    output wire [7:0] uio_oe,   // Bidirectional output enables (active high)
    input  wire       ena,      // Always 1 when design is powered
    input  wire       clk,      // System Clock (50 MHz)
    input  wire       rst_n     // Active-low reset
);

    // Bidirectional pin mapping:
    // uio[0] (in)  : host_valid
    // uio[1] (out) : npu_ready
    // uio[2] (in)  : cmd_mode
    // uio[3] (in)  : weight_stream
    // uio[4] (in)  : out_sel
    // uio[5] (out) : out_valid
    // uio[6] (out) : layer_done
    // uio[7] (out) : npu_busy

    wire host_valid    = uio_in[0];
    wire cmd_mode      = uio_in[2];
    wire weight_stream = uio_in[3];
    wire out_sel       = uio_in[4];

    wire npu_ready;
    wire out_valid;
    wire layer_done;
    wire npu_busy;
    wire overflow_any;

    // Pin Direction Configuration
    assign uio_oe = 8'b11100010;

    assign uio_out[0] = 1'b0;
    assign uio_out[1] = npu_ready;
    assign uio_out[2] = 1'b0;
    assign uio_out[3] = 1'b0;
    assign uio_out[4] = 1'b0;
    assign uio_out[5] = out_valid;
    assign uio_out[6] = layer_done;
    assign uio_out[7] = npu_busy;

    // Instantiate Scalable NPU Core (1x1 Tile: ROWS=1, COLS=1)
    npu_top #(
        .ROWS      (1),
        .COLS      (1),
        .DATA_WIDTH(8),
        .ACC_WIDTH (24)
    ) u_npu_core (
        .clk          (clk),
        .rst_n        (rst_n),
        .ena          (ena),
        .host_valid   (host_valid),
        .npu_ready    (npu_ready),
        .cmd_mode     (cmd_mode),
        .weight_stream(weight_stream),
        .data_in      (ui_in),
        .out_sel      (out_sel),
        .data_out     (uo_out),
        .out_valid    (out_valid),
        .layer_done   (layer_done),
        .npu_busy     (npu_busy),
        .overflow_any (overflow_any)
    );

    wire _unused_ok = &{1'b0, uio_in[7:5], uio_in[1], overflow_any, 1'b0};

endmodule

`default_nettype wire
