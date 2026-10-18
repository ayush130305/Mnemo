# Compression algorithm comparison

Corpus: 57 files, 1431470 bytes. All codecs verified lossless (decode equals input on every line, page and file).

Packed = ideal bitstream. Stored+meta = bytes the memory would really use: per-page slot model, 128 B chunks, plus 36 B page metadata. File-level candidates have no memory layout, so stored = packed.


### All files

| Candidate | Raw B | Packed B | Ratio packed | Stored+meta B | Ratio stored |
| --- | ---: | ---: | ---: | ---: | ---: |
| Zero+Raw | 1431470 | 964700 | 1.48 | 1023100 | 1.40 |
| BDI+Raw | 1431470 | 869366 | 1.65 | 964092 | 1.48 |
| FPC+Raw | 1431470 | 918458 | 1.56 | 998012 | 1.43 |
| Line-best | 1431470 | 848459 | 1.69 | 939388 | 1.52 |
| LZSS-page | 1431470 | 545863 | 2.62 | 649084 | 2.21 |
| LZSS-file | 1431470 | 561609 | 2.55 | 561609 | 2.55 |
| Zlib-1K | 1431470 | 459882 | 3.11 | 556232 | 2.57 |
| XZ-1K | 1431470 | 456546 | 3.14 | 548936 | 2.61 |
| Zlib-4K | 1431470 | 402872 | 3.55 | 429892 | 3.33 |
| XZ-4K | 1431470 | 379298 | 3.77 | 405188 | 3.53 |
| zlib-file | 1431470 | 365679 | 3.91 | 365679 | 3.91 |
| xz-file | 1431470 | 318660 | 4.49 | 318660 | 4.49 |
| bz2-file | 1431470 | 348671 | 4.11 | 348671 | 4.11 |

### Kind: firmware

| Candidate | Raw B | Packed B | Ratio packed | Stored+meta B | Ratio stored |
| --- | ---: | ---: | ---: | ---: | ---: |
| Zero+Raw | 124724 | 123912 | 1.01 | 133192 | 0.94 |
| BDI+Raw | 124724 | 123220 | 1.01 | 133064 | 0.94 |
| FPC+Raw | 124724 | 119782 | 1.04 | 133192 | 0.94 |
| Line-best | 124724 | 119694 | 1.04 | 133064 | 0.94 |
| LZSS-page | 124724 | 76020 | 1.64 | 88136 | 1.42 |
| LZSS-file | 124724 | 69691 | 1.79 | 69691 | 1.79 |
| Zlib-1K | 124724 | 65946 | 1.89 | 79560 | 1.57 |
| XZ-1K | 124724 | 62508 | 2.00 | 74824 | 1.67 |
| Zlib-4K | 124724 | 53280 | 2.34 | 57576 | 2.17 |
| XZ-4K | 124724 | 47839 | 2.61 | 52200 | 2.39 |
| zlib-file | 124724 | 46789 | 2.67 | 46789 | 2.67 |
| xz-file | 124724 | 38636 | 3.23 | 38636 | 3.23 |
| bz2-file | 124724 | 47803 | 2.61 | 47803 | 2.61 |

### Kind: hex_text

| Candidate | Raw B | Packed B | Ratio packed | Stored+meta B | Ratio stored |
| --- | ---: | ---: | ---: | ---: | ---: |
| Zero+Raw | 370245 | 372292 | 0.99 | 387684 | 0.96 |
| BDI+Raw | 370245 | 303966 | 1.22 | 329188 | 1.12 |
| FPC+Raw | 370245 | 369790 | 1.00 | 387300 | 0.96 |
| Line-best | 370245 | 301650 | 1.23 | 328804 | 1.13 |
| LZSS-page | 370245 | 126923 | 2.92 | 161892 | 2.29 |
| LZSS-file | 370245 | 110035 | 3.36 | 110035 | 3.36 |
| Zlib-1K | 370245 | 88384 | 4.19 | 131044 | 2.83 |
| XZ-1K | 370245 | 94267 | 3.93 | 134756 | 2.75 |
| Zlib-4K | 370245 | 71773 | 5.16 | 82596 | 4.48 |
| XZ-4K | 370245 | 68543 | 5.40 | 77988 | 4.75 |
| zlib-file | 370245 | 58832 | 6.29 | 58832 | 6.29 |
| xz-file | 370245 | 47636 | 7.77 | 47636 | 7.77 |
| bz2-file | 370245 | 54751 | 6.76 | 54751 | 6.76 |

### Kind: ram_image

| Candidate | Raw B | Packed B | Ratio packed | Stored+meta B | Ratio stored |
| --- | ---: | ---: | ---: | ---: | ---: |
| Zero+Raw | 458752 | 21568 | 21.27 | 39680 | 11.56 |
| BDI+Raw | 458752 | 21322 | 21.52 | 39680 | 11.56 |
| FPC+Raw | 458752 | 20724 | 22.14 | 39680 | 11.56 |
| Line-best | 458752 | 20722 | 22.14 | 39680 | 11.56 |
| LZSS-page | 458752 | 17389 | 26.38 | 34944 | 13.13 |
| LZSS-file | 458752 | 58893 | 7.79 | 58893 | 7.79 |
| Zlib-1K | 458752 | 14630 | 31.36 | 17612 | 26.05 |
| XZ-1K | 458752 | 14491 | 31.66 | 17228 | 26.63 |
| Zlib-4K | 458752 | 14310 | 32.06 | 16064 | 28.56 |
| XZ-4K | 458752 | 13874 | 33.07 | 15552 | 29.50 |
| zlib-file | 458752 | 15378 | 29.83 | 15378 | 29.83 |
| xz-file | 458752 | 15212 | 30.16 | 15212 | 30.16 |
| bz2-file | 458752 | 16541 | 27.73 | 16541 | 27.73 |

### Kind: native

| Candidate | Raw B | Packed B | Ratio packed | Stored+meta B | Ratio stored |
| --- | ---: | ---: | ---: | ---: | ---: |
| Zero+Raw | 147456 | 148032 | 1.00 | 152640 | 0.97 |
| BDI+Raw | 147456 | 148032 | 1.00 | 152640 | 0.97 |
| FPC+Raw | 147456 | 146375 | 1.01 | 152640 | 0.97 |
| Line-best | 147456 | 146375 | 1.01 | 152640 | 0.97 |
| LZSS-page | 147456 | 118523 | 1.24 | 132544 | 1.11 |
| LZSS-file | 147456 | 111545 | 1.32 | 111545 | 1.32 |
| Zlib-1K | 147456 | 107624 | 1.37 | 121024 | 1.22 |
| XZ-1K | 147456 | 107717 | 1.37 | 120640 | 1.22 |
| Zlib-4K | 147456 | 93152 | 1.58 | 96784 | 1.52 |
| XZ-4K | 147456 | 90893 | 1.62 | 94608 | 1.56 |
| zlib-file | 147456 | 83488 | 1.77 | 83488 | 1.77 |
| xz-file | 147456 | 77012 | 1.91 | 77012 | 1.91 |
| bz2-file | 147456 | 80255 | 1.84 | 80255 | 1.84 |

### Kind: data_bin

| Candidate | Raw B | Packed B | Ratio packed | Stored+meta B | Ratio stored |
| --- | ---: | ---: | ---: | ---: | ---: |
| Zero+Raw | 180224 | 180928 | 1.00 | 186560 | 0.97 |
| BDI+Raw | 180224 | 154896 | 1.16 | 186176 | 0.97 |
| FPC+Raw | 180224 | 143972 | 1.25 | 161984 | 1.11 |
| Line-best | 180224 | 142203 | 1.27 | 161984 | 1.11 |
| LZSS-page | 180224 | 127654 | 1.41 | 140352 | 1.28 |
| LZSS-file | 180224 | 130349 | 1.38 | 130349 | 1.38 |
| Zlib-1K | 180224 | 115371 | 1.56 | 129728 | 1.39 |
| XZ-1K | 180224 | 107503 | 1.68 | 121536 | 1.48 |
| Zlib-4K | 180224 | 107068 | 1.68 | 111280 | 1.62 |
| XZ-4K | 180224 | 96231 | 1.87 | 100144 | 1.80 |
| zlib-file | 180224 | 102165 | 1.76 | 102165 | 1.76 |
| xz-file | 180224 | 85128 | 2.12 | 85128 | 2.12 |
| bz2-file | 180224 | 93631 | 1.92 | 93631 | 1.92 |

### Kind: data_text

| Candidate | Raw B | Packed B | Ratio packed | Stored+meta B | Ratio stored |
| --- | ---: | ---: | ---: | ---: | ---: |
| Zero+Raw | 84533 | 84944 | 1.00 | 88272 | 0.96 |
| BDI+Raw | 84533 | 84906 | 1.00 | 88272 | 0.96 |
| FPC+Raw | 84533 | 84791 | 1.00 | 88144 | 0.96 |
| Line-best | 84533 | 84791 | 1.00 | 88144 | 0.96 |
| LZSS-page | 84533 | 46586 | 1.81 | 56144 | 1.51 |
| LZSS-file | 84533 | 41047 | 2.06 | 41047 | 2.06 |
| Zlib-1K | 84533 | 35159 | 2.40 | 43344 | 1.95 |
| XZ-1K | 84533 | 37292 | 2.27 | 46032 | 1.84 |
| Zlib-4K | 84533 | 30521 | 2.77 | 32536 | 2.60 |
| XZ-4K | 84533 | 29150 | 2.90 | 31640 | 2.67 |
| zlib-file | 84533 | 26191 | 3.23 | 26191 | 3.23 |
| xz-file | 84533 | 22076 | 3.83 | 22076 | 3.83 |
| bz2-file | 84533 | 22377 | 3.78 | 22377 | 3.78 |

### Kind: control

| Candidate | Raw B | Packed B | Ratio packed | Stored+meta B | Ratio stored |
| --- | ---: | ---: | ---: | ---: | ---: |
| Zero+Raw | 65536 | 33024 | 1.98 | 35072 | 1.87 |
| BDI+Raw | 65536 | 33024 | 1.98 | 35072 | 1.87 |
| FPC+Raw | 65536 | 33024 | 1.98 | 35072 | 1.87 |
| Line-best | 65536 | 33024 | 1.98 | 35072 | 1.87 |
| LZSS-page | 65536 | 32768 | 2.00 | 35072 | 1.87 |
| LZSS-file | 65536 | 40049 | 1.64 | 40049 | 1.64 |
| Zlib-1K | 65536 | 32768 | 2.00 | 33920 | 1.93 |
| XZ-1K | 65536 | 32768 | 2.00 | 33920 | 1.93 |
| Zlib-4K | 65536 | 32768 | 2.00 | 33056 | 1.98 |
| XZ-4K | 65536 | 32768 | 2.00 | 33056 | 1.98 |
| zlib-file | 65536 | 32836 | 2.00 | 32836 | 2.00 |
| xz-file | 65536 | 32960 | 1.99 | 32960 | 1.99 |
| bz2-file | 65536 | 33313 | 1.97 | 33313 | 1.97 |

## Ranking (size first, then speed)

Sizes within 1.0% count as a tie and are ordered by engine compute time. Compute time is the FPGA clock cycle model, not the link.

### A. Memory resident data (random access: lines and pages)

Size = bytes the memory really uses (slot model, 128 B chunks, page metadata).

| Rank | Candidate | Size B | Ratio | Compute s (compress) | Compute s (decompress) |
| ---: | --- | ---: | ---: | ---: | ---: |
| 1 | LZSS-page | 649084 | 2.21 | 4.58 | 0.09 |
| 2 | Line-best | 939388 | 1.52 | 0.02 | 0.02 |
| 3 | BDI+Raw | 964092 | 1.48 | 0.02 | 0.02 |
| 4 | FPC+Raw | 998012 | 1.43 | 0.02 | 0.02 |
| 5 | Zero+Raw | 1023100 | 1.40 | 0.02 | 0.02 |

### A2. Same, plus software block codecs (need a CPU, no hardware cycle model)

Zlib and XZ run per block with a real decode check. 4K blocks mean reading one line decodes 4 KB, so they suit cold data only. Compute time is n/a.

| Rank | Candidate | Size B | Ratio | Compute s (compress) | Compute s (decompress) |
| ---: | --- | ---: | ---: | ---: | ---: |
| 1 | XZ-4K | 405188 | 3.53 | n/a | n/a |
| 2 | Zlib-4K | 429892 | 3.33 | n/a | n/a |
| 3 | XZ-1K | 548936 | 2.61 | n/a | n/a |
| 4 | Zlib-1K | 556232 | 2.57 | n/a | n/a |
| 5 | LZSS-page | 649084 | 2.21 | 4.58 | 0.09 |
| 6 | Line-best | 939388 | 1.52 | 0.02 | 0.02 |
| 7 | BDI+Raw | 964092 | 1.48 | 0.02 | 0.02 |
| 8 | FPC+Raw | 998012 | 1.43 | 0.02 | 0.02 |
| 9 | Zero+Raw | 1023100 | 1.40 | 0.02 | 0.02 |

### B. Whole images and files (boot image, flash, host link): no random access needed

Size = packed bitstream. zlib, xz and bzip2 are software references that show how much is left on the table; they are not hardware candidates.

| Rank | Candidate | Size B | Ratio | Compute s (compress) | Compute s (decompress) |
| ---: | --- | ---: | ---: | ---: | ---: |
| 1 | xz-file | 318660 | 4.49 | n/a | n/a |
| 2 | bz2-file | 348671 | 4.11 | n/a | n/a |
| 3 | zlib-file | 365679 | 3.91 | n/a | n/a |
| 4 | LZSS-page | 545863 | 2.62 | 4.58 | 0.09 |
| 5 | LZSS-file | 561609 | 2.55 | 4.47 | 0.09 |

## Time against baud rate

Model: 8N1 serial (10 bits per byte), FPGA clock 25 MHz. All numbers are seconds for the whole corpus. Cycle costs are assumptions (last section); calibrate them from the RTL simulation.

### Where the engine, not the link, becomes the limit

Link bound while baud is below the value shown; above it the engine compute time decides. Raw bytes go in for compress, and raw bytes come out for decompress.

| Candidate | Compress compute s | Compress limited above (baud) | Decompress compute s | Decompress limited above (baud) |
| --- | ---: | ---: | ---: | ---: |
| Zero+Raw | 0.02 | 790,343,419 | 0.02 | 831,940,441 |
| BDI+Raw | 0.02 | 790,343,419 | 0.02 | 831,940,441 |
| FPC+Raw | 0.02 | 790,343,419 | 0.02 | 831,940,441 |
| Line-best | 0.02 | 790,343,419 | 0.02 | 831,940,441 |
| LZSS-page | 4.58 | 3,124,300 | 0.09 | 155,200,087 |
| LZSS-file | 4.47 | 3,203,736 | 0.09 | 156,673,158 |

### Loading a compressed image (send packed bytes, decompress inside the FPGA)

This is the case where compression speeds the link up: only packed bytes cross the wire. Time = slowest of link and decompress engine. First row is sending the raw bytes.

| Candidate | 115200 | 230400 | 460800 | 921600 | 1000000 | 2000000 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| raw, no compression | 124.3 | 62.1 | 31.1 | 15.5 | 14.3 | 7.2 |
| Zero+Raw | 83.74 | 41.87 | 20.94 | 10.47 | 9.65 | 4.82 |
| BDI+Raw | 75.47 | 37.73 | 18.87 | 9.43 | 8.69 | 4.35 |
| FPC+Raw | 79.73 | 39.86 | 19.93 | 9.97 | 9.18 | 4.59 |
| Line-best | 73.65 | 36.83 | 18.41 | 9.21 | 8.48 | 4.24 |
| LZSS-page | 47.38 | 23.69 | 11.85 | 5.92 | 5.46 | 2.73 |
| LZSS-file | 48.75 | 24.38 | 12.19 | 6.09 | 5.62 | 2.81 |

### Test-bench mode like compengine (raw in, packed out; or packed in, raw out)

The raw side always crosses the link, so time is almost the same for every codec and equals the raw link time until the engine becomes the limit.

| Candidate (compress) | 115200 | 230400 | 460800 | 921600 | 1000000 | 2000000 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Zero+Raw | 124.26 | 62.13 | 31.06 | 15.53 | 14.31 | 7.16 |
| BDI+Raw | 124.26 | 62.13 | 31.06 | 15.53 | 14.31 | 7.16 |
| FPC+Raw | 124.26 | 62.13 | 31.06 | 15.53 | 14.31 | 7.16 |
| Line-best | 124.26 | 62.13 | 31.06 | 15.53 | 14.31 | 7.16 |
| LZSS-page | 124.26 | 62.13 | 31.06 | 15.53 | 14.31 | 7.16 |
| LZSS-file | 124.26 | 62.13 | 31.06 | 15.53 | 14.31 | 7.16 |

## Assumptions in the time model

- Line codecs: 16 cycles to move a 64 B line over a 32 bit path plus 4 (compress) or 3 (decompress) codec cycles. Spec latencies, not measured.
- LZSS compress: tokens x (512/2 lanes + 6) cycles, from the compengine search structure (one compare per lane per clock). Decompress: 2 cycles per token + 1 per output byte.
- Python wall time is not hardware time and is not used for ranking.
- The UART link is the test harness path (PC to FPGA). In the real memory path the codec sits on the bus and only the cycle model matters.