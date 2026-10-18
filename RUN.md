# How to run

Python 3.9 or newer. Run every command from the folder shown. No third-party packages are needed.

## Python studies (`python_files/`)

```
cd python_files
python3 mnemo_corpus.py
python3 mnemo_compare.py
python3 mnemo_policy.py
python3 mnemo_blocks.py
```

`mnemo_corpus.py` rebuilds `test_files/` and needs `riscv64-unknown-elf-gcc` (the files are already included, skip it otherwise). Results go to `showcase/results/`.

## Simulator (`simulator/`)

```
cd simulator
python3 mnemo_sim.py
./build_viz.sh
open viz/mnemo_sim_visual.html
```

Options for `mnemo_sim.py`: `--min-gain 0.25` or `--gains "0,0.25,0.375,0.5"`.

## Full coprocessor model and its tests

```
cd simulator
python3 mnemo_model_test.py
```

This replays random traces against a shadow memory and checks the allocator invariants after every operation. Mismatches must be 0.

## RTL (`rtl/`)

```
cd rtl
./run_all.sh
```

Needs Icarus Verilog (`brew install icarus-verilog`). It compiles every `*.v` with its `tb_*.v` testbench and runs it. No RTL is written yet, see `rtl/README.md`.
