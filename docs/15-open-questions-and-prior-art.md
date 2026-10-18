# 15. Open questions and prior art

[Back to the README](../README.md)

**Open questions.**

1.  Where does it sit in the target system: a bridge on a bus (AXI), the memory controller itself, or a CXL-style device? This decides the memory-side wrapper and how translation is exposed to the host.

2.  Does the host cooperate (knows about the capacity register) or must the coprocessor be fully transparent? Transparent hardware needs a bigger reserve and may have to stall the host.

3.  What is the real target memory (SRAM, PSRAM, DDR)? Burst length and latency change the best line and chunk sizes.

4.  How much of the page table can stay on chip, and is ECC for metadata needed?

5.  Should the learning block be online only (counters), or also adapt parameters in hardware without the slow brain?

6.  What counts as a good result for the internship: ratio on real dumps, the learned policy gain, or a working board demo?

7.  Slot size 48 bytes was in the parameter table but is not useful with 128 byte chunks (section 6); the simulator will test 16, 32, 64 and a 24-byte-granular variant before this is fixed.

**Prior art to read and compare against.**

- IBM MXT (Memory Expansion Technology): hardware main memory compression with 256 byte sectors and a shared LZ engine; the origin of the pool and translation design.

- LCP (Linearly Compressed Pages, Pekhimenko et al.): fixed slot size per page plus exceptions; our offset computation.

- BDI (Base-Delta-Immediate) and FPC (Frequent Pattern Compression): low-latency line codecs.

- Compresso (Choukse et al.): reduces data movement caused by compression, metadata cache design.

- Zswap/zram in Linux: software analogue of cold page compression, useful for real page traces.

The point of this project against them is the learned, explainable policy and an open, board-level implementation, not a new codec.
