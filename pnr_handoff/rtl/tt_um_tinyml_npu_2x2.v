`default_nettype none
`timescale 1ns/1ps

//==============================================================================
// Module:      tt_um_tinyml_npu_2x2
// Project:     Scalable TinyML NPU for 2x2 Systolic Array (Tiny Tapeout Top)
// Author:      Thinh Pham
// Description: Standard Tiny Tapeout Top Wrapper for the 2x2 Systolic Array NPU.
//              Integrates streaming operand deserializer, runtime configuration,
//              and multi-channel PE readout multiplexing.
//              Allocates 1x2 tiles (202 um x 314 um) on Tiny Tapeout shuttle.
//==============================================================================

module tt_um_tinyml_npu_2x2 (
    input  wire [7:0] ui_in,    // Dedicated inputs: Data stream / Opcode
    output wire [7:0] uo_out,   // Dedicated outputs: Result byte or Status
    input  wire [7:0] uio_in,   // Bidirectional inputs
    output wire [7:0] uio_out,  // Bidirectional outputs
    output wire [7:0] uio_oe,   // Bidirectional output enables (active high)
    input  wire       ena,      // Chip enable (active high)
    input  wire       clk,      // System Clock (Nominal 50 MHz)
    input  wire       rst_n     // Master Active-low reset
);

    // Bidirectional pin mapping:
    // uio[0] (in)  : host_valid
    // uio[1] (out) : npu_ready
    // uio[2] (in)  : cmd_mode      (1 = Command/Config, 0 = Data Byte)
    // uio[3] (in)  : stream_sel    (Reserved / direct mode selector)
    // uio[4] (in)  : out_sel       (0 = PE Activation, 1 = Status Byte)
    // uio[5] (out) : out_valid
    // uio[6] (out) : layer_done
    // uio[7] (out) : npu_busy

    wire host_valid = uio_in[0];
    wire cmd_mode   = uio_in[2];
    wire stream_sel = uio_in[3];
    wire out_sel    = uio_in[4];

    reg  npu_ready;
    reg  out_valid;
    reg  layer_done;
    reg  npu_busy;

    // Pin Direction Configuration (uio[7:5], uio[1] are outputs -> 8'b11100010)
    assign uio_oe = 8'b11100010;

    assign uio_out[0] = 1'b0;
    assign uio_out[1] = npu_ready;
    assign uio_out[2] = 1'b0;
    assign uio_out[3] = 1'b0;
    assign uio_out[4] = 1'b0;
    assign uio_out[5] = out_valid;
    assign uio_out[6] = layer_done;
    assign uio_out[7] = npu_busy;

    // Internal 2x2 Array Control & Streaming Registers
    reg                  mac_en;
    reg                  acc_clear;
    reg                  load_bias;
    reg  signed [7:0]    r0_act;
    reg  signed [7:0]    r1_act;
    reg  signed [7:0]    c0_weight;
    reg  signed [7:0]    c1_weight;
    reg  signed [23:0]   bias_c0;
    reg  signed [23:0]   bias_c1;
    reg         [3:0]    shift_val;
    reg         [1:0]    act_type;
    reg         [1:0]    pe_sel;
    reg         [7:0]    cfg_vector_len;
    reg         [7:0]    mac_count;
    reg         [1:0]    byte_idx;

    localparam S_IDLE     = 2'd0;
    localparam S_POST_MAC = 2'd1;
    localparam S_FINISH   = 2'd2;

    reg [1:0] state;

    // FSM & Streaming Sequencer
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state          <= S_IDLE;
            npu_ready      <= 1'b1;
            out_valid      <= 1'b0;
            layer_done     <= 1'b0;
            npu_busy       <= 1'b0;
            mac_en         <= 1'b0;
            acc_clear      <= 1'b0;
            load_bias      <= 1'b0;
            r0_act         <= 8'sd0;
            r1_act         <= 8'sd0;
            c0_weight      <= 8'sd0;
            c1_weight      <= 8'sd0;
            bias_c0        <= 24'sd0;
            bias_c1        <= 24'sd0;
            shift_val      <= 4'd0;
            act_type       <= 2'b00;
            pe_sel         <= 2'b00;
            cfg_vector_len <= 8'd1;
            mac_count      <= 8'd0;
            byte_idx       <= 2'b00;
        end else if (ena) begin
            // Default single-cycle pulse clears
            mac_en     <= 1'b0;
            acc_clear  <= 1'b0;
            load_bias  <= 1'b0;
            layer_done <= 1'b0;

            case (state)
                S_IDLE: begin
                    npu_ready <= 1'b1;
                    if (host_valid) begin
                        if (cmd_mode) begin
                            // Command Decode
                            case (ui_in[7:6])
                                2'b00: begin // CMD_SET_LEN
                                    cfg_vector_len <= {2'b00, ui_in[5:0]} + 8'd1;
                                    mac_count      <= 8'd0;
                                    byte_idx       <= 2'b00;
                                end
                                2'b01: begin // CMD_SET_POST
                                    shift_val <= ui_in[3:0];
                                    act_type  <= ui_in[5:4];
                                end
                                2'b10: begin // CMD_ACC_OPS
                                    if (ui_in[0]) acc_clear <= 1'b1;
                                    if (ui_in[1]) load_bias <= 1'b1;
                                    pe_sel <= ui_in[5:4];
                                end
                                2'b11: begin // CMD_LOAD_BIAS (8-bit signed broadcast to bias_c0, c1)
                                    load_bias <= 1'b1;
                                    bias_c0   <= {{(16){ui_in[7]}}, ui_in};
                                    bias_c1   <= {{(16){ui_in[7]}}, ui_in};
                                    mac_count <= 8'd0;
                                end
                                default: ;
                            endcase
                        end else begin
                            // Streaming 2x2 Operand Ingestion
                            npu_busy <= 1'b1;
                            case (byte_idx)
                                2'b00: begin
                                    r0_act   <= ui_in;
                                    byte_idx <= 2'b01;
                                end
                                2'b01: begin
                                    r1_act   <= ui_in;
                                    byte_idx <= 2'b10;
                                end
                                2'b10: begin
                                    c0_weight <= ui_in;
                                    byte_idx  <= 2'b11;
                                end
                                2'b11: begin
                                    c1_weight <= ui_in;
                                    byte_idx  <= 2'b00;
                                    mac_en    <= 1'b1;
                                    state     <= S_POST_MAC;
                                end
                                default: byte_idx <= 2'b00;
                            endcase
                        end
                    end
                end

                S_POST_MAC: begin
                    if (mac_count + 8'd1 >= cfg_vector_len) begin
                        mac_count  <= 8'd0;
                        out_valid  <= 1'b1;
                        layer_done <= 1'b1;
                        state      <= S_FINISH;
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

    // Core Instantiation: 2x2 Systolic Array NPU
    wire signed [7:0]  core_data_out;
    wire signed [23:0] acc_out_selected;
    wire signed [23:0] pe00_acc, pe01_acc, pe10_acc, pe11_acc;
    wire signed [7:0]  pe00_act, pe01_act, pe10_act, pe11_act;
    wire signed [7:0]  act_out_r0, act_out_r1;
    wire signed [7:0]  weight_out_c0, weight_out_c1;
    wire               overflow_any;

    npu_top_2x2 #(
        .DATA_WIDTH(8),
        .ACC_WIDTH (24)
    ) u_core_2x2 (
        .clk             (clk),
        .rst_n           (rst_n),
        .ena             (ena),
        .mac_en          (mac_en),
        .acc_clear       (acc_clear),
        .load_bias       (load_bias),
        .act_in_r0       (r0_act),
        .act_in_r1       (r1_act),
        .weight_in_c0    (c0_weight),
        .weight_in_c1    (c1_weight),
        .bias_in_c0      (bias_c0),
        .bias_in_c1      (bias_c1),
        .shift_val       (shift_val),
        .act_type        (act_type),
        .pe_sel          (pe_sel),
        .out_acc_sel     (1'b0),
        .data_out        (core_data_out),
        .acc_out_selected(acc_out_selected),
        .pe00_acc        (pe00_acc),
        .pe01_acc        (pe01_acc),
        .pe10_acc        (pe10_acc),
        .pe11_acc        (pe11_acc),
        .pe00_act        (pe00_act),
        .pe01_act        (pe01_act),
        .pe10_act        (pe10_act),
        .pe11_act        (pe11_act),
        .act_out_r0      (act_out_r0),
        .act_out_r1      (act_out_r1),
        .weight_out_c0   (weight_out_c0),
        .weight_out_c1   (weight_out_c1),
        .overflow_any    (overflow_any)
    );

    // Output Status Byte:
    // [7]: overflow_any
    // [6]: npu_busy
    // [5]: out_valid
    // [4]: layer_done
    // [3:2]: byte_idx
    // [1:0]: pe_sel
    wire [7:0] status_byte = {
        overflow_any,
        npu_busy,
        out_valid,
        layer_done,
        byte_idx,
        pe_sel
    };

    assign uo_out = out_sel ? status_byte : core_data_out;

    // Unused signal tie-off to silence linter without synthesis overhead
    wire _unused_ok = &{
        1'b0,
        uio_in[7:5],
        uio_in[3],
        uio_in[1],
        stream_sel,
        acc_out_selected,
        pe00_acc, pe01_acc, pe10_acc, pe11_acc,
        pe00_act, pe01_act, pe10_act, pe11_act,
        act_out_r0, act_out_r1,
        weight_out_c0, weight_out_c1,
        1'b0
    };

endmodule

`default_nettype wire
