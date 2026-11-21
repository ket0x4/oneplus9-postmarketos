#!/usr/bin/env python3
"""Fail on broken relative links and absolute local paths in the Markdown files.

Run from the repository root, by hand or from CI:

    python3 .github/checks/docs-links.py

Only relative links are checked; http(s), mailto and in-page anchors are left
alone, as are anchor fragments (resolving those needs a Markdown renderer).
"""

import pathlib
import re
import sys

LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
SKIP = re.compile(r"^[a-z]+://|^mailto:|^#")


def markdown_files():
    yield from pathlib.Path(".").glob("*.md")
    yield from pathlib.Path("docs").rglob("*.md")
    yield from pathlib.Path("postmarketos").rglob("*.md")


def main():
    failed = False
    for md in markdown_files():
        text = md.read_text(encoding="utf-8")
        for match in LINK.finditer(text):
            link = match.group(1)
            if SKIP.match(link):
                continue
            target = (md.parent / link.split("#", 1)[0]).resolve()
            if not target.exists():
                print(f"::error file={md}::broken link {link}")
                failed = True
        if "file:///home/" in text:
            print(f"::error file={md}::absolute local path in a link")
            failed = True
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
