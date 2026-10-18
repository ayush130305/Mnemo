# 14. Build plan and boards

[Back to the README](../README.md)

| Milestone | Deliverable                                                                                               | Where it runs           |
|-----------|-----------------------------------------------------------------------------------------------------------|-------------------------|
| M0        | Python simulator: translation, allocator, zero/BDI/FPC/LZ codecs, simple learning, traces, metrics, plots | PC                      |
| M1        | Data study: ratios of real dumps; choose slot sizes and codec set from evidence                           | PC                      |
| M2        | Learned policy versus fixed policy; reason codes and telemetry format fixed                               | PC                      |
| M3        | RTL for the line codecs and the translation unit, tested against the simulator                            | Simulator (iverilog)    |
| M4        | RTL allocator and front end; block RAM as memory; UART host to drive traces                               | Basys 3                 |
| M5        | Page engine reusing the compengine LZSS core; hot buffer                                                  | Basys 3 or Zen 4        |
| M6        | Slow brain on RP2350 reading telemetry and writing policy registers                                       | Zen 4 plus RP2350       |
| M7        | Real memory behind it (PSRAM or DDR) and the in-use memory migration                                      | Board with external RAM |

**Boards.** Basys 3 (Artix-7, 100 MHz) has no external RAM, so block RAM stands in for the memory in M4 and M5; that is enough to prove the logic and measure the cost. The Zen 4 board (Trion T4F81 with an RP2350) fits M5 and M6 because the RP2350 can be the slow brain and the existing compengine link is already working. A board with PSRAM or DDR is needed for M7.

**Reuse.** The LZSS core, UART link, testbench style and Python host tools from compengine are reused as they are.

**First weeks.** M0 and M1 only. No RTL is written until the simulator shows which codecs and slot sizes earn their area.
