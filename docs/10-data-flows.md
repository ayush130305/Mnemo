# 10. Data flows

[Back to the README](../README.md)

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
