# 12. Integrity, safety, security

[Back to the README](../README.md)

**Correctness first.** Lossless means a read returns exactly the last bytes written. Three layers back this.

1.  Each codec has a decode-after-encode proof in simulation, and a debug mode in hardware that decodes every write and compares.

2.  An 8-bit CRC of the uncompressed line is stored per line and checked on read when enabled. A mismatch sets the integrity flag, returns SLVERR and logs reason 9.

3.  The simulator checks the allocator invariants (section 8) after every operation.

**Fail safe.** Bypass mode (CTRL bit 1) stores everything raw in a fixed layout, so a suspect policy or codec can be taken out of the loop without losing the translation. A reset clears pressure state but not the data; a startup scan rebuilds the free list from the page table.

**Metadata is critical.** A flipped bit in a PTE loses a whole page. In the demo the table is block RAM. In larger configurations the table needs ECC (SECDED) and a copy of the free bitmap; this is listed under open questions.

**Existing memory.** When placed in front of a memory that already holds data, the coprocessor starts in bypass (identity map). A background migration then converts pages one by one, with the host paused only for the page being moved. This is how the in-use chip case is handled.

**Side channels.** Compressed size and latency leak information about data (as in compression-based attacks). v0.1 does not defend against this. A mode that pads every access to a fixed latency and a per-domain disable are noted as future work.

**Not provided.** Encryption, authentication of the processor, and ECC of user data are out of scope; ECC in the memory chip, if any, keeps working because the coprocessor stores whole words.
