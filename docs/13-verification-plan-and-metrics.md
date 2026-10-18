# 13. Verification plan and metrics

[Back to the README](../README.md)

**Levels.**

| Level        | What                                               | Pass criterion                                       |
|--------------|----------------------------------------------------|------------------------------------------------------|
| Unit         | Each codec: random, structured and edge lines      | Decode(encode(x)) = x for 1 million lines each       |
| Allocator    | Random alloc, free, grow, shrink sequences         | Invariants hold after every step                     |
| System model | Python simulator with a shadow memory              | Every read equals the shadow, for all traces         |
| RTL          | Same traces replayed through the Verilog testbench | Read data identical to the Python model, bit for bit |
| Board        | Basys 3 with block RAM as memory                   | Same traces from a UART host, mismatch counter 0     |

**Workloads for traces.**

- Synthetic: zero pages, small integers, pointers (array of nearby addresses), floats, text, random (incompressible), mixes with phase changes.

- Real: memory dumps of running programs on a PC (heap, stack, code, data), an RP2350 SRAM dump, sensor logs like fakeimu from compengine, a small Linux or MicroPython image.

- Access patterns: sequential, strided, random, hot-cold (80/20), and phase shifting.

**Metrics.**

- Compression ratio overall and per codec and per workload.

- Effective capacity gained at a given physical size.

- Read and write latency in clocks (average, 99th percentile); extra memory accesses per host access.

- Exceptions per 1000 writes, repack traffic, LZ expansions per 1000 reads.

- Learning: prediction accuracy, ratio of learned policy against the best fixed policy and against an oracle that always picks the best codec, and regret over time.

- Cost: LUTs, block RAM, power estimate, fmax.

**Success gates for the simulator milestone.** Zero mismatches on all traces; mean ratio above 1.3 on the real mix; learned policy within 5 percent of the oracle and above the best static policy on at least the phase-shifting workloads.
