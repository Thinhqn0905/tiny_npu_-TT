"""Generate saved SV tests solely from approved contract and frozen trained model.

This generator never opens RTL. Expected values are independently recomputed
with Python integer arithmetic and checked against the saved training artifact.
"""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
model_path=ROOT/'models/tiny_ecg_qat/network.json'
model=json.loads(model_path.read_text())
approval=json.loads((ROOT/'schemas/review_approvals.json').read_text(encoding='utf-8-sig'))
assert approval['gate_1']['approved'] and approval['gate_3a']['approved']
assert model['architecture']==[20,8,3] and model['bias'] is False
assert model['shift']==[6,6] and model['activation']==[1,0]
def quant(a,mode): return max(0 if mode==1 else -128,min(127,(a+32)//64))
def reference(x):
    stages=[]
    for weights,mode in zip(model['weights'],model['activation']):
        acc=[sum(int(a)*int(w) for a,w in zip(x,row)) for row in weights]
        assert all(-(2**23)<=a<2**23 for a in acc)
        x=[quant(a,mode) for a in acc]; stages.append(x)
    return stages
for s in model['samples']:
    assert reference(s['input'])==[s['hidden'],s['output']],s
samples=[model['samples'][i] for i in [0,2,4,1,3,5]]
lines=['''`timescale 1ns/1ps
// TC-TRAINED-E2E / REQ-NPU-001/003/004/005/006.
// Source: FE-REVIEW-20261013 contract and locally trained QAT artifact.
// All dense/requant/ReLU stages execute through public TinyTapeout pins.
// Inputs are offline mapped feature tensors, not raw streaming ECG.
module tb_trained_network;
    reg clk=0,rst_n=0,ena=1;
    reg [7:0] ui_in=0,uio_in=0;
    wire [7:0] uo_out,uio_out,uio_oe;
    reg signed [7:0] inputs [0:1][0:19];
    reg signed [7:0] hidden_hw [0:1][0:7];
    reg signed [7:0] output_hw [0:1][0:2];
    integer cycles=0,start_cycle,batch_cycles,total_cycles=0;
    tt_um_tinyml_npu_2x2 dut(ui_in,uo_out,uio_in,uio_out,uio_oe,ena,clk,rst_n);
    npu_protocol_properties u_properties(clk,rst_n,ena,uo_out,uio_out,uio_oe);
    always #10 clk=~clk;
    always @(posedge clk) cycles=cycles+1;
    task send(input signed [7:0] value,input is_command);
        begin
            @(negedge clk);
            uio_in=0;
            while(!uio_out[1]) @(negedge clk);
            ui_in=value; uio_in=is_command ? 8'h05 : 8'h01;
            @(posedge clk); #1; uio_in=0;
        end
    endtask
    task read_pe(input [1:0] index,output signed [7:0] value);
        begin
            send(8'h80 | {2'b00,index,4'b0000},1'b1);
            value=$signed(uo_out);
        end
    endtask
    reg signed [7:0] r00,r01,r10,r11;
    initial begin
        #1; rst_n=0;
        repeat(3) @(negedge clk);
        rst_n=1;
        @(negedge clk);
''']
observations=[]
for batch in range(3):
    pair=samples[2*batch:2*batch+2]
    lines.append(f'        // Batch{batch}: '+', '.join(f"{s['record']}:{s['r_sample']} label{s['label']}" for s in pair))
    for r,s in enumerate(pair):
        for i,x in enumerate(s['input']): lines.append(f"        inputs[{r}][{i}]=8'sd{abs(x)}".replace("=8'sd", "=-8'sd" if x<0 else "=8'sd")+';')
    lines.append('        start_cycle=cycles;')
    for layer,(weights,mode) in enumerate(zip(model['weights'],model['activation'])):
        k=len(weights[0]); count=len(weights)
        for first in range(0,count,2):
            lines.extend([f"        send(8'd{k-1},1'b1);",f"        send(8'h{0x40+(mode<<4)+6:02x},1'b1);","        send(8'h81,1'b1);"])
            for i in range(k):
                for r in range(2): lines.append(f"        send({'inputs' if layer==0 else 'hidden_hw'}[{r}][{i}],1'b0);")
                for c in range(2):
                    w=weights[first+c][i] if first+c<count else 0
                    lines.append(f"        send({'-' if w<0 else ''}8'sd{abs(w)},1'b0);")
            lines.extend(["        read_pe(2'd0,r00);","        read_pe(2'd1,r01);","        read_pe(2'd2,r10);","        read_pe(2'd3,r11);"])
            for r in range(2):
                for c in range(2):
                    if first+c>=count: continue
                    var=f'r{r}{c}'; expected=pair[r]['hidden' if layer==0 else 'output'][first+c]
                    dest='hidden_hw' if layer==0 else 'output_hw'
                    lines.append(f'        {dest}[{r}][{first+c}]={var};')
                    lines.append(f"        if ({var} !== {'-' if expected<0 else ''}8'sd{abs(expected)}) $fatal(1,\"TC-TRAINED-E2E batch{batch} layer{layer} row{r} neuron{first+c}: got %0d\",{var});")
            # All next-layer inputs above refer to captured hardware values.
    lines.extend(['        batch_cycles=cycles-start_cycle; total_cycles=total_cycles+batch_cycles;',
                  f'        $display("[PASS] TC-TRAINED-E2E batch{batch}: all hidden and output values match; cycles=%0d",batch_cycles);'])
    observations.extend(pair)
lines.extend(['        $display("NETWORK_RESULT samples=6 batches=3 logical_macs=1104 total_cycles=%0d",total_cycles);',
              '        $finish;','    end','    initial begin #1000000; $fatal(1,"TC-TRAINED-E2E timeout"); end','endmodule'])
target=ROOT/'src/tb/tests/tc_trained_network.sv'; target.parent.mkdir(parents=True,exist_ok=True)
target.write_text('\n'.join(lines)+'\n')
(ROOT/'src/tb/filelist_tb.f').write_text('src/sva/npu_protocol_properties.sv\nsrc/tb/tests/tc_trained_network.sv\nsrc/tb/tests/tc_coverage_baseline.sv\n')
(ROOT/'evidence/review/final/network_fixture.json').write_text(json.dumps(dict(
    test='TC-TRAINED-E2E',model_sha256=hashlib.sha256(model_path.read_bytes()).hexdigest(),
    model_source='models/tiny_ecg_qat/network.json',samples=observations,
    expected_source='independent integer reference; saved training outputs cross-checked',
    hardware_execution='public wrapper only; second layer inputs captured from DUT outputs'),indent=2)+'\n')
print('Saved',target,'six held-out real-data samples; independent oracle agrees with frozen fixture')
