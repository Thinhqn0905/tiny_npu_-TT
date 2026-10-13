# Run from pnr_handoff/reports.
set here [pwd]
read_liberty $here/../config/sg13g2_stdcell_typ_1p20V_25C.lib
read_verilog $here/mapped_netlist.v
link_design tt_um_tinyml_npu_2x2
read_sdc $here/../constraints/design.sdc
report_checks -path_delay max -group_count 5 -format full_clock_expanded -digits 4
report_checks -path_delay min -group_count 5 -digits 4
report_worst_slack
check_setup -verbose
exit
