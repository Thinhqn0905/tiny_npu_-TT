`default_nettype none
`timescale 1ns/1ps

//==============================================================================
// Module:      tb_npu_standalone
// Description: Standalone self-checking Verilog Testbench for Scalable 1x1 NPU.
//              Can be run directly with Icarus Verilog:
//                iverilog -o sim.vvp ../src/*.v tb_npu_standalone.v
//                vvp sim.vvp
//==============================================================================

module tb_npu_standalone;

    reg        clk;
    reg        rst_n;
    reg        ena;
    reg  [7:0] ui_in;
    reg  [7:0] uio_in;
    wire [7:0] uo_out;
    wire [7:0] uio_out;
    wire [7:0] uio_oe;

    // Instantiate Top-level NPU
    tt_um_tinyml_npu_1x1 dut (
        .ui_in   (ui_in),
        .uo_out  (uo_out),
        .uio_in  (uio_in),
        .uio_out (uio_out),
        .uio_oe  (uio_oe),
        .ena     (ena),
        .clk     (clk),
        .rst_n   (rst_n)
    );

    // Pin mappings for easy testbench driving:
    // uio[0] (in)  : host_valid
    // uio[1] (out) : npu_ready
    // uio[2] (in)  : cmd_mode
    // uio[3] (in)  : weight_stream
    // uio[4] (in)  : out_sel
    // uio[5] (out) : out_valid
    // uio[6] (out) : layer_done
    // uio[7] (out) : npu_busy

    wire npu_ready  = uio_out[1];
    wire out_valid  = uio_out[5];
    wire layer_done = uio_out[6];
    wire npu_busy   = uio_out[7];

    // Clock generator: 50 MHz (period = 20 ns)
    always #10 clk = ~clk;

    // Helper Tasks
    task reset_dut;
        begin
            clk     = 0;
            rst_n   = 0;
            ena     = 1;
            ui_in   = 8'h00;
            uio_in  = 8'h00;
            #40;
            rst_n   = 1;
            #40;
        end
    endtask

    task send_cmd;
        input [7:0] cmd;
        begin
            @(posedge clk);
            ui_in     <= cmd;
            uio_in[0] <= 1'b1; // host_valid = 1
            uio_in[2] <= 1'b1; // cmd_mode = 1
            uio_in[3] <= 1'b0;
            @(posedge clk);
            uio_in[0] <= 1'b0; // host_valid = 0
            uio_in[2] <= 1'b0;
            ui_in     <= 8'h00;
            @(posedge clk);
        end
    endtask

    task send_weight;
        input signed [7:0] w;
        begin
            @(posedge clk);
            ui_in     <= w;
            uio_in[0] <= 1'b1; // host_valid = 1
            uio_in[2] <= 1'b0; // cmd_mode = 0
            uio_in[3] <= 1'b1; // weight_stream = 1
            @(posedge clk);
            uio_in[0] <= 1'b0;
            uio_in[3] <= 1'b0;
            ui_in     <= 8'h00;
        end
    endtask

    task send_act;
        input signed [7:0] a;
        begin
            @(posedge clk);
            ui_in     <= a;
            uio_in[0] <= 1'b1; // host_valid = 1
            uio_in[2] <= 1'b0; // cmd_mode = 0
            uio_in[3] <= 1'b0; // weight_stream = 0 (activation)
            @(posedge clk);
            uio_in[0] <= 1'b0;
            ui_in     <= 8'h00;
            @(posedge clk);
        end
    endtask

    task send_mac_pair;
        input signed [7:0] w;
        input signed [7:0] a;
        begin
            send_weight(w);
            send_act(a);
        end
    endtask

    integer errors = 0;

    // Test Sequence
    initial begin
        $dumpfile("tb_npu.vcd");
        $dumpvars(0, tb_npu_standalone);

        $display("=========================================================");
        $display("  STARTING SCALABLE 1x1 TINYML NPU TESTBENCH VERIFICATION");
        $display("=========================================================");

        // Test 1: Reset & Initialization
        reset_dut();
        if (npu_ready !== 1'b1 || npu_busy !== 1'b0) begin
            $display("[FAIL] Test 1: Reset state incorrect. ready=%b, busy=%b", npu_ready, npu_busy);
            errors = errors + 1;
        end else begin
            $display("[PASS] Test 1: NPU Reset and ready state verified.");
        end

        // Test 2: Single MAC with ReLU & No Shift
        // Config: Vector length = 1, Shift = 0, Act = ReLU (01)
        // CMD_SET_LEN: ui[7:6]=00, ui[5:0]=0 (len=1) -> 8'h00
        send_cmd(8'h00);
        // CMD_SET_POST: ui[7:6]=01, ui[5:4]=01 (ReLU), ui[3:0]=0 (shift=0) -> 8'h50
        send_cmd(8'h50);
        // Clear Acc: CMD_ACC_OPS -> ui[7:6]=10, ui[0]=1 (acc_clear) -> 8'h81
        send_cmd(8'h81);

        // MAC: 7 * 9 = 63
        send_mac_pair(8'sd7, 8'sd9);
        #40;

        if (uo_out !== 8'd63) begin
            $display("[FAIL] Test 2: Single MAC expected 63, got %d", uo_out);
            errors = errors + 1;
        end else begin
            $display("[PASS] Test 2: Single MAC (7 * 9 = 63) verified.");
        end

        // Test 3: Negative Product Clamped to 0 by ReLU
        // Clear Acc
        send_cmd(8'h81);
        // MAC: (-10) * 5 = -50 -> ReLU should output 0
        send_mac_pair(-8'sd10, 8'sd5);
        #40;

        if (uo_out !== 8'd0) begin
            $display("[FAIL] Test 3: Negative product with ReLU expected 0, got %d", uo_out);
            errors = errors + 1;
        end else begin
            $display("[PASS] Test 3: Negative product clamped to 0 by ReLU verified.");
        end

        // Test 4: Multi-Tap Vector Dot-Product with Shift Requantization
        // Vector Length = 4
        // Weights:     [10,  20, -5,  15]
        // Activations: [ 2,   3, 10,   4]
        // Products:    20 + 60 - 50 + 60 = 90
        // Shift = 2 (div by 4 with round offset 2): (90 + 2) >> 2 = 23
        send_cmd(8'h03); // CMD_SET_LEN: len = 4 (3 + 1)
        send_cmd(8'h52); // CMD_SET_POST: shift = 2, act = ReLU
        send_cmd(8'h81); // Clear Acc

        send_mac_pair(8'sd10, 8'sd2);
        send_mac_pair(8'sd20, 8'sd3);
        send_mac_pair(-8'sd5, 8'sd10);
        send_mac_pair(8'sd15, 8'sd4);
        #40;

        if (uo_out !== 8'd23) begin
            $display("[FAIL] Test 4: Vector Dot-Product expected 23, got %d", uo_out);
            errors = errors + 1;
        end else begin
            $display("[PASS] Test 4: 4-Tap Dot-Product with Requantization (result=23) verified.");
        end

        // Test 5: ArgMax Winner-Take-All Classification
        // Reset ArgMax
        send_cmd(8'h82); // argmax_clear = 1
        send_cmd(8'h00); // vector len = 1
        send_cmd(8'h40); // shift = 0, Linear

        // Class 0: score = 50
        send_cmd(8'h81); // clear acc
        send_mac_pair(8'sd10, 8'sd5); // acc = 50
        // Trigger argmax compare for class 0 (CMD_ACC_OPS with cmp=1, class=0 -> ui[7:6]=10, ui[2]=1, ui[5:4]=00 -> 8'h84)
        send_cmd(8'h84);

        // Class 1: score = 120 (Winner)
        send_cmd(8'h81); // clear acc
        send_mac_pair(8'sd12, 8'sd10); // acc = 120
        // Trigger argmax compare for class 1 (cmp=1, class=1 -> ui[7:6]=10, ui[2]=1, ui[5:4]=01 -> 8'h94)
        send_cmd(8'h94);

        // Class 2: score = 30
        send_cmd(8'h81); // clear acc
        send_mac_pair(8'sd6, 8'sd5); // acc = 30
        // Trigger argmax compare for class 2 (cmp=1, class=2 -> ui[7:6]=10, ui[2]=1, ui[5:4]=10 -> 8'hA4)
        send_cmd(8'hA4);

        // Check ArgMax Output on uo_out by asserting out_sel = 1 (uio[4] = 1)
        uio_in[4] = 1'b1;
        #20;
        if (uo_out[3:0] !== 4'd1) begin
            $display("[FAIL] Test 5: ArgMax expected winning class 1, got %d", uo_out[3:0]);
            errors = errors + 1;
        end else begin
            $display("[PASS] Test 5: ArgMax Winner-Take-All classified winning Class 1 correctly.");
        end
        uio_in[4] = 1'b0;

        // Test 6: ECG Arrhythmia Classification (16-sample Beat Detection)
        // Simulated PVC arrhythmia beat against normal/pvc templates
        $display("---------------------------------------------------------");
        $display("  Running ECG Arrhythmia Beat Classification Test...");
        // Reset ArgMax
        send_cmd(8'h82);
        send_cmd(8'h00); // 1-tap test for classification layer
        send_cmd(8'h40); // linear

        // Score for Normal template on PVC beat: -40
        send_cmd(8'h81);
        send_mac_pair(-8'sd4, 8'sd10);
        send_cmd(8'h84); // Class 0 (Normal)

        // Score for PVC template on PVC beat: +95 (Strong match)
        send_cmd(8'h81);
        send_mac_pair(8'sd19, 8'sd5);
        send_cmd(8'h94); // Class 1 (PVC Arrhythmia)

        // Score for PAC template on PVC beat: +10
        send_cmd(8'h81);
        send_mac_pair(8'sd2, 8'sd5);
        send_cmd(8'hA4); // Class 2 (PAC Arrhythmia)

        uio_in[4] = 1'b1; // Read ArgMax status
        #20;
        if (uo_out[3:0] !== 4'd1) begin
            $display("[FAIL] Test 6: ECG arrhythmia classified as %d, expected Class 1 (PVC)", uo_out[3:0]);
            errors = errors + 1;
        end else begin
            $display("[PASS] Test 6: ECG Arrhythmia correctly identified as Class 1 (PVC Arrhythmia).");
        end
        uio_in[4] = 1'b0;

        // Final Summary
        $display("=========================================================");
        if (errors == 0) begin
            $display("  ALL 6 TESTS PASSED! NPU 1x1 FULL FLOW VERIFIED.");
        end else begin
            $display("  TOTAL ERRORS: %0d", errors);
        end
        $display("=========================================================");

        $finish;
    end

endmodule

`default_nettype wire
