#!/usr/bin/env python3
"""Compatibility entry point. Canonical EDA invocations are visible in Makefile."""
import os,sys
from pathlib import Path
os.chdir(Path(__file__).resolve().parents[1])
args=['make']
if '--synth-only' in sys.argv:
    args+=['preflight','synthesis','timing']
elif '--baseline' in sys.argv:
    raise SystemExit('Original negative controls are immutable under evidence/review/negative_controls; do not overwrite them with corrected RTL.')
else:
    args+=['regression']
os.execvp(args[0],args)
