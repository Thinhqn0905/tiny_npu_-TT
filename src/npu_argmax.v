`default_nettype none
`timescale 1ns/1ps

//==============================================================================
// Module:      npu_argmax
// Description: Winner-take-all ArgMax unit for classification tasks (e.g. ECG
//              arrhythmia detection, MNIST, audio keyword spotting).
//              Tracks max signed score and reports winning class index.
//==============================================================================

module npu_argmax #(
    parameter ACC_WIDTH = 24
)(
    input  wire                         clk,
    input  wire                         rst_n,
    input  wire                         ena,

    input  wire                         clear,        // Clear for new inference
    input  wire                         compare_en,   // Trigger comparison
    input  wire signed [ACC_WIDTH-1:0]  score,        // Current class score
    input  wire [3:0]                   class_idx,    // Current class index (0..15)

    output reg  [3:0]                   best_class,   // Winning class index
    output reg  signed [ACC_WIDTH-1:0]  best_score    // Maximum score seen
);

    // Minimum 24-bit signed value: -2^23 = -8,388,608
    localparam signed [ACC_WIDTH-1:0] MIN_SCORE = -(24'sd1 <<< (ACC_WIDTH-1));

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            best_class <= 4'd0;
            best_score <= MIN_SCORE;
        end else if (ena) begin
            if (clear) begin
                best_class <= 4'd0;
                best_score <= MIN_SCORE;
            end else if (compare_en) begin
                if (score > best_score) begin
                    best_score <= score;
                    best_class <= class_idx;
                end
            end
        end
    end

endmodule

`default_nettype wire
