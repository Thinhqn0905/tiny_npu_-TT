`default_nettype none
`timescale 1ns/1ps

//==============================================================================
// Testbench:   tb_tt_um_2x2
// Description: Comprehensive verification of Tiny Tapeout 2x2 Top Module
//              (tt_um_tinyml_npu_2x2). Tests streaming ingestion, FSM control,
//              4-PE concurrent computation, and multiplexed readout.
//==============================================================================

module tb_tt_um_2x2;

    reg        clk;
    reg        rst_n;
    reg        ena;
    reg  [7:0] ui_in;
    reg  [7:0] uio_in;
    wire [7:0] uo_out;
    wire [7:0] uio_out;
    wire [7:0] uio_oe;

    tt_um_tinyml_npu_2x2 dut (
        .ui_in  (ui_in),
        .uo_out (uo_out),
        .uio_in (uio_in),
        .uio_out(uio_out),
        .uio_oe (uio_oe),
        .ena    (ena),
        .clk    (clk),
        .rst_n  (rst_n)
    );

    // Clock generator (50 MHz -> 20ns period)
    always #10 clk = ~clk;

    // Helper functions
    function [7:0] make_uio(input valid, input cmd, input out_sel);
        make_uio = (valid ? 8'h01 : 8'h00) |
                   (cmd   ? 8'h04 : 8'h00) |
                   (out_sel ? 8'h10 : 8'h00);
    endfunction

    task send_cmd(input [7:0] cmd_byte);
        begin
            @(posedge clk);
            ui_in  <= cmd_byte;
            uio_in <= make_uio(1'b1, 1'b1, 1'b0);
            @(posedge clk);
            uio_in <= 8'h00;
            ui_in  <= 8'h00;
            @(posedge clk);
        end
    endtask

    task send_data_byte(input [7:0] data_byte);
        begin
            @(posedge clk);
            ui_in  <= data_byte;
            uio_in <= make_uio(1'b1, 1'b0, 1'b0);
            @(posedge clk);
            uio_in <= 8'h00;
            ui_in  <= 8'h00;
        end
    endtask

    integer err_count = 0;

    initial begin
        $dumpfile("tb_tt_um_2x2.vcd");
        $dumpvars(0, tb_tt_um_2x2);

        clk    = 0;
        rst_n  = 0;
        ena    = 1;
        ui_in  = 8'h00;
        uio_in = 8'h00;

        #100;
        @(posedge clk);
        rst_n = 1;
        #40;

        $display("==================================================================");
        $display("  STARTING TT_UM_TINYML_NPU_2X2 TINY TAPEOUT TOP VERIFICATION");
        $display("==================================================================");

        // Test 1: Reset Check
        if (uio_out[1] == 1'b1 && uio_out[7] == 1'b0) begin
            $display("[PASS] TC1_RESET: npu_ready=1 and npu_busy=0 as expected.");
        end else begin
            $display("[FAIL] TC1_RESET: npu_ready or npu_busy mismatch! uio_out=%b", uio_out);
            err_count = err_count + 1;
        end

        // Test 2: Set Vector Length = 1, Requant Shift = 0, Linear activation
        send_cmd(8'h00); // CMD_SET_LEN: len = 1
        send_cmd(8'h40); // CMD_SET_POST: shift = 0, Linear (00)
        send_cmd(8'h81); // CMD_ACC_OPS: acc_clear = 1, pe_sel = 00

        // Test 3: Stream 4 operands for 2x2 Parallel MAC
        // Row 0 act = 8, Row 1 act = 7
        // Col 0 weight = 9, Col 1 weight = 5
        // Expected products:
        // PE00: 8 * 9 = 72
        // PE01: 8 * 5 = 40
        // PE10: 7 * 9 = 63
        // PE11: 7 * 5 = 35
        send_data_byte(8'd8); // r0_act
        send_data_byte(8'd7); // r1_act
        send_data_byte(8'd9); // c0_weight
        send_data_byte(8'd5); // c1_weight -> triggers mac_en

        // Wait for out_valid pulse
        @(posedge clk);
        @(posedge clk);
        @(posedge clk);

        // Read PE00 (pe_sel = 00)
        send_cmd(8'h80); // CMD_ACC_OPS: pe_sel = 00
        @(posedge clk);
        if ($signed(uo_out) == 8'sd72) begin
            $display("[PASS] TC2_PE00: PE00 = %d (Expected: 72)", $signed(uo_out));
        end else begin
            $display("[FAIL] TC2_PE00: PE00 = %d (Expected: 72)", $signed(uo_out));
            err_count = err_count + 1;
        end

        // Read PE01 (pe_sel = 01)
        send_cmd(8'h90); // CMD_ACC_OPS: pe_sel = 01
        @(posedge clk);
        if ($signed(uo_out) == 8'sd40) begin
            $display("[PASS] TC3_PE01: PE01 = %d (Expected: 40)", $signed(uo_out));
        end else begin
            $display("[FAIL] TC3_PE01: PE01 = %d (Expected: 40)", $signed(uo_out));
            err_count = err_count + 1;
        end

        // Read PE10 (pe_sel = 10)
        send_cmd(8'hA0); // CMD_ACC_OPS: pe_sel = 10
        @(posedge clk);
        if ($signed(uo_out) == 8'sd63) begin
            $display("[PASS] TC4_PE10: PE10 = %d (Expected: 63)", $signed(uo_out));
        end else begin
            $display("[FAIL] TC4_PE10: PE10 = %d (Expected: 63)", $signed(uo_out));
            err_count = err_count + 1;
        end

        // Read PE11 (pe_sel = 11)
        send_cmd(8'hB0); // CMD_ACC_OPS: pe_sel = 11
        @(posedge clk);
        if ($signed(uo_out) == 8'sd35) begin
            $display("[PASS] TC5_PE11: PE11 = %d (Expected: 35)", $signed(uo_out));
        end else begin
            $display("[FAIL] TC5_PE11: PE11 = %d (Expected: 35)", $signed(uo_out));
            err_count = err_count + 1;
        end

        // Test 4: Requantization Test with Shift=2 and ReLU on 2x2 grid
        // Clear Acc, shift=2, act=ReLU
        send_cmd(8'h00); // len = 1
        send_cmd(8'h52); // shift = 2, ReLU (01)
        send_cmd(8'h81); // acc_clear = 1

        // Operands: r0=-10, r1=12, c0=4, c1=6
        // PE00 = -10 * 4 = -40 -> ReLU clamp to 0
        // PE01 = -10 * 6 = -60 -> ReLU clamp to 0
        // PE10 =  12 * 4 =  48 -> (48 + 2) >> 2 = 12
        // PE11 =  12 * 6 =  72 -> (72 + 2) >> 2 = 18
        send_data_byte(-8'sd10);
        send_data_byte(8'sd12);
        send_data_byte(8'sd4);
        send_data_byte(8'sd6);

        @(posedge clk);
        @(posedge clk);
        @(posedge clk);

        send_cmd(8'h80); // pe_sel = 00
        @(posedge clk);
        if (uo_out == 8'd0) begin
            $display("[PASS] TC6_RELU_PE00: PE00 = %d (Expected: 0)", uo_out);
        end else begin
            $display("[FAIL] TC6_RELU_PE00: PE00 = %d (Expected: 0)", uo_out);
            err_count = err_count + 1;
        end

        send_cmd(8'hA0); // pe_sel = 10
        @(posedge clk);
        if (uo_out == 8'd12) begin
            $display("[PASS] TC7_REQUANT_PE10: PE10 = %d (Expected: 12)", uo_out);
        end else begin
            $display("[FAIL] TC7_REQUANT_PE10: PE10 = %d (Expected: 12)", uo_out);
            err_count = err_count + 1;
        end

        send_cmd(8'hB0); // pe_sel = 11
        @(posedge clk);
        if (uo_out == 8'd18) begin
            $display("[PASS] TC8_REQUANT_PE11: PE11 = %d (Expected: 18)", uo_out);
        end else begin
            $display("[FAIL] TC8_REQUANT_PE11: PE11 = %d (Expected: 18)", uo_out);
            err_count = err_count + 1;
        end

        $display("==================================================================");
        if (err_count == 0) begin
            $display("  ALL TT_UM_TINYML_NPU_2X2 VERIFICATION TESTS PASSED (0 ERRORS)!");
        end else begin
            $display("  VERIFICATION FAILED WITH %d ERRORS!", err_count);
        end
        $display("==================================================================");

        #100;
        $finish;
    end

endmodule

`default_nettype wire
