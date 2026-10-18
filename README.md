# Mnemo: Architecture Spec v0.1

Oct 17, 2026 · @Ayush Jain

## 1. Goal and scope

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

## 2. Parameters and assumptions

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

## 3. System context and block diagram

<img src="media/image1.png" style="width:6in;height:3.53571in" alt="memory coprocessor · 8 blocks between processor and memory" />

memory coprocessor · 8 blocks between processor and memory

The processor sees an ordinary AXI4 memory. Inside, a request goes front end, translation, then the codec bank or page engine, with the allocator owning every physical chunk and the arbiter giving host accesses the memory port first. The learning block watches decisions and outcomes and steers codec, slot and hotness; it never sits on the data path itself. Section 4 describes each block, section 10 the flows.

## 4. Blocks and their responsibilities

Eight blocks, each with one job and one owner of state, so each can be simulated and tested alone.

| Block                   | Job                                                                                                | State it owns                                    |
|-------------------------|----------------------------------------------------------------------------------------------------|--------------------------------------------------|
| Front end               | Accepts processor reads and writes, splits bursts into lines, orders requests, inserts wait states | Request queue, line buffer                       |
| Translation unit        | Maps a virtual page to its chunks and finds a line's offset                                        | Page table (PTE) and its cache                   |
| Codec bank              | Compresses and decompresses a 64 byte line with zero, BDI, FPC or raw; reports the size            | Stateless apart from pipeline registers          |
| Codec selector          | Runs the codecs in parallel on a write and picks the winner, or follows the learned prediction     | Selector counters (from the learning block)      |
| Page engine             | LZ-compresses cold pages and expands them into the hot buffer (reuses the compengine LZSS core)    | Hot buffer (4 pages), LZ scratch RAM             |
| Allocator               | Hands out and takes back 128 byte chunks, handles exceptions, repacks pages, watches pressure      | Chunk bitmap and free count, exception lists     |
| Learning / policy block | Predicts codec, slot size and hotness per region; writes reason codes and telemetry                | Region table, predictor counters, telemetry ring |
| Control / status        | Register file, interrupts, debug access to the page table                                          | Registers                                        |

The memory-side port is shared by the translation unit (page table spill, later), the allocator and the data path; a small arbiter gives data reads priority over background work (repack, LZ compress).

## 5. Interfaces

Three interfaces: AXI4 toward the processor, a simple synchronous port toward the memory, and an AXI4-Lite port for control.

**Processor side (data window).** AXI4 slave, 32-bit data, INCR bursts up to 16 beats (one line). Virtual address range 0 to V_BYTES-1. Reads and writes may stall with ready low while a page is expanded or a chunk is allocated. A write that cannot be satisfied because the pool is exhausted returns SLVERR; reads never fail except on an integrity error (also SLVERR, flagged in a register).

**Control side.** AXI4-Lite slave, separate base address, 32-bit registers (section 11). One interrupt line, level, cleared by writing the status register.

**Memory side (native port).** Word-addressed, synchronous, one outstanding request in v0:

| Signal   | Direction | Meaning                                               |
|----------|-----------|-------------------------------------------------------|
| m_req    | out       | A request is valid                                    |
| m_we     | out       | 1 = write, 0 = read                                   |
| m_addr   | out       | Physical word address (chunk number and word offset)  |
| m_wdata  | out       | Write data, 32 bits                                   |
| m_wstrb  | out       | Byte enables                                          |
| m_ready  | in        | Request accepted this clock                           |
| m_rvalid | in        | Read data valid (fixed latency in v0, variable later) |
| m_rdata  | in        | Read data, 32 bits                                    |

The native port is wrapped later: a block-RAM model first, then a QSPI PSRAM controller or a DDR port. Only the wrapper changes.

## 6. Address translation and page metadata

Each 1 KB virtual page has one page table entry (PTE) of about 20 bytes; a line's physical address is computed from it with no search.

**Page modes** (2 bits): 0 = zero or unallocated (no chunks at all), 1 = raw (8 chunks, uncompressed), 2 = line-compressed (a fixed slot size per page, with exceptions), 3 = LZ cold page (one compressed stream, expanded on access).

| PTE field      | Bits    | Meaning                                                                         |
|----------------|---------|---------------------------------------------------------------------------------|
| mode           | 2       | Page mode above                                                                 |
| slot           | 2       | Line slot size in mode 2: 16, 32 or 64 bytes                                    |
| nchunks        | 4       | Chunks owned by the page (0 to 8)                                               |
| ptr\[0..7\]    | 8 x 9   | Chunk numbers (9 bits for the 512 chunk demo; log2 of the pool size in general) |
| codec\[0..15\] | 16 x 2  | Codec of each line: raw, zero, BDI, FPC                                         |
| exc\[0..15\]   | 16      | Line is stored in the exception area instead of its slot                        |
| lzlen          | 10      | Compressed length in mode 3                                                     |
| hot, dirty, hb | 1, 1, 2 | In the hot buffer, modified, hot buffer index                                   |
| heat           | 4       | Access heat (decays; used by the learning block)                                |

A side RAM holds an 8-bit CRC of the uncompressed text of each line (section 12).

**Finding a line (mode 2).** Let slot be 16, 32 or 64 bytes and lpc = 128 / slot lines per chunk. For line i of the page: if exc\[i\] is 0, the chunk index is i / lpc and the offset in the chunk is (i mod lpc) x slot. If exc\[i\] is 1, let j be the number of set exc bits below i; the line sits in the exception area, which starts after the regular chunks, at 64 byte entry j (two entries per chunk). The physical byte address is ptr\[chunk index\] x 128 + offset. Because slots divide the chunk size, no line ever straddles two chunks, so a line costs one memory access (two for a raw 64 byte line read as two bursts).

**Why not 48 byte slots.** Only two 48 byte slots fit in a 128 byte chunk, so a page would still need eight chunks and save nothing.

**Page grows past raw.** If a page would need more than 8 chunks (regular plus exceptions), it is converted to raw mode.

**Metadata storage.** In the demo the whole table is on-chip RAM: 96 pages x 20 bytes plus 1.5 KB of CRCs. For a larger memory the table lives in the memory itself and an on-chip cache (4-way, 64 entries, write-back) holds recent PTEs; a miss costs one memory read of 5 words and is counted in a register.

## 7. Compression engines and the codec selector

Two tiers. Line codecs sit on the access path and must finish in a few clocks. The page codec (LZ) is slower and only runs off the access path, on cold pages.

| Codec | Scope       | Idea                                                                                                     | Typical size of a 64 byte line | Latency (clocks)             |
|-------|-------------|----------------------------------------------------------------------------------------------------------|--------------------------------|------------------------------|
| zero  | line        | All bytes are 0                                                                                          | 0 bytes (flag only)            | 1                            |
| BDI   | line        | One 4 or 8 byte base plus small deltas (1, 2 or 4 bytes), with an implicit zero base                     | 16 to 40 bytes                 | 2                            |
| FPC   | line        | Each 32 bit word coded by a 3 bit pattern: zero, sign-extended 4/8/16 bit, repeated byte, half-word, raw | 16 to 56 bytes                 | 3                            |
| raw   | line        | Stored as is                                                                                             | 64 bytes                       | 1                            |
| LZ    | page (1 KB) | LZSS from compengine, window 512, 64 byte blocks with history carried                                    | 25 to 60 percent of the page   | 60 to 400 per page, off path |

**Slot rounding.** A compressed line is rounded up to the next slot size (16, 32 or 64) of its page. A line that needs more than the page's slot goes to the exception area.

**Selector.** On a write the selector runs zero, BDI and FPC in parallel, ignores any codec whose output does not fit the current slot (or the next smaller slot, if shrinking is allowed), and picks the smallest. Ties prefer the cheaper decode (zero, then BDI, then FPC, then raw). When the learning block holds a confident prediction for the region, the selector runs only the predicted codec and the raw fallback, saving power; a mispredict costs one extra pass.

**Decode path.** The PTE codec field names the codec, so a read runs exactly one decoder and never searches.

**Cold pages.** The page engine compresses a page with LZ when its heat reaches zero and the allocator wants space. The result must be at most 6 chunks (75 percent) to be worth keeping; otherwise the page stays in line mode. A read or write to a mode 3 page expands it into the hot buffer first (the first word arrives after the whole page is decoded in v0; a streaming restart is a later improvement).

**Losslessness rule.** Every encoder output is decoded and compared to the input in the simulator and in RTL simulation. The hardware has a debug mode that does the same check on every write and counts mismatches.

## 8. Allocator: chunk pool, exceptions, repack, pressure

**Pool.** The physical memory is cut into 128 byte chunks. A bitmap marks used chunks and a free list (a RAM of chunk numbers used as a stack) hands them out in one clock. Chunk 0 to 15 are the reserve.

**Allocate on write.** A write to an unallocated page starts it in mode 0 (zero). The first non-zero line makes it mode 2 with the slot the selector chose for that line, and the allocator gives the chunks that slot needs: 16 lines x slot / 128, that is 2, 4 or 8 chunks. Later writes that fit just rewrite their slot.

**Exceptions.** A line that no longer fits goes to the exception area (64 bytes each, two per chunk). If the page has no free exception entry, the allocator adds one chunk. If the page would then need more than 8 chunks, it becomes raw mode.

**Shrink and repack.** Pages are not repacked on every write. A background task walks the page table when the pool is under 25 percent free (or the host asks through a register), picks pages whose lines would all fit a smaller slot and rewrites them into fewer chunks, returning chunks to the free list. It yields to any host access.

**Pressure levels.** The free count is compared with three thresholds.

| Level    | Free chunks      | Action                                                                                           |
|----------|------------------|--------------------------------------------------------------------------------------------------|
| Normal   | above 25 percent | Nothing                                                                                          |
| Low      | 10 to 25 percent | Repack in background; compress cold pages with LZ; raise the status bit                          |
| Critical | below 10 percent | Interrupt the host; stop growing pages that are not hot; only writes that fit their slot proceed |
| Full     | reserve only     | New allocations return SLVERR; the reserve completes in-flight writes                            |

**Effective capacity register.** Reports free chunks x 128 plus an estimate of what the remaining pages would add, using the current average ratio. The host can use it for balloon-style decisions.

**Invariants** (checked in the simulator after every operation): every chunk is owned by exactly one page or is free; free count equals the bitmap population; a page's nchunks matches the chunks its mode and slot require; no two exception entries overlap.

**Atomicity.** A page changes mode in this order: allocate new chunks, write the data, update the PTE, free the old chunks. A reset in the middle leaves a consistent table plus at worst some leaked chunks that a startup scan reclaims.

## 9. Learning and policy block

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

## 10. Data flows

**Read of a line (common case).**

1.  Front end receives the AXI read burst and computes page = addr / 1024, line = (addr / 64) mod 16.

2.  Translation unit reads the PTE (1 clock from on-chip RAM; a cache miss adds a memory read in larger configurations).

3.  If the page is in the hot buffer, read the line from there and finish.

4.  If mode 0, return zeros without touching memory. If mode 2, compute chunk and offset and read the slot (1 to 4 words, depending on slot size).

5.  The codec named in the PTE decodes the line; the CRC is checked in debug or when enabled.

6.  Return 16 beats. Typical added latency is 4 to 6 clocks over a plain memory.

**Write of a line.**

1.  Front end collects the 16 beats into the line buffer (a partial line first reads and merges the old line).

2.  Selector compresses with the candidate codecs and picks one; the size is rounded to a slot.

3.  If it fits the page slot, write it in place and update codec\[i\] and the CRC.

4.  If it does not fit, the allocator reserves an exception entry (adding a chunk if needed), writes the line there, sets exc\[i\], and logs reason 4.

5.  If the page is in mode 0, the first non-zero write converts it to mode 2 (allocate, write, update PTE).

**Overflow to raw.** When a page would exceed 8 chunks, the page engine rewrites it as 8 raw chunks (mode 1) and logs reason 5. A later repack may bring it back.

**Cold page.** The page engine picks a page whose heat is zero, reads all its lines through the decoders, feeds them to the LZSS core, and writes the stream to fewer chunks if it fits in 6 or fewer. The old chunks are freed after the PTE is updated.

**Access to a cold page.** The page engine expands it into one of the 4 hot buffer slots (evicting the least recently used, writing it back if dirty), sets the hot bit, and the access continues from the hot buffer.

**Out of space.** A write that needs a chunk when only the reserve is left returns SLVERR and sets the full flag; reads and writes to existing slots continue. The interrupt fired earlier at the critical level so the host can free memory or wait for a repack.

**Arbitration.** Host accesses always win the memory port; repack, cold compression and expansion take free slots and are abortable between lines.

## 11. Register map

AXI4-Lite, 32-bit registers, offsets in bytes from the control base. R = read only, RW = read and write, W1C = write 1 to clear.

| Offset | Name         | Access | Meaning                                                                                                      |
|--------|--------------|--------|--------------------------------------------------------------------------------------------------------------|
| 0x00   | ID           | R      | Magic and version (0x4D435000 plus version)                                                                  |
| 0x04   | CTRL         | RW     | Bit 0 enable, bit 1 bypass (raw only), bit 2 debug check on write, bit 3 learning enable, bit 4 start repack |
| 0x08   | STATUS       | W1C    | Bit 0 low pressure, 1 critical, 2 full, 3 integrity error, 4 table error                                     |
| 0x0C   | IRQ_EN       | RW     | Interrupt enables, same bits as STATUS                                                                       |
| 0x10   | POOL_CHUNKS  | R      | Total chunks                                                                                                 |
| 0x14   | FREE_CHUNKS  | R      | Free chunks now                                                                                              |
| 0x18   | EFF_CAPACITY | R      | Estimated bytes still storable                                                                               |
| 0x1C   | RATIO        | R      | Current ratio, fixed point 8.8                                                                               |
| 0x20   | THRESH       | RW     | Low and critical thresholds in percent                                                                       |
| 0x24   | POLICY0      | RW     | Prediction margin, explore interval, cold threshold                                                          |
| 0x28   | POLICY1      | RW     | Region size, slot coverage percent                                                                           |
| 0x2C   | FORCE        | RW     | Force a codec for all writes (0 = learned)                                                                   |
| 0x30   | CNT_READ     | R      | Reads served                                                                                                 |
| 0x34   | CNT_WRITE    | R      | Writes served                                                                                                |
| 0x38   | CNT_EXC      | R      | Exceptions created                                                                                           |
| 0x3C   | CNT_REPACK   | R      | Pages repacked                                                                                               |
| 0x40   | CNT_LZ       | R      | LZ compressions and expansions                                                                               |
| 0x44   | CNT_PRED     | R      | Predictions made and correct (two halves)                                                                    |
| 0x48   | CNT_PTE_MISS | R      | Page table cache misses                                                                                      |
| 0x4C   | CNT_MISMATCH | R      | Debug check mismatches (must stay 0)                                                                         |
| 0x50   | TEL_HEAD     | R      | Telemetry write index                                                                                        |
| 0x54   | TEL_TAIL     | RW     | Telemetry read index                                                                                         |
| 0x58   | TEL_DATA     | R      | Next 32-bit word of the event at the tail                                                                    |
| 0x5C   | PT_ADDR      | RW     | Debug: page number to inspect                                                                                |
| 0x60   | PT_DATA      | R      | Debug: PTE word, auto-increments                                                                             |

The simulator exposes the same names so one test script drives both.

## 12. Integrity, safety, security

**Correctness first.** Lossless means a read returns exactly the last bytes written. Three layers back this.

1.  Each codec has a decode-after-encode proof in simulation, and a debug mode in hardware that decodes every write and compares.

2.  An 8-bit CRC of the uncompressed line is stored per line and checked on read when enabled. A mismatch sets the integrity flag, returns SLVERR and logs reason 9.

3.  The simulator checks the allocator invariants (section 8) after every operation.

**Fail safe.** Bypass mode (CTRL bit 1) stores everything raw in a fixed layout, so a suspect policy or codec can be taken out of the loop without losing the translation. A reset clears pressure state but not the data; a startup scan rebuilds the free list from the page table.

**Metadata is critical.** A flipped bit in a PTE loses a whole page. In the demo the table is block RAM. In larger configurations the table needs ECC (SECDED) and a copy of the free bitmap; this is listed under open questions.

**Existing memory.** When placed in front of a memory that already holds data, the coprocessor starts in bypass (identity map). A background migration then converts pages one by one, with the host paused only for the page being moved. This is how the in-use chip case is handled.

**Side channels.** Compressed size and latency leak information about data (as in compression-based attacks). v0.1 does not defend against this. A mode that pads every access to a fixed latency and a per-domain disable are noted as future work.

**Not provided.** Encryption, authentication of the processor, and ECC of user data are out of scope; ECC in the memory chip, if any, keeps working because the coprocessor stores whole words.

## 13. Verification plan and metrics

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

## 14. Build plan and boards

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

## 15. Open questions and prior art

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


## 16. Changes since v0.1 (simulator findings)

These are implemented in `simulator/mnemo_model.py` and still to be merged into the sections above.

- **Light page table entry.** The entry size depends on the mode: about 36 B for a compressed page (mode 2 or 3), about 8 B for a raw page, 2 B for a zero page. The raw and zero sizes are assumptions to confirm against the RTL layout.
- **Minimum saving threshold.** A page is compressed only if it saves at least X% of its eight chunks, otherwise it is stored raw (reason 5). X is the new `POLICY2` register (offset 0x64): bits 7:0 minimum saving percent, bit 8 cold algorithm (0 = LZSS, 1 = xz). A 25% threshold costs about 2% of the ratio and removes the decode on about 15% of pages.
- **xz cold tier.** xz can replace LZSS as the cold-page codec (software tier, later). The PTE gains a 1-bit algorithm flag in mode 3.
- **Where the learning block pays.** On the corpus the per-page size oracle equals xz-only, so learning earns its place through latency and hot-page prediction, not through size.

## 17. Repository layout

| Folder | Content |
| --- | --- |
| `showcase/` | What we did: this spec as a Word file, results, feature list |
| `test_files/` | Test corpus (firmware, native code, data, controls) |
| `c_files/` | C sources and linker script for the firmware in the corpus |
| `python_files/` | Codecs, corpus builder, comparator, policy and block-size studies |
| `simulator/` | Page simulator, visual simulator, full coprocessor model and its tests |
| `rtl/` | Verilog and the RTL simulation runner |

How to run everything: see `RUN.md`.
