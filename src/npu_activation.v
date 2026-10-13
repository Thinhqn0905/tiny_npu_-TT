`default_nettype none
`timescale 1ns/1ps

//==============================================================================
// Module:      npu_activation
// Description: Requantization, arithmetic shifter, and activation function.
//              Converts high-precision 24-bit accumulator to quantized 8-bit
//              activations with rounding, arithmetic right-shift, and saturation.
//==============================================================================

module npu_activation #(
    parameter ACC_WIDTH  = 24,
    parameter DATA_WIDTH = 8
)(
    input  wire signed [ACC_WIDTH-1:0]  acc_in,       // 24-bit signed accumulator
    input  wire [3:0]                   shift_val,    // Arithmetic right-shift (0..15)
    input  wire [1:0]                   act_type,     // Signed output: 01 ReLU, all others signed clip
    output wire signed [DATA_WIDTH-1:0] data_out,     // Saturated 8-bit signed output
    output wire [DATA_WIDTH-1:0]        udata_out     // Saturated 8-bit unsigned output
);

    // Rounding addition: add 2^(shift-1) if shift_val > 0
    // One extra bit prevents positive accumulators wrapping during rounding.
    // Round to nearest with exact ties toward positive infinity (also for negatives).
    localparam signed [ACC_WIDTH:0] ONE = 1;
    localparam signed [ACC_WIDTH:0] ZERO = 0;
    localparam signed [ACC_WIDTH:0] SIGNED_MAX = 127;
    localparam signed [ACC_WIDTH:0] SIGNED_MIN = -128;
    localparam signed [ACC_WIDTH:0] UNSIGNED_MAX = 255;
    wire signed [ACC_WIDTH:0] round_offset = (shift_val > 4'd0) ?
                                             (ONE <<< (shift_val - 4'd1)) : 0;

    wire signed [ACC_WIDTH:0] acc_rounded = {acc_in[ACC_WIDTH-1], acc_in} + round_offset;

    // Arithmetic right shift
    wire signed [ACC_WIDTH:0] shifted = acc_rounded >>> shift_val;

    // Saturated signed 8-bit clipping [-128, 127]
    wire signed [7:0] signed_clipped = (shifted > SIGNED_MAX)  ? 8'sd127 :
                                       (shifted < SIGNED_MIN) ? -8'sd128 :
                                       shifted[7:0];

    // ReLU activation: max(0, x)
    wire [7:0] relu_clipped = (shifted < ZERO)   ? 8'd0 :
                              (shifted > UNSIGNED_MAX) ? 8'd255 :
                              shifted[7:0];

    // Unsigned clipping [0, 255]
    wire [7:0] unsigned_clipped = (shifted < ZERO)   ? 8'd0 :
                                  (shifted > UNSIGNED_MAX) ? 8'd255 :
                                  shifted[7:0];

    // Mux outputs based on activation type
    reg signed [7:0] result_signed;
    reg [7:0]        result_unsigned;

    always @(*) begin
        case (act_type)
            2'b00: begin // Linear
                result_signed   = signed_clipped;
                result_unsigned = unsigned_clipped;
            end
            2'b01: begin // ReLU
                result_signed   = (signed_clipped < 8'sd0) ? 8'sd0 : signed_clipped;
                result_unsigned = relu_clipped;
            end
            2'b10: begin // Saturated Signed
                result_signed   = signed_clipped;
                result_unsigned = unsigned_clipped;
            end
            2'b11: begin // Saturated Unsigned
                result_signed   = signed_clipped;
                result_unsigned = unsigned_clipped;
            end
        endcase
    end

    assign data_out  = result_signed;
    assign udata_out = result_unsigned;

endmodule

`default_nettype wire
