import sys, os as _os; _H = _os.path.dirname(_os.path.abspath(__file__)); sys.path[:0] = [_os.path.join(_H, "..", "python_files"), _os.path.join(_H, "..", "simulator")]  # Lets the scripts import each other across folders
#!/usr/bin/env python3
"""Mnemo simulator core (M0): a chunk pool, a page table, the codec bank and two scripted runs.

Run 1: files arrive over a UART, are compressed page by page into a small chip, then read back byte-exact.
Run 2: a full chip of raw files is compressed in place and the freed space is measured.

The result is written as JSON for the visual front end:   python3 mnemo_sim.py --out viz/data.json
"""
import os, sys, json, base64, hashlib, argparse, io, random, math
import mnemo_codecs as C

HERE = os.path.dirname(os.path.abspath(__file__))  # This holds the folder of this script
N_CHUNKS = 256                                      # This holds the number of 128 B chunks in the demo chip (16 x 16)
CH = C.CHUNK                                        # This holds the chunk size in bytes
PG = C.PAGE                                         # This holds the page size in bytes
BAUD = 921600                                       # This holds the UART speed shown in run 1
PREF = ("zero", "bdi", "fpc", "raw")                # This holds the tie-break order, cheapest decode first


class Chip:
    """A tiny memory chip: byte storage, a free pool of chunks, and a page table for stored pages."""

    def __init__(self):
        self.mem = bytearray(N_CHUNKS * CH)  # This holds the physical bytes of the chip
        self.free = set(range(N_CHUNKS))     # This holds the numbers of unused chunks
        self.pt = {}                         # This holds the page table: (file, page) -> entry dict

    def alloc(self, n):
        """Takes the n lowest free chunks, like the hardware free list."""
        if n > len(self.free):                          # Not enough space left
            raise MemoryError("pool exhausted")
        got = sorted(self.free)[:n]                     # Lowest numbers first
        self.free -= set(got)                           # Remove them from the pool
        return got

    def release(self, chunks):
        """Returns chunks to the free pool."""
        assert not (self.free & set(chunks)), "double free"  # A chunk must not be freed twice
        self.free |= set(chunks)                             # Put them back

    def write(self, chunks, data):
        """Writes bytes across the given chunks in order."""
        for i, c in enumerate(chunks):                       # One chunk at a time
            part = data[i * CH:(i + 1) * CH].ljust(CH, b"\0")  # Pad the last chunk with zeros
            self.mem[c * CH:(c + 1) * CH] = part             # Store it

    def read(self, chunks):
        """Reads the bytes of the given chunks in order."""
        return b"".join(bytes(self.mem[c * CH:(c + 1) * CH]) for c in chunks)

    def owner_map(self):
        """Returns, for each chunk, (file, page) of its owner or None if free."""
        m = [None] * N_CHUNKS                     # Start with all free
        for key, e in self.pt.items():            # Visit each stored page
            for c in e["chunks"]:
                assert m[c] is None, "chunk owned twice"  # Invariant: one owner per chunk
                m[c] = key
        assert {i for i, v in enumerate(m) if v is None} == self.free, "free set mismatch"  # Invariant: free set matches
        return m


def line_pick(line):
    """Picks the smallest codec for one 64 B line. Returns (codec, payload bits, payload int)."""
    cand = C.line_candidates(line)                                     # All codecs that can code this line
    best = min(cand, key=lambda k: (cand[k][0], PREF.index(k)))        # Smallest bits, cheapest decoder on ties
    return best, cand[best][0], cand[best][1]


def payload_bytes(bits, nb):
    """Converts a payload integer of nb bits to left aligned bytes."""
    if nb == 0:
        return b""                                       # Zero payload stores nothing
    pad = (-nb) % 8                                      # Bits to add to reach a byte boundary
    return (bits << pad).to_bytes((nb + pad) // 8, "big")  # Align to the top


def compress_page_lines(page):
    """Line mode: returns (entry fields, bytes to store). entry has mode, slot, per-line info."""
    lines = []                                           # Per line records
    for i in range(16):                                  # Sixteen lines per page
        ln = page[i * 64:(i + 1) * 64]
        codec, nb, bits = line_pick(ln)                  # Best codec for this line
        pb = payload_bytes(bits, nb)                     # Its payload bytes
        lines.append(dict(c=codec, b=len(pb), p=pb))
    if all(l["c"] == "zero" for l in lines):
        return dict(mode=0, slot=0, lines=lines, exc=[]), b""   # Zero page, nothing to store
    best = None                                          # Cheapest slot choice
    for s in C.SLOTS:                                    # Try 16, 32 and 64 byte slots
        exc = [i for i, l in enumerate(lines) if l["b"] > s]     # Lines that do not fit
        cost = 16 * s + 64 * len(exc)
        if best is None or cost < best[0]:
            best = (cost, s, exc)
    cost, s, exc = best
    if cost >= PG:                                       # No saving: store the page raw
        raw = [dict(c="raw", b=64, p=page[i * 64:(i + 1) * 64]) for i in range(16)]
        return dict(mode=1, slot=64, lines=raw, exc=[]), page
    buf = bytearray(16 * s + 64 * len(exc))              # Regular slots then the exception area
    for i, l in enumerate(lines):
        if i in exc:                                     # Exception: stored raw in the exception area
            j = exc.index(i)
            buf[16 * s + 64 * j:16 * s + 64 * (j + 1)] = page[i * 64:(i + 1) * 64]
            l["c"] = "raw"; l["b"] = 64; l["p"] = page[i * 64:(i + 1) * 64]
        else:
            buf[i * s:i * s + len(l["p"])] = l["p"]      # Compressed line in its slot
    return dict(mode=2, slot=s, lines=lines, exc=exc), bytes(buf)


def nchunks(nbytes):
    """Number of 128 B chunks needed for nbytes."""
    return -(-nbytes // CH)


MIN_GAIN = 0.25                                         # Compress a page only if it saves at least this share of its 8 raw chunks (0 = whenever smaller)


def store_page(chip, key, page, allow_lz=False, allow_xz=False, min_gain=None):
    """Compresses one page, allocates chunks, writes it and records the page table entry.
    Line codecs always run first; with allow_lz the page engine also tries LZSS (mode 3), and with allow_xz the software tier
    tries xz (mode 4). The result that needs the fewest chunks wins; ties go to the simpler decoder (line, then LZSS, then xz)."""
    fields, data = compress_page_lines(page)             # Line mode result
    lm_chunks = nchunks(len(data))                       # Chunks the line mode result would need
    lz = None                                            # Stream result if one wins
    best = lm_chunks                                     # Fewest chunks seen so far
    if any(page):
        for mode, algo, on, enc in ((3, "lzss", allow_lz, lambda p: C.lzss_encode(p)),
                                    (4, "xz", allow_xz, lambda p: (C.xz_encode(p), 0))):
            if not on:
                continue
            blob, ntok = enc(page)                       # Encode the whole page as one stream
            if nchunks(len(blob)) < best and nchunks(len(blob)) <= 6:
                best = nchunks(len(blob))
                lz = dict(len=len(blob), tokens=ntok, b64=b64(blob), algo=algo)
                fields = dict(mode=mode, slot=0, lines=fields["lines"], exc=[], lzlen=len(blob), tokens=ntok)  # Keep the line attempt for display
                data = blob
    gate = MIN_GAIN if min_gain is None else min_gain    # Threshold layer: is the saving big enough to be worth a decode on every read?
    would = nchunks(len(data)) if data else 0             # Chunks the best codec would use before the threshold check
    gated = False                                        # True when a compressible page is kept raw because it saves too little
    if data and fields["mode"] != 1 and 1 - nchunks(len(data)) / 8 < gate - 1e-9:
        raw = [dict(c="raw", b=64, p=page[i * 64:(i + 1) * 64]) for i in range(16)]
        fields = dict(mode=1, slot=64, lines=raw, exc=[]); data = page; lz = None; gated = True
    chunks = chip.alloc(nchunks(len(data))) if data else []  # Zero pages own no chunks
    chip.write(chunks, data)
    chip.pt[key] = dict(fields, chunks=chunks, stored=len(data), lm_chunks=lm_chunks, lz=lz, gated=gated, would=would)
    return chip.pt[key]


def load_page(chip, key):
    """Reads one page back through the page table and decodes it."""
    e = chip.pt[key]                                     # Page table entry
    mode = e["mode"]
    if mode == 0:
        return bytes(PG)                                 # Zero page
    data = chip.read(e["chunks"])                        # Bytes from the chunks
    if mode == 1:
        return data[:PG]                                 # Raw page
    if mode == 3:
        return C.lzss_decode(data[:e["lzlen"]]).ljust(PG, b"\0")[:PG]  # LZSS page
    if mode == 4:
        return C.xz_decode(data[:e["lzlen"]]).ljust(PG, b"\0")[:PG]    # xz page (software tier)
    s = e["slot"]; exc = e["exc"]
    out = b""
    for i, l in enumerate(e["lines"]):                   # Decode each line with its codec
        if i in exc:
            j = exc.index(i)
            out += data[16 * s + 64 * j:16 * s + 64 * (j + 1)]       # Exception line, raw
            continue
        raw = data[i * s:i * s + l["b"]]                 # Payload bytes of this line
        n = len(raw) * 8
        bits = int.from_bytes(raw, "big") if raw else 0
        if l["c"] == "zero": out += C.zero_decode(0, 0)
        elif l["c"] == "bdi": out += C.bdi_decode(bits, n)
        elif l["c"] == "fpc": out += C.fpc_decode(bits, n)
        else: out += raw
    return out


def split_pages(data):
    """Pads a file to whole pages and returns the list of 1 KB pages."""
    data = data + bytes((-len(data)) % PG)
    return [data[i:i + PG] for i in range(0, len(data), PG)]


def free_file(chip, name):
    """Frees every page of a file."""
    for key in [k for k in chip.pt if k[0] == name]:
        chip.release(chip.pt[key]["chunks"])
        del chip.pt[key]


# ---------------------------------------------------------------- sample files
def make_jpeg(w, h, seed):
    """Makes a real JPEG (already compressed data) from a synthetic picture."""
    from PIL import Image, ImageDraw, ImageFilter
    rnd = random.Random(seed)
    img = Image.new("RGB", (w, h))
    px = img.load()
    for y in range(h):                                   # Sky-to-sea gradient
        for x in range(w):
            t = y / h
            px[x, y] = (int(40 + 120 * t), int(90 + 80 * (1 - t)), int(160 - 60 * t))
    d = ImageDraw.Draw(img)
    d.ellipse((w * 0.62, h * 0.12, w * 0.85, h * 0.12 + w * 0.23), fill=(250, 220, 120))  # Sun
    d.polygon([(0, h), (w * 0.35, h * 0.5), (w * 0.7, h)], fill=(40, 60, 50))             # Hill
    img = img.filter(ImageFilter.GaussianBlur(0.8))
    px = img.load()
    for _ in range(w * h // 3):                          # Sensor noise makes it hard to compress
        x, y = rnd.randrange(w), rnd.randrange(h)
        r, g, b = px[x, y]
        n = rnd.randint(-18, 18)
        px[x, y] = (max(0, min(255, r + n)), max(0, min(255, g + n)), max(0, min(255, b + n)))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=88)
    return buf.getvalue()


def cut_at_line(data, limit):
    """Cuts text data to at most limit bytes at a line boundary."""
    cut = data[:limit]
    nl = cut.rfind(b"\n")
    return cut[:nl + 1] if nl > 0 else cut


def corpus(name):
    """Reads one file from the comparator corpus."""
    return open(os.path.join(HERE, "..", "test_files", name), "rb").read()


def b64(b):
    """Base64 text of bytes."""
    return base64.b64encode(b).decode()


def file_record(name, kind, data):
    """Basic description of a file for the front end."""
    return dict(name=name, kind=kind, size=len(data), sha1=hashlib.sha1(data).hexdigest(), b64=b64(data))


# ---------------------------------------------------------------- run 1
def run1():
    """Four files arrive over the UART, get compressed into the chip, idle pages go cold, then files are read back."""
    jpg = make_jpeg(112, 80, 7)                                         # Photo that will not compress
    files = [
        ("telemetry.csv", "csv", cut_at_line(corpus("data_imu.csv"), 8 * 1024)),
        ("picorv32.hex", "hex", cut_at_line(corpus("pico_fw_rv32imc.hex"), 6 * 1024)),
        ("picorv32.bin", "code", corpus("pico_fw_rv32imc.bin")[:6 * 1024]),
        ("photo.jpg", "jpg", jpg[:8 * 1024]),
    ]
    chip = Chip()
    out = dict(files=[], cold=[], baud=BAUD)
    # Load phase: every page gets line codecs and, because a bulk upload is predicted cold, an LZSS try as well.
    for name, kind, data in files:
        rec = file_record(name, kind, data)
        rec["uart_ms"] = round(len(data) * 10 / BAUD * 1000, 2)         # Time on the wire for the raw file
        rec["pages"] = []
        for pi, page in enumerate(split_pages(data)):
            e = store_page(chip, (name, pi), page, allow_lz=True, allow_xz=True)       # Compress and place the page
            rec["pages"].append(dict(idx=pi, mode=e["mode"], slot=e["slot"], exc=e["exc"], chunks=e["chunks"], stored=e["stored"], lm_chunks=e["lm_chunks"],
                                     lz=e["lz"], gated=e["gated"], would=e["would"], lines=[dict(c=l["c"], b=l["b"], p=l["p"].hex()) for l in e["lines"]]))
        out["files"].append(rec)
    out["chip_loaded"] = [None if o is None else [o[0], o[1]] for o in chip.owner_map()]  # Who owns each chunk after loading
    out["used_loaded"] = N_CHUNKS - len(chip.free)
    out["used_cold"] = out["used_loaded"]
    # Read back everything and compare to the original bytes.
    for rec, (name, kind, data) in zip(out["files"], files):
        back = b"".join(load_page(chip, (name, pi)) for pi in range(len(split_pages(data))))[:len(data)]
        rec["verified"] = (back == data)                                # Byte-exact check
        assert rec["verified"], f"{name} did not read back exactly"
        rec["stored_chunks_loaded"] = sum(len(p["chunks"]) for p in rec["pages"])
        rec["stored_chunks_cold"] = rec["stored_chunks_loaded"]
    return out


# ---------------------------------------------------------------- run 2
def run2():
    """A fragmented, nearly full chip of raw files is compressed in place and the freed chunks are counted."""
    jpg = make_jpeg(72, 52, 11)
    rnd = random.Random(5)
    spec = [  # (name, kind, data)
        ("imu.csv", "csv", cut_at_line(corpus("data_imu.csv")[3000:], 4 * 1024)),
        ("boot.hex", "hex", cut_at_line(corpus("pico_fw_rv32im.hex")[6000:], 3 * 1024)),
        ("kernel.bin", "code", corpus("pico_fw_rv32im.bin")[1500:1500 + 3 * 1024]),
        ("photo.jpg", "jpg", jpg[:3 * 1024]),
        ("accel.i16", "data", corpus("data_imu_i16.bin")[2000:2000 + 3 * 1024]),
        ("ptrs.bin", "data", corpus("data_pointers.bin")[:3 * 1024]),
        ("counts.bin", "data", corpus("data_counters.bin")[:2 * 1024]),
        ("notes.txt", "txt", cut_at_line(corpus("data_text.txt")[5000:], 3 * 1024)),
        ("wave.f32", "data", corpus("data_float32.bin")[:2 * 1024]),
        ("tool.elf", "code", corpus("native_ls.bin")[8000:8000 + 2 * 1024]),
        ("key.bin", "key", bytes(rnd.getrandbits(8) for _ in range(1024))),
        ("config.txt", "txt", cut_at_line(corpus("data_text.txt")[20000:], 2 * 1024)),
    ]
    chip = Chip()
    # Fragmenting history: temporary files are written between real ones and then deleted.
    ghosts = []
    for gi in range(5):
        ghosts.append((f"tmp{gi}", bytes(rnd.getrandbits(8) for _ in range(PG))))
    order = []
    for i, (name, kind, data) in enumerate(spec):
        if i % 2 == 0 and ghosts:                         # Write a temp file before every other real file
            gname, gdata = ghosts.pop(0)
            store_page(chip, (gname, 0), gdata)
            order.append(gname)
        for pi, page in enumerate(split_pages(data)):
            fields = dict(mode=1, slot=64, lines=[], exc=[])  # Raw storage: the chip is full of plain files
            ch = chip.alloc(8)
            chip.write(ch, page)
            chip.pt[(name, pi)] = dict(fields, chunks=ch, stored=PG)
        if i % 3 == 2 and order:                          # Delete an old temp file, leaving holes
            free_file(chip, order.pop(0))
    for gname in order:                                   # Remove remaining temp files
        free_file(chip, gname)
    before_map = [None if o is None else [o[0], o[1]] for o in chip.owner_map()]
    used_before = N_CHUNKS - len(chip.free)
    out = dict(files=[], before=before_map, used_before=used_before)
    # Compress every page in place: read, compress, free old chunks, allocate new ones.
    pieces = []
    for name, kind, data in spec:
        rec = file_record(name, kind, data)
        rec["pages"] = []
        for pi, page in enumerate(split_pages(data)):
            key = (name, pi)
            old = chip.pt[key]
            assert chip.read(old["chunks"])[:PG] == page    # What is in the chip is the original page
            chip.release(old["chunks"]); del chip.pt[key]
            e = store_page(chip, key, page, allow_lz=True, allow_xz=True)  # Line codecs or LZSS, whichever is smaller
            rec["pages"].append(dict(mode=e["mode"], slot=e["slot"], k=len(e["chunks"]), stored=e["stored"],
                                     codecs=[e["lz"]["algo"]] if e["mode"] >= 3 else (sorted({l["c"] for l in e["lines"]}) if e["lines"] else [])))
            pieces.append(dict(file=name, page=pi, k=len(e["chunks"]), mode=e["mode"], slot=e["slot"], before=8))
        back = b"".join(load_page(chip, (name, pi)) for pi in range(len(rec["pages"])))[:len(data)]
        assert back == data, f"{name} lost data"            # Byte-exact after compaction
        rec["verified"] = True
        rec["raw_chunks"] = 8 * len(rec["pages"])
        rec["new_chunks"] = sum(p["k"] for p in rec["pages"])
        out["files"].append(rec)
    chip.owner_map()                                        # Check invariants once more
    out["used_after"] = N_CHUNKS - len(chip.free)
    out["pieces"] = pieces
    return out


def main():
    """Runs both scenes and writes the JSON for the front end."""
    global MIN_GAIN                                      # The threshold layer reads this when pages are stored
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(HERE, "viz", "data.json"))
    ap.add_argument("--min-gain", type=float, default=MIN_GAIN, dest="min_gain", help="default threshold shown by the page (0 to 1)")
    ap.add_argument("--gains", default="0,0.25,0.375,0.5", help="comma separated thresholds the page lets you choose between")
    args = ap.parse_args()
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    sets = []                                            # One full simulation per threshold
    for g in [float(x) for x in args.gains.split(",")]:
        MIN_GAIN = g                                     # Apply the threshold to every page stored in both runs
        sets.append(dict(gain=g, run1=run1(), run2=run2()))
    data = dict(meta=dict(chunks=N_CHUNKS, chunk=CH, page=PG, grid=16, baud=BAUD, default_gain=args.min_gain), sets=sets)
    json.dump(data, open(args.out, "w"), separators=(",", ":"))
    for st in sets:                                      # Summary per threshold
        r1, r2 = st["run1"], st["run2"]
        gated = sum(1 for f in r1["files"] for p in f["pages"] if p.get("gated"))
        print(f"min saving {st['gain']:5.3f}: run1 {r1['used_loaded']}/{N_CHUNKS} chunks, run2 {r2['used_before']} -> {r2['used_after']}, run1 pages kept raw by threshold {gated}")
        if st["gain"] == args.min_gain:                  # Detail for the default only
            for f in r1["files"]:
                print(f"  {f['name']:14s} {f['size']:6d} B  chunks {f['stored_chunks_loaded']:3d}  verified {f['verified']}")
            for f in r2["files"]:
                print(f"  {f['name']:14s} {f['size']:6d} B  chunks {f['raw_chunks']:3d} -> {f['new_chunks']:3d}")
    print(f"json {os.path.getsize(args.out)//1024} KB")


if __name__ == "__main__":
    main()
