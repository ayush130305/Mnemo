import sys, os as _os; _H = _os.path.dirname(_os.path.abspath(__file__)); sys.path[:0] = [_os.path.join(_H, "..", "python_files"), _os.path.join(_H, "..", "simulator")]  # Lets the scripts import each other across folders
#!/usr/bin/env python3
"""Mnemo policy study: how much does choosing a codec per page gain over any single fixed rule?"""
import os, csv, math, argparse                                     # This holds the standard library imports
import mnemo_codecs as C                                           # This holds the Mnemo codecs
import mnemo_sim as S                                              # This holds the simulator page engine (line codec page mode)

HERE = os.path.dirname(os.path.abspath(__file__))                  # This holds the folder of this script
META = 36                                                          # Page metadata bytes (20 PTE + 16 CRC)
KINDS = ["firmware", "hex_text", "ram_image", "native", "data_bin", "data_text", "control"]  # Report order


def page_options(page):
    """Returns chunk-rounded stored bytes for every way to store one 1 KB page (0 for a zero page)."""
    if not any(page):
        return dict(zero=0, line=0, lzss=0, xz=0, raw=0)           # A zero page needs no chunks in any mode
    raw = S.CH * 8                                                 # Raw page is 8 chunks
    _, ldata = S.compress_page_lines(page)                         # Line codecs with the slot/exception layout
    line = S.nchunks(len(ldata)) * S.CH
    lz = min(S.nchunks(len(C.lzss_encode(page)[0])) * S.CH, raw)   # LZSS, raw fallback
    xz = min(S.nchunks(len(C.xz_encode(page))) * S.CH, raw)        # xz, raw fallback
    return dict(zero=raw, line=line, lzss=lz, xz=xz, raw=raw)


def study(data):
    """Runs every policy over one file. Returns stored bytes (with metadata) per policy and the oracle's winner counts."""
    padded = data + bytes((-len(data)) % C.PAGE)
    pol = dict(line=0, lzss=0, xz=0, hw_fixed=0, oracle=0, oracle_cold4k=0)   # Totals per policy
    wins = dict(line=0, lzss=0, xz=0, raw=0, zero=0)               # Which option the oracle picked
    group = 0                                                      # Running oracle bytes of the current 4 KB group
    bests = []                                                     # Best stored bytes per non-zero page, for the threshold sweep
    recs = []                                                      # (kind, best data bytes) for every page, kind is 'zero' or 'data'
    for i in range(0, len(padded), C.PAGE):
        page = padded[i:i + C.PAGE]
        o = page_options(page)
        pol["line"] += o["line"] + META; pol["lzss"] += o["lzss"] + META; pol["xz"] += o["xz"] + META
        pol["hw_fixed"] += min(o["line"], o["lzss"]) + META        # The hardware design today: line codecs or LZSS
        best = min(o["line"], o["lzss"], o["xz"], o["raw"])
        pol["oracle"] += best + META
        if any(page): bests.append(best)
        recs.append(('data', best) if any(page) else ('zero', 0))
        group += best + META
        if not any(page): wins["zero"] += 1
        elif best == o["line"]: wins["line"] += 1
        elif best == o["lzss"]: wins["lzss"] += 1
        elif best == o["xz"]: wins["xz"] += 1
        else: wins["raw"] += 1
        if (i // C.PAGE) % 4 == 3 or i + C.PAGE >= len(padded):    # End of a 4 KB group: cold tier may re-code it as one xz block
            blk = padded[(i // 4096) * 4096:(i // 4096) * 4096 + 4096]
            cold = (min(S.nchunks(len(C.xz_encode(blk))) * S.CH, S.CH * 8 * (len(blk) // C.PAGE)) + META * (len(blk) // C.PAGE)) if any(blk) else META * (len(blk) // C.PAGE)
            pol["oracle_cold4k"] += min(group, cold); group = 0
    pol["_recs"] = recs; pol["_bests"] = bests; pol["_zero"] = len(padded) // C.PAGE - len(bests)   # Extra data for the sweep
    return pol, wins


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default=os.path.join(HERE, "..", "test_files"))
    ap.add_argument("--out", default=os.path.join(HERE, "..", "showcase", "results", "policy.md"))
    ap.add_argument("--meta-full", type=int, default=36, dest="meta_full", help="metadata bytes of a compressed page in the light layout")
    ap.add_argument("--meta-raw", type=int, default=8, dest="meta_raw", help="metadata bytes of a raw page in the light layout (assumed)")
    ap.add_argument("--meta-zero", type=int, default=2, dest="meta_zero", help="metadata bytes of a zero page in the light layout (assumed)")
    args = ap.parse_args()
    manifest = {r["file"]: r["kind"] for r in csv.DictReader(open(os.path.join(args.corpus, "MANIFEST.csv")))}
    allrecs = []                                                   # Every page of every file: ('zero'|'data', best data bytes)
    sweep = []; zero_pages = 0                                     # Best bytes of every non-zero page, and the zero page count
    tot = {}; wtot = dict(line=0, lzss=0, xz=0, raw=0, zero=0); raw_by = {}   # Aggregates per kind
    for name, kind in sorted(manifest.items()):
        data = open(os.path.join(args.corpus, name), "rb").read()
        pol, wins = study(data)
        a = tot.setdefault(kind, dict(raw=0, **{k: 0 for k in pol}))
        a["raw"] += len(data)
        allrecs.extend(pol.pop("_recs")); sweep.extend(pol.pop("_bests")); zero_pages += pol.pop("_zero")
        for k, v in pol.items(): a[k] += v
        for k, v in wins.items(): wtot[k] += v
        print(f"  {name:32s} oracle {pol['oracle']:8d}  hw_fixed {pol['hw_fixed']:8d}", flush=True)
    names = [("line", "Line codecs only"), ("lzss", "LZSS only"), ("xz", "xz only"), ("hw_fixed", "Hardware rule: line or LZSS per page"),
             ("oracle", "Oracle per page: line, LZSS, xz or raw"), ("oracle_cold4k", "Oracle plus 4 KB cold xz blocks")]
    md = ["# Policy study: fixed rule against per-page choice\n",
          "Stored bytes with chunk rounding and 36 B metadata per 1 KB page, ratio = raw / stored. 'Oracle' picks the smallest option for every page with perfect knowledge, so it is an upper bound for any learned policy, not something hardware can do.\n"]
    for title, keys in (("All files", KINDS),) + tuple((k, [k]) for k in KINDS):
        a = {k: sum(tot.get(kd, {}).get(k, 0) for kd in keys) for k in ["raw"] + [n for n, _ in names]}
        if not a["raw"]: continue
        md.append(f"\n## {title}\n\n| Policy | Stored B | Ratio |\n| --- | ---: | ---: |")
        for key, label in names: md.append(f"| {label} | {a[key]} | {a['raw']/max(a[key],1):.2f} |")
    allk = {k: sum(tot.get(kd, {}).get(k, 0) for kd in KINDS) for k in ["raw", "line", "lzss", "oracle_cold4k"]}
    md.append("\n## Cost of keeping data hot (all files)\n\nHot pages must stay line-compressed so a single 64 B line can be read in about 20 cycles with no page decode. "
              "Cold pages use the smallest option (LZSS, xz page or 4 KB xz block). Mix assumes the hot pages are an average sample of the data.\n"
              "\n| Hot share | Stored B | Ratio |\n| ---: | ---: | ---: |")
    for h in (0, 10, 25, 50, 75, 100):
        sz = (h * allk["line"] + (100 - h) * allk["oracle_cold4k"]) / 100
        md.append(f"| {h}% | {sz:.0f} | {allk['raw']/sz:.2f} |")
    raw_total = allk["raw"]; pages_nz = len(sweep)
    md.append("\n## Threshold layer: compress a page only if it saves at least X%\n\nBest codec per page (line, LZSS or xz page); if the saving is below X% of the 1 KB page it is stored raw instead. "
              "Raw pages need no decode on read. Chunk granularity is 12.5%, so thresholds move in steps of one chunk.\n"
              "\n| X (min saving) | Stored B | Ratio | Pages kept raw | Pages needing decode on read |\n| ---: | ---: | ---: | ---: | ---: |")
    for x in (0, 12.5, 25, 37.5, 50, 62.5, 75):
        tot_b = zero_pages * META; kept = 0
        for b in sweep:
            if 100 * (1 - b / C.PAGE) < x - 1e-9: tot_b += C.PAGE + META; kept += 1   # Saving too small: store raw
            else: tot_b += b + META
        md.append(f"| {x:g}% | {tot_b} | {raw_total/tot_b:.2f} | {100*kept/pages_nz:.1f}% | {100*(pages_nz-kept)/pages_nz:.1f}% |")
    layouts = [("Today: 36 B for every page", 36, 36, 36), (f"Light: {args.meta_full} B compressed, {args.meta_raw} B raw, {args.meta_zero} B zero", args.meta_full, args.meta_raw, args.meta_zero)]
    md.append("\n## Metadata layout: one size for every page against a size per page type\n\nSame best-codec choice per page; only the bookkeeping bytes differ. "
              "Raw and zero entry sizes in the light layout are assumptions to be checked against the real page table layout.\n"
              "\n| Min saving | " + " | ".join(f"{name} (B, ratio)" for name, *_ in layouts) + " |\n| ---: | " + " | ".join("---:" for _ in layouts) + " |")
    for x in (0, 25, 37.5, 50):
        cells = []
        for name, mf, mr, mz in layouts:
            tot_b = 0
            for kind, b in allrecs:
                if kind == "zero": tot_b += mz
                elif 100 * (1 - b / C.PAGE) < x - 1e-9 or b >= C.PAGE: tot_b += C.PAGE + mr   # Raw page (too little saving, or no saving)
                else: tot_b += b + mf
            cells.append(f"{tot_b} B, {raw_total/tot_b:.2f}")
        md.append(f"| {x:g}% | " + " | ".join(cells) + " |")
    md.append("\nWorst case, 32 KB of random data: " + " and ".join(f"{(32768 + 32 * mr)} B ({100*32*mr/32768:.1f}% over raw)" for _, _, mr, _ in layouts) + ".")
    n = sum(wtot.values())
    md.append("\n## What the oracle picked (pages)\n\n| Option | Pages | Share |\n| --- | ---: | ---: |")
    for k in ("zero", "line", "lzss", "xz", "raw"): md.append(f"| {k} | {wtot[k]} | {100*wtot[k]/n:.1f}% |")
    text = "\n".join(md); open(args.out, "w").write(text + "\n"); print(text)


if __name__ == "__main__":
    main()
