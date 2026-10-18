# RTL

Verilog sources and testbenches for Mnemo go here. Name testbenches `tb_<module>.v`.
`run_all.sh` compiles each `tb_*.v` with the sources in this folder using Icarus Verilog and runs it, so a failing testbench stops the run.
No RTL is written yet: the spec asks for the simulator to show which codecs and slot sizes earn their area first.
