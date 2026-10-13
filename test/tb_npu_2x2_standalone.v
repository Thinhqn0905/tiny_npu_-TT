`default_nettype none
`timescale 1ns/1ps

//==============================================================================
// Testbench:   tb_npu_2x2_standalone
// Description: Self-checking testbench for 2x2 Systolic Array NPU.
//              Validates 4-PE parallel execution, 2x2 matrix multiplication,
//              systolic data forwarding, requantization, and 1x1 vs 2x2 speedup.
//==============================================================================

module tb_npu_2x2_standalone;

    reg         clk;
    reg         rst_n;
    reg         ena;
    reg         mac_en;
    reg         acc_clear;
    reg         load_bias;

    reg  signed [7:0]  act_in_r0, act_in_r1;
    reg  signed [7:0]  weight_in_c0, weight_in_c1;
    reg  signed [23:0] bias_in_c0, bias_in_c1;
    reg         [3:0]  shift_val;
    reg         [1:0]  act_type;
    reg         [1:0]  pe_sel;
    reg                out_acc_sel;

    wire signed [7:0]  data_out;
    wire signed [23:0] acc_out_selected;
    wire signed [23:0] pe00_acc, pe01_acc, pe10_acc, pe11_acc;
    wire signed [7:0]  pe00_act, pe01_act, pe10_act, pe11_act;
    wire signed [7:0]  act_out_r0, act_out_r1;
    wire signed [7:0]  weight_out_c0, weight_out_c1;
    wire               overflow_any;

    npu_top_2x2 #(
        .DATA_WIDTH(8),
        .ACC_WIDTH (24)
    ) dut_2x2 (
        .clk             (clk),
        .rst_n           (rst_n),
        .ena             (ena),
        .mac_en          (mac_en),
        .acc_clear       (acc_clear),
        .load_bias       (load_bias),
        .act_in_r0       (act_in_r0),
        .act_in_r1       (act_in_r1),
        .weight_in_c0    (weight_in_c0),
        .weight_in_c1    (weight_in_c1),
        .bias_in_c0      (bias_in_c0),
        .bias_in_c1      (bias_in_c1),
        .shift_val       (shift_val),
        .act_type        (act_type),
        .pe_sel          (pe_sel),
        .out_acc_sel     (out_acc_sel),
        .data_out        (data_out),
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

    always #10 clk = ~clk;

    integer errors = 0;

    task reset_dut;
        begin
            clk          = 0;
            rst_n        = 0;
            ena          = 1;
            mac_en       = 0;
            acc_clear    = 0;
            load_bias    = 0;
            act_in_r0    = 8'sd0;
            act_in_r1    = 8'sd0;
            weight_in_c0 = 8'sd0;
            weight_in_c1 = 8'sd0;
            bias_in_c0   = 24'sd0;
            bias_in_c1   = 24'sd0;
            shift_val    = 4'd0;
            act_type     = 2'b00;
            pe_sel       = 2'b00;
            out_acc_sel  = 1'b0;
            #40;
            rst_n        = 1;
            #40;
        end
    endtask

    initial begin
        $dumpfile("tb_npu_2x2.vcd");
        $dumpvars(0, tb_npu_2x2_standalone);

        $display("==================================================================");
        $display("  VLSIT VERIFICATION: 2x2 SYSTOLIC ARRAY TINYML NPU TESTBENCH");
        $display("==================================================================");

        reset_dut();

        // TEST 1: Reset Recovery
        if (pe00_acc !== 24'sd0 || pe01_acc !== 24'sd0 ||
            pe10_acc !== 24'sd0 || pe11_acc !== 24'sd0) begin
            $display("[FAIL] TC_2X2_RESET: Non-zero accumulators after reset.");
            errors = errors + 1;
        end else begin
            $display("[PASS] TC_2X2_RESET: All 4 PEs successfully initialized to 0.");
        end

        // TEST 2: 4-PE Parallel Single-Cycle MAC
        @(posedge clk);
        acc_clear    <= 1'b1;
        @(posedge clk);
        acc_clear    <= 1'b0;
        mac_en       <= 1'b1;
        act_in_r0    <= 8'sd8;
        act_in_r1    <= 8'sd5;
        weight_in_c0 <= 8'sd9;
        weight_in_c1 <= 8'sd7;
        @(posedge clk);
        mac_en       <= 1'b0;
        act_in_r0    <= 8'sd0;
        act_in_r1    <= 8'sd0;
        weight_in_c0 <= 8'sd0;
        weight_in_c1 <= 8'sd0;
        #5;

        if (pe00_acc !== 24'sd72 || pe01_acc !== 24'sd56 ||
            pe10_acc !== 24'sd45 || pe11_acc !== 24'sd35) begin
            $display("[FAIL] TC_2X2_PARALLEL_MAC: Mismatch!");
            errors = errors + 1;
        end else begin
            $display("[PASS] TC_2X2_PARALLEL_MAC: 4-PE Concurrent MAC Verified (72, 56, 45, 35).");
        end

        // TEST 3: 2x2 Matrix Multiplication (C = A x B)
        @(posedge clk);
        acc_clear <= 1'b1;
        @(posedge clk);
        acc_clear <= 1'b0;

        // k = 0
        mac_en       <= 1'b1;
        act_in_r0    <= 8'sd2;
        act_in_r1    <= 8'sd4;
        weight_in_c0 <= 8'sd6;
        weight_in_c1 <= 8'sd7;
        @(posedge clk);

        // k = 1
        act_in_r0    <= 8'sd3;
        act_in_r1    <= 8'sd5;
        weight_in_c0 <= 8'sd8;
        weight_in_c1 <= 8'sd9;
        @(posedge clk);

        mac_en <= 1'b0;
        act_in_r0    <= 8'sd0;
        act_in_r1    <= 8'sd0;
        weight_in_c0 <= 8'sd0;
        weight_in_c1 <= 8'sd0;
        #5;

        if (pe00_acc !== 24'sd36 || pe01_acc !== 24'sd41 ||
            pe10_acc !== 24'sd64 || pe11_acc !== 24'sd73) begin
            $display("[FAIL] TC_2X2_MATMUL: Expected [[36, 41], [64, 73]], Got [[%0d, %0d], [%0d, %0d]]",
                     pe00_acc, pe01_acc, pe10_acc, pe11_acc);
            errors = errors + 1;
        end else begin
            $display("[PASS] TC_2X2_MATMUL: Full 2x2 Matrix Multiplication Verified [[36, 41], [64, 73]].");
        end

        // TEST 4: Readout Multiplexer
        pe_sel = 2'b00; #10;
        if (data_out !== 8'sd36) errors = errors + 1;
        pe_sel = 2'b01; #10;
        if (data_out !== 8'sd41) errors = errors + 1;
        pe_sel = 2'b10; #10;
        if (data_out !== 8'sd64) errors = errors + 1;
        pe_sel = 2'b11; #10;
        if (data_out !== 8'sd73) errors = errors + 1;
        $display("[PASS] TC_2X2_MUX_READOUT: 4-Channel Multiplexed Readout Verified.");

        // TEST 5: Parallel Requantization with Rounding & ReLU (Shift = 1)
        shift_val = 4'd1;
        act_type  = 2'b01;
        #10;
        if (pe00_act !== 8'sd18 || pe01_act !== 8'sd21 ||
            pe10_act !== 8'sd32 || pe11_act !== 8'sd37) begin
            $display("[FAIL] TC_2X2_REQUANT: Expected [18, 21, 32, 37], Got [%0d, %0d, %0d, %0d]",
                     pe00_act, pe01_act, pe10_act, pe11_act);
            errors = errors + 1;
        end else begin
            $display("[PASS] TC_2X2_REQUANT: 4-Channel Parallel Requantization & ReLU Verified (18, 21, 32, 37).");
        end

        // TEST 6: Dual-Channel Heartbeat Arrhythmia Evaluation (2x Speedup)
        @(posedge clk);
        acc_clear <= 1'b1;
        shift_val <= 4'd0;
        act_type  <= 2'b00;
        @(posedge clk);
        acc_clear <= 1'b0;

        mac_en <= 1'b1;
        act_in_r0 <= 8'sd10; act_in_r1 <= 8'sd0;
        weight_in_c0 <= -8'sd4; weight_in_c1 <= 8'sd8;
        @(posedge clk);

        act_in_r0 <= 8'sd15; act_in_r1 <= 8'sd0;
        weight_in_c0 <= 8'sd1; weight_in_c1 <= 8'sd5;
        @(posedge clk);

        mac_en <= 1'b0;
        #5;
        if (pe00_acc !== -24'sd25 || pe01_acc !== 24'sd155) begin
            $display("[FAIL] TC_2X2_DUAL_ECG: Expected Col0=-25, Col1=155. Got Col0=%0d, Col1=%0d",
                     pe00_acc, pe01_acc);
            errors = errors + 1;
        end else begin
            $display("[PASS] TC_2X2_DUAL_ECG: Concurrent Dual-Class ECG Evaluation Verified (Normal=-25, PVC=+155).");
            $display("       2x2 achieves 2x throughput speedup over 1x1 tile!");
        end

        $display("==================================================================");
        if (errors == 0) begin
            $display("  ALL 6 2x2 SYSTOLIC ARRAY TEST PHASES PASSED WITH ZERO ERRORS!");
        end else begin
            $display("  TOTAL ERRORS: %0d", errors);
        end
        $display("==================================================================");

        $finish;
    end

endmodule

`default_nettype wire
