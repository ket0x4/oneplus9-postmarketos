#!/usr/bin/env python3
"""Check the .desktop launchers, the image builder's unit list and the symlinks.

    python3 .github/checks/desktop-entries.py

The `units` job in checks.yml proves that every Exec*= in a systemd unit points
at something that exists. Nothing did the same for the other places that name
programs or files, and all three have broken the tree before:

  * a .desktop launcher whose Exec names a binary that is not in rootfs/ (the
    launcher then appears in the app grid and silently does nothing),
  * `populate-mounted-rootfs.sh`'s list of units to enable, which names a
    service that no longer exists (the image builds, but that service is never
    started on the phone), and
  * the pmaports symlinks into patches/<pkg>/, which go dangling if a patch is
    moved or deleted (git is happy; abuild fails on the phone).

The Exec rule is the same one the units job uses: a file under rootfs/ at that
path, or a tool compiled from tools/. System binaries (/usr/bin/...) are accepted
only if .github/checks/system-binaries.txt lists them, so a typo there is caught.
"""

import os
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(".")
ROOTFS = ROOT / "rootfs"
ALLOWLIST = pathlib.Path(".github/checks/system-binaries.txt")
IMAGE_BUILDER = ROOT / "postmarketos" / "build-pmos-image.sh"

# The .desktop files this repository owns. Anything under rootfs/ counts.
DESKTOP_GLOBS = ("rootfs/**/*.desktop",)

# systemd runs a unit's Exec through a shell only for ExecStart= without a path,
# so a .desktop Exec may carry arguments; only the program matters here.
EXEC = re.compile(r"^Exec=(.*)$", re.M)

# populate-mounted-rootfs.sh enables units by name, in two loop lists and a
# couple of explicit ln -sfn calls.
UNIT_NAME = re.compile(r"\b([a-z0-9@._-]+\.(?:service|timer|target))\b")


def allowlisted():
    try:
        return {line.strip() for line in ALLOWLIST.read_text().splitlines()
                if line.strip() and not line.startswith("#")}
    except OSError:
        return set()


def executable_exists(program, allowed):
    """The same rule checks.yml's units job applies, for one program path."""
    if program.startswith("/usr/local/bin/"):
        name = program.rsplit("/", 1)[1]
        return ((ROOTFS / program.lstrip("/")).exists()
                or (ROOT / "tools" / f"{name}.c").exists()
                or (ROOT / "tools" / "bringup" / f"{name}.c").exists())
    if program.startswith(("/usr/bin/", "/usr/sbin/")):
        return program in allowed
    # A bare name would be found on PATH at runtime; resolve it against rootfs/
    # so a launcher for a program this repository ships is still checked.
    return (ROOTFS / "usr/local/bin" / program).exists() or program in allowed


def split_exec(value):
    """The program an Exec line runs, dropping the field-code prefixes and args.

    %f/%F/%u/... are the launcher's own substitutions; they never name a program.
    """
    value = value.strip()
    value = re.sub(r"^([+@!:-]+)", "", value)
    if not value:
        return None
    return value.split()[0]


def check_desktop_entries(allowed):
    problems = []
    files = sorted({p for pattern in DESKTOP_GLOBS for p in ROOT.glob(pattern)})
    for path in files:
        text = path.read_text(encoding="utf-8", errors="replace")
        matches = EXEC.findall(text)
        if not matches:
            problems.append(f"{path}: no Exec line")
            continue
        for value in matches:
            program = split_exec(value)
            if program is None:
                continue
            if not executable_exists(program, allowed):
                problems.append(f"{path}: Exec runs {program}, which does not exist in rootfs/")
    return files, problems


# populate-mounted-rootfs.sh enables units three ways: two `for <var> in ...`
# lists, and explicit `ln -sfn /etc/systemd/{system,user}/<unit>` calls. Only
# those name units the image then tries to start; the .wants directory paths and
# the standard targets are not units of this repository.
ENABLE_LOOP = re.compile(r"for\s+\w+\s+in\s+([^;]+);\s*do")
UNIT_IN_ETC = re.compile(r"ln\s+-sfn\s+\"?/etc/systemd/(?:system|user)/([a-z0-9@._-]+\.(?:service|timer|target))")

# Units the populate script enables that postmarketOS itself ships, so their
# files are not in this repository.
EXTERNAL_UNITS = {"mmsd-tng.service"}


def check_image_builder():
    """Units the populate script enables must have a unit file in rootfs/."""
    problems = []
    try:
        text = IMAGE_BUILDER.read_text(encoding="utf-8")
    except OSError:
        return problems
    unit_files = {p.name for p in ROOTFS.glob("etc/systemd/**/*")
                  if p.suffix in (".service", ".timer", ".target")}
    named = set(UNIT_IN_ETC.findall(text))
    for group in ENABLE_LOOP.findall(text):
        named |= set(UNIT_NAME.findall(group))
    for name in sorted(named):
        if name in EXTERNAL_UNITS:
            continue
        if name not in unit_files:
            problems.append(f"{IMAGE_BUILDER}: enables {name}, which is not in rootfs/etc/systemd")
    return problems


def check_symlinks():
    """Every tracked symlink must resolve.

    The pmaports packages reach their patches through symlinks into patches/<pkg>/,
    which is where abuild finds them. Deleting or moving a patch without updating
    the link leaves a dangling entry that git is happy with and that only shows up
    when abuild fails on the phone, so check them here.
    """
    problems = []
    try:
        out = subprocess.run(["git", "ls-files", "-s"], capture_output=True, text=True,
                             check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return problems                      # not a git checkout: nothing to compare
    for line in out.splitlines():
        parts = line.split("\t", 1)
        if len(parts) != 2:
            continue
        mode, path = parts[0].split()[0], parts[1]
        if mode != "120000":                 # 120000 is a symlink
            continue
        if not os.path.exists(path):
            target = os.readlink(path) if os.path.islink(path) else "?"
            problems.append(f"{path}: dangling symlink -> {target}")
    return problems


def main():
    allowed = allowlisted()
    files, problems = check_desktop_entries(allowed)
    problems += check_image_builder()
    problems += check_symlinks()
    for problem in problems:
        print(f"::error::{problem}")
    print(f"checked {len(files)} .desktop launchers, {IMAGE_BUILDER} and the tracked symlinks")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
