# Policy study: fixed rule against per-page choice

Stored bytes with chunk rounding and 36 B metadata per 1 KB page, ratio = raw / stored. 'Oracle' picks the smallest option for every page with perfect knowledge, so it is an upper bound for any learned policy, not something hardware can do.


## All files

| Policy | Stored B | Ratio |
| --- | ---: | ---: |
| Line codecs only | 939388 | 1.52 |
| LZSS only | 649084 | 2.21 |
| xz only | 565244 | 2.53 |
| Hardware rule: line or LZSS per page | 649084 | 2.21 |
| Oracle per page: line, LZSS, xz or raw | 565244 | 2.53 |
| Oracle plus 4 KB cold xz blocks | 445820 | 3.21 |

## firmware

| Policy | Stored B | Ratio |
| --- | ---: | ---: |
| Line codecs only | 133064 | 0.94 |
| LZSS only | 88136 | 1.42 |
| xz only | 74824 | 1.67 |
| Hardware rule: line or LZSS per page | 88136 | 1.42 |
| Oracle per page: line, LZSS, xz or raw | 74824 | 1.67 |
| Oracle plus 4 KB cold xz blocks | 54984 | 2.27 |

## hex_text

| Policy | Stored B | Ratio |
| --- | ---: | ---: |
| Line codecs only | 328804 | 1.13 |
| LZSS only | 161892 | 2.29 |
| xz only | 134756 | 2.75 |
| Hardware rule: line or LZSS per page | 161892 | 2.29 |
| Oracle per page: line, LZSS, xz or raw | 134756 | 2.75 |
| Oracle plus 4 KB cold xz blocks | 87780 | 4.22 |

## ram_image

| Policy | Stored B | Ratio |
| --- | ---: | ---: |
| Line codecs only | 39680 | 11.56 |
| LZSS only | 34944 | 13.13 |
| xz only | 32384 | 14.17 |
| Hardware rule: line or LZSS per page | 34944 | 13.13 |
| Oracle per page: line, LZSS, xz or raw | 32384 | 14.17 |
| Oracle plus 4 KB cold xz blocks | 30848 | 14.87 |

## native

| Policy | Stored B | Ratio |
| --- | ---: | ---: |
| Line codecs only | 152640 | 0.97 |
| LZSS only | 132544 | 1.11 |
| xz only | 120640 | 1.22 |
| Hardware rule: line or LZSS per page | 132544 | 1.11 |
| Oracle per page: line, LZSS, xz or raw | 120640 | 1.22 |
| Oracle plus 4 KB cold xz blocks | 98496 | 1.50 |

## data_bin

| Policy | Stored B | Ratio |
| --- | ---: | ---: |
| Line codecs only | 161984 | 1.11 |
| LZSS only | 140352 | 1.28 |
| xz only | 121536 | 1.48 |
| Hardware rule: line or LZSS per page | 140352 | 1.28 |
| Oracle per page: line, LZSS, xz or raw | 121536 | 1.48 |
| Oracle plus 4 KB cold xz blocks | 104768 | 1.72 |

## data_text

| Policy | Stored B | Ratio |
| --- | ---: | ---: |
| Line codecs only | 88144 | 0.96 |
| LZSS only | 56144 | 1.51 |
| xz only | 46032 | 1.84 |
| Hardware rule: line or LZSS per page | 56144 | 1.51 |
| Oracle per page: line, LZSS, xz or raw | 46032 | 1.84 |
| Oracle plus 4 KB cold xz blocks | 33872 | 2.50 |

## control

| Policy | Stored B | Ratio |
| --- | ---: | ---: |
| Line codecs only | 35072 | 1.87 |
| LZSS only | 35072 | 1.87 |
| xz only | 35072 | 1.87 |
| Hardware rule: line or LZSS per page | 35072 | 1.87 |
| Oracle per page: line, LZSS, xz or raw | 35072 | 1.87 |
| Oracle plus 4 KB cold xz blocks | 35072 | 1.87 |

## Cost of keeping data hot (all files)

Hot pages must stay line-compressed so a single 64 B line can be read in about 20 cycles with no page decode. Cold pages use the smallest option (LZSS, xz page or 4 KB xz block). Mix assumes the hot pages are an average sample of the data.

| Hot share | Stored B | Ratio |
| ---: | ---: | ---: |
| 0% | 445820 | 3.21 |
| 10% | 495177 | 2.89 |
| 25% | 569212 | 2.51 |
| 50% | 692604 | 2.07 |
| 75% | 815996 | 1.75 |
| 100% | 939388 | 1.52 |

## Threshold layer: compress a page only if it saves at least X%

Best codec per page (line, LZSS or xz page); if the saving is below X% of the 1 KB page it is stored raw instead. Raw pages need no decode on read. Chunk granularity is 12.5%, so thresholds move in steps of one chunk.

| X (min saving) | Stored B | Ratio | Pages kept raw | Pages needing decode on read |
| ---: | ---: | ---: | ---: | ---: |
| 0% | 565244 | 2.53 | 0.0% | 100.0% |
| 12.5% | 565244 | 2.53 | 5.2% | 94.8% |
| 25% | 577276 | 2.48 | 15.0% | 85.0% |
| 37.5% | 616444 | 2.32 | 30.9% | 69.1% |
| 50% | 658684 | 2.17 | 42.3% | 57.7% |
| 62.5% | 728828 | 1.96 | 56.5% | 43.5% |
| 75% | 856188 | 1.67 | 77.2% | 22.8% |

## Metadata layout: one size for every page against a size per page type

Same best-codec choice per page; only the bookkeeping bytes differ. Raw and zero entry sizes in the light layout are assumptions to be checked against the real page table layout.

| Min saving | Today: 36 B for every page (B, ratio) | Light: 36 B compressed, 8 B raw, 2 B zero (B, ratio) |
| ---: | ---: | ---: |
| 0% | 565244 B, 2.53 | 548442 B, 2.61 |
| 25% | 577276 B, 2.48 | 557842 B, 2.57 |
| 37.5% | 616444 B, 2.32 | 592726 B, 2.42 |
| 50% | 658684 B, 2.17 | 631886 B, 2.27 |

Worst case, 32 KB of random data: 33920 B (3.5% over raw) and 33024 B (0.8% over raw).

## What the oracle picked (pages)

| Option | Pages | Share |
| --- | ---: | ---: |
| zero | 453 | 32.0% |
| line | 50 | 3.5% |
| lzss | 311 | 22.0% |
| xz | 601 | 42.5% |
| raw | 0 | 0.0% |
