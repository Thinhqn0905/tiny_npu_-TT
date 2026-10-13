`default_nettype none
`timescale 1ns/1ps

//==============================================================================
// Module:      npu_array
// Description: Parameterized 2D Processing Element (PE) Array for Scalable
//              TinyML NPU. Configurable grid dimensions (ROWS x COLS) supporting
//              both 2D Fold-SIMD Parallel Broadcast matrix multiplication and
//              Kung-Leiserson Systolic Wavefront forward chaining.
//              Features parameterized bitwidths and vertical cascade accumulators.
//==============================================================================

module npu_array #(
    parameter ROWS          = 1,
    parameter COLS          = 1,
    parameter DATA_WIDTH    = 8,
    parameter ACC_WIDTH     = 24,
    parameter SYSTOLIC_MODE = 0  // 0: 2D Fold-SIMD Parallel Broadcast, 1: Systolic Wavefront
)(
    input  wire                                  clk,
    input  wire                                  rst_n,
    input  wire                                  ena,
    input  wire                                  mac_en,
    input  wire                                  acc_clear,
    input  wire                                  load_bias,
    input  wire signed [ROWS*DATA_WIDTH-1:0]     data_a_in_vec,
    input  wire signed [COLS*DATA_WIDTH-1:0]     data_b_in_vec,
    input  wire signed [COLS*ACC_WIDTH-1:0]      cascade_acc_in_vec,
    output wire signed [ROWS*DATA_WIDTH-1:0]     data_a_out_vec,
    output wire signed [COLS*DATA_WIDTH-1:0]     data_b_out_vec,
    output wire signed [ROWS*COLS*ACC_WIDTH-1:0] acc_out_grid,
    output wire                                  overflow_any
);

    wire signed [DATA_WIDTH-1:0] a_wire   [0:ROWS-1][0:COLS];
    wire signed [DATA_WIDTH-1:0] b_wire   [0:ROWS][0:COLS-1];
    wire signed [ACC_WIDTH-1:0]  acc_wire [0:ROWS-1][0:COLS-1];
    wire                         ovf_wire [0:ROWS-1][0:COLS-1];

    genvar r, c;
    generate
        // Boundary Activation Wiring
        for (r = 0; r < ROWS; r = r + 1) begin : gen_west_in
            assign a_wire[r][0] = data_a_in_vec[r*DATA_WIDTH +: DATA_WIDTH];
            assign data_a_out_vec[r*DATA_WIDTH +: DATA_WIDTH] = a_wire[r][COLS];
        end

        // Boundary Weight Wiring
        for (c = 0; c < COLS; c = c + 1) begin : gen_north_in
            assign b_wire[0][c] = data_b_in_vec[c*DATA_WIDTH +: DATA_WIDTH];
            assign data_b_out_vec[c*DATA_WIDTH +: DATA_WIDTH] = b_wire[ROWS][c];
        end

        // 2D Processing Element Grid Instantiation
        for (r = 0; r < ROWS; r = r + 1) begin : gen_pe_rows
            for (c = 0; c < COLS; c = c + 1) begin : gen_pe_cols

                // Select input source based on SYSTOLIC_MODE parameter
                wire signed [DATA_WIDTH-1:0] pe_a_in;
                wire signed [DATA_WIDTH-1:0] pe_b_in;

                if (SYSTOLIC_MODE == 1) begin : gen_systolic_in
                    assign pe_a_in = a_wire[r][c];
                    assign pe_b_in = b_wire[r][c];
                end else begin : gen_broadcast_in
                    assign pe_a_in = data_a_in_vec[r*DATA_WIDTH +: DATA_WIDTH];
                    assign pe_b_in = data_b_in_vec[c*DATA_WIDTH +: DATA_WIDTH];
                end

                // Safe North boundary or vertical cascade partial sum selection
                wire signed [ACC_WIDTH-1:0] pe_bias_in;
                if (r == 0) begin : gen_north_bias
                    assign pe_bias_in = cascade_acc_in_vec[c*ACC_WIDTH +: ACC_WIDTH];
                end else begin : gen_internal_cascade
                    assign pe_bias_in = acc_wire[r-1][c];
                end

                npu_pe #(
                    .DATA_WIDTH(DATA_WIDTH),
                    .ACC_WIDTH (ACC_WIDTH)
                ) u_pe (
                    .clk            (clk),
                    .rst_n          (rst_n),
                    .ena            (ena),
                    .mac_en         (mac_en),
                    .acc_clear      (acc_clear),
                    .load_bias      (load_bias),
                    .data_a_in      (pe_a_in),
                    .data_b_in      (pe_b_in),
                    .cascade_acc_in (pe_bias_in),
                    .data_a_out     (a_wire[r][c+1]),
                    .data_b_out     (b_wire[r+1][c]),
                    .acc_out        (acc_wire[r][c]),
                    .overflow_flag  (ovf_wire[r][c])
                );

                assign acc_out_grid[(r*COLS + c)*ACC_WIDTH +: ACC_WIDTH] = acc_wire[r][c];
            end
        end
    endgenerate

    // Reduction OR for all PE overflow flags in array
    reg ovf_comb;
    integer ir, ic;
    always @(*) begin
        ovf_comb = 1'b0;
        for (ir = 0; ir < ROWS; ir = ir + 1) begin
            for (ic = 0; ic < COLS; ic = ic + 1) begin
                ovf_comb = ovf_comb | ovf_wire[ir][ic];
            end
        end
    end
    assign overflow_any = ovf_comb;

endmodule

`default_nettype wire
