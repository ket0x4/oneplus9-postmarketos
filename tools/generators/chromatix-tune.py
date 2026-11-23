#!/usr/bin/env python3
"""Inspect a CamX tuning blob for the data libcamera's soft ISP can use.

The stock camera tuning (``com.qti.tuned.<module>.bin``) is a "Parameter
Parser V3" file: a header at 0xa8 lists sections as (type, offset, size)
triples; section 1 holds node records, section 2 the data. A node record is
``<id u32><name char[40]><0xffffffff><data offset><size>``.

This tool lists and dumps nodes so the lens-shading grids and the AWB colour
gain / prior curves can be pulled out and turned into libcamera tuning:

  chromatix-tune.py <bin> --list
        every node, its size and a guess at its element type.

  chromatix-tune.py <bin> --dump <name-substring> [--type f32|f64|u32]
        print the values of the first node whose name contains the substring.

  chromatix-tune.py <bin> --lsc <name-substring> --grid 17
        reshape a node to grid*grid*3 and print a libcamera `Lsc` YAML block
        (three channels, ``r``/``g``/``b``). Node channel order is the order
        the blob stores; check ``--dump`` first.

  chromatix-tune.py <bin> --awb <name-substring> --ct <name-substring>
        print a ``colourGains`` curve (ct -> r,gain,b) when the gains and the
        colour-temperature table are separate nodes.

The node names differ between modules and tuning revisions, so start with
``--list`` and look for names containing rolloff/shading/lsc/mesh (lens
shading) and awb/gain/ct (white balance).
"""
import re
import struct
import sys


def parse_nodes(path):
    b = open(path, "rb").read()
    sec = struct.unpack_from("<9I", b, 0xa8)
    nodes_off, nodes_size = sec[1], sec[2]
    data_off = sec[4]

    nodes = []
    p = nodes_off
    end = nodes_off + nodes_size
    while p + 56 <= end:
        if struct.unpack_from("<I", b, p + 44)[0] != 0xFFFFFFFF:
            p += 4
            continue
        name = b[p + 4:p + 44].split(b"\0")[0]
        off, size = struct.unpack_from("<II", b, p + 48)
        if name and name.isascii() and name[:1].isalpha():
            nodes.append((name.decode(), data_off + off, size))
        p += 56
    return b, nodes


def guess_type(raw, size):
    if size == 0:
        return "empty"
    # Chromatix stores its matrices and curves as float32.
    if size % 4 == 0:
        vals = struct.unpack_from("<%df" % (size // 4), raw)
        if all(abs(v) < 1e6 for v in vals) and any(v != 0 for v in vals):
            return "f32"
        return "u32"
    return "bytes"


def values(raw, size, kind):
    if kind == "f64":
        return list(struct.unpack_from("<%dd" % (size // 8), raw))
    if kind == "f32":
        return list(struct.unpack_from("<%df" % (size // 4), raw))
    if kind == "u32":
        return list(struct.unpack_from("<%dI" % (size // 4), raw))
    return list(raw)


def main(argv):
    if len(argv) < 3:
        print(__doc__)
        return 1
    path = argv[1]
    opt = argv[2]
    b, nodes = parse_nodes(path)

    if opt == "--list":
        for name, off, size in nodes:
            raw = b[off:off + size]
            print("%-44s %6d  %s" % (name, size, guess_type(raw, size)))
        return 0

    if opt in ("--dump", "--lsc", "--awb"):
        pat = argv[3]
        matches = [n for n in nodes if pat.lower() in n[0].lower() and n[2]]
        if not matches:
            print("no node matches %r; run --list" % pat)
            return 1
        name, off, size = max(matches, key=lambda n: n[2])

        kind = None
        if "--type" in argv:
            kind = argv[argv.index("--type") + 1]
        raw = b[off:off + size]
        kind = kind or guess_type(raw, size)
        vals = values(raw, size, kind)

        if opt == "--dump":
            print("# %s: %d values (%s)" % (name, len(vals), kind))
            for i in range(0, len(vals), 8):
                print("  " + " ".join("%g" % v for v in vals[i:i + 8]))
            return 0

        if opt == "--lsc":
            grid = int(argv[argv.index("--grid") + 1]) if "--grid" in argv else 17
            ct = int(argv[argv.index("--ct") + 1]) if "--ct" in argv else 6500
            # softisp stores LSC as UQ<2, 6> register values: 64 == 1.0.
            scale = float(argv[argv.index("--scale") + 1]) if "--scale" in argv else 64.0
            need = grid * grid * 3
            if len(vals) < need:
                print("# %s has %d values, need %d for %dx%d RGB"
                      % (name, len(vals), need, grid, grid))
                return 1
            print("  - Lsc:")
            print("      sets:")
            print("        - ct: %d" % ct)
            for ch, cname in enumerate("rgb"):
                flat = [vals[(y * grid + x) * 3 + ch] for y in range(grid)
                        for x in range(grid)]
                flat = [max(0, min(255, int(round(v * scale)))) for v in flat]
                print("          %s: [ %s ]" % (cname, ", ".join(str(v) for v in flat)))
            return 0

        if opt == "--awb":
            print("# %s: %d values (%s)" % (name, len(vals), kind))
            for i in range(0, len(vals), 8):
                print("  " + " ".join("%g" % v for v in vals[i:i + 8]))
            return 0

    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
