`default_nettype none
`timescale 1ns/1ps

//==============================================================================
// Module:      npu_pe
// Description: Parameterized Processing Element (PE) for Scalable TinyML NPU.
//              Supports single-cycle signed INT8 MAC, accumulator load/clear,
//              and horizontal/vertical systolic cascade paths for scaling
//              from 1x1 tile to MxN systolic grid.
//==============================================================================

module npu_pe #(
    parameter DATA_WIDTH = 8,
    parameter ACC_WIDTH  = 24
)(
    input  wire                         clk,
    input  wire                         rst_n,
    input  wire                         ena,

    // Control signals
    input  wire                         mac_en,          // Enable MAC: Acc <= Acc + (A * B)
    input  wire                         acc_clear,       // Clear accumulator to 0
    input  wire                         load_bias,       // Load bias from cascade_acc_in

    // Data inputs
    input  wire signed [DATA_WIDTH-1:0] data_a_in,       // Feature / Activation input
    input  wire signed [DATA_WIDTH-1:0] data_b_in,       // Weight input
    input  wire signed [ACC_WIDTH-1:0]  cascade_acc_in,  // Cascade partial sum / bias in

    // Systolic pass-through outputs (for scaling to array)
    output reg  signed [DATA_WIDTH-1:0] data_a_out,      // Forward activation to east PE
    output reg  signed [DATA_WIDTH-1:0] data_b_out,      // Forward weight to south PE

    // Computation outputs
    output wire signed [ACC_WIDTH-1:0]  acc_out,         // Current accumulator value
    output reg                          overflow_flag    // Accumulator overflow indicator
);

    // Multiplier: Signed 8-bit x Signed 8-bit -> Signed 16-bit
    wire signed [15:0] prod = data_a_in * data_b_in;

    // Sign-extended product to accumulator width
    wire signed [ACC_WIDTH-1:0] prod_sext = {{(ACC_WIDTH-16){prod[15]}}, prod};

    // Internal Accumulator register
    reg signed [ACC_WIDTH-1:0] acc_reg;
    wire signed [ACC_WIDTH-1:0] acc_next = acc_reg + prod_sext;
    wire ovf_detected = (acc_reg[ACC_WIDTH-1] == prod_sext[ACC_WIDTH-1]) &&
                        (acc_next[ACC_WIDTH-1] != acc_reg[ACC_WIDTH-1]);

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            acc_reg       <= {ACC_WIDTH{1'b0}};
            data_a_out    <= {DATA_WIDTH{1'b0}};
            data_b_out    <= {DATA_WIDTH{1'b0}};
            overflow_flag <= 1'b0;
        end else if (ena) begin
            // Systolic forward registers
            data_a_out <= data_a_in;
            data_b_out <= data_b_in;

            if (acc_clear) begin
                acc_reg       <= {ACC_WIDTH{1'b0}};
                overflow_flag <= 1'b0;
            end else if (load_bias) begin
                acc_reg       <= cascade_acc_in;
                overflow_flag <= 1'b0;
            end else if (mac_en) begin
                acc_reg       <= acc_next;
                overflow_flag <= ovf_detected;
            end
        end
    end

    assign acc_out = acc_reg;

endmodule

`default_nettype wire
