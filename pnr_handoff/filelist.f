# ==============================================================================
# TinyML NPU 2x2 Systolic Array - Synthesizable RTL Filelist
# Project:      tiny_npu_-TT (Tiny Tapeout Shuttle Handoff)
# Top Module:   tt_um_tinyml_npu_2x2
# Core Module:  npu_top_2x2
# Target:       IHP SG13G2 130nm / SkyWater Sky130A
# Dependency:   Strict Bottom-Up Dependency Ordering
# ==============================================================================

# Leaf Processing Element (Signed INT8 x INT8 Multiplier + 24-bit Accumulator)
rtl/npu_pe.v

# Activation & Requantization Engine (Right-shift, Rounding, ReLU/Clipping)
rtl/npu_activation.v

# Parameterized 2D Systolic Array Grid (ROWS=2, COLS=2, Systolic/SIMD Dataflow)
rtl/npu_array.v

# 2x2 Core Datapath & Parallel Multi-Channel Requantizers
rtl/npu_top_2x2.v

# Tiny Tapeout Top Wrapper (Pinout Contract, Streaming Sequencer, Multiplexer)
rtl/tt_um_tinyml_npu_2x2.v
