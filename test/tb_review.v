`timescale 1ns/1ps
module tb_review;
    reg clk = 0, rst_n = 0, ena = 1;
    reg mac_en = 0, acc_clear = 0, load_bias = 0;
    reg signed [7:0] a = 0, b = 0;
    reg signed [23:0] bias = 0, qacc = 0;
    reg [3:0] shift = 0;
    reg [1:0] mode = 0;
    wire signed [23:0] acc;
    wire signed [7:0] af, bf, q;
    wire [7:0] uq;
    wire overflow;
    npu_pe pe(clk,rst_n,ena,mac_en,acc_clear,load_bias,a,b,bias,af,bf,acc,overflow);
    npu_activation activation(qacc,shift,mode,q,uq);
    reg [15:0] av = 0, bv = 0;
    reg [47:0] biases = 0;
    wire [95:0] grid0, grid1;
    wire [15:0] af0, bf0, af1, bf1;
    wire ov0, ov1;
    npu_array #(.ROWS(2),.COLS(2),.SYSTOLIC_MODE(0)) broadcast_array
        (clk,rst_n,ena,mac_en,acc_clear,load_bias,av,bv,biases,af0,bf0,grid0,ov0);
    npu_array #(.ROWS(2),.COLS(2),.SYSTOLIC_MODE(1)) systolic_array
        (clk,rst_n,ena,mac_en,acc_clear,load_bias,av,bv,biases,af1,bf1,grid1,ov1);
endmodule
