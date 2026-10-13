`default_nettype none
`timescale 1ns/1ps

//==============================================================================
// Module:      npu_top_2x2
// Description: 2x2 broadcast MAC core; SYSTOLIC_MODE=0 is fixed here.
//              Contains 4 PEs (ROWS=2, COLS=2),
//              4 parallel requantization/activation units, and multi-PE multiplexer.
//==============================================================================

module npu_top_2x2 #(
    parameter DATA_WIDTH = 8,
    parameter ACC_WIDTH  = 24
)(
    input  wire                  clk,
    input  wire                  rst_n,
    input  wire                  ena,

    // Array-wide execution control
    input  wire                  mac_en,
    input  wire                  acc_clear,
    input  wire                  load_bias,

    // West activation inputs (Row 0, Row 1)
    input  wire signed [DATA_WIDTH-1:0] act_in_r0,
    input  wire signed [DATA_WIDTH-1:0] act_in_r1,

    // North weight inputs (Col 0, Col 1)
    input  wire signed [DATA_WIDTH-1:0] weight_in_c0,
    input  wire signed [DATA_WIDTH-1:0] weight_in_c1,

    // North bias/cascade inputs (Col 0, Col 1)
    input  wire signed [ACC_WIDTH-1:0]  bias_in_c0,
    input  wire signed [ACC_WIDTH-1:0]  bias_in_c1,

    // Requantization parameters
    input  wire [3:0]            shift_val,
    input  wire [1:0]            act_type,

    // PE Readout multiplexer selector (2'b00: PE00, 2'b01: PE01, 2'b10: PE10, 2'b11: PE11)
    input  wire [1:0]            pe_sel,
    input  wire                  out_acc_sel,

    // Outputs
    output wire signed [DATA_WIDTH-1:0] data_out,
    output wire signed [ACC_WIDTH-1:0]  acc_out_selected,

    // Direct parallel accumulator outputs from all 4 PEs
    output wire signed [ACC_WIDTH-1:0]  pe00_acc,
    output wire signed [ACC_WIDTH-1:0]  pe01_acc,
    output wire signed [ACC_WIDTH-1:0]  pe10_acc,
    output wire signed [ACC_WIDTH-1:0]  pe11_acc,

    // Direct parallel requantized outputs from all 4 PEs
    output wire signed [DATA_WIDTH-1:0] pe00_act,
    output wire signed [DATA_WIDTH-1:0] pe01_act,
    output wire signed [DATA_WIDTH-1:0] pe10_act,
    output wire signed [DATA_WIDTH-1:0] pe11_act,

    // Boundary outputs
    output wire signed [DATA_WIDTH-1:0] act_out_r0,
    output wire signed [DATA_WIDTH-1:0] act_out_r1,
    output wire signed [DATA_WIDTH-1:0] weight_out_c0,
    output wire signed [DATA_WIDTH-1:0] weight_out_c1,

    output wire                  overflow_any
);

    wire signed [2*DATA_WIDTH-1:0] data_a_in_vec = {act_in_r1, act_in_r0};
    wire signed [2*DATA_WIDTH-1:0] data_b_in_vec = {weight_in_c1, weight_in_c0};
    wire signed [2*ACC_WIDTH-1:0]  cascade_in_vec = {bias_in_c1, bias_in_c0};

    wire signed [2*DATA_WIDTH-1:0] data_a_out_vec;
    wire signed [2*DATA_WIDTH-1:0] data_b_out_vec;
    wire signed [4*ACC_WIDTH-1:0]  acc_out_grid;

    assign act_out_r0    = data_a_out_vec[0*DATA_WIDTH +: DATA_WIDTH];
    assign act_out_r1    = data_a_out_vec[1*DATA_WIDTH +: DATA_WIDTH];
    assign weight_out_c0 = data_b_out_vec[0*DATA_WIDTH +: DATA_WIDTH];
    assign weight_out_c1 = data_b_out_vec[1*DATA_WIDTH +: DATA_WIDTH];

    npu_array #(
        .ROWS      (2),
        .COLS      (2),
        .DATA_WIDTH(DATA_WIDTH),
        .ACC_WIDTH (ACC_WIDTH)
    ) u_array_2x2 (
        .clk               (clk),
        .rst_n             (rst_n),
        .ena               (ena),
        .mac_en            (mac_en),
        .acc_clear         (acc_clear),
        .load_bias         (load_bias),
        .data_a_in_vec     (data_a_in_vec),
        .data_b_in_vec     (data_b_in_vec),
        .cascade_acc_in_vec(cascade_in_vec),
        .data_a_out_vec    (data_a_out_vec),
        .data_b_out_vec    (data_b_out_vec),
        .acc_out_grid      (acc_out_grid),
        .overflow_any      (overflow_any)
    );

    assign pe00_acc = acc_out_grid[0*ACC_WIDTH +: ACC_WIDTH];
    assign pe01_acc = acc_out_grid[1*ACC_WIDTH +: ACC_WIDTH];
    assign pe10_acc = acc_out_grid[2*ACC_WIDTH +: ACC_WIDTH];
    assign pe11_acc = acc_out_grid[3*ACC_WIDTH +: ACC_WIDTH];

    wire [DATA_WIDTH-1:0] upe00_act, upe01_act, upe10_act, upe11_act;

    npu_activation #(.ACC_WIDTH(ACC_WIDTH), .DATA_WIDTH(DATA_WIDTH)) u_act_00 (
        .acc_in(pe00_acc), .shift_val(shift_val), .act_type(act_type),
        .data_out(pe00_act), .udata_out(upe00_act)
    );

    npu_activation #(.ACC_WIDTH(ACC_WIDTH), .DATA_WIDTH(DATA_WIDTH)) u_act_01 (
        .acc_in(pe01_acc), .shift_val(shift_val), .act_type(act_type),
        .data_out(pe01_act), .udata_out(upe01_act)
    );

    npu_activation #(.ACC_WIDTH(ACC_WIDTH), .DATA_WIDTH(DATA_WIDTH)) u_act_10 (
        .acc_in(pe10_acc), .shift_val(shift_val), .act_type(act_type),
        .data_out(pe10_act), .udata_out(upe10_act)
    );

    npu_activation #(.ACC_WIDTH(ACC_WIDTH), .DATA_WIDTH(DATA_WIDTH)) u_act_11 (
        .acc_in(pe11_acc), .shift_val(shift_val), .act_type(act_type),
        .data_out(pe11_act), .udata_out(upe11_act)
    );

    reg signed [DATA_WIDTH-1:0] mux_act;
    reg signed [ACC_WIDTH-1:0]  mux_acc;

    always @(*) begin
        case (pe_sel)
            2'b00: begin mux_act = pe00_act; mux_acc = pe00_acc; end
            2'b01: begin mux_act = pe01_act; mux_acc = pe01_acc; end
            2'b10: begin mux_act = pe10_act; mux_acc = pe10_acc; end
            2'b11: begin mux_act = pe11_act; mux_acc = pe11_acc; end
        endcase
    end

    assign data_out         = mux_act;
    assign acc_out_selected = mux_acc;

    wire _unused_ok = &{1'b0, out_acc_sel, upe00_act, upe01_act, upe10_act, upe11_act, 1'b0};

endmodule

`default_nettype wire
