`default_nettype none
`timescale 1ns/1ps

//==============================================================================
// Module:      npu_controller
// Description: Scalable instruction decoder and streaming MAC controller.
//              Decodes runtime micro-ops (vector length, quantization shift,
//              activation type, bias loading, ArgMax) and manages the
//              ready/valid streaming handshake with the host MCU.
//==============================================================================

module npu_controller #(
    parameter DATA_WIDTH = 8,
    parameter ACC_WIDTH  = 24
)(
    input  wire                         clk,
    input  wire                         rst_n,
    input  wire                         ena,

    // Host Handshake & Control
    input  wire                         host_valid,
    output reg                          npu_ready,
    input  wire                         cmd_mode,       // 1 = Command/Config, 0 = Data Byte
    input  wire                         weight_stream,  // 1 = Weight, 0 = Activation
    input  wire [DATA_WIDTH-1:0]        data_in,

    // Status to Host
    output reg                          out_valid,
    output reg                          layer_done,
    output reg                          npu_busy,

    // Internal Datapath Control
    output reg                          mac_en,
    output reg                          acc_clear,
    output reg                          load_bias,
    output reg  signed [DATA_WIDTH-1:0] latched_weight,
    output reg  signed [DATA_WIDTH-1:0] current_act,
    output reg  signed [ACC_WIDTH-1:0]  bias_to_load,

    // Post-processing Config
    output reg  [3:0]                   shift_val,
    output reg  [1:0]                   act_type,
    output reg                          argmax_clear,
    output reg                          argmax_compare,
    output reg  [3:0]                   current_class_idx,
    output reg  [7:0]                   mac_count
);

    // Configuration registers
    reg [7:0] cfg_vector_len;   // Number of MACs per dot-product (1..256)
    reg       has_weight;       // Flag indicating weight is latched
    reg       auto_argmax;      // Automatically compare ArgMax on vector finish

    // Opcodes when cmd_mode = 1:
    // ui_in[7:6]:
    //   00 = CMD_SET_LEN      ui_in[5:0] = length - 1 (1 to 64, or multi-byte)
    //   01 = CMD_SET_POST     ui_in[3:0] = shift, ui_in[5:4] = act_type
    //   10 = CMD_ACC_OPS      ui_in[0] = acc_clear, ui_in[1] = argmax_clear, ui_in[2] = argmax_cmp, ui_in[5:4] = class
    //   11 = CMD_LOAD_BIAS    ui_in[5:0] = signed bias (or followed by full byte)

    localparam S_IDLE     = 2'd0;
    localparam S_STREAM   = 2'd1;
    localparam S_POST_MAC = 2'd2;
    localparam S_FINISH   = 2'd3;

    reg [1:0] state;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state             <= S_IDLE;
            npu_ready         <= 1'b1;
            out_valid         <= 1'b0;
            layer_done        <= 1'b0;
            npu_busy          <= 1'b0;
            mac_en            <= 1'b0;
            acc_clear         <= 1'b0;
            load_bias         <= 1'b0;
            latched_weight    <= {DATA_WIDTH{1'b0}};
            current_act       <= {DATA_WIDTH{1'b0}};
            bias_to_load      <= {ACC_WIDTH{1'b0}};
            shift_val         <= 4'd0;
            act_type          <= 2'b00;
            argmax_clear      <= 1'b0;
            argmax_compare    <= 1'b0;
            current_class_idx <= 4'd0;
            cfg_vector_len    <= 8'd1;
            mac_count         <= 8'd0;
            has_weight        <= 1'b0;
            auto_argmax       <= 1'b0;
        end else if (ena) begin
            // Default single-cycle pulse clears
            mac_en         <= 1'b0;
            acc_clear      <= 1'b0;
            load_bias      <= 1'b0;
            argmax_clear   <= 1'b0;
            argmax_compare <= 1'b0;
            layer_done     <= 1'b0;

            case (state)
                S_IDLE: begin
                    npu_ready <= 1'b1;
                    if (host_valid) begin
                        if (cmd_mode) begin
                            // Command decode
                            case (data_in[7:6])
                                2'b00: begin // CMD_SET_LEN
                                    cfg_vector_len <= {2'b00, data_in[5:0]} + 8'd1;
                                    mac_count      <= 8'd0;
                                end
                                2'b01: begin // CMD_SET_POST
                                    shift_val   <= data_in[3:0];
                                    act_type    <= data_in[5:4];
                                end
                                2'b10: begin // CMD_ACC_OPS
                                    if (data_in[0]) acc_clear    <= 1'b1;
                                    if (data_in[1]) argmax_clear <= 1'b1;
                                    if (data_in[2]) begin
                                        argmax_compare    <= 1'b1;
                                        current_class_idx <= {2'b00, data_in[5:4]};
                                    end
                                    auto_argmax <= data_in[3]; // bit 3: enable auto argmax at end
                                end
                                2'b11: begin // CMD_LOAD_BIAS (8-bit signed)
                                    load_bias    <= 1'b1;
                                    bias_to_load <= {{(ACC_WIDTH-DATA_WIDTH){data_in[5]}}, data_in[5:0], 2'b00};
                                    mac_count    <= 8'd0;
                                end
                                default: ;
                            endcase
                        end else begin
                            // Data stream starts
                            npu_busy <= 1'b1;
                            if (weight_stream) begin
                                latched_weight <= data_in;
                                has_weight     <= 1'b1;
                            end else begin
                                current_act <= data_in;
                                if (has_weight) begin
                                    mac_en <= 1'b1;
                                    state  <= S_POST_MAC;
                                end
                            end
                        end
                    end
                end

                S_POST_MAC: begin
                    // After MAC computation
                    has_weight <= 1'b0; // Consumed pair
                    if (mac_count + 8'd1 >= cfg_vector_len) begin
                        // Dot-product finished!
                        mac_count  <= 8'd0;
                        out_valid  <= 1'b1;
                        layer_done <= 1'b1;
                        if (auto_argmax) begin
                            argmax_compare <= 1'b1;
                        end
                        state <= S_FINISH;
                    end else begin
                        mac_count <= mac_count + 8'd1;
                        state     <= S_IDLE;
                    end
                end

                S_FINISH: begin
                    out_valid <= 1'b0;
                    npu_busy  <= 1'b0;
                    state     <= S_IDLE;
                end

                default: begin
                    state <= S_IDLE;
                end
            endcase
        end
    end

endmodule

`default_nettype wire
