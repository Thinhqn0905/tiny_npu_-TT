import random
import cocotb
from cocotb.triggers import Timer
from oracle import signed, mac, requant

SEED = 0x2EC62026

async def tick(d):
    d.clk.value = 0
    await Timer(5, unit="ns")
    d.clk.value = 1
    await Timer(5, unit="ns")
    d.clk.value = 0

async def reset(d):
    d.ena.value = 1
    d.mac_en.value = d.acc_clear.value = d.load_bias.value = 0
    d.a.value = d.b.value = d.av.value = d.bv.value = 0
    d.rst_n.value = 0
    await tick(d)
    d.rst_n.value = 1
    await tick(d)

def grid(handle):
    v = int(handle.value)
    return [signed(v >> (i * 24)) for i in range(4)]

def pack(a, b):
    return (a & 255) | ((b & 255) << 8)

@cocotb.test()
async def rounding_boundaries(d):
    await reset(d)
    rng = random.Random(SEED)
    count = 0
    for shift in range(16):
        offset = 2 ** (shift - 1) if shift else 0
        values = {-(2**23), 2**23-1, 2**23-1-offset, 2**23-offset,
                  -129, -128, -127, -1, 0, 1, 126, 127, 128, 254, 255, 256}
        for threshold in [-129, -128, -1, 0, 1, 127, 128, 255, 256]:
            values.update(threshold * 2**shift - offset + delta for delta in [-1,0,1])
        values.update(rng.randint(-(2**23), 2**23-1) for _ in range(256))
        for value in sorted(v for v in values if -(2**23) <= v < 2**23):
            for mode in range(4):
                d.qacc.value, d.shift.value, d.mode.value = value, shift, mode
                await Timer(1, unit="ns")
                assert signed(int(d.q.value),8) == requant(value,shift,mode), (value,shift,mode)
                assert int(d.uq.value) == requant(value,shift,mode,True), (value,shift,mode,"unsigned")
                count += 1
    d._log.info("ORACLE_CASES requant=%d seed=%d",count,SEED)

@cocotb.test()
async def exhaustive_products_and_overflow(d):
    await reset(d)
    count = 0
    for a in range(-128,128):
        for b in range(-128,128):
            d.load_bias.value, d.mac_en.value = 1, 0
            d.bias.value = 0
            await tick(d)
            d.load_bias.value, d.mac_en.value = 0, 1
            d.a.value, d.b.value = a,b
            await tick(d)
            assert signed(int(d.acc.value)) == a*b, (a,b)
            assert int(d.overflow.value) == 0
            assert signed(int(d.af.value),8) == a and signed(int(d.bf.value),8) == b
            count += 1
    rng = random.Random(SEED)
    acc = signed(int(d.acc.value))
    for i in range(4096):
        if i % 16 == 0:
            acc = rng.choice([-(2**23),2**23-1,rng.randrange(-(2**23),2**23)])
            d.bias.value = acc
            d.mac_en.value, d.load_bias.value = 0,1
            await tick(d)
        a,b = rng.randint(-128,127),rng.randint(-128,127)
        d.a.value,d.b.value = a,b
        d.mac_en.value,d.load_bias.value = 1,0
        acc,ov = mac(acc,a,b)
        await tick(d)
        assert signed(int(d.acc.value)) == acc
        assert int(d.overflow.value) == ov
        count += 1
    # Exact positive/negative accumulation limits and first overflowing cycle.
    for a,b,n in [(-128,-128,512),(-128,127,517),(127,127,521)]:
        d.mac_en.value,d.acc_clear.value = 0,1
        await tick(d)
        d.mac_en.value,d.acc_clear.value = 1,0
        acc=0
        for _ in range(n):
            d.a.value,d.b.value = a,b
            acc,ov=mac(acc,a,b)
            await tick(d)
            assert signed(int(d.acc.value)) == acc and int(d.overflow.value)==ov
            count+=1
    d._log.info("ORACLE_CASES mac=%d seed=%d",count,SEED)

@cocotb.test()
async def systolic_and_broadcast(d):
    await reset(d)
    rng=random.Random(SEED)
    count=0
    # Host explicitly skews row 1 and column 1; K+R+C-2 MAC edges.
    for k in [1,2,3,16,64]*8:
        aa=[[rng.randint(-128,127) for _ in range(k)] for _ in range(2)]
        bb=[[rng.randint(-128,127) for _ in range(2)] for _ in range(k)]
        d.mac_en.value,d.acc_clear.value=0,1
        d.av.value=d.bv.value=0
        await tick(d)
        d.acc_clear.value,d.mac_en.value=0,1
        for t in range(k+2):
            a0=aa[0][t] if t<k else 0
            a1=aa[1][t-1] if 0<=t-1<k else 0
            b0=bb[t][0] if t<k else 0
            b1=bb[t-1][1] if 0<=t-1<k else 0
            d.av.value,d.bv.value=pack(a0,a1),pack(b0,b1)
            await tick(d)
            # Cycle-by-cycle expected partial sums at each PE, including fill/drain.
            exp=[]
            for r in range(2):
                for c in range(2):
                    exp.append(sum(aa[r][i]*bb[i][c] for i in range(k) if i+r+c<=t))
            assert grid(d.grid1)==exp,(k,t,grid(d.grid1),exp)
            count+=4
        # Drain boundary registers with zeros before next operation.
        d.av.value=d.bv.value=0
        d.mac_en.value=0
        await tick(d)
        d.acc_clear.value=1
        await tick(d)
        d.acc_clear.value,d.mac_en.value=0,1
        for t in range(k):
            d.av.value,d.bv.value=pack(aa[0][t],aa[1][t]),pack(bb[t][0],bb[t][1])
            await tick(d)
            exp=[sum(aa[r][i]*bb[i][c] for i in range(t+1)) for r in range(2) for c in range(2)]
            assert grid(d.grid0)==exp
            count+=4
    # Cascading bias is a simultaneous snapshot, not broadcast to all rows.
    d.mac_en.value,d.load_bias.value=0,1
    prior=grid(d.grid0)
    d.biases.value=(123 & 0xffffff)|((-456 & 0xffffff)<<24)
    await tick(d)
    assert grid(d.grid0)==[123,-456,prior[0],prior[1]]
    # Enable stalls freeze accumulators AND forwarding registers.
    snapshot=(int(d.grid0.value),int(d.grid1.value),int(d.af1.value),int(d.bf1.value))
    d.ena.value=0
    d.av.value=d.bv.value=0xffff
    await tick(d)
    assert snapshot==(int(d.grid0.value),int(d.grid1.value),int(d.af1.value),int(d.bf1.value))
    await reset(d)
    assert grid(d.grid0)==grid(d.grid1)==[0]*4
    d._log.info("ORACLE_CASES array=%d seed=%d",count,SEED)
