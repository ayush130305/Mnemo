# Mnemo: features so far

## Codecs (python_files/mnemo_codecs.py)
- Line codecs with real encoders and decoders: zero, BDI, FPC, raw.
- LZSS page codec in the compengine format (window 512, match 3 to 18).
- xz (raw LZMA2, preset 9) and zlib (raw deflate) as software block codecs.
- Memory model: slots 16/32/64, 128 B chunks, rounding, metadata.

## Studies (python_files/)
- Corpus of 57 files, 1.43 MB: RISC-V firmware (.bin, .hex, RAM images), real PicoRV32 firmware, x86 code, sensor, pointer, float, text, random and zero controls.
- Comparator with lossless round-trip check on every file, ranking tables, baud-rate time model.
- Block-size study (1 KB, 4 KB, 8 KB).
- Policy study: fixed rule against per-page oracle, hot-share cost, threshold sweep, metadata layout comparison.
- Threshold layer: compress only if the saving is at least X%, otherwise store raw.
- Light metadata layout: 36 B compressed, about 8 B raw, 2 B zero (raw and zero sizes are assumptions).

## Page simulator (simulator/mnemo_sim.py)
- Stores real files page by page in a chunk pool with modes 0 to 4 (xz as mode 4), exceptions and raw fallback.
- Visual simulator (viz/mnemo_sim_visual.html): store and retrieve scene, compact-a-full-chip scene, live min-saving selector.

## Full coprocessor model (simulator/mnemo_model.py)
- Front end: line and byte reads and writes, partial-line merge, SLVERR responses.
- Translation: PTE with mode, slot, chunk pointers, codec per line, exception bits, LZ length, hot/dirty/index, heat.
- Selector: parallel codecs, tie order, prediction with raw fallback, epsilon-greedy exploration, FORCE register.
- Allocator: free stack, reserve chunks 0 to 15, exceptions, overflow to raw, repack, pressure levels with sticky status bits.
- Page engine: cold LZ (LZSS or xz), hot buffer of 4 pages with LRU and write back, threshold layer.
- Learning block: regions, win counters, size histogram, slot prediction, reason codes 0 to 9, 256-entry telemetry ring.
- Integrity: CRC8 per line, decode-after-encode debug check, bypass mode, startup scan.
- Register map with the spec names, plus POLICY2 (minimum saving, cold algorithm).
- Tests (mnemo_model_test.py): shadow memory, allocator invariants after every operation. Last run: 0 mismatches.

## Key findings
- Line codecs alone give about 1.0x on real code (0.94x after metadata). LZSS pages give 2.21x over the whole corpus, xz pages 2.53x.
- Per-page size oracle equals xz-only, so the learning block earns its place through latency and hotness prediction, not size.
- Hot data kept line-compressed costs capacity: 3.21x at 0% hot down to 1.52x at 100% hot.
- A 25% threshold costs about 2% of the ratio and removes the decode on about 15% of pages.
- Cycle numbers are assumptions until calibrated from RTL.
