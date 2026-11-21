#!/bin/bash
# Proves the initramfs build is reproducible: builds it twice into fresh temp
# directories and fails unless the two archives are byte-identical.
#
#   .github/checks/reproducible-initramfs.sh [busybox]
#
# Without an argument it fetches the pinned busybox first (the same one
# initramfs/busybox.sh builds), so this works on a clean checkout.
#
# A full kernel build takes far too long for this check; the initramfs shares
# the properties that make it reproducible (SOURCE_DATE_EPOCH, sorted archive
# entries, no embedded names or timestamps), so it is the cheap proxy.
set -euo pipefail
cd "$(dirname "$(realpath "$0")")/../.."

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT

BUSYBOX=${1:-}
if [ -z "$BUSYBOX" ]; then
	initramfs/busybox.sh "$WORK/busybox" >/dev/null
	BUSYBOX=$WORK/busybox
fi

# The same value kernel/build.sh derives from the pinned base commit.
export SOURCE_DATE_EPOCH=1792365298

initramfs/build.sh "$BUSYBOX" "$WORK/one.gz"
# A different second, in case anything still reads the clock.
sleep 2
initramfs/build.sh "$BUSYBOX" "$WORK/two.gz"

if cmp -s "$WORK/one.gz" "$WORK/two.gz"; then
	echo "reproducible: $(sha256sum "$WORK/one.gz" | cut -d' ' -f1)"
else
	echo "::error::the initramfs is not reproducible: two builds differ" >&2
	sha256sum "$WORK/one.gz" "$WORK/two.gz" >&2
	echo "  Something in the build reads the clock, the path or the filesystem order." >&2
	exit 1
fi
