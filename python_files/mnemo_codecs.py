import sys, os as _os; _H = _os.path.dirname(_os.path.abspath(__file__)); sys.path[:0] = [_os.path.join(_H, "..", "python_files"), _os.path.join(_H, "..", "simulator")]  # Lets the scripts import each other across folders
#!/usr/bin/env python3
"""Reference models of every compression candidate. Each codec is a real bitstream with a decoder,
so the size is exact and round-trip is checked, not estimated.

Line codecs work on one 64 byte line:    encode_x(line) -> (nbits, payload_bits_as_int) or None
Page codec (LZSS) works on a byte string: lzss_encode(data) -> (bytes, ntokens)
"""
import struct, zlib, lzma, bz2

LINE = 64            # This holds the line size in bytes
PAGE = 1024          # This holds the page size in bytes
CHUNK = 128          # This holds the physical allocation unit in bytes
SLOTS = (16, 32, 64) # This holds the allowed per-page line slot sizes in bytes


# ---------------------------------------------------------------- bit I/O
class BitWriter:
    """Collects variable width fields MSB first and pads to bytes at the end."""

    def __init__(self):
        self.v = 0  # This holds all bits written so far as one integer
        self.n = 0  # This holds how many bits are in v

    def put(self, value, nbits):
        """Appends the low nbits of value."""
        self.v = (self.v << nbits) | (value & ((1 << nbits) - 1))  # Shift old bits up and add the new field
        self.n += nbits                                            # Count the new bits

    def to_bytes(self):
        """Returns the stream padded with zero bits to a whole number of bytes."""
        pad = (-self.n) % 8                                        # Number of padding bits needed
        return (self.v << pad).to_bytes((self.n + pad) // 8, "big")  # Align to the top and convert


class BitReader:
    """Reads fields written by BitWriter."""

    def __init__(self, data):
        self.v = int.from_bytes(data, "big")  # This holds the stream as one integer
        self.n = len(data) * 8                # This holds the total bit count
        self.pos = 0                          # This holds the next bit to read

    def left(self):
        """Returns how many bits remain."""
        return self.n - self.pos

    def get(self, nbits):
        """Reads the next nbits as an unsigned integer."""
        shift = self.n - self.pos - nbits                   # Position of the field from the right
        self.pos += nbits                                   # Advance the cursor
        return (self.v >> shift) & ((1 << nbits) - 1)       # Cut the field out


def sgn(x, bits):
    """Interprets the low bits of x as a signed number."""
    x &= (1 << bits) - 1                                    # Keep only the field
    return x - (1 << bits) if x >> (bits - 1) else x        # Apply the sign


def fits(v, bits):
    """True when signed value v fits in the given number of bits."""
    return -(1 << (bits - 1)) <= v < (1 << (bits - 1))


# ---------------------------------------------------------------- line codecs
def payload_reader(bits, n):
    """Wraps an n bit payload integer in a BitReader."""
    pad = (-n) % 8                                           # Padding bits to reach a whole byte
    return BitReader((bits << pad).to_bytes((n + pad) // 8, "big") if n else b"")  # Align and convert


def zero_encode(line):
    """Zero codec: a line of all zero bytes costs no payload."""
    return (0, 0) if not any(line) else None  # Zero bits when every byte is zero


def zero_decode(bits, n):
    """Zero decoder: returns a line of zeros."""
    return bytes(LINE)


BDI_CFG = ((8, 1), (8, 2), (8, 4), (4, 1), (4, 2), (2, 1))  # This holds the (base bytes, delta bytes) configurations


def bdi_encode(line):
    """BDI codec: one base plus small deltas, with an implicit zero base chosen per word by a mask bit."""
    best = None  # This holds the smallest encoding found
    # Repeated 8 byte value: tag 0 then the value.
    w8 = struct.unpack("<8Q", line)                       # View the line as eight 64 bit words
    if all(w == w8[0] for w in w8):                       # All words equal
        best = (3 + 64, (0 << 64) | w8[0])                # Tag 0 plus the repeated word
    for ci, (bb, db) in enumerate(BDI_CFG):               # Try every base/delta configuration
        bits = bb * 8                                     # Word width in bits
        words = [int.from_bytes(line[i:i + bb], "little") for i in range(0, LINE, bb)]  # Split into words
        base = 0                                          # Base starts at zero
        for w in words:                                   # Look for the first word the zero base cannot cover
            if not fits(sgn(w, bits), db * 8):
                base = w
                break
        mask = 0                                          # Which words use the zero base
        deltas = []                                       # Per word delta
        ok = True                                         # Stays true while all words fit
        for w in words:
            if fits(sgn(w, bits), db * 8):                # Close to zero
                mask = (mask << 1) | 1
                deltas.append(sgn(w, bits))
            else:
                d = sgn(w - base, bits)                   # Wrapped difference to the base
                if not fits(d, db * 8):                   # Too far from both bases
                    ok = False
                    break
                mask <<= 1
                deltas.append(d)
        if not ok:
            continue                                      # This configuration cannot hold the line
        n = len(words)                                    # Number of words
        total = 3 + bits + n + n * db * 8                 # Tag, base, mask bits, deltas
        if best is None or total < best[0]:
            v = ci + 1                                    # Tag 1..6 selects the configuration
            v = (v << bits) | base                        # Append the base
            v = (v << n) | mask                           # Append the mask
            for d in deltas:                              # Append each delta
                v = (v << (db * 8)) | (d & ((1 << (db * 8)) - 1))
            best = (total, v)
    return best


def bdi_decode(bits, n):
    """BDI decoder: rebuilds the line from tag, base, mask and deltas."""
    br = payload_reader(bits, n)                          # Wrap the payload
    tag = br.get(3)                                       # Read the configuration tag
    if tag == 0:                                          # Repeated 8 byte value
        return struct.pack("<Q", br.get(64)) * 8
    bb, db = BDI_CFG[tag - 1]                             # Look up the configuration
    bits_w = bb * 8                                       # Word width
    cnt = LINE // bb                                      # Words per line
    base = br.get(bits_w)                                 # Read the base
    mask = br.get(cnt)                                    # Read the mask
    out = b""                                             # Rebuilt line
    for i in range(cnt):
        d = sgn(br.get(db * 8), db * 8)                   # Read one signed delta
        use_zero = (mask >> (cnt - 1 - i)) & 1            # Mask bit for this word
        w = (d if use_zero else base + d) & ((1 << bits_w) - 1)  # Add to the right base
        out += w.to_bytes(bb, "little")
    return out


def fpc_encode(line):
    """FPC codec: each 32 bit word gets a 3 bit prefix and a short payload; runs of zero words are merged."""
    words = struct.unpack("<16I", line)  # View the line as sixteen words
    bw = BitWriter()                     # Output stream
    i = 0
    while i < 16:
        w = words[i]
        s = sgn(w, 32)                   # Signed view of the word
        if w == 0:                       # Zero run, up to 8 words
            run = 1
            while i + run < 16 and words[i + run] == 0 and run < 8:
                run += 1
            bw.put(0, 3); bw.put(run - 1, 3)
            i += run
            continue
        if fits(s, 4):   bw.put(1, 3); bw.put(w, 4)                     # 4 bit signed
        elif fits(s, 8): bw.put(2, 3); bw.put(w, 8)                     # 8 bit signed
        elif fits(s, 16): bw.put(3, 3); bw.put(w, 16)                   # 16 bit signed
        elif w & 0xFFFF == 0: bw.put(4, 3); bw.put(w >> 16, 16)         # Low half zero
        elif fits(sgn(w, 16), 8) and fits(sgn(w >> 16, 16), 8):         # Two signed bytes in halves
            bw.put(5, 3); bw.put((w >> 16) & 0xFF, 8); bw.put(w & 0xFF, 8)
        elif len({w & 255, (w >> 8) & 255, (w >> 16) & 255, w >> 24}) == 1:  # One byte repeated
            bw.put(6, 3); bw.put(w & 255, 8)
        else: bw.put(7, 3); bw.put(w, 32)                               # Uncompressed
        i += 1
    return (bw.n, bw.v)


def fpc_decode(bits, n):
    """FPC decoder: reads prefixes until sixteen words are produced."""
    br = payload_reader(bits, n)                          # Wrap the payload
    out = []
    while len(out) < 16:
        p = br.get(3)
        if p == 0:   out += [0] * (br.get(3) + 1)
        elif p == 1: out.append(sgn(br.get(4), 4) & 0xFFFFFFFF)
        elif p == 2: out.append(sgn(br.get(8), 8) & 0xFFFFFFFF)
        elif p == 3: out.append(sgn(br.get(16), 16) & 0xFFFFFFFF)
        elif p == 4: out.append(br.get(16) << 16)
        elif p == 5:
            hi = sgn(br.get(8), 8) & 0xFFFF; lo = sgn(br.get(8), 8) & 0xFFFF
            out.append((hi << 16) | lo)
        elif p == 6: b = br.get(8); out.append(b * 0x01010101)
        else: out.append(br.get(32))
    return struct.pack("<16I", *out)


def line_candidates(line):
    """Returns {codec name: (payload bits, payload int)} for one line; the 2 bit codec tag lives in the page table."""
    c = {"raw": (512, int.from_bytes(line, "big"))}  # Raw always works
    z = zero_encode(line)
    if z: c["zero"] = z
    b = bdi_encode(line)
    if b: c["bdi"] = b
    f = fpc_encode(line)
    c["fpc"] = f
    return c


# ---------------------------------------------------------------- LZSS (compengine format)
WIN = 512      # This holds the LZSS window size
MINLEN = 3     # This holds the shortest match
MAXLEN = 18    # This holds the longest match


def lzss_encode(data):
    """LZSS as in compengine: literal = 0 + 8 bits, match = 1 + 9 bit distance-1 + 4 bit length-3.
    Greedy longest match, nearest distance wins a tie. Returns (bytes, token count)."""
    bw = BitWriter()          # Output stream
    table = {}                # 3 byte key -> ascending positions seen so far
    pos, n, tokens = 0, len(data), 0
    def insert(p):
        """Adds position p to the match table."""
        if p + 3 <= n:
            table.setdefault(data[p:p + 3], []).append(p)
    while pos < n:
        best_len, best_dist = 0, 0
        if pos + MINLEN <= n:
            cands = table.get(data[pos:pos + 3], [])
            maxl = min(MAXLEN, n - pos)
            for c in reversed(cands):                     # Nearest candidate first
                if pos - c > WIN:
                    break                                 # Older ones are outside the window
                l = 3
                while l < maxl and data[c + l] == data[pos + l]:
                    l += 1
                if l > best_len:                          # Strictly longer wins, so nearest wins ties
                    best_len, best_dist = l, pos - c
                    if l == maxl:
                        break
        if best_len >= MINLEN:
            bw.put(1, 1); bw.put(best_dist - 1, 9); bw.put(best_len - MINLEN, 4)
            for k in range(best_len):
                insert(pos + k)
            pos += best_len
        else:
            bw.put(0, 1); bw.put(data[pos], 8)
            insert(pos)
            pos += 1
        tokens += 1
    return bw.to_bytes(), tokens


def lzss_decode(blob):
    """Decodes an LZSS stream; trailing padding is shorter than any token so it is ignored."""
    br = BitReader(blob)
    out = bytearray()
    while br.left() >= 9:
        if br.get(1):
            if br.left() < 13:
                break
            d = br.get(9) + 1; l = br.get(4) + MINLEN
            for _ in range(l):
                out.append(out[-d])
        else:
            out.append(br.get(8))
    return bytes(out)


# ---------------------------------------------------------------- page level memory model
def lcp_page_bytes(line_bytes):
    """Stored size of one 1 KB page under the per-page fixed slot model (spec section 6).
    line_bytes = compressed size of each of the 16 lines in bytes (0 for a zero line)."""
    if not any(line_bytes):
        return 0                                               # Zero page costs no chunks
    best = PAGE                                                # Raw page is the fallback
    for s in SLOTS:                                            # Try each slot size
        exc = sum(1 for b in line_bytes if b > s)              # Lines that do not fit are exceptions
        best = min(best, 16 * s + 64 * exc)
    return best


def round_chunks(nbytes):
    """Rounds a byte count up to whole 128 byte chunks."""
    return -(-nbytes // CHUNK) * CHUNK


# ---------------------------------------------------------------- reference baselines
def zlib_size(data):  return len(zlib.compress(data, 9))      # zlib level 9, whole input
def xz_size(data):    return len(lzma.compress(data, preset=9))  # xz level 9, whole input
def bz2_size(data):   return len(bz2.compress(data, 9))       # bzip2 level 9, whole input


# ---------------------------------------------------------------- software block codecs (xz and zlib), with decoders
XZ_FILTERS = [{"id": lzma.FILTER_LZMA2, "preset": 9}]                 # This holds the raw LZMA2 filter chain used for xz blocks


def xz_encode(block):
    """Compresses one block as a raw LZMA2 stream (no container header)."""
    return lzma.compress(block, format=lzma.FORMAT_RAW, filters=XZ_FILTERS)


def xz_decode(blob):
    """Decompresses a raw LZMA2 stream made by xz_encode."""
    return lzma.decompress(blob, format=lzma.FORMAT_RAW, filters=XZ_FILTERS)


def zlib_encode(block):
    """Compresses one block as a raw deflate stream (no zlib header or checksum)."""
    c = zlib.compressobj(9, zlib.DEFLATED, -15)                       # wbits -15 means raw deflate
    return c.compress(block) + c.flush()


def zlib_decode(blob):
    """Decompresses a raw deflate stream made by zlib_encode."""
    return zlib.decompress(blob, -15)
