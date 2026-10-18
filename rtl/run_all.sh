#!/bin/sh
# Runs every testbench in this folder with Icarus Verilog
cd "$(dirname "$0")"
set -e
n=0
for tb in tb_*.v; do
  [ -e "$tb" ] || { echo "no testbenches yet"; exit 0; }
  out="${tb%.v}.vvp"
  iverilog -g2012 -o "$out" "$tb" $(ls *.v | grep -v '^tb_')   # Compile the testbench with the design files
  vvp "$out"                                                    # Run it
  n=$((n+1))
done
echo "$n testbench(es) passed"
