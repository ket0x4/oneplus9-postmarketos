#!/usr/bin/env python3
"""Check every APKBUILD under postmarketos/pmaports for metadata and checksum hygiene.

    python3 .github/checks/apkbuild-sums.py

Rules:
  * source entries fetched over http(s), and every patch, must have a real
    checksum; SKIP is allowed only for git+ sources (the commit is the pin).
  * the source and checksum arrays must have the same number of entries.
  * pkgname, pkgver, pkgrel, arch, license, source and a checksum array must
    exist, and arch must be aarch64.

The checksum array is a whitespace-separated block in abuild, not a bash array,
so it is parsed as a here-document-style string.
"""

import pathlib
import re
import sys

REQUIRED = ("pkgname", "pkgver", "pkgrel", "arch", "license", "source")
SUM_KEYS = ("sha512sums", "sha256sums", "b2sums")


def array(text, key):
    """Return the tokens of a source list, however abuild writes it.

    abuild packages write `source="a b c"` or a multi-line quoted string, not the
    bash array `source=( ... )` a PKGBUILD uses, so both forms are accepted.
    """
    match = re.search(rf"^{key}=\(", text, re.M)
    if match:
        depth, index, body = 1, match.end(), []
        while index < len(text) and depth:
            char = text[index]
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
                if not depth:
                    break
            body.append(char)
            index += 1
        return [item.strip().strip("\"'") for item in "".join(body).split() if item.strip()]

    match = re.search(rf'^{key}="(.*?)"', text, re.S | re.M)
    if match:
        return [item.strip() for item in match.group(1).split() if item.strip()]

    match = re.search(rf"^{key}=(\S+)$", text, re.M)
    if match:
        return [match.group(1).strip("\"'")]

    return None


def sums_block(text):
    """abuild writes checksums as `sha512sums="\\n<sum>  <file>\\n..."`."""
    for key in SUM_KEYS:
        match = re.search(rf'^{key}="(.*?)"', text, re.S | re.M)
        if not match:
            continue
        rows = []
        for line in match.group(1).splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split(None, 1)
            if len(parts) == 2:
                rows.append((parts[0], parts[1]))
        return key, rows
    return None, []


def check(path):
    text = path.read_text(encoding="utf-8")
    problems = []

    for key in REQUIRED:
        if not re.search(rf"^{key}=", text, re.M):
            problems.append(f"no {key}")

    if not re.search(r'^arch="?aarch64"?', text, re.M):
        problems.append("arch is not aarch64")

    key, rows = sums_block(text)
    if key is None:
        problems.append("no checksum block")
        return problems

    source = array(text, "source") or []
    if len(source) != len(rows):
        problems.append(f"source has {len(source)} entries but {key} has {len(rows)}")

    for entry, (value, name) in zip(source, rows):
        fetched = entry.startswith(("http://", "https://")) or name.endswith(".patch")
        if fetched and value == "SKIP":
            problems.append(f"source {name} is fetched or a patch and has SKIP")

    return problems


def main():
    failed = False
    paths = sorted(pathlib.Path("postmarketos/pmaports").glob("*/*/APKBUILD"))
    for path in paths:
        for problem in check(path):
            print(f"::error file={path}::{problem}")
            failed = True
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
