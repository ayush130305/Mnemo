# 1. Goal and scope

[Back to the README](../README.md)

The coprocessor sits between a processor and its memory, stores data compressed and losslessly, and manages the physical memory itself, so the processor sees an ordinary memory.

**It does:**

- Compress on write and decompress on read, with no data loss, for any memory it is placed in front of.

- Allocate physical memory dynamically to every block, in variable sizes, as compressibility changes.

- Choose among several codecs per block and fall back to raw storage when compression does not pay.

- Learn which codec, slot size and placement work for each region, and record why (reason codes and telemetry).

- Report how much capacity is really free, and signal the host before the physical memory runs out.

**It does not (v0.1):**

- It does not change the processor or the memory chip. It must be in the data path, as a bridge or as the memory controller.

- It does not promise a fixed larger memory. It exposes an effective-capacity register and pressure signals instead.

- It does not provide encryption, ECC replacement or cache coherence.

**Success means:** byte-exact reads of everything written (always), a measured compression ratio above 1.3 on mixed workloads, an average added read latency under 6 clocks for line-level data, and a learned policy that beats a fixed one on the same traces.
