# 6. Address translation and page metadata

[Back to the README](../README.md)

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
