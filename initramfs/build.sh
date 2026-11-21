#!/bin/bash
# Builds the initramfs: initramfs/build.sh <static aarch64 busybox> <output.gz>
#
# The busybox needs the telnetd and udhcpd applets. It brings up USB networking
# and an unauthenticated root shell on the USB link, then switches to the root
# filesystem on userdata. See postmarketos/GUIDE.md.
#
# Reproducible: entries are sorted, timestamps come from SOURCE_DATE_EPOCH (the
# base kernel commit's date, set by kernel/build.sh), the cpio archive is
# device-independent and gzip is told not to store a name or timestamp.
set -euo pipefail
HERE=$(dirname "$(realpath "$0")")
BUSYBOX=$(realpath "$1"); OUTPUT=$(realpath -m "$2")
ROOT=$(mktemp -d); trap 'rm -rf "$ROOT"' EXIT

: "${SOURCE_DATE_EPOCH:=0}"
export SOURCE_DATE_EPOCH

mkdir -p "$ROOT"/{bin,sbin,usr/bin,usr/sbin,dev,etc,mnt,proc,run,sys,tmp,config}
cp "$BUSYBOX" "$ROOT/bin/busybox"
# -frandom-seed keeps the embedded symbol names stable across builds
aarch64-linux-gnu-gcc -static -O2 -frandom-seed=op9-dmcreate \
	-o "$ROOT/bin/dmcreate" "$HERE/../tools/dmcreate.c"
install -m 755 "$HERE/init" "$ROOT/init"

# Normalise the tree before archiving, so ownership, modes and mtimes don't
# depend on the machine doing the build.
find "$ROOT" -exec touch -d "@$SOURCE_DATE_EPOCH" {} +
chmod -R u=rwX,go=rX "$ROOT"
chmod 755 "$ROOT/init" "$ROOT/bin/busybox" "$ROOT/bin/dmcreate"

(cd "$ROOT" && find . -print0 | LC_ALL=C sort -z |
	cpio -o -H newc --quiet --owner 0:0 --reproducible |
	gzip -9 -n) > "$OUTPUT"

echo "initramfs: $OUTPUT"
echo "initramfs_sha256=$(sha256sum "$OUTPUT" | cut -d' ' -f1)"
