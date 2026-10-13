"""
test.py - Cocotb Testbench for Scalable 2x2 TinyML NPU (tt_um_tinyml_npu_2x2)
Compatible with RTL simulation, gate-level simulation, and GitHub Actions CI.
"""

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, RisingEdge
import os

GL_TEST = os.environ.get("GATES", "no") == "yes"
TIMING_MULT = 3 if GL_TEST else 1
CLK_PERIOD_NS = 20  # 50 MHz


class NPU2x2Driver:

    def __init__(self, dut):
        self.dut = dut

    def _make_uio(self, valid=0, cmd=0, out_sel=0):
        val = (
            (1 if valid else 0)
            | ((1 if cmd else 0) << 2)
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
        self.dut.uio_in.value = self._make_uio(valid=1, cmd=1, out_sel=0)
        await RisingEdge(self.dut.clk)
        self.dut.uio_in.value = 0
        self.dut.ui_in.value = 0
        await ClockCycles(self.dut.clk, 1)

    async def send_data_byte(self, byte_val):
        await RisingEdge(self.dut.clk)
        self.dut.ui_in.value = byte_val & 0xFF
        self.dut.uio_in.value = self._make_uio(valid=1, cmd=0, out_sel=0)
        await RisingEdge(self.dut.clk)
        self.dut.uio_in.value = 0
        self.dut.ui_in.value = 0

    async def stream_2x2_operands(self, r0_act, r1_act, c0_wt, c1_wt):
        await self.send_data_byte(r0_act)
        await self.send_data_byte(r1_act)
        await self.send_data_byte(c0_wt)
        await self.send_data_byte(c1_wt)

    async def read_pe(self, pe_sel):
        cmd = 0x80 | ((pe_sel & 0x03) << 4)
        await self.send_cmd(cmd)
        self.dut.uio_in.value = self._make_uio(valid=0, cmd=0, out_sel=0)
        await ClockCycles(self.dut.clk, 1)
        val = int(self.dut.uo_out.value)
        if val >= 128:
            val -= 256
        return val

    async def read_status(self):
        self.dut.uio_in.value = self._make_uio(valid=0, cmd=0, out_sel=1)
        await ClockCycles(self.dut.clk, 1)
        return int(self.dut.uo_out.value)


@cocotb.test()
async def test_reset(dut):
    """Test 1: Verify Reset and Initial Ready State"""
    clock = Clock(dut.clk, CLK_PERIOD_NS, unit="ns")
    cocotb.start_soon(clock.start())
    drv = NPU2x2Driver(dut)
    await drv.reset()

    uio_out = int(dut.uio_out.value)
    ready = (uio_out >> 1) & 1
    busy = (uio_out >> 7) & 1

    assert ready == 1, f"Expected npu_ready=1, got {ready}"
    assert busy == 0, f"Expected npu_busy=0, got {busy}"
    dut._log.info("PASS: test_reset")


@cocotb.test()
async def test_mac_2x2_parallel(dut):
    """Test 2: Concurrent 4-PE Parallel Matrix MAC Computation"""
    clock = Clock(dut.clk, CLK_PERIOD_NS, unit="ns")
    cocotb.start_soon(clock.start())
    drv = NPU2x2Driver(dut)
    await drv.reset()

    # Set len=1, shift=0, Linear (00), clear Acc
    await drv.send_cmd(0x00)  # len = 1
    await drv.send_cmd(0x40)  # shift = 0, Linear
    await drv.send_cmd(0x81)  # clear acc

    # Stream operands: r0=8, r1=7, c0=9, c1=5
    # Expected:
    # PE00: 8 * 9 = 72
    # PE01: 8 * 5 = 40
    # PE10: 7 * 9 = 63
    # PE11: 7 * 5 = 35
    await drv.stream_2x2_operands(8, 7, 9, 5)
    await ClockCycles(dut.clk, 3)

    pe00 = await drv.read_pe(0)
    pe01 = await drv.read_pe(1)
    pe10 = await drv.read_pe(2)
    pe11 = await drv.read_pe(3)

    dut._log.info(f"PE00={pe00} (exp 72), PE01={pe01} (exp 40), PE10={pe10} (exp 63), PE11={pe11} (exp 35)")
    assert pe00 == 72, f"Expected PE00=72, got {pe00}"
    assert pe01 == 40, f"Expected PE01=40, got {pe01}"
    assert pe10 == 63, f"Expected PE10=63, got {pe10}"
    assert pe11 == 35, f"Expected PE11=35, got {pe11}"
    dut._log.info("PASS: test_mac_2x2_parallel")


@cocotb.test()
async def test_relu_clipping_and_requant(dut):
    """Test 3: Verify ReLU Clamping and Saturated Requantization on 2x2 Grid"""
    clock = Clock(dut.clk, CLK_PERIOD_NS, unit="ns")
    cocotb.start_soon(clock.start())
    drv = NPU2x2Driver(dut)
    await drv.reset()

    # Set len=1, shift=2, ReLU (01), clear Acc
    await drv.send_cmd(0x00)  # len = 1
    await drv.send_cmd(0x52)  # shift = 2, ReLU
    await drv.send_cmd(0x81)  # clear acc

    # Operands: r0=-10, r1=12, c0=4, c1=6
    # PE00: -10 * 4 = -40 -> ReLU clamp to 0
    # PE01: -10 * 6 = -60 -> ReLU clamp to 0
    # PE10:  12 * 4 =  48 -> (48 + 2) >> 2 = 12
    # PE11:  12 * 6 =  72 -> (72 + 2) >> 2 = 18
    await drv.stream_2x2_operands(-10, 12, 4, 6)
    await ClockCycles(dut.clk, 3)

    pe00 = await drv.read_pe(0)
    pe01 = await drv.read_pe(1)
    pe10 = await drv.read_pe(2)
    pe11 = await drv.read_pe(3)

    dut._log.info(f"PE00={pe00} (exp 0), PE01={pe01} (exp 0), PE10={pe10} (exp 12), PE11={pe11} (exp 18)")
    assert pe00 == 0, f"Expected PE00=0, got {pe00}"
    assert pe01 == 0, f"Expected PE01=0, got {pe01}"
    assert pe10 == 12, f"Expected PE10=12, got {pe10}"
    assert pe11 == 18, f"Expected PE11=18, got {pe11}"
    dut._log.info("PASS: test_relu_clipping_and_requant")


@cocotb.test()
async def test_dual_channel_ecg_inference(dut):
    """Test 4: Concurrent Dual-Template ECG Arrhythmia Classification"""
    clock = Clock(dut.clk, CLK_PERIOD_NS, unit="ns")
    cocotb.start_soon(clock.start())
    drv = NPU2x2Driver(dut)
    await drv.reset()

    # Column 0: Normal template weights [ -5, 10 ]
    # Column 1: PVC template weights    [  15, 20 ]
    # Row 0: Beat sample segment A      [  2,   3 ]
    # Step 1:
    # PE00: 2 * (-5) = -10
    # PE01: 2 * 15   =  30
    # Step 2:
    # PE00: -10 + 3 * 10 = +20 (Normal score)
    # PE01:  30 + 3 * 20 = +90 (PVC score -> Winning Arrhythmia Class!)
    await drv.send_cmd(0x01)  # len = 2
    await drv.send_cmd(0x40)  # shift = 0, Linear
    await drv.send_cmd(0x81)  # clear acc

    # Step 1 operands: r0=2, r1=0, c0=-5, c1=15
    await drv.stream_2x2_operands(2, 0, -5, 15)
    await ClockCycles(dut.clk, 2)

    # Step 2 operands: r0=3, r1=0, c0=10, c1=20
    await drv.stream_2x2_operands(3, 0, 10, 20)
    await ClockCycles(dut.clk, 3)

    normal_score = await drv.read_pe(0)
    pvc_score = await drv.read_pe(1)

    dut._log.info(f"ECG Normal Template Score: {normal_score}, PVC Template Score: {pvc_score}")
    assert normal_score == 20, f"Expected Normal score=20, got {normal_score}"
    assert pvc_score == 90, f"Expected PVC score=90, got {pvc_score}"
    assert pvc_score > normal_score, "PVC score must exceed Normal score for abnormal heartbeat"
    dut._log.info("PASS: test_dual_channel_ecg_inference (PVC correctly identified with higher match score)")
