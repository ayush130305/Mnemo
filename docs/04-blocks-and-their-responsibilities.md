# 4. Blocks and their responsibilities

[Back to the README](../README.md)

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
