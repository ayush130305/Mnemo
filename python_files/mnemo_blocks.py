import sys, os as _os; _H = _os.path.dirname(_os.path.abspath(__file__)); sys.path[:0] = [_os.path.join(_H, "..", "python_files"), _os.path.join(_H, "..", "simulator")]  # Lets the scripts import each other across folders
#!/usr/bin/env python3
"""Mnemo block-size study: how much a software cold tier (zlib, xz) gains from bigger blocks than 1 KB pages."""
import os, sys, lzma, zlib, math                                   # This holds the standard library imports
import mnemo_codecs as C                                           # This holds the Mnemo codecs

CORPUS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "test_files")   # This holds the corpus folder
FILES = sys.argv[1:] or ["pico_fw_rv32imc.bin", "pico_fw_rv32imc.hex", "data_imu.csv", "data_pointers.bin", "data_text.txt"]  # Files to study
BLOCKS = [1024, 4096, 8192]                                        # Block sizes in bytes


def chunks(n):
    """Rounds a byte count up to whole 128 B chunks."""
    return math.ceil(n / C.CHUNK) * C.CHUNK


def xz_block(b):
    """Size of one block as a raw LZMA2 stream (no container header)."""
    return len(lzma.compress(b, format=lzma.FORMAT_RAW, filters=[{"id": lzma.FILTER_LZMA2, "preset": 9}]))


def total(data, block, fn):
    """Sum of chunk-rounded stored sizes over all blocks, never larger than the raw block."""
    return sum(min(chunks(fn(data[i:i + block])), chunks(len(data[i:i + block]))) for i in range(0, len(data), block))


print(f"{'file':26}{'raw':>8}  " + "  ".join(f"{n}@{b//1024}K".rjust(10) for b in BLOCKS for n in ("lzss", "zlib", "xz") if not (n == "lzss" and b > 1024)))
for f in FILES:
    d = open(os.path.join(CORPUS, f), "rb").read()
    cols = []
    for b in BLOCKS:
        if b == 1024:
            cols.append(f"{d and len(d)/total(d, b, lambda x: len(C.lzss_encode(x)[0])):.2f}x")  # LZSS only at the page size
        cols.append(f"{len(d)/total(d, b, lambda x: len(zlib.compress(x, 9))):.2f}x")
        cols.append(f"{len(d)/total(d, b, xz_block):.2f}x")
    print(f"{f:26}{len(d):>8}  " + "  ".join(c.rjust(10) for c in cols))
