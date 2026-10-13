"""Production wrapper tests. Host drives before edges and obeys ready/valid."""
import random
import json
import os
from pathlib import Path
import cocotb
from cocotb.triggers import Timer
from oracle import requant

SEED=0x2EC62026

class Host:
    def __init__(self,d):
        self.d=d
        self.cycles=0
        self.done=0
    async def tick(self):
        self.d.clk.value=0
        await Timer(10,unit="ns")
        self.d.clk.value=1
        await Timer(10,unit="ns")
        self.d.clk.value=0
        self.cycles+=1
        out=int(self.d.uio_out.value)
        assert ((out>>5)&1)==((out>>6)&1)
        self.done+=(out>>6)&1
        assert int(self.d.uio_oe.value)==0xe2
    async def reset(self):
        # Keep asynchronous-reset transitions away from monitor clock edges.
        self.d.clk.value=0
        await Timer(1,unit="ns")
        self.d.ena.value=1
        self.d.rst_n.value=0
        self.d.ui_in.value=self.d.uio_in.value=0
        await Timer(1,unit="ns")
        await self.tick()
        self.d.rst_n.value=1
        await self.tick()
        assert int(self.d.uio_out.value)==2
    async def send(self,value,cmd=False,stall=0):
        self.d.uio_in.value=0
        for _ in range(stall): await self.tick()
        for _ in range(20):
            await Timer(1,unit="ns")
            if int(self.d.uio_out.value)&2: break
            await self.tick()
        else: raise AssertionError("ready timeout")
        self.d.ui_in.value=value & 255
        self.d.uio_in.value=5 if cmd else 1
        await self.tick()
        self.d.uio_in.value=0
    async def finish(self):
        # Every tuple spends one POST_MAC edge; final tuple also FINISH edge.
        for _ in range(20):
            await Timer(1,unit="ns")
            if int(self.d.uio_out.value)&2: return
            await self.tick()
        raise AssertionError("finish timeout")
    async def outputs(self,expected):
        for pe,value in enumerate(expected):
            await self.send(0x80 | (pe<<4),True)
            assert int(self.d.uo_out.value)==(value & 255),(pe,value,int(self.d.uo_out.value))

@cocotb.test()
async def ready_back_to_back(d):
    h=Host(d); await h.reset()
    await h.send(1,True) # K=2
    await h.send(0x81,True)
    for value in [2,4,6,7]: await h.send(value)
    # A MAC is pending; advertising ready here loses the next tuple's first byte.
    await Timer(1,unit="ns")
    assert not (int(d.uio_out.value)&2), "ready asserted while POST_MAC ignores input"
    for value in [3,5,8,9]: await h.send(value)
    await h.finish()
    assert h.done==1
    await h.outputs([36,41,64,73])
    # Immediately start another transaction without reset.
    await h.send(0,True); await h.send(0x81,True)
    for value in [-128,127,-128,127]: await h.send(value)
    await h.finish()
    await h.outputs([127,-128,-128,127])
    assert h.done==2

@cocotb.test()
async def randomized_signed_transactions(d):
    h=Host(d); await h.reset(); rng=random.Random(SEED)
    count=0
    for iteration in range(128):
        k=[1,2,3,45,63,64][iteration%6]
        shift=iteration%16; mode=(iteration//16)%4
        await h.send(k-1,True)
        await h.send(0x40|(mode<<4)|shift,True)
        await h.send(0x81,True)
        sums=[0]*4
        for t in range(k):
            a0,a1,b0,b1=[rng.randint(-128,127) for _ in range(4)]
            for value in [a0,a1,b0,b1]: await h.send(value,stall=rng.randrange(3))
            for pe,p in enumerate([a0*b0,a0*b1,a1*b0,a1*b1]): sums[pe]+=p
        await h.finish()
        await h.outputs([requant(s,shift,mode) for s in sums])
        # Full accumulators additionally checked in RTL simulation.
        for pe,s in zip(["pe00_acc","pe01_acc","pe10_acc","pe11_acc"],sums):
            raw=int(getattr(d.dut.u_core_2x2,pe).value)
            assert raw == (s & 0xffffff)
        count+=4
    assert h.done==128
    d._log.info("ORACLE_CASES wrapper=%d transactions=128 seed=%d",count,SEED)

@cocotb.test()
async def reset_and_enable_recovery(d):
    h=Host(d); await h.reset()
    for prefix in [0,1,2,3,4]:
        await h.send(0,True)
        for value in [12,13,14,15][:prefix]: await h.send(value)
        # Assert reset in idle/partial tuple/POST_MAC and recover.
        await h.reset()
        await h.send(0,True)
        for value in [1,2,3,4]: await h.send(value)
        await h.finish(); await h.outputs([3,4,6,8])
    # Freeze a pending MAC, then resume: it must execute exactly once.
    await h.send(0x81,True)
    for value in [2,3,4,5]: await h.send(value)
    d.ena.value=0
    await Timer(1,unit="ns")
    assert not (int(d.uio_out.value)&2)
    for _ in range(4): await h.tick()
    d.ena.value=1
    await h.finish(); await h.outputs([8,10,12,15])

@cocotb.test()
async def bias_snapshot_contract(d):
    h=Host(d); await h.reset()
    for value in [2,3,4,5]: await h.send(value)
    await h.finish()
    await h.send(0xc0,True) # signed full opcode -64, top row only; bottom gets old top.
    await h.tick()
    await h.outputs([-64,-64,8,10])
    await h.send(0xff,True)
    await h.tick()
    await h.outputs([-1,-1,-64,-64])
    # Clear has priority if clear/load are simultaneously requested.
    await h.send(0x83,True); await h.tick()
    await h.outputs([0]*4)

@cocotb.test()
async def synthetic_dual_dot_product(d):
    h=Host(d); await h.reset()
    rng=random.Random(SEED)
    samples=[rng.randint(-20,20) for _ in range(45)]
    normal=[rng.randint(-8,8) for _ in range(45)]
    pvc=[rng.randint(-8,8) for _ in range(45)]
    await h.send(44,True); await h.send(0x47,True); await h.send(0x81,True)
    start=h.cycles
    for x,w0,w1 in zip(samples,normal,pvc):
        for value in [x,0,w0,w1]: await h.send(value)
    await h.finish()
    elapsed=h.cycles-start
    expected=[requant(sum(x*w for x,w in zip(samples,normal)),7,0),
              requant(sum(x*w for x,w in zip(samples,pvc)),7,0),0,0]
    assert elapsed==226,elapsed
    await h.outputs(expected)
    result=dict(seed=SEED,input_samples=samples,weights=[normal,pvc],outputs=expected,
                logical_macs=90,physical_macs=4,stream_completion_cycles=elapsed,
                setup_cycles=3,readout_cycles=4,total_cycles=elapsed+7,
                source="deterministic synthetic integers; no clinical dataset; no training",
                host_operations="operand scheduling, zero row padding, external class comparison")
    if os.environ.get("REVIEW_OUT"):
        Path(os.environ["REVIEW_OUT"],"workload.json").write_text(json.dumps(result,indent=2)+"\n")
    d._log.info("WORKLOAD 90 useful MACs / 226 cycles = %.6f MMAC/s at 50MHz",90*50/226)
