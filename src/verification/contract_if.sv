// Abstract contract shell for syntax/elaboration only. Never used as a DUT oracle.
module tt_um_tinyml_npu_2x2 (
    input wire [7:0] ui_in, output wire [7:0] uo_out,
    input wire [7:0] uio_in, output wire [7:0] uio_out,uio_oe,
    input wire ena,clk,rst_n
);
    assign uo_out=8'h00;
    assign uio_out={6'b0,(ena && rst_n),1'b0};
    assign uio_oe=8'he2;
endmodule
