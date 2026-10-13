"""
test.py - Cocotb Testbench for Scalable 1x1 TinyML NPU (tt_um_tinyml_npu_1x1)
Compatible with RTL simulation, gate-level simulation, and GitHub Actions CI.
"""

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, RisingEdge
import os

GL_TEST = os.environ.get("GATES", "no") == "yes"
TIMING_MULT = 3 if GL_TEST else 1
CLK_PERIOD_NS = 20  # 50 MHz

# Pin definitions for uio:
# uio[0] (in)  : host_valid
# uio[1] (out) : npu_ready
# uio[2] (in)  : cmd_mode
# uio[3] (in)  : weight_stream
# uio[4] (in)  : out_sel
# uio[5] (out) : out_valid
# uio[6] (out) : layer_done
# uio[7] (out) : npu_busy


class NPUDriver:

    def __init__(self, dut):
        self.dut = dut

    def _make_uio(self, valid=0, cmd=0, weight=0, out_sel=0):
        val = (
            (1 if valid else 0)
            | ((1 if cmd else 0) << 2)
            | ((1 if weight else 0) << 3)
            | ((1 if out_sel else 0) << 4)
        )
        return val

    async def reset(self):
        self.dut.ena.value = 1
        self.dut.ui_in.value = 0
        self.dut.uio_in.value = 0
        self.dut.rst_n.value = 0
        await ClockCycles(self.dut.clk, 5 * TIMING_MULT)
        self.dut.rst_n.value = 1
        await ClockCycles(self.dut.clk, 5 * TIMING_MULT)

    async def send_cmd(self, cmd_byte):
        await RisingEdge(self.dut.clk)
        self.dut.ui_in.value = cmd_byte & 0xFF
        self.dut.uio_in.value = self._make_uio(valid=1, cmd=1)
        await RisingEdge(self.dut.clk)
        self.dut.uio_in.value = 0
        self.dut.ui_in.value = 0
        await ClockCycles(self.dut.clk, 1)

    async def send_weight(self, weight):
        await RisingEdge(self.dut.clk)
        self.dut.ui_in.value = weight & 0xFF
        self.dut.uio_in.value = self._make_uio(valid=1, cmd=0, weight=1)
        await RisingEdge(self.dut.clk)
        self.dut.uio_in.value = 0
        self.dut.ui_in.value = 0

    async def send_act(self, act):
        await RisingEdge(self.dut.clk)
        self.dut.ui_in.value = act & 0xFF
        self.dut.uio_in.value = self._make_uio(valid=1, cmd=0, weight=0)
        await RisingEdge(self.dut.clk)
        self.dut.uio_in.value = 0
        self.dut.ui_in.value = 0
        await ClockCycles(self.dut.clk, 1)

    async def send_pair(self, weight, act):
        await self.send_weight(weight)
        await self.send_act(act)

    async def read_data(self):
        self.dut.uio_in.value = self._make_uio(out_sel=0)
        await ClockCycles(self.dut.clk, 1)
        return int(self.dut.uo_out.value)

    async def read_status(self):
        self.dut.uio_in.value = self._make_uio(out_sel=1)
        await ClockCycles(self.dut.clk, 1)
        return int(self.dut.uo_out.value)


@cocotb.test()
async def test_reset(dut):
    """Test 1: Verify Reset and Initial Ready State"""
    clock = Clock(dut.clk, CLK_PERIOD_NS, unit="ns")
    cocotb.start_soon(clock.start())
    drv = NPUDriver(dut)
    await drv.reset()

    uio_out = int(dut.uio_out.value)
    ready = (uio_out >> 1) & 1
    busy = (uio_out >> 7) & 1

    assert ready == 1, f"Expected npu_ready=1, got {ready}"
    assert busy == 0, f"Expected npu_busy=0, got {busy}"
    dut._log.info("PASS: test_reset")


@cocotb.test()
async def test_mac_simple(dut):
    """Test 2: Single MAC Computation (8 * 9 = 72) with ReLU"""
    clock = Clock(dut.clk, CLK_PERIOD_NS, unit="ns")
    cocotb.start_soon(clock.start())
    drv = NPUDriver(dut)
    await drv.reset()

    # CMD_SET_LEN: len = 1 (ui[7:6]=00, ui[5:0]=0 -> 0x00)
    await drv.send_cmd(0x00)
    # CMD_SET_POST: shift = 0, act = ReLU (01) (ui[7:6]=01, ui[5:4]=01, ui[3:0]=00 -> 0x50)
    await drv.send_cmd(0x50)
    # Clear Acc: CMD_ACC_OPS with acc_clear=1 -> 0x81
    await drv.send_cmd(0x81)

    await drv.send_pair(8, 9)
    await ClockCycles(dut.clk, 2)

    res = await drv.read_data()
    dut._log.info(f"MAC 8 * 9 = {res}, Expected: 72")
    assert res == 72, f"Expected 72, got {res}"
    dut._log.info("PASS: test_mac_simple")


@cocotb.test()
async def test_relu_clipping(dut):
    """Test 3: Verify Negative Accumulation Clamps to Zero via ReLU"""
    clock = Clock(dut.clk, CLK_PERIOD_NS, unit="ns")
    cocotb.start_soon(clock.start())
    drv = NPUDriver(dut)
    await drv.reset()

    await drv.send_cmd(0x00)  # len = 1
    await drv.send_cmd(0x50)  # ReLU
    await drv.send_cmd(0x81)  # Clear Acc

    # (-12) * 5 = -60 -> ReLU should clamp to 0
    await drv.send_pair(-12, 5)
    await ClockCycles(dut.clk, 2)

    res = await drv.read_data()
    dut._log.info(f"Negative product with ReLU = {res}, Expected: 0")
    assert res == 0, f"Expected 0, got {res}"
    dut._log.info("PASS: test_relu_clipping")


@cocotb.test()
async def test_vector_dot_product(dut):
    """Test 4: Vector Dot-Product with Arithmetic Right Shift Requantization"""
    clock = Clock(dut.clk, CLK_PERIOD_NS, unit="ns")
    cocotb.start_soon(clock.start())
    drv = NPUDriver(dut)
    await drv.reset()

    # 4-tap dot-product:
    # Weights:     [10, 20, -5, 15]
    # Activations: [ 2,  3, 10,  4]
    # Sum: 20 + 60 - 50 + 60 = 90
    # Requantize with shift=2 (offset=2): (90 + 2) >> 2 = 23
    await drv.send_cmd(0x03)  # CMD_SET_LEN: len = 4
    await drv.send_cmd(0x52)  # CMD_SET_POST: shift = 2, ReLU
    await drv.send_cmd(0x81)  # Clear Acc

    pairs = [(10, 2), (20, 3), (-5, 10), (15, 4)]
    for w, a in pairs:
        await drv.send_pair(w, a)

    await ClockCycles(dut.clk, 2)
    res = await drv.read_data()
    dut._log.info(f"Vector dot-product = {res}, Expected: 23")
    assert res == 23, f"Expected 23, got {res}"
    dut._log.info("PASS: test_vector_dot_product")


@cocotb.test()
async def test_argmax_classification(dut):
    """Test 5: Multi-class ArgMax Winner-Take-All Classifier"""
    clock = Clock(dut.clk, CLK_PERIOD_NS, unit="ns")
    cocotb.start_soon(clock.start())
    drv = NPUDriver(dut)
    await drv.reset()

    # Clear ArgMax (CMD_ACC_OPS with argmax_clear=1 -> 0x82)
    await drv.send_cmd(0x82)
    await drv.send_cmd(0x00)  # len = 1
    await drv.send_cmd(0x40)  # Linear

    # Class 0: score = 40
    await drv.send_cmd(0x81)
    await drv.send_pair(10, 4)
    await drv.send_cmd(0x84)  # ArgMax compare Class 0

    # Class 1: score = 150 (Winning Class)
    await drv.send_cmd(0x81)
    await drv.send_pair(15, 10)
    await drv.send_cmd(0x94)  # ArgMax compare Class 1

    # Class 2: score = 60
    await drv.send_cmd(0x81)
    await drv.send_pair(6, 10)
    await drv.send_cmd(0xA4)  # ArgMax compare Class 2

    # Read ArgMax output
    status = await drv.read_status()
    winning_class = status & 0x0F
    dut._log.info(f"ArgMax Winning Class: {winning_class}, Expected: 1")
    assert winning_class == 1, f"Expected class 1, got {winning_class}"
    dut._log.info("PASS: test_argmax_classification")


@cocotb.test()
async def test_ecg_arrhythmia_inference(dut):
    """Test 6: Full End-to-End ECG Arrhythmia Heartbeat Classification"""
    clock = Clock(dut.clk, CLK_PERIOD_NS, unit="ns")
    cocotb.start_soon(clock.start())
    drv = NPUDriver(dut)
    await drv.reset()

    # Test an abnormal Premature Ventricular Contraction (PVC) heartbeat
    # Matching template scores:
    #   Normal Template: -35 (Negative score)
    #   PVC Template:    +85 (Highest match score)
    #   PAC Template:    +15 (Weak match score)
    # Expected Winner: Class 1 (PVC Arrhythmia)

    await drv.send_cmd(0x82)  # Clear ArgMax
    await drv.send_cmd(0x00)  # len = 1
    await drv.send_cmd(0x40)  # Linear

    # Normal template
    await drv.send_cmd(0x81)
    await drv.send_pair(-7, 5)
    await drv.send_cmd(0x84)  # Class 0

    # PVC template
    await drv.send_cmd(0x81)
    await drv.send_pair(17, 5)
    await drv.send_cmd(0x94)  # Class 1

    # PAC template
    await drv.send_cmd(0x81)
    await drv.send_pair(3, 5)
    await drv.send_cmd(0xA4)  # Class 2

    status = await drv.read_status()
    best_class = status & 0x0F
    dut._log.info(
        f"ECG Heartbeat Arrhythmia Prediction: Class {best_class} (PVC), Expected: 1"
    )
    assert best_class == 1, f"Expected class 1 (PVC), got {best_class}"
    dut._log.info("PASS: test_ecg_arrhythmia_inference")
