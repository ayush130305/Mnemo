# 2. Parameters and assumptions

[Back to the README](../README.md)

v0.1 fixes these defaults so the simulator and the RTL use the same numbers; every one is a configuration constant.

| Parameter       | v0.1 default                                                | Why                                                                               |
|-----------------|-------------------------------------------------------------|-----------------------------------------------------------------------------------|
| Line            | 64 bytes                                                    | Unit of compression and of one processor burst (16 beats of 32 bits)              |
| Page            | 1 KB = 16 lines                                             | Unit of translation and allocation; small enough for an on-chip table in the demo |
| Chunk           | 128 bytes                                                   | Unit of physical allocation (like the 256 B sectors of IBM MXT, but finer)        |
| Chunks per page | up to 8                                                     | A page never needs more than 1 KB of chunks                                       |
| Line slot sizes | 0 (zero page), 16, 32, 64 bytes (48 dropped, see section 6) | One slot size per page, so a line's offset is a multiplication (as in LCP)        |
| Exception slot  | 64 bytes, raw                                               | Holds a line that does not fit the page's slot size                               |
| Codecs          | zero, BDI, FPC, raw per line; LZ per cold page              | Cheap codecs on the access path, LZ only off it                                   |
| Demo sizes      | 96 KB virtual, 64 KB physical (512 chunks)                  | Overcommit 1.5x, configurable; fits Basys 3 block RAM                             |
| Hot buffer      | 4 pages decompressed (4 KB)                                 | Hides LZ latency and keeps hot data uncompressed                                  |
| Reserve         | 16 chunks                                                   | Guarantees writes to existing pages can finish under pressure                     |
| Clock           | 100 MHz target on Artix-7                                   | Latency below is counted in clocks                                                |

**Assumptions.** The memory behind the coprocessor is addressable in 32-bit words with a fixed read latency (block RAM in v0; PSRAM or DRAM later). The host tolerates wait states on the bus. The host reads the capacity registers or accepts a bus error when the physical memory is full.
