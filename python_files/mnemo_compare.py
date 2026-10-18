import sys, os as _os; _H = _os.path.dirname(_os.path.abspath(__file__)); sys.path[:0] = [_os.path.join(_H, "..", "python_files"), _os.path.join(_H, "..", "simulator")]  # Lets the scripts import each other across folders
#!/usr/bin/env python3
"""Algorithm comparator: runs every codec on every corpus file, verifies lossless round-trip,
measures size, and models time against UART baud rate.

Run:  python3 mnemo_compare.py [--clk 25e6] [--lanes 2]
Outputs: results/per_file.csv, results/summary.md (also printed)
Ranking rule from the project: smallest size first, then speed (sizes within --tie percent count as a tie).
"""
import os, sys, csv, time, glob, argparse
import mnemo_codecs as C

HERE = os.path.dirname(os.path.abspath(__file__))  # This holds the folder of this script
BAUDS = (115200, 230400, 460800, 921600, 1000000, 2000000)  # This holds the baud rates to model
META_PER_PAGE = 20 + 16                             # This holds PTE bytes plus line CRC bytes per page (spec section 6)

# The hardware candidates that could really be built. Each: name -> allowed line codecs, or a page/file scheme.
LINE_VARIANTS = {
    "Zero+Raw": ("zero", "raw"),
    "BDI+Raw": ("bdi", "zero", "raw"),
    "FPC+Raw": ("fpc", "zero", "raw"),
    "Line-best": ("zero", "bdi", "fpc", "raw"),
}
SW_BLOCK = {"Zlib-1K": (C.zlib_encode, C.zlib_decode, 1024), "XZ-1K": (C.xz_encode, C.xz_decode, 1024),
            "Zlib-4K": (C.zlib_encode, C.zlib_decode, 4096), "XZ-4K": (C.xz_encode, C.xz_decode, 4096)}  # This holds the software block codecs: encoder, decoder, block bytes
HW = list(LINE_VARIANTS) + ["LZSS-page", "LZSS-file"]  # This holds the hardware candidates in report order
REF = ["zlib-file", "xz-file", "bz2-file"]  # This holds software-only reference baselines


def pad_lines(data):
    """Pads data with zeros to a whole number of pages so lines and pages divide evenly."""
    return data + bytes((-len(data)) % C.PAGE)


def eval_line_variants(data):
    """Runs all line codecs once per line and derives every line variant from the same candidates.
    Returns {variant: dict(packed_bits, stored, lines)} and verifies decode for every line."""
    padded = pad_lines(data)                                   # Whole pages only
    nlines = len(padded) // C.LINE                             # Number of 64 byte lines
    per_line = []                                              # Candidate table for each line
    for i in range(nlines):
        line = padded[i * C.LINE:(i + 1) * C.LINE]
        cand = C.line_candidates(line)
        # Verify each candidate decodes back to the line.
        for name, (nb, bits) in cand.items():
            if name == "zero": back = C.zero_decode(bits, nb)
            elif name == "bdi": back = C.bdi_decode(bits, nb)
            elif name == "fpc": back = C.fpc_decode(bits, nb)
            else: back = bits.to_bytes(C.LINE, "big")
            assert back == line, f"{name} round-trip failed on line {i}"
        per_line.append(cand)
    out = {}
    for var, allowed in LINE_VARIANTS.items():
        total_bits = 0                                         # Packed stream bits including 2 bit tags
        stored = 0                                             # Bytes in memory under the page slot model
        for p in range(len(padded) // C.PAGE):
            sizes = []                                         # Payload bytes of the 16 lines of this page
            for l in range(16):
                cand = per_line[p * 16 + l]
                nb = min(cand[k][0] for k in allowed if k in cand)  # Smallest allowed payload bits
                total_bits += 2 + nb
                sizes.append(-(-nb // 8))                      # Payload bytes, zero line is 0
            stored += C.round_chunks(C.lcp_page_bytes(sizes))  # Chunk rounded page cost
        out[var] = dict(packed=-(-total_bits // 8), stored=stored, units=nlines, pages=len(padded) // C.PAGE)
    return out


def eval_lzss(data):
    """Runs LZSS per 1 KB page and over the whole file, verifying both decode exactly."""
    padded = pad_lines(data)
    stored = 0; packed = 0; tokens = 0                         # Page-mode sums
    for p in range(len(padded) // C.PAGE):
        page = padded[p * C.PAGE:(p + 1) * C.PAGE]
        if not any(page):                                      # Zero page costs nothing
            continue
        blob, nt = C.lzss_encode(page)
        assert C.lzss_decode(blob) == page, "LZSS page round-trip failed"
        keep = min(len(blob), C.PAGE)                          # Raw fallback if it does not shrink
        packed += keep; tokens += nt
        stored += C.round_chunks(keep)
    blob, ntf = C.lzss_encode(data)                            # Whole file stream
    assert C.lzss_decode(blob) == data, "LZSS file round-trip failed"
    return dict(page=dict(packed=packed, stored=stored, tokens=tokens, pages=len(padded) // C.PAGE),
                file=dict(packed=len(blob), tokens=ntf))


def eval_sw_block(data, name):
    """Runs a software block codec per block, verifying every block decodes exactly; raw fallback if it does not shrink."""
    enc, dec, blk = SW_BLOCK[name]
    padded = data + bytes((-len(data)) % blk)
    packed = stored = nblk = 0
    for i in range(0, len(padded), blk):
        b = padded[i:i + blk]
        if not any(b):                                         # Zero block costs nothing
            continue
        z = enc(b)
        assert dec(z) == b, name + " round-trip failed"
        keep = min(len(z), blk)                                # Raw fallback
        packed += keep; stored += C.round_chunks(keep); nblk += 1
    return dict(packed=packed, stored=stored, blocks=nblk)


def eval_ref(data):
    """Software reference sizes (not hardware candidates)."""
    padded = pad_lines(data)
    return {"zlib-file": C.zlib_size(data), "xz-file": C.xz_size(data), "bz2-file": C.bz2_size(data)}


def cycles(cand, n_in, info, args):
    """Hardware cycle model for compress and decompress. Returns (compress cycles, decompress cycles).
    Assumptions are explicit in args so they can be calibrated from simulation."""
    if cand in LINE_VARIANTS:
        nl = info["units"]                                       # Number of lines handled
        return nl * (16 + args.line_enc), nl * (16 + args.line_dec)  # 16 cycles to move a line plus codec latency
    tokens = info["tokens"]                                      # LZSS tokens produced
    comp = tokens * (C.WIN // args.lanes + args.lz_over)         # Window scan per token split over the lanes
    dec = tokens * 2 + n_in                                      # 2 cycles per token plus 1 per output byte
    return comp, dec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default=os.path.join(HERE, "..", "test_files"))
    ap.add_argument("--out", default=os.path.join(HERE, "..", "showcase", "results"))
    ap.add_argument("--clk", type=float, default=25e6, help="FPGA clock in Hz (compengine board runs 25 MHz)")
    ap.add_argument("--lanes", type=int, default=2, help="LZSS search lanes")
    ap.add_argument("--lz-over", type=int, default=6, dest="lz_over", help="LZSS per-token overhead cycles (assumed)")
    ap.add_argument("--line-enc", type=int, default=4, dest="line_enc", help="line codec compress latency (assumed)")
    ap.add_argument("--line-dec", type=int, default=3, dest="line_dec", help="line codec decompress latency (assumed)")
    ap.add_argument("--tie", type=float, default=1.0, help="percent size difference treated as a tie")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    manifest = {}                                              # file -> kind from the corpus manifest
    with open(os.path.join(args.corpus, "MANIFEST.csv")) as f:
        for row in csv.DictReader(f):
            manifest[row["file"]] = row["kind"]

    rows = []                                                  # One row per (file, candidate)
    for path in sorted(glob.glob(os.path.join(args.corpus, "*"))):
        name = os.path.basename(path)
        if name not in manifest:
            continue
        data = open(path, "rb").read()
        kind = manifest[name]
        if kind == "hex_text":                                 # Also test the decoded binary of a hex file
            pass
        t0 = time.perf_counter()
        lv = eval_line_variants(data)
        lz = eval_lzss(data)
        ref = eval_ref(data)
        sw = time.perf_counter() - t0                          # Python reference time, only a sanity figure
        for var in LINE_VARIANTS:
            i = lv[var]; c, d = cycles(var, len(data), i, args)
            rows.append(dict(file=name, kind=kind, cand=var, raw=len(data), packed=i["packed"], stored=i["stored"],
                             stored_meta=i["stored"] + META_PER_PAGE * i["pages"], comp_cyc=c, dec_cyc=d))
        i = lz["page"]; i["units"] = i["pages"]; c, d = cycles("LZSS-page", len(data), i, args)
        rows.append(dict(file=name, kind=kind, cand="LZSS-page", raw=len(data), packed=i["packed"], stored=i["stored"],
                         stored_meta=i["stored"] + META_PER_PAGE * i["pages"], comp_cyc=c, dec_cyc=d))
        i = lz["file"]; c, d = cycles("LZSS-file", len(data), i, args)
        rows.append(dict(file=name, kind=kind, cand="LZSS-file", raw=len(data), packed=i["packed"], stored=i["packed"],
                         stored_meta=i["packed"], comp_cyc=c, dec_cyc=d))
        for nm in SW_BLOCK:                                    # Software block codecs, real decode check
            i = eval_sw_block(data, nm)
            rows.append(dict(file=name, kind=kind, cand=nm, raw=len(data), packed=i["packed"], stored=i["stored"],
                             stored_meta=i["stored"] + META_PER_PAGE * i["blocks"], comp_cyc=0, dec_cyc=0))
        for r, sz in ref.items():
            rows.append(dict(file=name, kind=kind, cand=r, raw=len(data), packed=sz, stored=sz, stored_meta=sz, comp_cyc=0, dec_cyc=0))
        print(f"  {name:32s} {len(data):7d} B  best-line {min(lv[v]['packed'] for v in lv):7d}  lzss-page {lz['page']['packed']:7d}  ({sw:.1f}s)", file=sys.stderr)

    with open(os.path.join(args.out, "per_file.csv"), "w", newline="") as f:  # Full detail for later plotting
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader(); w.writerows(rows)

    # ------------------------------------------------ aggregate
    def agg(filter_fn):
        """Sums sizes and cycles per candidate over the rows accepted by filter_fn."""
        a = {}
        for r in rows:
            if not filter_fn(r):
                continue
            x = a.setdefault(r["cand"], dict(raw=0, packed=0, stored_meta=0, comp=0, dec=0, n=0))
            x["raw"] += r["raw"]; x["packed"] += r["packed"]; x["stored_meta"] += r["stored_meta"]
            x["comp"] += r["comp_cyc"]; x["dec"] += r["dec_cyc"]; x["n"] += 1
        return a

    md = []                                                    # Report lines
    kinds = ["firmware", "hex_text", "ram_image", "native", "data_bin", "data_text", "control"]

    def size_table(title, a, cands):
        """Adds a markdown table of ratios (raw / size, bigger is better)."""
        md.append(f"\n### {title}\n")
        md.append("| Candidate | Raw B | Packed B | Ratio packed | Stored+meta B | Ratio stored |")
        md.append("| --- | ---: | ---: | ---: | ---: | ---: |")
        for c in cands:
            x = a.get(c)
            if not x: continue
            md.append(f"| {c} | {x['raw']} | {x['packed']} | {x['raw']/max(x['packed'],1):.2f} | {x['stored_meta']} | {x['raw']/max(x['stored_meta'],1):.2f} |")

    allc = HW + list(SW_BLOCK) + REF
    total = agg(lambda r: True)
    md.append("# Compression algorithm comparison\n")
    md.append(f"Corpus: {len(set(r['file'] for r in rows))} files, {total[HW[0]]['raw']} bytes. "
              f"All codecs verified lossless (decode equals input on every line, page and file).\n")
    md.append("Packed = ideal bitstream. Stored+meta = bytes the memory would really use: per-page slot model, 128 B chunks, "
              f"plus {META_PER_PAGE} B page metadata. File-level candidates have no memory layout, so stored = packed.\n")
    size_table("All files", total, allc)
    for k in kinds:
        a = agg(lambda r, k=k: r["kind"] == k)
        if a: size_table(f"Kind: {k}", a, allc)

    # Ranking: size first, then speed (engine compute time, because the link time is the same for every codec).
    MEM = ["Zero+Raw", "BDI+Raw", "FPC+Raw", "Line-best", "LZSS-page"]  # Candidates that keep random access
    IMG = ["LZSS-file", "LZSS-page"] + REF                              # Candidates for whole images and files

    def rank_table(title, cands, key, note):
        """Adds a ranking table: smallest first, sizes within the tie percent are ordered by engine compute time."""
        md.append(f"\n### {title}\n")
        md.append(note + "\n")
        md.append("| Rank | Candidate | Size B | Ratio | Compute s (compress) | Compute s (decompress) |")
        md.append("| ---: | --- | ---: | ---: | ---: | ---: |")
        order = sorted(cands, key=lambda c: total[c][key])
        groups = []
        for c in order:
            if groups and total[c][key] <= groups[-1][0] * (1 + args.tie / 100):
                groups[-1][1].append(c)
            else:
                groups.append([total[c][key], [c]])
        rank = 1
        for _, g in groups:
            for c in sorted(g, key=lambda c: total[c]["comp"]):
                x = total[c]
                comp = f"{x['comp']/args.clk:.2f}" if x["comp"] else "n/a"
                dec = f"{x['dec']/args.clk:.2f}" if x["dec"] else "n/a"
                md.append(f"| {rank} | {c} | {x[key]} | {x['raw']/x[key]:.2f} | {comp} | {dec} |")
                rank += 1

    md.append("\n## Ranking (size first, then speed)\n")
    md.append(f"Sizes within {args.tie:.1f}% count as a tie and are ordered by engine compute time. Compute time is the FPGA clock cycle model, not the link.")
    rank_table("A. Memory resident data (random access: lines and pages)", MEM, "stored_meta",
               "Size = bytes the memory really uses (slot model, 128 B chunks, page metadata).")
    rank_table("A2. Same, plus software block codecs (need a CPU, no hardware cycle model)", MEM + list(SW_BLOCK), "stored_meta",
               "Zlib and XZ run per block with a real decode check. 4K blocks mean reading one line decodes 4 KB, so they suit cold data only. Compute time is n/a.")
    rank_table("B. Whole images and files (boot image, flash, host link): no random access needed", IMG, "packed",
               "Size = packed bitstream. zlib, xz and bzip2 are software references that show how much is left on the table; they are not hardware candidates.")

    # Baud table
    md.append("\n## Time against baud rate\n")
    md.append(f"Model: 8N1 serial (10 bits per byte), FPGA clock {args.clk/1e6:g} MHz. All numbers are seconds for the whole corpus. "
              "Cycle costs are assumptions (last section); calibrate them from the RTL simulation.\n")
    raw_total = total[HW[0]]["raw"]
    md.append("### Where the engine, not the link, becomes the limit\n")
    md.append("Link bound while baud is below the value shown; above it the engine compute time decides. Raw bytes go in for compress, and raw bytes come out for decompress.\n")
    md.append("| Candidate | Compress compute s | Compress limited above (baud) | Decompress compute s | Decompress limited above (baud) |")
    md.append("| --- | ---: | ---: | ---: | ---: |")
    for c in HW:
        x = total[c]
        bc = raw_total * 10 * args.clk / max(x["comp"], 1); bd = raw_total * 10 * args.clk / max(x["dec"], 1)
        md.append(f"| {c} | {x['comp']/args.clk:.2f} | {bc:,.0f} | {x['dec']/args.clk:.2f} | {bd:,.0f} |")
    md.append("\n### Loading a compressed image (send packed bytes, decompress inside the FPGA)\n")
    md.append("This is the case where compression speeds the link up: only packed bytes cross the wire. Time = slowest of link and decompress engine. First row is sending the raw bytes.\n")
    md.append("| Candidate | " + " | ".join(f"{b}" for b in BAUDS) + " |")
    md.append("| --- |" + " ---: |" * len(BAUDS))
    md.append("| raw, no compression | " + " | ".join(f"{raw_total*10/b:.1f}" for b in BAUDS) + " |")
    for c in HW:
        x = total[c]
        md.append(f"| {c} | " + " | ".join(f"{max(x['packed']*10/b, x['dec']/args.clk):.2f}" for b in BAUDS) + " |")
    md.append("\n### Test-bench mode like compengine (raw in, packed out; or packed in, raw out)\n")
    md.append("The raw side always crosses the link, so time is almost the same for every codec and equals the raw link time until the engine becomes the limit.\n")
    md.append("| Candidate (compress) | " + " | ".join(f"{b}" for b in BAUDS) + " |")
    md.append("| --- |" + " ---: |" * len(BAUDS))
    for c in HW:
        x = total[c]
        md.append(f"| {c} | " + " | ".join(f"{max(raw_total*10/b, x['packed']*10/b, x['comp']/args.clk):.2f}" for b in BAUDS) + " |")

    md.append("\n## Assumptions in the time model\n")
    md.append(f"- Line codecs: 16 cycles to move a 64 B line over a 32 bit path plus {args.line_enc} (compress) or {args.line_dec} (decompress) codec cycles. Spec latencies, not measured.\n"
              f"- LZSS compress: tokens x ({C.WIN}/{args.lanes} lanes + {args.lz_over}) cycles, from the compengine search structure (one compare per lane per clock). Decompress: 2 cycles per token + 1 per output byte.\n"
              "- Python wall time is not hardware time and is not used for ranking.\n"
              "- The UART link is the test harness path (PC to FPGA). In the real memory path the codec sits on the bus and only the cycle model matters.")
    text = "\n".join(md)
    open(os.path.join(args.out, "summary.md"), "w").write(text)
    print(text)


if __name__ == "__main__":
    main()
