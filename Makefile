# Canonical, visible front-end EDA commands. Run in Linux / WSL at design root.
.NOTPARALLEL:
PYTHON ?= python3
STA ?= sta
TT_TOOLS ?= /tmp/tt-support-tools
ECG_PYTHONPATH ?= /tmp/npu-ecg-libs
DATA_SOURCE ?= /mnt/e/ResearchOnWork/data/ecg/mitdb_1.0.0
TRAIN_PYTHON ?= python3
COVERAGE_MAX_ROUNDS ?= 5
TC ?=
TEST_MODULE ?= test_release
SOURCES := $(shell $(PYTHON) scripts/front_end_reports.py filelist)
ABS_SOURCES := $(addprefix $(CURDIR)/,$(SOURCES))
REPORTS := evidence/review/final
export PATH := $(HOME)/.local/bin:$(PATH)
export PYTHONPATH := $(CURDIR)/test:$(CURDIR)/test/legacy
export COCOTB_RANDOM_SEED := 784736294
export PYGPI_PYTHON_BIN := $(shell $(PYTHON) -m cocotb_tools.config --python-bin)
export GPI_USERS := $(shell $(PYTHON) -m cocotb_tools.config --libpython);$(shell $(PYTHON) -m cocotb_tools.config --pygpi-entry-point)
export REVIEW_OUT := $(CURDIR)/$(REPORTS)
.PHONY: help preflight rtl-preflight lint tb-compile test regression arithmetic release existing legacy standalone synthesis timing integration reports manifest manifest-check ecg-benchmark mutation coverage-baseline coverage-regression coverage-report
help:
	@echo 'Run from repository root in Linux/WSL; make -n TARGET shows real commands.'
	@echo 'preflight: validate frozen copies/config, recover legacy tests, prepare Yosys/STA scripts; saves run_identity.json.'
	@echo 'rtl-preflight: prepare RTL-only checks without requiring Yosys or OpenSTA; REPORTS=work/ci-results isolates CI outputs.'
	@echo 'lint: Verilator4.038 -Wall; tb-compile: Icarus11 production and unit harnesses.'
	@echo 'test TEST_MODULE=test_release TC=ready_back_to_back: one Cocotb2.1 test; test modules: test_arithmetic/test_release/test/test_legacy.'
	@echo 'regression: all diagnostics, Yosys0.9 generic/IHP mapping, OpenSTA2.0.17, local official docs/structural checks; no physical PnR.'
	@echo 'synthesis/timing/integration/reports: raw evidence and parsed reports in pnr_handoff/reports and evidence/review/final.'
	@echo 'STA=/path/to/sta TT_TOOLS=/path/to/pinned/tt-support-tools override installed tools.'
	@echo 'manifest / manifest-check: generate and verify path/size/SHA256 inventory; independent PowerShell checker provided.'
	@echo 'ecg-benchmark: software-only TFLite2.14/wfdb4.1.2/NumPy1.26.4; ECG_PYTHONPATH and DATA_SOURCE configure isolated dependencies/data.'
	@echo 'generate-network-test/sva-compile/contract-shell-compile/trained-network: independent saved SV and approved public-port assertions.'
	@echo 'mutation: compile and simulate 18 isolated faults; raw logs/XML and per-REQ detection scores.'
	@echo 'coverage-baseline/coverage-regression: Verilator --coverage --assert with public-pin integer checks; coverage-report parses native point counts.'
	@echo 'COVERAGE_MAX_ROUNDS=$(COVERAGE_MAX_ROUNDS) (closure limit after instrumentation/target approval).'
rtl-preflight:
	$(PYTHON) scripts/front_end_reports.py prepare
	mkdir -p work/compile $(REPORTS)
	verilator --version > $(REPORTS)/tools.log
	iverilog -V >> $(REPORTS)/tools.log 2>&1
	$(PYTHON) --version >> $(REPORTS)/tools.log
	cocotb-config --version >> $(REPORTS)/tools.log
preflight: rtl-preflight
	yosys -V >> $(REPORTS)/tools.log
	$(STA) -version >> $(REPORTS)/tools.log
lint:
	verilator --lint-only -Wall --top-module tt_um_tinyml_npu_2x2 $(SOURCES) > $(REPORTS)/verilator.log 2>&1
tb-compile:
	iverilog -g2012 -s tb -o work/compile/production.vvp $(SOURCES) src/sva/npu_protocol_properties.sv test/tb.v > $(REPORTS)/production_compile.log 2>&1
	iverilog -g2012 -s tb_review -o work/compile/arithmetic.vvp $(SOURCES) test/tb_review.v > $(REPORTS)/arithmetic_compile.log 2>&1
generate-network-test:
	$(PYTHON) scripts/generate_network_tb.py
sva-compile:
	iverilog -g2012 -s npu_protocol_properties -o work/compile/sva.vvp -f src/sva/filelist_sva.f > $(REPORTS)/sva_compile.log 2>&1
contract-shell-compile:
	iverilog -g2012 -s tb_trained_network -o work/compile/contract_shell.vvp src/verification/contract_if.sv -f src/tb/filelist_tb.f > $(REPORTS)/contract_shell_compile.log 2>&1
trained-network:
	iverilog -g2012 -s tb_trained_network -o work/compile/trained_network.vvp $(SOURCES) -f src/tb/filelist_tb.f > $(REPORTS)/trained_network_compile.log 2>&1
	vvp work/compile/trained_network.vvp > $(REPORTS)/trained_network.log 2>&1
ifeq ($(TC),TC-TRAINED-E2E)
test: generate-network-test trained-network
else ifeq ($(TC),TC-COVERAGE-BASE)
test: coverage-baseline
else
test:
	$(MAKE) -C test MODULE=$(TEST_MODULE) COCOTB_TEST_MODULES=$(TEST_MODULE) COCOTB_TESTCASE='$(TC)' SRC_DIR=$(CURDIR)/pnr_handoff/rtl SIM_BUILD=$(CURDIR)/work/sim/manual COCOTB_RESULTS_FILE=$(CURDIR)/$(REPORTS)/manual.xml
endif
arithmetic:
	$(MAKE) -C test MODULE=test_arithmetic COCOTB_TEST_MODULES=test_arithmetic TOPLEVEL=tb_review VERILOG_SOURCES='$(ABS_SOURCES) $(CURDIR)/test/tb_review.v' SIM_BUILD=$(CURDIR)/work/sim/arithmetic COCOTB_RESULTS_FILE=$(CURDIR)/$(REPORTS)/arithmetic.xml > $(REPORTS)/arithmetic.log 2>&1
release:
	$(MAKE) -C test MODULE=test_release COCOTB_TEST_MODULES=test_release SRC_DIR=$(CURDIR)/pnr_handoff/rtl SIM_BUILD=$(CURDIR)/work/sim/release COCOTB_RESULTS_FILE=$(CURDIR)/$(REPORTS)/release.xml > $(REPORTS)/release.log 2>&1
existing:
	$(MAKE) -C test MODULE=test COCOTB_TEST_MODULES=test SRC_DIR=$(CURDIR)/pnr_handoff/rtl SIM_BUILD=$(CURDIR)/work/sim/existing COCOTB_RESULTS_FILE=$(CURDIR)/$(REPORTS)/existing.xml > $(REPORTS)/existing.log 2>&1
legacy:
	$(MAKE) -C test MODULE=test_legacy COCOTB_TEST_MODULES=test_legacy TOPLEVEL=tb VERILOG_SOURCES='$(wildcard $(CURDIR)/src/*.v) $(CURDIR)/test/legacy/tb.v' SIM_BUILD=$(CURDIR)/work/sim/legacy COCOTB_RESULTS_FILE=$(CURDIR)/$(REPORTS)/legacy.xml > $(REPORTS)/legacy.log 2>&1
standalone:
	iverilog -g2012 -s tb_npu_standalone -o work/compile/legacy.vvp src/*.v test/tb_npu_standalone.v > $(REPORTS)/tb_npu_standalone_compile.log 2>&1
	vvp work/compile/legacy.vvp > $(REPORTS)/tb_npu_standalone.log 2>&1
	iverilog -g2012 -s tb_npu_2x2_standalone -o work/compile/core.vvp $(SOURCES) test/tb_npu_2x2_standalone.v > $(REPORTS)/tb_npu_2x2_standalone_compile.log 2>&1
	vvp work/compile/core.vvp > $(REPORTS)/tb_npu_2x2_standalone.log 2>&1
	iverilog -g2012 -s tb_tt_um_2x2 -o work/compile/wrapper.vvp $(SOURCES) test/tb_tt_um_2x2.v > $(REPORTS)/tb_tt_um_2x2_compile.log 2>&1
	vvp work/compile/wrapper.vvp > $(REPORTS)/tb_tt_um_2x2.log 2>&1
synthesis:
	cd pnr_handoff && yosys -s reports/generic.ys > reports/yosys_synth.log 2>&1
	cd pnr_handoff && yosys -s reports/mapped.ys > reports/yosys_mapped.log 2>&1
	$(PYTHON) scripts/front_end_reports.py synth-report
timing:
	cd pnr_handoff/reports && $(STA) -exit timing.tcl > timing_est.rpt 2>&1
	$(PYTHON) scripts/front_end_reports.py timing-report
integration:
	$(PYTHON) scripts/check_tt_metadata.py --tools $(TT_TOOLS) > $(REPORTS)/tinytapeout_metadata.log 2>&1
reports:
	$(PYTHON) scripts/front_end_reports.py collect
	$(PYTHON) scripts/front_end_reports.py historical-manifests
	$(PYTHON) scripts/write_review_docs.py
regression: preflight lint tb-compile arithmetic release existing legacy standalone generate-network-test sva-compile contract-shell-compile trained-network synthesis timing integration coverage-baseline mutation reports
manifest:
	$(PYTHON) scripts/front_end_reports.py manifest
manifest-check:
	$(PYTHON) scripts/front_end_reports.py manifest-check
ecg-benchmark:
	PYTHONPATH=$(ECG_PYTHONPATH) $(PYTHON) scripts/ecg_benchmark.py --source-dataset $(DATA_SOURCE) > evidence/ecg_wsl.log 2>&1
tiny-features:
	PYTHONPATH=$(ECG_PYTHONPATH) $(PYTHON) scripts/train_tiny_ecg.py features > evidence/tiny_ecg_features.log 2>&1
tiny-train:
	$(TRAIN_PYTHON) scripts/train_tiny_ecg.py train > evidence/tiny_ecg_training.log 2>&1
coverage-baseline coverage-regression: coverage-measure coverage-report
coverage-report:
	$(PYTHON) scripts/coverage_report.py
coverage-measure:
	mkdir -p work/coverage/baseline evidence/review/coverage
	verilator --cc --exe --build --coverage --assert --top-module coverage_top --Mdir $(CURDIR)/work/coverage/obj $(SOURCES) src/sva/npu_protocol_properties.sv src/tb/tests/tc_coverage_baseline.sv $(CURDIR)/test/coverage_driver.cpp > evidence/review/coverage/build.log 2>&1
	work/coverage/obj/Vcoverage_top > evidence/review/coverage/run.log 2>&1
	verilator_coverage --write work/coverage/baseline/merged.dat work/coverage/baseline/coverage.dat > evidence/review/coverage/merge.log 2>&1
	verilator_coverage --write-info work/coverage/baseline/coverage.info work/coverage/baseline/merged.dat > evidence/review/coverage/report.log 2>&1
mutation:
	$(PYTHON) scripts/mutation_artifacts.py prepare
	while read mid kind tc; do \
	  folder=work/mutation/$$mid; output=evidence/review/mutation/$$mid; \
	  if [ "$$kind" = network ]; then \
	    iverilog -g2012 -s tb_trained_network -o $$folder/sim.vvp $$folder/*.v -f src/tb/filelist_tb.f > $$output/compile.log 2>&1; cr=$$?; \
	  elif [ "$$kind" = unit ]; then \
	    iverilog -g2012 -s tb_review -o $$folder/sim.vvp $$folder/*.v test/tb_review.v > $$output/compile.log 2>&1; cr=$$?; \
	  else \
	    iverilog -g2012 -s tb -o $$folder/sim.vvp $$folder/*.v src/sva/npu_protocol_properties.sv test/tb.v > $$output/compile.log 2>&1; cr=$$?; \
	  fi; echo $$cr > $$output/compile_rc.txt; \
	  if [ $$cr -ne 0 ]; then echo 99 > $$output/run_rc.txt; continue; fi; \
	  if [ "$$kind" = network ]; then \
	    vvp $$folder/sim.vvp > $$output/run.log 2>&1; rr=$$?; \
	  else \
	    if [ "$$kind" = unit ]; then top=tb_review; mod=test_arithmetic; else top=tb; mod=test_release; fi; \
	    COCOTB_TOPLEVEL=$$top COCOTB_TEST_MODULES=$$mod COCOTB_TEST_FILTER=".*$$tc$$" COCOTB_RESULTS_FILE=$(CURDIR)/$$output/results.xml TOPLEVEL_LANG=verilog vvp -m $$(cocotb-config --lib-name-path vpi icarus) $$folder/sim.vvp > $$output/run.log 2>&1; rr=$$?; \
	  fi; echo $$rr > $$output/run_rc.txt; \
	done < work/mutation/manifest.txt
	$(PYTHON) scripts/mutation_artifacts.py collect
