"""Mnemo coprocessor: functional model that follows the spec (v0.1) from front end to memory.

Blocks modelled: front end (line and byte access), translation (PTE), codec selector, allocator
(chunk pool, reserve, exceptions, repack, pressure), page engine (cold LZ, hot buffer), learning
block (regions, prediction, exploration, reason codes, telemetry), integrity (CRC8, debug check,
bypass, startup scan) and the register map. Everything is bit exact: a read returns what was written.
"""
import sys, os as _os; _H = _os.path.dirname(_os.path.abspath(__file__)); sys.path[:0] = [_os.path.join(_H, "..", "python_files"), _os.path.join(_H, "..", "simulator")]  # Lets the scripts import each other across folders
import collections, functools, random, struct
import mnemo_codecs as C

LINE, PAGE, CHUNK, LPP = 64, 1024, 128, 16          # This holds line, page and chunk sizes and lines per page
MODE_ZERO, MODE_RAW, MODE_LINE, MODE_LZ = 0, 1, 2, 3  # This holds the four page modes
CODEC_RAW, CODEC_ZERO, CODEC_BDI, CODEC_FPC = 0, 1, 2, 3  # This holds the 2 bit codec codes stored per line
CODEC_NAME = ["raw", "zero", "bdi", "fpc"]            # Names of the codec codes
SLOTS = (16, 32, 64)                                  # Allowed line slot sizes in mode 2
OKAY, SLVERR = 0, 2                                   # AXI response codes used by the model
RESERVE = 16                                          # Chunks 0 to 15 are the reserve
HB_SLOTS = 4                                          # Hot buffer pages
TEL_DEPTH = 256                                       # Telemetry ring depth

# Reason codes (spec section 9)
R_DEFAULT, R_ZERO, R_PRED, R_EXPLORE, R_OVERFLOW, R_RAW, R_COLD, R_PRESSURE, R_HOT, R_CRC = range(10)
REASON_NAME = ["default", "zero page", "predicted won", "explored", "slot overflow", "raw: no gain",
               "cold LZ", "pressure repack", "hot expand", "crc fail"]

# Pressure levels
P_NORMAL, P_LOW, P_CRIT, P_FULL = range(4)
LEVEL_NAME = ["normal", "low", "critical", "full"]

# Register offsets (spec section 11)
REG = dict(ID=0x00, CTRL=0x04, STATUS=0x08, IRQ_EN=0x0C, POOL_CHUNKS=0x10, FREE_CHUNKS=0x14,
           EFF_CAPACITY=0x18, RATIO=0x1C, THRESH=0x20, POLICY0=0x24, POLICY1=0x28, FORCE=0x2C,
           CNT_READ=0x30, CNT_WRITE=0x34, CNT_EXC=0x38, CNT_REPACK=0x3C, CNT_LZ=0x40, CNT_PRED=0x44,
           CNT_PTE_MISS=0x48, CNT_MISMATCH=0x4C, TEL_HEAD=0x50, TEL_TAIL=0x54, TEL_DATA=0x58,
           PT_ADDR=0x5C, PT_DATA=0x60, POLICY2=0x64)  # POLICY2 is new: minimum saving percent and cold algorithm

CTRL_ENABLE, CTRL_BYPASS, CTRL_DEBUG, CTRL_LEARN, CTRL_REPACK = 1, 2, 4, 8, 16  # CTRL bit masks
ST_LOW, ST_CRIT, ST_FULL, ST_INTEG, ST_TABLE = 1, 2, 4, 8, 16                 # STATUS bit masks


def _crc8_table():
    """Builds the CRC8 (polynomial 0x07) lookup table."""
    t = []
    for i in range(256):
        c = i
        for _ in range(8):
            c = ((c << 1) ^ 0x07) & 0xFF if c & 0x80 else (c << 1) & 0xFF  # Shift and reduce
        t.append(c)
    return t


_CRC = _crc8_table()  # This holds the CRC8 table


def crc8(data):
    """CRC8 of a byte string (stored per line, spec section 12)."""
    c = 0
    for b in data:
        c = _CRC[c ^ b]                                    # Table step
    return c


def _pb(nbits, bits):
    """Left aligned bytes of an nbits payload integer."""
    if nbits == 0:
        return b""
    pad = (-nbits) % 8
    return (bits << pad).to_bytes((nbits + pad) // 8, "big")


@functools.lru_cache(maxsize=1 << 17)
def line_options(line):
    """Payload bytes of every codec for one line: {code: bytes or None}. Cached because pure."""
    c = C.line_candidates(line)                            # Real codecs, (bits, int) each
    out = {CODEC_RAW: bytes(line), CODEC_ZERO: b"" if "zero" in c else None}
    out[CODEC_BDI] = _pb(*c["bdi"]) if "bdi" in c else None
    out[CODEC_FPC] = _pb(*c["fpc"]) if "fpc" in c else None
    return out


def decode_line(code, slot_bytes):
    """Decodes one line from the bytes found in its slot."""
    if code == CODEC_ZERO:
        return bytes(LINE)
    if code == CODEC_RAW:
        return bytes(slot_bytes[:LINE])
    bits = int.from_bytes(slot_bytes, "big") if slot_bytes else 0
    n = len(slot_bytes) * 8
    return C.bdi_decode(bits, n) if code == CODEC_BDI else C.fpc_decode(bits, n)  # BDI or FPC


def best_option(line):
    """Smallest payload over all codecs with ties to the cheaper decoder. Returns (code, bytes)."""
    o = line_options(line)
    best = None
    for code in (CODEC_ZERO, CODEC_BDI, CODEC_FPC, CODEC_RAW):    # Tie order: zero, bdi, fpc, raw
        p = o[code]
        if p is not None and (best is None or len(p) < len(best[1])):
            best = (code, p)
    return best


def slot_for(nbytes):
    """Smallest slot that holds nbytes (raw 64 needs slot 64)."""
    return 16 if nbytes <= 16 else 32 if nbytes <= 32 else 64


def need_chunks(mode, slot=0, nexc=0, lzlen=0):
    """Chunks a page needs for its mode (spec section 6 and 8)."""
    if mode == MODE_ZERO: return 0
    if mode == MODE_RAW: return 8
    if mode == MODE_LINE: return 16 * slot // CHUNK + (nexc + 1) // 2
    return (lzlen + CHUNK - 1) // CHUNK


def plan_page(lines, min_save=0.0):
    """Chooses the best representation for a page. Returns a dict with mode, slot, chunks, gated, would."""
    if not any(any(l) for l in lines):
        return dict(mode=MODE_ZERO, slot=0, chunks=0, gated=False, would=0)
    best = None
    for s in SLOTS:
        k = sum(1 for l in lines if len(best_option(l)[1]) > s)        # Lines that do not fit the slot
        ch = need_chunks(MODE_LINE, s, k)
        if best is None or (ch, k) < (best[0], best[1]):
            best = (ch, k, s)
    ch, k, s = best
    if ch >= 8:
        return dict(mode=MODE_RAW, slot=0, chunks=8, gated=False, would=ch)
    if 1 - ch / 8 < min_save - 1e-9:                                   # Threshold layer: not enough saving
        return dict(mode=MODE_RAW, slot=0, chunks=8, gated=True, would=ch)
    return dict(mode=MODE_LINE, slot=s, chunks=ch, gated=False, would=ch)


class SlvErr(Exception):
    """Raised inside the model when an operation must return SLVERR."""


class PTE:
    """One page table entry (spec section 6)."""
    __slots__ = ("mode", "slot", "ptr", "codec", "exc", "lzlen", "lzalgo", "lztok", "hot", "dirty", "hb", "heat")

    def __init__(self):
        self.mode = MODE_ZERO; self.slot = 0; self.ptr = []                      # Mode, slot, chunk pointers
        self.codec = [CODEC_ZERO] * LPP; self.exc = [False] * LPP                # Per line codec and exception flags
        self.lzlen = 0; self.lzalgo = 0; self.lztok = 0                          # LZ length, algorithm bit, token count
        self.hot = False; self.dirty = False; self.hb = 0; self.heat = 0        # Hot buffer state and heat

    @property
    def nexc(self):
        """Number of lines stored in the exception area."""
        return sum(self.exc)

    def pack(self):
        """Packs the entry into five 32 bit words for the PT_DATA debug window."""
        v = self.mode | (self.slot_code() << 2) | (len(self.ptr) << 4)
        for i in range(8):
            v |= (self.ptr[i] if i < len(self.ptr) else 0) << (8 + 9 * i)         # ptr[0..7], 9 bits each
        v |= sum(c << (80 + 2 * i) for i, c in enumerate(self.codec))             # codec[0..15]
        v |= sum((1 << i) for i, e in enumerate(self.exc) if e) << 112             # exc[0..15]
        v |= self.lzlen << 128 | int(self.hot) << 138 | int(self.dirty) << 139 | self.hb << 140 | self.heat << 142
        v |= self.lzalgo << 146
        return [(v >> (32 * i)) & 0xFFFFFFFF for i in range(5)]

    def slot_code(self):
        """2 bit slot field: 0 none, 1 = 16 B, 2 = 32 B, 3 = 64 B."""
        return {0: 0, 16: 1, 32: 2, 64: 3}[self.slot]


class Mnemo:
    """The coprocessor model."""

    def __init__(self, n_chunks=512, v_pages=96, seed=1, **cfg):
        """Creates the chip: memory, free lists, page table, regions, hot buffer, registers."""
        self.N = n_chunks; self.V = v_pages                                       # Pool size and virtual pages
        self.mem = bytearray(n_chunks * CHUNK)                                    # Physical memory
        self.rng = random.Random(seed)                                            # Exploration randomness
        self.free_main = list(range(n_chunks - 1, RESERVE - 1, -1))               # Stack of free chunks (lowest on top)
        self.free_res = list(range(RESERVE - 1, -1, -1))                          # Stack of free reserve chunks
        self.pt = {p: PTE() for p in range(v_pages)}                              # Page table, all pages start in mode 0
        self.crc = {p: [crc8(bytes(LINE))] * LPP for p in range(v_pages)}         # Side RAM of per line CRC8
        self.touched = set()                                                      # Pages written at least once
        self.hbq = collections.OrderedDict()                                      # Hot buffer: page -> [bytearray, dirty]
        # Registers
        self.ctrl = CTRL_ENABLE | CTRL_LEARN | (CTRL_DEBUG if cfg.get("debug", True) else 0)
        self.status = 0; self.irq_en = ST_CRIT | ST_FULL | ST_INTEG; self.force = 0
        self.thr_low = cfg.get("thr_low", 25); self.thr_crit = cfg.get("thr_crit", 10)
        self.margin = cfg.get("margin", 2); self.explore = cfg.get("explore", 32); self.cold_thr = cfg.get("cold_thr", 0)
        self.region_pages = cfg.get("region_pages", 4); self.slot_cov = cfg.get("slot_cov", 90)
        self.min_save_pct = cfg.get("min_save_pct", 0); self.cold_algo = cfg.get("cold_algo", "lzss")
        self.fixed_slot = cfg.get("fixed_slot", 32); self.decay_n = cfg.get("decay_n", 64)
        self.pt_addr = 0; self.pt_words = []; self.tel_tail = 0
        if cfg.get("learn") is False: self.ctrl &= ~CTRL_LEARN
        if cfg.get("bypass"): self.ctrl |= CTRL_BYPASS
        # Counters
        self.cnt = collections.Counter()
        self.tel = collections.deque(maxlen=TEL_DEPTH); self.tel_head = 0         # Telemetry ring and write index
        self.regions = {}                                                         # Region records
        self.clock = 0; self.accesses = 0; self.scan = 0                          # Op counter, access counter, repack cursor
        self.rd_lat = []; self.wr_lat = []                                        # Latency samples in cycles
        self.explicit_repack = False

    # ------------------------------------------------------------------ helpers
    def region(self, page):
        """Returns the learning record of the page's region."""
        r = page // self.region_pages
        if r not in self.regions:
            self.regions[r] = dict(win=[0] * 4, hist=[0, 0, 0, 0], wr=0, rd=0, ovf=0, dec=0, why=0)
        return self.regions[r]

    def learn_on(self):
        """True when the learning block is enabled."""
        return bool(self.ctrl & CTRL_LEARN)

    def log(self, page, old, new, reason, osz, nsz):
        """Writes one event into the telemetry ring and remembers the region's last reason."""
        self.tel.append((self.clock, page, old, new, reason, osz, nsz)); self.tel_head += 1
        r = self.region(page); r["why"] = reason
        self.cnt["reason%d" % reason] += 1

    def state_of(self, pte):
        """Compact (mode, slot or algo) state for telemetry."""
        return (pte.mode, pte.slot if pte.mode == MODE_LINE else pte.lzalgo if pte.mode == MODE_LZ else 0)

    # ------------------------------------------------------------------ allocator
    def free_total(self):
        """Free chunks, main pool plus reserve."""
        return len(self.free_main) + len(self.free_res)

    def level(self):
        """Pressure level from the main pool occupancy against the two thresholds."""
        main = self.N - RESERVE
        f = len(self.free_main)
        if f == 0: return P_FULL
        pct = 100.0 * f / main
        if pct < self.thr_crit: return P_CRIT
        if pct < self.thr_low: return P_LOW
        return P_NORMAL

    def refresh_status(self):
        """Sets the sticky STATUS bits that match the current pressure level."""
        lv = self.level()
        if lv >= P_LOW: self.status |= ST_LOW
        if lv >= P_CRIT: self.status |= ST_CRIT
        if lv >= P_FULL: self.status |= ST_FULL
        return lv

    def alloc(self, n, inflight):
        """Takes n chunks. inflight=True lets the reserve complete a started operation."""
        got = []
        if n == 0:
            return got
        if len(self.free_main) >= n:
            got = [self.free_main.pop() for _ in range(n)]
        elif inflight and self.free_total() >= n:
            while len(got) < n:
                got.append(self.free_main.pop() if self.free_main else self.free_res.pop())  # Main first, reserve last
        else:
            self.cnt["alloc_fail"] += 1
            raise SlvErr("pool exhausted")
        self.refresh_status()
        return got

    def release(self, chunks):
        """Gives chunks back to the pool they belong to."""
        for c in chunks:
            (self.free_res if c < RESERVE else self.free_main).append(c)
        self.free_main.sort(reverse=True); self.free_res.sort(reverse=True)    # Keeps lowest-first allocation deterministic

    # ------------------------------------------------------------------ physical access through a pointer list
    def vwrite(self, ptr, off, data):
        """Writes bytes at a virtual offset of a chunk list."""
        i = 0
        while i < len(data):
            c, o = divmod(off + i, CHUNK)
            n = min(CHUNK - o, len(data) - i)
            a = ptr[c] * CHUNK + o
            self.mem[a:a + n] = data[i:i + n]; i += n

    def vread(self, ptr, off, n):
        """Reads n bytes at a virtual offset of a chunk list."""
        out = bytearray(); i = 0
        while i < n:
            c, o = divmod(off + i, CHUNK)
            k = min(CHUNK - o, n - i)
            a = ptr[c] * CHUNK + o
            out += self.mem[a:a + k]; i += k
        return bytes(out)

    # ------------------------------------------------------------------ page images
    def build_image(self, slot, codes, pays, exc, lines):
        """Mode 2 image: regular area (16 x slot) then the exception area in line order."""
        reg = bytearray(16 * slot)
        for i in range(LPP):
            if not exc[i]:
                reg[i * slot:i * slot + len(pays[i])] = pays[i]
        for i in range(LPP):
            if exc[i]:
                reg += lines[i]
        return bytes(reg)

    def decode_page(self, pte):
        """Reads a whole page back through the decoders. Returns (bytes, list of CRC-checked lines)."""
        if pte.mode == MODE_ZERO:
            return bytes(PAGE)
        if pte.mode == MODE_RAW:
            return self.vread(pte.ptr, 0, PAGE)
        if pte.mode == MODE_LZ:
            blob = self.vread(pte.ptr, 0, pte.lzlen)
            d = C.xz_decode(blob) if pte.lzalgo else C.lzss_decode(blob)
            return d.ljust(PAGE, b"\0")[:PAGE]
        return b"".join(self.read_line_raw(pte, i) for i in range(LPP))

    def read_line_raw(self, pte, i):
        """Mode 2: finds line i (slot or exception area) and decodes it."""
        s = pte.slot
        if pte.exc[i]:
            j = sum(pte.exc[:i])                                              # Exception entries below i
            return self.vread(pte.ptr, 16 * s + LINE * j, LINE)
        return decode_line(pte.codec[i], self.vread(pte.ptr, i * s, s))

    # ------------------------------------------------------------------ commit a new page representation
    def commit(self, page, lines, plan, reason, inflight=True, pays=None, codes=None):
        """Allocate, write, update the PTE, free the old chunks (the order of spec section 8)."""
        old = self.pt[page]
        new = PTE()
        new.heat, new.hot, new.dirty, new.hb = old.heat, old.hot, old.dirty, old.hb
        new.mode = plan["mode"]
        if new.mode == MODE_ZERO:
            image = b""
        elif new.mode == MODE_RAW:
            image = b"".join(lines)
        elif new.mode == MODE_LINE:
            new.slot = plan["slot"]
            opts = [best_option(l) for l in lines]
            new.codec = [CODEC_RAW if len(o[1]) > new.slot else o[0] for o in opts]
            new.exc = [len(o[1]) > new.slot for o in opts]
            image = self.build_image(new.slot, new.codec, [o[1] for o in opts], new.exc, lines)
        else:
            image = plan["blob"]; new.lzlen = len(image); new.lzalgo = plan["algo"]; new.lztok = plan.get("tok", 0)
        n = need_chunks(new.mode, new.slot, new.nexc, new.lzlen)
        new.ptr = self.alloc(n, inflight)                                          # Allocate first
        self.vwrite(new.ptr, 0, image.ljust(n * CHUNK, b"\0"))                     # Write data
        self.pt[page] = new                                                        # Update the PTE
        self.release(old.ptr)                                                      # Free old chunks last
        for i, l in enumerate(lines): self.crc[page][i] = crc8(l)
        self.log(page, self.state_of(old) + (len(old.ptr),), self.state_of(new) + (n,), reason, len(old.ptr), n)
        self.touched.add(page)
        return new

    def store_lines(self, page, lines, reason, inflight=True):
        """Plans and commits a page from its 16 lines (line mode, raw or zero)."""
        plan = plan_page(lines, self.min_save_pct / 100.0)
        if plan["mode"] == MODE_RAW:
            reason = R_RAW                                                         # Compression did not pay
        if plan["mode"] == MODE_ZERO:
            reason = R_ZERO
        return self.commit(page, lines, plan, reason, inflight)

    # ------------------------------------------------------------------ hot buffer
    def hb_evict(self, keep=None):
        """Evicts the least recently used hot buffer page, writing it back when dirty."""
        for page in list(self.hbq):
            if page == keep: continue
            data, dirty = self.hbq[page]
            pte = self.pt[page]
            if dirty:
                lines = [bytes(data[i * LINE:(i + 1) * LINE]) for i in range(LPP)]
                try:
                    self.store_lines(page, lines, R_DEFAULT)
                except SlvErr:
                    continue                                                       # Try the next victim
                pte = self.pt[page]
            pte.hot = False; pte.dirty = False
            del self.hbq[page]
            return True
        return False

    def hb_load(self, page, reason=R_HOT):
        """Expands a page into the hot buffer (evicting if needed) and marks it hot."""
        if page in self.hbq:
            self.hbq.move_to_end(page); return self.hbq[page]
        if len(self.hbq) >= HB_SLOTS and not self.hb_evict(keep=page):
            raise SlvErr("hot buffer stuck")
        pte = self.pt[page]
        data = self.decode_page(pte)
        if pte.mode == MODE_LZ:
            self.cnt["lz_expand"] += 1
        used = {v for v in range(HB_SLOTS)} - {self.pt[p].hb for p in self.hbq}
        pte.hot = True; pte.hb = min(used) if used else 0
        self.hbq[page] = [bytearray(data), False]
        self.log(page, self.state_of(pte), self.state_of(pte), reason, len(pte.ptr), len(pte.ptr))
        return self.hbq[page]

    # ------------------------------------------------------------------ learning block
    def predicted_codec(self, page):
        """Codec with the highest win counter if its lead is above the margin, else None."""
        w = self.region(page)["win"]
        order = sorted(range(4), key=lambda c: -w[c])
        if w[order[0]] == 0 or w[order[0]] - w[order[1]] < self.margin:
            return None
        return order[0]

    def predicted_slot(self, page, first_line):
        """Slot for a new page: smallest that covers slot_cov percent of recent lines in the region."""
        h = self.region(page)["hist"]; tot = sum(h)
        if not self.learn_on():
            return self.fixed_slot
        if tot < 8:
            return slot_for(len(best_option(first_line)[1]))                       # No history: use the first line
        acc = 0
        for s, c in zip(SLOTS, h[:3]):
            acc += c
            if 100 * acc >= self.slot_cov * tot:
                return s
        return 64

    def note_write(self, page, win_code, need):
        """Updates win counters and the size histogram of the region."""
        r = self.region(page)
        r["wr"] = min(63, r["wr"] + 1)
        if win_code is not None:
            r["win"][win_code] += 1
            if r["win"][win_code] > 63:
                r["win"] = [v // 2 for v in r["win"]]                              # Saturate by halving
        r["hist"][0 if need <= 16 else 1 if need <= 32 else 2] += 1
        if sum(r["hist"][:3]) > 60:
            r["hist"] = [v // 2 for v in r["hist"]]

    # ------------------------------------------------------------------ selector
    def select(self, page, line, slot):
        """Picks codec and payload for a written line. Returns (code, payload, reason, fits)."""
        o = line_options(line)
        winner = best_option(line)
        need = len(winner[1])
        if self.force:
            code = self.force - 1
            p = o.get(code)
            if p is None or len(p) > slot:
                code, p = CODEC_RAW, o[CODEC_RAW]
            self.cnt["codec_runs"] += 1
            return code, p, R_DEFAULT, len(p) <= slot, winner, need
        if not any(line):
            return CODEC_ZERO, b"", R_ZERO, True, winner, need
        pred = self.predicted_codec(page) if self.learn_on() else None
        explore = pred is not None and self.explore and self.rng.randrange(self.explore) == 0
        if pred is not None and not explore:
            self.cnt["pred_made"] += 1
            p = o.get(pred); self.cnt["codec_runs"] += 1
            if p is not None and len(p) <= slot:
                self.cnt["pred_ok"] += 1
                return pred, p, R_PRED, True, winner, need
            self.cnt["pred_miss"] += 1                                             # Mispredict: one extra pass
        self.cnt["codec_runs"] += 3
        best = None
        for code in (CODEC_BDI, CODEC_FPC, CODEC_RAW):                              # Ties prefer the cheaper decode
            p = o[code]
            if p is not None and len(p) <= slot and (best is None or len(p) < len(best[1])):
                best = (code, p)
        reason = R_DEFAULT
        if explore:
            self.cnt["explored"] += 1
            reason = R_PRED if winner[0] == pred else R_EXPLORE
        if best is None:
            return CODEC_RAW, o[CODEC_RAW], reason, False, winner, need
        return best[0], best[1], reason, True, winner, need

    # ------------------------------------------------------------------ latency model (cycles)
    def lat_read(self, kind, slot=0, code=0):
        """Added cycles for a line read: translation + memory words + decode (assumption, not measured)."""
        words = {"zero": 0, "hot": 1, "raw": 16, "exc": 16}.get(kind, (slot + 3) // 4)
        dec = {CODEC_BDI: 2, CODEC_FPC: 3}.get(code, 0) if kind == "line" else 0
        return 1 + words + dec

    # ------------------------------------------------------------------ front end: reads
    def tick(self, page):
        """Per access bookkeeping: operation clock, heat bump and periodic decay."""
        self.clock += 1; self.accesses += 1
        pte = self.pt[page]; was_hot = pte.heat > self.cold_thr
        pte.heat = min(15, pte.heat + 1)
        if self.accesses % self.decay_n == 0:
            for p in self.pt.values(): p.heat = max(0, p.heat - 1)                  # Decay by one
            for r in self.regions.values():
                r["rd"] >>= 1; r["wr"] >>= 1; r["ovf"] >>= 1
        return was_hot

    def read_line(self, addr):
        """AXI read of one 64 B line. Returns (status, data, cycles)."""
        page, li = divmod(addr % (self.V * PAGE), PAGE)[0], (addr % PAGE) // LINE
        if not self.ctrl & CTRL_ENABLE: return SLVERR, b"", 0
        self.tick(page); self.cnt["read"] += 1
        pte = self.pt[page]; self.region(page)["rd"] = min(63, self.region(page)["rd"] + 1)
        try:
            if page in self.hbq or pte.mode == MODE_LZ:
                buf = self.hb_load(page)
                data = bytes(buf[0][li * LINE:(li + 1) * LINE]); cyc = 2 + (0 if page in self.hbq and pte.lzlen == 0 else 0)
                if pte.mode == MODE_LZ and pte.lzlen: cyc = 2 + 2 * pte.lztok + 1 * PAGE if self.cnt["lz_expand_last"] != self.cnt["lz_expand"] else 2
                self.cnt["lz_expand_last"] = self.cnt["lz_expand"]
                kind_hot = True
            elif pte.mode == MODE_ZERO:
                data, cyc = bytes(LINE), self.lat_read("zero")
            elif pte.mode == MODE_RAW:
                data, cyc = self.vread(pte.ptr, li * LINE, LINE), self.lat_read("raw")
            else:
                data = self.read_line_raw(pte, li)
                cyc = self.lat_read("exc" if pte.exc[li] else "line", pte.slot, pte.codec[li])
        except SlvErr:
            self.cnt["slverr"] += 1; self.rd_lat.append(1); return SLVERR, b"", 1
        if (self.ctrl & CTRL_DEBUG) and crc8(data) != self.crc[page][li]:
            self.status |= ST_INTEG; self.cnt["crc_fail"] += 1; self.cnt["slverr"] += 1
            self.log(page, self.state_of(pte), self.state_of(pte), R_CRC, len(pte.ptr), len(pte.ptr))
            self.rd_lat.append(cyc); return SLVERR, data, cyc
        self.rd_lat.append(cyc)
        return OKAY, data, cyc

    # ------------------------------------------------------------------ front end: writes
    def write_line(self, addr, data):
        """AXI write of one full 64 B line. Returns (status, cycles). SLVERR leaves the line unchanged."""
        assert len(data) == LINE
        page, li = (addr % (self.V * PAGE)) // PAGE, (addr % PAGE) // LINE
        if not self.ctrl & CTRL_ENABLE: return SLVERR, 0
        was_hot = self.tick(page); self.cnt["write"] += 1
        data = bytes(data)
        try:
            cyc = self._write(page, li, data, was_hot)
        except SlvErr:
            self.cnt["slverr"] += 1; self.wr_lat.append(1); self.refresh_status()
            return SLVERR, 1
        self.wr_lat.append(cyc)
        return OKAY, cyc

    def _write(self, page, li, data, was_hot):
        """Write path of spec section 10. Returns the cycle count."""
        pte = self.pt[page]
        if self.ctrl & CTRL_BYPASS:                                                 # Bypass: everything raw
            return self._write_raw(page, li, data)
        if page in self.hbq or pte.mode == MODE_LZ:                                 # Hot buffer or cold page
            buf = self.hb_load(page)
            buf[0][li * LINE:(li + 1) * LINE] = data; buf[1] = True; self.pt[page].dirty = True
            self.crc[page][li] = crc8(data); self.touched.add(page)
            self.note_write(page, None, len(best_option(data)[1]))
            return 3
        if pte.mode == MODE_ZERO:
            if not any(data):
                return 2                                                            # Zero into zero: nothing to store
            if not was_hot and self.level() >= P_CRIT:
                raise SlvErr("critical: no growth for cold page")
            return self._new_page(page, li, data)
        if pte.mode == MODE_RAW:
            return self._write_raw(page, li, data)
        return self._write_line_mode(page, li, data, was_hot)

    def _write_raw(self, page, li, data):
        """Raw page: write the line in place (bypass converts the page to raw first)."""
        pte = self.pt[page]
        if pte.mode != MODE_RAW:
            lines = [self.read_line_raw(pte, i) if pte.mode == MODE_LINE else self.decode_page(pte)[i * LINE:(i + 1) * LINE] for i in range(LPP)]
            lines[li] = data
            self.commit(page, lines, dict(mode=MODE_RAW, slot=0), R_DEFAULT)
            return 20
        self.vwrite(pte.ptr, li * LINE, data); self.crc[page][li] = crc8(data); self.touched.add(page)
        self.note_write(page, None, len(best_option(data)[1]))
        return 1 + 16 + 1

    def _new_page(self, page, li, data):
        """Mode 0 to mode 2 on the first non-zero line (spec section 8, allocate on write)."""
        slot = self.predicted_slot(page, data)
        code, pay, reason, fits, winner, need = self.select(page, data, slot)
        pte = PTE(); old = self.pt[page]
        pte.heat = old.heat; pte.mode = MODE_LINE; pte.slot = slot
        pte.exc[li] = not fits
        pte.codec[li] = code if fits else CODEC_RAW
        lines = [bytes(LINE)] * LPP; lines[li] = data
        pays = [b""] * LPP; pays[li] = pay if fits else b""
        n = need_chunks(MODE_LINE, slot, pte.nexc)
        pte.ptr = self.alloc(n, inflight=False)
        image = self.build_image(slot, pte.codec, pays, pte.exc, lines)
        self.vwrite(pte.ptr, 0, image.ljust(n * CHUNK, b"\0"))
        self.pt[page] = pte
        self.crc[page][li] = crc8(data); self.touched.add(page)
        if not fits: self.cnt["exc"] += 1; self.region(page)["ovf"] += 1
        self.note_write(page, winner[0] if self.learn_on() and winner[0] != CODEC_ZERO else None, need)
        self.log(page, (MODE_ZERO, 0, 0), (MODE_LINE, slot, n), reason if fits else R_OVERFLOW, 0, n)
        self.debug_check(page, li, data)
        return 4 + n

    def _write_line_mode(self, page, li, data, was_hot):
        """Mode 2 write: in place when it fits the slot, else exception area, else raw."""
        pte = self.pt[page]; s = pte.slot
        code, pay, reason, fits, winner, need = self.select(page, data, s)
        self.note_write(page, winner[0] if self.learn_on() and winner[0] != CODEC_ZERO else None, need)
        if fits:
            if pte.exc[li]:                                                          # Line moves back to its slot
                self._remove_exception(page, li, code, pay, data)
            else:
                self.vwrite(pte.ptr, li * s, pay.ljust(s, b"\0")); pte.codec[li] = code
            self.crc[page][li] = crc8(data); self.touched.add(page)
            self.debug_check(page, li, data)
            return 3 + (s + 3) // 4
        if pte.exc[li]:                                                              # Already an exception: overwrite
            j = sum(pte.exc[:li]); self.vwrite(pte.ptr, 16 * s + LINE * j, data)
            self.crc[page][li] = crc8(data); self.debug_check(page, li, data)
            return 3 + 16
        # New exception
        k = pte.nexc + 1
        need_ch = need_chunks(MODE_LINE, s, k)
        if need_ch > 8:                                                              # Overflow to raw
            lines = [self.read_line_raw(pte, i) for i in range(LPP)]; lines[li] = data
            self.commit(page, lines, dict(mode=MODE_RAW, slot=0), R_RAW)
            self.crc[page][li] = crc8(data)
            return 30
        if need_ch > len(pte.ptr):                                                   # Needs one more chunk
            if self.level() >= P_CRIT and not was_hot:
                raise SlvErr("critical: no growth for cold page")
            new = self.alloc(1, inflight=was_hot or self.level() < P_FULL)
        else:
            new = []
        exc_lines = {i: self.vread(pte.ptr, 16 * s + LINE * sum(pte.exc[:i]), LINE) for i in range(LPP) if pte.exc[i]}
        exc_lines[li] = data
        pte.ptr += new
        pte.exc[li] = True; pte.codec[li] = CODEC_RAW
        blob = b"".join(exc_lines[i] for i in sorted(exc_lines))
        self.vwrite(pte.ptr, 16 * s, blob)
        self.crc[page][li] = crc8(data); self.touched.add(page)
        self.cnt["exc"] += 1; self.region(page)["ovf"] = min(63, self.region(page)["ovf"] + 1)
        self.log(page, (MODE_LINE, s, need_ch - (1 if new else 0)), (MODE_LINE, s, need_ch), R_OVERFLOW, need_ch - len(new), need_ch)
        self.debug_check(page, li, data)
        return 6 + 16 + (2 if new else 0)

    def _remove_exception(self, page, li, code, pay, data):
        """An exception line now fits its slot: store it there and compact the exception area."""
        pte = self.pt[page]; s = pte.slot
        exc_lines = {i: self.vread(pte.ptr, 16 * s + LINE * sum(pte.exc[:i]), LINE) for i in range(LPP) if pte.exc[i] and i != li}
        pte.exc[li] = False; pte.codec[li] = code
        self.vwrite(pte.ptr, li * s, pay.ljust(s, b"\0"))
        blob = b"".join(exc_lines[i] for i in sorted(exc_lines))
        keep = need_chunks(MODE_LINE, s, pte.nexc)
        self.vwrite(pte.ptr, 16 * s, blob)
        extra = pte.ptr[keep:]; pte.ptr = pte.ptr[:keep]
        self.release(extra)

    def debug_check(self, page, li, data):
        """Debug mode: decode what was just stored and compare (CNT_MISMATCH must stay 0)."""
        if not self.ctrl & CTRL_DEBUG: return
        pte = self.pt[page]
        got = self.read_line_raw(pte, li) if pte.mode == MODE_LINE else data
        if got != data:
            self.cnt["mismatch"] += 1

    def write_bytes(self, addr, data):
        """Byte granular write: partial lines read, merge, then write. Returns status."""
        i = 0
        while i < len(data):
            la = (addr + i) // LINE * LINE
            off = (addr + i) - la; n = min(LINE - off, len(data) - i)
            if n == LINE:
                line = data[i:i + n]
            else:
                st, old, _ = self.read_line(la)
                if st != OKAY: return st
                line = old[:off] + data[i:i + n] + old[off + n:]                    # Merge into the old line
            st, _ = self.write_line(la, line)
            if st != OKAY: return st
            i += n
        return OKAY

    def read_bytes(self, addr, n):
        """Byte granular read. Returns (status, bytes)."""
        out = b""
        for la in range(addr // LINE * LINE, addr + n, LINE):
            st, d, _ = self.read_line(la)
            if st != OKAY: return st, out
            out += d
        s = addr - addr // LINE * LINE
        return OKAY, out[s:s + n]

    # ------------------------------------------------------------------ background tasks
    def background(self, budget=1):
        """Repack and cold compression, one step at a time, yielding to host accesses (call between ops)."""
        lv = self.refresh_status()
        want = self.explicit_repack or (self.ctrl & CTRL_REPACK)
        if lv < P_LOW and not want:
            return 0
        done = 0
        for _ in range(budget):
            try:
                if self._repack_one(R_PRESSURE if lv >= P_LOW else R_DEFAULT):
                    done += 1; continue
                if lv >= P_LOW and self._cold_lz_one():
                    done += 1; continue
            except SlvErr:
                break                                                              # No chunks to work with: try later
            if want:
                self.explicit_repack = False; self.ctrl &= ~CTRL_REPACK
            break
        return done

    def _repack_one(self, reason):
        """Finds one mode 2 or raw page that would shrink with a fresh plan and rewrites it."""
        for _ in range(self.V):
            page = self.scan; self.scan = (self.scan + 1) % self.V
            pte = self.pt[page]
            if pte.mode not in (MODE_LINE, MODE_RAW) or page in self.hbq:
                continue
            lines = [self.read_line_raw(pte, i) for i in range(LPP)] if pte.mode == MODE_LINE else [self.vread(pte.ptr, i * LINE, LINE) for i in range(LPP)]
            plan = plan_page(lines, self.min_save_pct / 100.0)
            if plan["chunks"] < len(pte.ptr):
                self.store_lines(page, lines, reason); self.cnt["repack"] += 1
                return True
        return False

    def _cold_lz_one(self):
        """Compresses one cold page (heat zero) into an LZ stream of at most 6 chunks."""
        for page, pte in self.pt.items():
            if pte.mode not in (MODE_LINE, MODE_RAW) or pte.heat > self.cold_thr or page in self.hbq:
                continue
            data = self.decode_page(pte)
            blob, tok = C.lzss_encode(data) if self.cold_algo == "lzss" else (C.xz_encode(data), 0)
            ch = need_chunks(MODE_LZ, lzlen=len(blob))
            if ch <= 6 and ch < len(pte.ptr) and 1 - ch / 8 >= self.min_save_pct / 100.0 - 1e-9:
                lines = [data[i * LINE:(i + 1) * LINE] for i in range(LPP)]
                self.commit(page, lines, dict(mode=MODE_LZ, blob=blob, algo=0 if self.cold_algo == "lzss" else 1, tok=tok), R_COLD)
                self.cnt["lz_compress"] += 1
                return True
        return False

    # ------------------------------------------------------------------ reset and recovery
    def startup_scan(self):
        """Rebuilds the free lists from the page table (reset keeps the data, loses the lists)."""
        owned = {c for p in self.pt.values() for c in p.ptr}
        before = self.free_total()
        self.free_main = sorted((c for c in range(RESERVE, self.N) if c not in owned), reverse=True)
        self.free_res = sorted((c for c in range(RESERVE) if c not in owned), reverse=True)
        self.status = 0; self.refresh_status()
        return self.free_total() - before                                           # Leaked chunks reclaimed

    # ------------------------------------------------------------------ registers
    def reg_read(self, off):
        """Reads a control register by byte offset."""
        if off == REG["ID"]: return 0x4D435001
        if off == REG["CTRL"]: return self.ctrl
        if off == REG["STATUS"]: return self.status
        if off == REG["IRQ_EN"]: return self.irq_en
        if off == REG["POOL_CHUNKS"]: return self.N
        if off == REG["FREE_CHUNKS"]: return self.free_total()
        if off == REG["EFF_CAPACITY"]: return int(self.free_total() * CHUNK * max(1.0, self.ratio()))
        if off == REG["RATIO"]: return min(0xFFFF, int(self.ratio() * 256))
        if off == REG["THRESH"]: return self.thr_low | self.thr_crit << 8
        if off == REG["POLICY0"]: return self.margin | self.explore << 8 | self.cold_thr << 16
        if off == REG["POLICY1"]: return self.region_pages | self.slot_cov << 8
        if off == REG["POLICY2"]: return self.min_save_pct | (1 if self.cold_algo == "xz" else 0) << 8
        if off == REG["FORCE"]: return self.force
        if off == REG["CNT_READ"]: return self.cnt["read"]
        if off == REG["CNT_WRITE"]: return self.cnt["write"]
        if off == REG["CNT_EXC"]: return self.cnt["exc"]
        if off == REG["CNT_REPACK"]: return self.cnt["repack"]
        if off == REG["CNT_LZ"]: return (self.cnt["lz_compress"] & 0xFFFF) | (self.cnt["lz_expand"] & 0xFFFF) << 16
        if off == REG["CNT_PRED"]: return (self.cnt["pred_made"] & 0xFFFF) | (self.cnt["pred_ok"] & 0xFFFF) << 16
        if off == REG["CNT_PTE_MISS"]: return 0
        if off == REG["CNT_MISMATCH"]: return self.cnt["mismatch"]
        if off == REG["TEL_HEAD"]: return self.tel_head
        if off == REG["TEL_TAIL"]: return self.tel_tail
        if off == REG["TEL_DATA"]: return self._tel_word()
        if off == REG["PT_ADDR"]: return self.pt_addr
        if off == REG["PT_DATA"]:
            if not self.pt_words: self.pt_words = self.pt[self.pt_addr].pack()
            return self.pt_words.pop(0)                                              # Auto-increments through the 5 words
        raise KeyError(off)

    def reg_write(self, off, val):
        """Writes a control register by byte offset."""
        if off == REG["CTRL"]:
            self.ctrl = val & 0x1F
            if val & CTRL_REPACK: self.explicit_repack = True
        elif off == REG["STATUS"]: self.status &= ~val                                # W1C
        elif off == REG["IRQ_EN"]: self.irq_en = val & 0x1F
        elif off == REG["THRESH"]: self.thr_low, self.thr_crit = val & 0xFF, (val >> 8) & 0xFF
        elif off == REG["POLICY0"]: self.margin, self.explore, self.cold_thr = val & 0xFF, (val >> 8) & 0xFF, (val >> 16) & 0xF
        elif off == REG["POLICY1"]: self.region_pages, self.slot_cov = max(1, val & 0xFF), (val >> 8) & 0xFF
        elif off == REG["POLICY2"]: self.min_save_pct, self.cold_algo = min(100, val & 0xFF), "xz" if (val >> 8) & 1 else "lzss"
        elif off == REG["FORCE"]: self.force = val & 3 if val else 0
        elif off == REG["TEL_TAIL"]: self.tel_tail = val
        elif off == REG["PT_ADDR"]: self.pt_addr = val % self.V; self.pt_words = []
        else: raise KeyError(off)

    def _tel_word(self):
        """Next 32 bit word of the telemetry event at the tail (3 words per event)."""
        idx = self.tel_tail - (self.tel_head - len(self.tel))
        if idx < 0 or idx >= len(self.tel): return 0
        t, page, old, new, reason, osz, nsz = self.tel[idx]
        words = [t & 0xFFFFFFFF, page | old[0] << 16 | new[0] << 18 | reason << 20, osz | nsz << 8 | (old[1] if old[1] < 16 else 3) << 16]
        w = words[getattr(self, "_tw", 0)]; self._tw = (getattr(self, "_tw", 0) + 1) % 3
        if self._tw == 0: self.tel_tail += 1
        return w & 0xFFFFFFFF

    # ------------------------------------------------------------------ reporting
    def used_chunks(self):
        """Chunks owned by pages."""
        return sum(len(p.ptr) for p in self.pt.values())

    def meta_bytes(self, layout="light"):
        """Page table bytes for the touched pages (36 B uniform, or 36/8/2 by mode)."""
        if layout == "uniform":
            return 36 * len(self.touched)
        return sum({MODE_ZERO: 2, MODE_RAW: 8}.get(self.pt[p].mode, 36) for p in self.touched)

    def ratio(self, layout="light"):
        """Logical bytes of touched pages over stored bytes (data chunks plus metadata)."""
        st = self.used_chunks() * CHUNK + self.meta_bytes(layout)
        return (len(self.touched) * PAGE) / st if st else 0.0

    def check(self):
        """Invariants of spec section 8, raising AssertionError on any violation."""
        owner = {}
        for page, p in self.pt.items():
            assert len(p.ptr) == need_chunks(p.mode, p.slot, p.nexc, p.lzlen), ("nchunks", page, p.mode, p.slot, p.nexc, len(p.ptr))
            assert len(set(p.ptr)) == len(p.ptr)
            for c in p.ptr:
                assert c not in owner, ("chunk owned twice", c, page, owner[c])
                owner[c] = page
            if p.mode == MODE_LINE:
                assert p.slot in SLOTS and 16 * p.slot // CHUNK + (p.nexc + 1) // 2 <= 8
            if p.hot:
                assert page in self.hbq
        free = set(self.free_main) | set(self.free_res)
        assert len(free) == len(self.free_main) + len(self.free_res), "duplicate in free list"
        assert not (free & set(owner)), "chunk both free and owned"
        assert len(free) + len(owner) == self.N, ("chunk leak", len(free), len(owner), self.N)
        assert all(c >= RESERVE for c in self.free_main) and all(c < RESERVE for c in self.free_res)
        assert len(self.hbq) <= HB_SLOTS
        return True
