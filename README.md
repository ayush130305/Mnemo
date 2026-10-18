# Mnemo: architecture

Mnemo is a coprocessor between a processor and its memory. It stores data compressed and losslessly, owns the physical memory allocation, and learns which codec and layout suit each region. The processor sees an ordinary AXI4 memory. The full spec is `showcase/Mnemo_Architecture_Spec_v0.1.docx`.

## Goal

- Byte-exact reads of everything written (always).
- Compression ratio above 1.3 on mixed workloads, average added read latency under 6 clocks for line-level data.
- A learned policy that beats a fixed one on the same traces.
- It does not promise a fixed larger memory: it reports effective capacity and pressure instead. No encryption, ECC replacement or coherence.

## Parameters

| Item | Value |
| --- | --- |
| Line | 64 B (one 16-beat burst) |
| Page | 1 KB = 16 lines (unit of translation) |
| Chunk | 128 B (unit of physical allocation, up to 8 per page) |
| Reserve | chunks 0 to 15, only for in-flight operations |

## Block diagram

```
 processor --AXI4--> front end --> translation (PTE) --> codec bank / page engine --> arbiter --> memory
                                        |                       |                       ^
                                        v                       v                       |
                                   allocator (chunk pool, exceptions, repack, pressure) -+
                                        ^
                       learning block (regions, prediction, reasons, telemetry)   <-- registers (AXI4-Lite)
```

| Block | Job |
| --- | --- |
| Front end | AXI4 slave, collects 16-beat bursts, merges partial lines |
| Translation | One PTE per page, line address computed from the PTE with no search |
| Codec bank | Zero, BDI, FPC run in parallel on a write; the selector picks the winner or follows the prediction |
| Page engine | Cold-page LZ compression, hot buffer of 4 expanded pages, raw overflow |
| Allocator | Bitmap plus free stack, exceptions, repack, pressure levels |
| Learning block | Per-region counters, codec and slot prediction, epsilon-greedy exploration, reason codes, telemetry ring |
| Registers | AXI4-Lite control, counters, telemetry window, PTE debug window |

## Page modes

| Mode | Meaning | Chunks |
| --- | --- | --- |
| 0 | Zero or unallocated | 0 |
| 1 | Raw | 8 |
| 2 | Line-compressed: fixed slot (16, 32 or 64 B) per page plus an exception area | 2/4/8 + exceptions/2 |
| 3 | Cold page, one LZ stream (LZSS, xz as a later software tier), at most 6 chunks | up to 6 |

A line in mode 2 sits at `line x slot`. A line that does not fit goes to the exception area (64 B entries, two per chunk), located by counting set exception bits below it. A page that would need more than 8 chunks becomes raw.

## Page table entry

Compressed pages carry the full entry (mode, slot, chunk pointers, 2-bit codec per line, exception bits, LZ length, hot/dirty/hot-buffer index, heat). With the light layout the entry size depends on the mode: about 36 B for a compressed page, about 8 B for a raw page and 2 B for a zero page (raw and zero sizes are assumptions to confirm in RTL). An 8-bit CRC per line lives in a side RAM.

## Write and read

- Read: page and line from the address, read the PTE, hot buffer hit returns at once, mode 0 returns zeros, mode 2 reads the slot and decodes it, optional CRC check.
- Write: partial line merges first, the selector picks a codec that fits the slot, writes in place or into the exception area (reason 4), the first non-zero line turns a zero page into a mode 2 page, overflow turns a page raw (reason 5).
- Cold page: a page with heat zero is compressed with LZ into 6 chunks or fewer under pressure; access expands it into the hot buffer (LRU, write back when dirty).

## Pressure

| Level | Free chunks | Action |
| --- | --- | --- |
| Normal | above 25% | nothing |
| Low | 10 to 25% | background repack, cold LZ, status bit |
| Critical | below 10% | interrupt, no growth for non-hot pages |
| Full | reserve only | new allocations return SLVERR, the reserve finishes in-flight writes |

## Threshold layer

A page is compressed only if it saves at least X% of its eight chunks, otherwise it is stored raw (reason 5). X is the `POLICY2` register (new in this revision).

## Learning

Regions of 4 pages keep codec win counters, a size histogram and access counters. The selector follows the codec with the highest win counter when its lead is above a margin, explores all codecs one time in 32, and a new page takes the smallest slot that covers 90% of recent lines. Every decision stores a reason code (0 to 9) and goes into a 256-entry telemetry ring. A slow brain (RP2350 or host, later) trains parameters offline and writes them into the policy registers.

## Integrity

Decode-after-encode in debug mode, CRC8 per line checked on read, allocator invariants checked after every operation in the simulator, bypass mode (everything raw), and a startup scan that rebuilds the free list.

## What is measured so far

See `showcase/FEATURES.md` and `showcase/results/`. How to run everything: `RUN.md`.

## Folders

| Folder | Content |
| --- | --- |
| `showcase/` | What we did: spec, results, feature list |
| `test_files/` | Test corpus (firmware, native code, data, controls) |
| `c_files/` | C sources and linker script for the firmware in the corpus |
| `python_files/` | Codecs, corpus builder, comparator, policy and block-size studies |
| `simulator/` | Page simulator, visual simulator, full coprocessor model and its tests |
| `rtl/` | Verilog and the RTL simulation runner |
