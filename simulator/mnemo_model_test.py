"""Shadow memory test for the Mnemo model: random traces, invariants after every op, special cases."""
import sys, os as _os; _H = _os.path.dirname(_os.path.abspath(__file__)); sys.path[:0] = [_os.path.join(_H, "..", "python_files"), _os.path.join(_H, "..", "simulator")]  # Lets the scripts import each other across folders
import random, sys
import mnemo_model as M

def run(trace, m, check_every=1, bg_every=8, seed=1):
    """Replays a trace against the model and a shadow dict; returns the number of mismatches."""
    sh = {}; bad = 0; rng = random.Random(seed)
    for n, (op, addr, data) in enumerate(trace):
        if op == "w":
            st, _ = m.write_line(addr, data)
            if st == M.OKAY: sh[addr] = data
        else:
            st, d, _ = m.read_line(addr)
            if st == M.OKAY and d != sh.get(addr, bytes(64)): bad += 1
        if n % bg_every == 0: m.background(1)
        if n % check_every == 0: m.check()
    m.check()
    for a, d in sh.items():                      # Final full readback
        st, x, _ = m.read_line(a)
        if st == M.OKAY and x != d: bad += 1
    return bad

def gen_line(rng, kind):
    """Makes a 64 B line of a given flavour."""
    if kind == 0: return bytes(64)
    if kind == 1: b = rng.randrange(1 << 20); return b"".join((b + rng.randrange(100)).to_bytes(4, "little") for _ in range(16))
    if kind == 2: return b"".join(rng.choice([0, 1, 5, 100, 7]).to_bytes(4, "little") for _ in range(16))
    return bytes(rng.randrange(256) for _ in range(64))

if __name__ == "__main__":
    rng = random.Random(7)
    for name, mk in [("mixed", lambda: gen_line(rng, rng.choice([0, 1, 2, 3, 1, 2]))), ("random", lambda: gen_line(rng, 3))]:
        m = M.Mnemo(n_chunks=256, v_pages=64)
        tr = []
        for _ in range(4000):
            a = rng.randrange(64 * 16) * 64
            tr.append(("w", a, mk()) if rng.random() < 0.6 else ("r", a, None))
        bad = run(tr, m)
        print(name, "bad", bad, "ratio %.2f" % m.ratio(), dict(m.cnt))
