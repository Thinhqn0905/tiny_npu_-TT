#!/usr/bin/env bash
export PATH="/home/hacker/.local/bin:$PATH"
cd /mnt/e/PROJECTS/tinyml_npu_ecg/ttihp26a-inferenceFCNN-16h3/test
echo "Cocotb makefile: $(cocotb-config --makefiles)"
make clean
make
