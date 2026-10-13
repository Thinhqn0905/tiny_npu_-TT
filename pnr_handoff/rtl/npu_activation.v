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
    input  wire [1:0]                   act_type,     // 00: Linear, 01: ReLU, 10: Sgn Clip, 11: Unsgn Clip
    output wire signed [DATA_WIDTH-1:0] data_out,     // Saturated 8-bit signed output
    output wire [DATA_WIDTH-1:0]        udata_out     // Saturated 8-bit unsigned output
);

    // Rounding addition: add 2^(shift-1) if shift_val > 0
    wire signed [ACC_WIDTH-1:0] round_offset = (shift_val > 4'd0) ?
                                               ($signed(24'sd1) <<< (shift_val - 4'd1)) : 24'sd0;

    wire signed [ACC_WIDTH-1:0] acc_rounded = acc_in + round_offset;

    // Arithmetic right shift
    wire signed [ACC_WIDTH-1:0] shifted = acc_rounded >>> shift_val;

    // Saturated signed 8-bit clipping [-128, 127]
    wire signed [7:0] signed_clipped = (shifted > 24'sd127)  ? 8'sd127 :
                                       (shifted < -24'sd128) ? -8'sd128 :
                                       shifted[7:0];

    // ReLU activation: max(0, x)
    wire [7:0] relu_clipped = (shifted < 24'sd0)   ? 8'd0 :
                              (shifted > 24'sd255) ? 8'd255 :
                              shifted[7:0];

    // Unsigned clipping [0, 255]
    wire [7:0] unsigned_clipped = (shifted < 24'sd0)   ? 8'd0 :
                                  (shifted > 24'sd255) ? 8'd255 :
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
