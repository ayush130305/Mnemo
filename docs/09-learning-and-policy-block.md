# 9. Learning and policy block

[Back to the README](../README.md)

The learning block answers two questions for every region of memory: what should we do with it, and why did that happen. It never touches data and can never make a result wrong; at worst it picks a poor codec and costs capacity or speed.

**Regions.** A region is a group of pages with a common behaviour, identified by the page number divided by a configurable region size (default 4 pages, 24 regions in the demo). Hardware keeps one small record per region.

| Region record              | Bits  | Use                                              |
|----------------------------|-------|--------------------------------------------------|
| codec win counters         | 4 x 6 | How often each codec was the winner              |
| size histogram             | 4 x 4 | Lines that needed 16, 32, 48+ or exception slots |
| write rate, read rate      | 2 x 6 | Decaying access counters                         |
| overflow count             | 6     | Exceptions caused in this region recently        |
| last decision, last reason | 4 + 4 | For telemetry                                    |

**Decisions made (fast path, in hardware).**

1.  Codec prediction: the codec with the highest win counter, if its lead is above a margin.

2.  Slot size for a new page: the smallest slot that covered 90 percent of recent lines in the region (from the size histogram).

3.  Hotness: heat is bumped on access and decays by one every N accesses; below the cold threshold the page becomes a candidate for LZ.

4.  Exploration: with probability 1 in 32 the selector runs all codecs even when it has a prediction, so the counters keep learning (an epsilon-greedy policy).

**Reason codes.** Every decision stores one of a fixed set, so the system can explain itself.

| Code | Reason                            |
|------|-----------------------------------|
| 0    | Default (no history)              |
| 1    | Zero page                         |
| 2    | Predicted codec won               |
| 3    | Explored; another codec won       |
| 4    | Line overflowed its slot          |
| 5    | Page raw: compression did not pay |
| 6    | Cold; LZ compressed               |
| 7    | Pressure forced repack            |
| 8    | Hot; expanded to hot buffer       |
| 9    | Integrity check failed            |

**Telemetry.** A ring of 256 events (time, page, old state, new state, reason, sizes) readable through registers, plus counters for ratio, hits of the prediction, exceptions per region, repacks and LZ expansions. This is the data the slow brain learns from.

**Slow brain (software, later).** An RP2350 or the host reads the telemetry, trains a better model off line (for example a small decision tree or a table of per-region parameters) and writes new parameters into the policy registers: margins, thresholds, region size. Because only parameters change, the hardware stays small and the model can be replaced without new RTL.

**What the learning must beat.** The same traces run with a fixed policy (always the best static codec, fixed slot 32). Section 13 defines the comparison. If the learned policy does not win on real data, the block is simplified, not defended.
