`default_nettype none
`timescale 1ns/1ps

//==============================================================================
// Module:      npu_top
// Description: Core Integration Top Module for Scalable TinyML NPU.
//              Combines controller, PE array, activation/requantizer,
//              and ArgMax unit.
//==============================================================================

module npu_top #(
    parameter ROWS       = 1,
    parameter COLS       = 1,
    parameter DATA_WIDTH = 8,
    parameter ACC_WIDTH  = 24
)(
    input  wire                  clk,
    input  wire                  rst_n,
    input  wire                  ena,

    // Host Streaming / Control Interface
    input  wire                  host_valid,
    output wire                  npu_ready,
    input  wire                  cmd_mode,
    input  wire                  weight_stream,
    input  wire [DATA_WIDTH-1:0] data_in,

    // Status & Result Interface
    input  wire                  out_sel,          // 0: Result Activation, 1: ArgMax Class / Status
    output wire [DATA_WIDTH-1:0] data_out,
    output wire                  out_valid,
    output wire                  layer_done,
    output wire                  npu_busy,
    output wire                  overflow_any
);

    // Controller internal signals
    wire                          mac_en;
    wire                          acc_clear;
    wire                          load_bias;
    wire signed [DATA_WIDTH-1:0]  latched_weight;
    wire signed [DATA_WIDTH-1:0]  current_act;
    wire signed [ACC_WIDTH-1:0]   bias_to_load;
    wire [3:0]                    shift_val;
    wire [1:0]                    act_type;
    wire                          argmax_clear;
    wire                          argmax_compare;
    wire [3:0]                    current_class_idx;
    wire [7:0]                    mac_count;

    // Controller instance
    npu_controller #(
        .DATA_WIDTH(DATA_WIDTH),
        .ACC_WIDTH (ACC_WIDTH)
    ) u_ctrl (
        .clk              (clk),
        .rst_n            (rst_n),
        .ena              (ena),
        .host_valid       (host_valid),
        .npu_ready        (npu_ready),
        .cmd_mode         (cmd_mode),
        .weight_stream    (weight_stream),
        .data_in          (data_in),
        .out_valid        (out_valid),
        .layer_done       (layer_done),
        .npu_busy         (npu_busy),
        .mac_en           (mac_en),
        .acc_clear        (acc_clear),
        .load_bias        (load_bias),
        .latched_weight   (latched_weight),
        .current_act      (current_act),
        .bias_to_load     (bias_to_load),
        .shift_val        (shift_val),
        .act_type         (act_type),
        .argmax_clear     (argmax_clear),
        .argmax_compare   (argmax_compare),
        .current_class_idx(current_class_idx),
        .mac_count        (mac_count)
    );

    // Array Datapath (Instantiates ROWS x COLS PEs)
    wire signed [ROWS*COLS*ACC_WIDTH-1:0] acc_out_grid;
    wire signed [ROWS*DATA_WIDTH-1:0]     data_a_out_vec;
    wire signed [COLS*DATA_WIDTH-1:0]     data_b_out_vec;

    npu_array #(
        .ROWS      (ROWS),
        .COLS      (COLS),
        .DATA_WIDTH(DATA_WIDTH),
        .ACC_WIDTH (ACC_WIDTH)
    ) u_array (
        .clk               (clk),
        .rst_n             (rst_n),
        .ena               (ena),
        .mac_en            (mac_en),
        .acc_clear         (acc_clear),
        .load_bias         (load_bias),
        .data_a_in_vec     (current_act),
        .data_b_in_vec     (latched_weight),
        .cascade_acc_in_vec(bias_to_load),
        .data_a_out_vec    (data_a_out_vec),
        .data_b_out_vec    (data_b_out_vec),
        .acc_out_grid      (acc_out_grid),
        .overflow_any      (overflow_any)
    );

    // Primary accumulator value from PE (0,0)
    wire signed [ACC_WIDTH-1:0] pe00_acc = acc_out_grid[ACC_WIDTH-1:0];

    // Activation & Requantization
    wire signed [DATA_WIDTH-1:0] act_signed;
    wire [DATA_WIDTH-1:0]        act_unsigned;

    npu_activation #(
        .ACC_WIDTH (ACC_WIDTH),
        .DATA_WIDTH(DATA_WIDTH)
    ) u_activation (
        .acc_in   (pe00_acc),
        .shift_val(shift_val),
        .act_type (act_type),
        .data_out (act_signed),
        .udata_out(act_unsigned)
    );

    // ArgMax Unit
    wire [3:0]                  best_class;
    wire signed [ACC_WIDTH-1:0] best_score;

    npu_argmax #(
        .ACC_WIDTH(ACC_WIDTH)
    ) u_argmax (
        .clk       (clk),
        .rst_n     (rst_n),
        .ena       (ena),
        .clear     (argmax_clear),
        .compare_en(argmax_compare),
        .score     (pe00_acc),
        .class_idx (current_class_idx),
        .best_class(best_class),
        .best_score(best_score)
    );

    // Output Multiplexing
    wire [7:0] status_byte = {
        overflow_any,        // [7]
        npu_busy,            // [6]
        out_valid,           // [5]
        layer_done,          // [4]
        best_class           // [3:0] Winning class from ArgMax!
    };

    assign data_out = out_sel ? status_byte : act_unsigned;

    wire _unused_ok = &{1'b0, mac_count, data_a_out_vec, data_b_out_vec, act_signed, best_score, 1'b0};

endmodule

`default_nettype wire
