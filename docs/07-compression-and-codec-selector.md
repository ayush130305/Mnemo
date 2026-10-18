# 7. Compression engines and the codec selector

[Back to the README](../README.md)

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
