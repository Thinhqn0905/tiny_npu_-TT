import sys
sys.path.insert(0, '/tmp/tt-support-tools')
from project_checks import check_project_docs

print("Checking docs with sky130A:")
check_project_docs('/mnt/e/PROJECTS/tinyml_npu_ecg/ttihp26a-inferenceFCNN-16h3', 'sky130A')
print("PASS: sky130A")

print("Checking docs with ihp-sg13g2:")
check_project_docs('/mnt/e/PROJECTS/tinyml_npu_ecg/ttihp26a-inferenceFCNN-16h3', 'ihp-sg13g2')
print("PASS: ihp-sg13g2")
