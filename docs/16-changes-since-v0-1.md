# 16. Changes since v0.1 (simulator findings)

[Back to the README](../README.md)

These are implemented in `simulator/mnemo_model.py` and still to be merged into the sections above.

- **Light page table entry.** The entry size depends on the mode: about 36 B for a compressed page (mode 2 or 3), about 8 B for a raw page, 2 B for a zero page. The raw and zero sizes are assumptions to confirm against the RTL layout.
- **Minimum saving threshold.** A page is compressed only if it saves at least X% of its eight chunks, otherwise it is stored raw (reason 5). X is the new `POLICY2` register (offset 0x64): bits 7:0 minimum saving percent, bit 8 cold algorithm (0 = LZSS, 1 = xz). A 25% threshold costs about 2% of the ratio and removes the decode on about 15% of pages.
- **xz cold tier.** xz can replace LZSS as the cold-page codec (software tier, later). The PTE gains a 1-bit algorithm flag in mode 3.
- **Where the learning block pays.** On the corpus the per-page size oracle equals xz-only, so learning earns its place through latency and hot-page prediction, not through size.
