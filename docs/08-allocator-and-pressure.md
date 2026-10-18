# 8. Allocator: chunk pool, exceptions, repack, pressure

[Back to the README](../README.md)

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
