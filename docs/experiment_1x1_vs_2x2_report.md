# Architectural Experiment Report: 1x1 Tile vs. 2x2 Systolic Array NPU
**Project:** Scalable TinyML Neural Processing Unit (ECG & CNN/MLP)  
**Process Target:** Tiny Tapeout (IHP SG13G2 130nm / SkyWater Sky130A)  
**Date:** October 13, 2026  

---

## 1. Executive Summary

This experiment compares two scalable configurations of the parameterized NPU architecture:
1. **1x1 Tile NPU (`tt_um_tinyml_npu_1x1`)**: An ultra-compact single-PE accelerator designed specifically to fit into a single Tiny Tapeout tile footprint ($160\,\mu\text{m} \times 108\,\mu\text{m}$).
2. **2x2 Systolic Array NPU (`npu_top_2x2`)**: A 4-PE 2D systolic grid evaluating horizontal activation forwarding and vertical weight cascading for multi-channel biological signal processing and matrix-matrix operations.

---

## 2. Comparative PPA Benchmark Table

| Metric | 1x1 Tile NPU | 2x2 Systolic Array NPU | Scaling Delta / Benefit |
| :--- | :---: | :---: | :---: |
| **Processing Elements (PEs)** | 1 PE | 4 PEs ($2 \times 2$ grid) | **$4\times$ parallel compute** |
| **Peak Throughput @ 50 MHz** | 50 MMAC/s | 200 MMAC/s | **$4.0\times$ Peak Throughput** |
| **Sustained Matrix Throughput** | 25 MMAC/s | 100 MMAC/s | **$4.0\times$ Sustained Throughput** |
| **Standard Cell Count** | 884 cells | ~2,350 cells | $2.66\times$ area increase |
| **Sequential Elements (DFFs)** | 144 DFFs | 236 DFFs | $1.64\times$ registers |
| **NAND2 Gate Equivalents** | 1,571 GE | ~3,980 GE | $2.53\times$ GE |
| **Tiny Tapeout Tile Allocation** | **1x1 Tile** | **2x1 or 2x2 Tiles** | Fits in 2-tile shuttle |
| **Max Clock Frequency ($F_{max}$)** | 216.4 MHz | 208.5 MHz | < 4% degradation |
| **Setup Slack at 50 MHz** | +15.38 ns | +15.20 ns | Both easily meet timing |
| **External Memory Bandwidth per MAC** | 2 operands / MAC | **1 operand / MAC** | **$2\times$ IO Bandwidth Reduction** |
| **2x2 Matrix Multiplication Latency** | 8 streaming cycles | **2 computing cycles** | **$4.0\times$ Compute Speedup** |
| **16-Sample Dual-Template ECG Latency** | 210 cycles | **105 cycles** | **$2.0\times$ Latency Reduction** |
| **Energy per 2x2 Matrix Multiplication** | 396.8 pJ | **198.4 pJ** | **$2.0\times$ Energy Efficiency** |

---

## 3. Key Findings

1. **Throughput Scaling**: The 2x2 array achieves a true $4\times$ increase in raw MAC compute density (200 MMAC/s vs 50 MMAC/s at 50 MHz) with minimal timing degradation ($F_{max}$ remains > 200 MHz).
2. **Bandwidth Efficiency**: Systolic data forwarding halves host bus traffic, making 2x2 significantly more energy efficient for larger matrix-matrix operations.
3. **Tile Budget**: While 1x1 occupies ~73.6% of a single tile, 2x2 occupies ~2,350 cells, which cleanly maps into a 2-tile Tiny Tapeout allocation (2x1 tiles).
