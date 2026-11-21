#!/usr/bin/env python3
"""Check that each pmaports package's patches still apply to its pinned upstream.

    python3 .github/checks/apply-patches.py [package ...]

APKBUILDs write their source as ``$pkgname-$pkgver.tar.gz::<url>``, so the archive
URL has to be resolved from the shell variables the APKBUILD defines before
anything can be fetched. This does that, clones the upstream at the pinned tag
or commit and runs ``git apply --check``, which is what ``abuild prepare`` does
on the phone. Packages with no patches are skipped.

Needs git on PATH. No network access is required for packages without patches.
"""

import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

VAR = re.compile(r"\$(\{(\w+)\}|(\w+))")


def assignments(text):
    """Collect simple NAME=value assignments, including NAME=( ... ) lists."""
    found = {}
    for match in re.finditer(r"^(\w+)=(.*)$", text, re.M):
        name, value = match.group(1), match.group(2).strip()
        if value.startswith("("):
            found[name] = " ".join(
                item.strip().strip("\"'")
                for item in re.findall(r"[^\s()]+", value.strip("()")))
        else:
            found[name] = value.strip("\"'")
    return found


def expand(value, vars):
    """Substitute $var / ${var}, and the one bash parameter expansion PKGBUILDs use.

    ModemManager's source is ``#tag=${pkgver/[a-z]/-&}``: substitute the first
    lowercase letter with a dash before it ("1.24.2rc1" -> "1.24.2-rc1"). Versions
    with no lowercase letter, such as "1.24.2", come through unchanged.
    """
    def substitute_first_lower(match):
        value = vars.get(match.group(1), "")
        return re.sub(r"[a-z]", lambda m: "-" + m.group(0), value, count=1)

    value = re.sub(r"\$\{(\w+)/\[a-z\]/-&\}", substitute_first_lower, value)
    return VAR.sub(lambda m: vars.get(m.group(2) or m.group(3), ""), value)


def source_entries(text):
    """Tokens of the source list, in either form abuild and makepkg accept.

    abuild writes `source="a b c"` (usually across lines); makepkg writes the
    bash array `source=( ... )`. Both are handled.
    """
    match = re.search(r"^source=\(", text, re.M)
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

    match = re.search(r'^source="(.*?)"', text, re.S | re.M)
    if match:
        return [item.strip() for item in match.group(1).split() if item.strip()]

    return []


def upstream(path):
    """Resolve an APKBUILD's upstream to (clone_url, ref).

    The source is either `name::url` or a bare url, and the url is a forge
    archive link such as https://host/p/-/archive/v0.59.0/p-v0.59.0.tar.gz,
    https://host/p/archive/<sha>.tar.gz or .../archive/refs/tags/v1.tar.gz.
    The clone URL is the repository part and the ref is the tag or commit in it.
    """
    text = path.read_text(encoding="utf-8")
    variables = assignments(text)
    for entry in source_entries(text):
        url = entry.split("::", 1)[1] if "::" in entry else entry
        url = expand(url, variables)
        if not url.startswith(("http://", "https://")):
            continue

        # git+https://host/repo.git#tag=0.20.2
        if "#tag=" in url or "#commit=" in url:
            base, _, ref = url.replace("git+", "").rpartition("#")
            return base.split("=", 1)[1] if "=" in base and "git+" in url else base, ref.split("=", 1)[1]

        # https://host/group/project/-/archive/<ref>/<name>.tar.gz  (GitLab)
        match = re.match(r"(https://[^/]+/.+?)/-/archive/([^/]+)/", url)
        if match:
            return match.group(1), match.group(2)

        # https://host/group/project/archive/refs/tags/<ref>.tar.gz   (GitHub tags)
        match = re.match(r"(https://[^/]+/.+?)/archive/refs/tags/([^/]+?)(?:\.tar)?\.(?:gz|xz|bz2|zst)$", url)
        if match:
            return match.group(1), match.group(2)

        # https://host/group/project/archive/<ref>.tar.gz             (GitHub/GitLab)
        match = re.match(r"(https://[^/]+/.+?)(?:\.git)?/archive/([^/]+?)(?:\.tar)?\.(?:gz|xz|bz2|zst)$", url)
        if match:
            return match.group(1), match.group(2)

        # https://host/group/project/archive/<ref>/<name>.tar.gz      (GitLab)
        match = re.match(r"(https://[^/]+/.+?)/archive/([^/]+)/[^/]+$", url)
        if match:
            return match.group(1), match.group(2)

    return None


def main(packages):
    failed = False
    directories = [pathlib.Path(p) for p in packages] if packages else \
        sorted(p for p in pathlib.Path("postmarketos/pmaports").glob("*/*") if p.is_dir())

    for directory in directories:
        pkgbuild = directory / "APKBUILD"
        patches = sorted(directory.glob("*.patch"))
        if not pkgbuild.is_file() or not patches:
            continue

        found = upstream(pkgbuild)
        if not found:
            print(f"::warning file={pkgbuild}::no resolvable upstream, patches not checked")
            continue
        url, ref = found
        if not url.startswith(("http://", "https://", "ssh://")) or "$" in url:
            print(f"::warning file={pkgbuild}::unresolved source {url!r}, skipped")
            continue

        tmp = tempfile.mkdtemp()
        try:
            dest = f"{tmp}/src"
            clone = subprocess.run(["git", "clone", "-q", url, dest],
                                   capture_output=True, text=True)
            if clone.returncode:
                print(f"::warning file={pkgbuild}::cannot clone {url}, skipped")
                continue
            if ref and subprocess.run(["git", "-C", dest, "checkout", "-q", ref],
                                      capture_output=True).returncode:
                print(f"::warning file={pkgbuild}::cannot check out {ref}, using default branch")

            for patch in patches:
                check = subprocess.run(
                    ["git", "-C", dest, "apply", "--check", str(patch.resolve())],
                    capture_output=True, text=True)
                if check.returncode:
                    print(f"::error file={patch}::does not apply to {directory.name}"
                          f" at {ref or 'default branch'}: {check.stderr.strip().splitlines()[-1:]}")
                    failed = True
                else:
                    print(f"ok  {patch} -> {directory.name}@{ref or 'default'}")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
