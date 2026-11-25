#!/bin/bash
# Builds the OnePlus 9 / 9 Pro kernel: Linux v7.3 plus patches/kernel.
#
#   kernel/build.sh [workdir]        default workdir: ./work
#
# TOOLCHAIN=gcc|clang            compiler suite. Default is gcc. The clang path
#                                builds with ThinLTO, but that kernel does not
#                                boot on this phone (it dies before the ramoops
#                                console is up, so there is no log to read); the
#                                toolchain is only kept for testing it.
# KERNEL_GIT=<url>               where to fetch the kernel from
# KERNEL_COMMIT=<sha>            the base commit to build on (default: the one
#                                pinned below). This is the commit, not the tag
#                                name: tags can be moved or re-pointed.
# JOBS=<n>                       parallel jobs
# SOURCE_DATE_EPOCH=<secs>       build timestamp (default: the base commit's date)
# KERNEL_LOCALVERSION=<suffix>   appended to the release name (kernel.release
#                                and /lib/modules/<release>). Set it when testing
#                                a kernel that must not share a module tree with
#                                the installed one: modules built for another
#                                config load silently (MODVERSIONS is off) and
#                                corrupt the running kernel.
# CCACHE_DISABLE=1               do not wrap the compiler in ccache
# KERNEL_FORCE_RESET=1           discard local changes in the source tree. Off by
#                                default: an existing $SRC may hold work in progress
#                                and the build refuses to throw it away.
#
# The build is reproducible: the same base commit, patch series, config and
# compiler version give the same Image, and the shipped config has no debug info
# in it. Nothing here depends on the clock, the user or the host name. The
# compiler and linker versions are recorded in build-manifest.txt because LTO
# output does depend on them.
#
# The default build has no addresses in it and runs on every phone: the Wi-Fi and
# Bluetooth addresses are read from the modem at boot by op9-addresses.service.
# To bake a phone's addresses into the device tree instead (the old way, which
# makes the image phone-specific):
# WIFI_MAC="aa bb cc dd ee ff"   this phone's Wi-Fi address
# BT_ADDR="aa bb cc dd ee ff"    this phone's Bluetooth address, in the normal order
set -euo pipefail
HERE=$(dirname "$(realpath "$0")")
# The series lives at the repository root, so it is obvious what changes the kernel
PATCHES=$(realpath "$HERE/../patches/kernel")
WORK=$(realpath -m "${1:-work}")
KERNEL_GIT=${KERNEL_GIT:-https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git}
# Linux 7.3 (the commit behind the v7.3 tag). Pinned by hash so a re-tagged or
# deleted tag upstream can't silently change what gets built.
KERNEL_COMMIT=${KERNEL_COMMIT:-c03c1a14507dfaf8b856c2608f9ac216021fc222}
SRC=$WORK/linux; OUT=$WORK/build; JOBS=${JOBS:-$(nproc)}
TOOLCHAIN=${TOOLCHAIN:-gcc}
CROSS_COMPILE=${CROSS_COMPILE:-aarch64-linux-gnu-}
# Appended to the release name by scripts/setlocalversion (it reads LOCALVERSION
# from the environment). Left unset when empty: setlocalversion only adds the
# "+" suffix for a tree that is not on a tag when LOCALVERSION is unset, and the
# installed module tree is named 7.3.0-op9+.
KERNEL_LOCALVERSION=${KERNEL_LOCALVERSION:-}
if [ -n "$KERNEL_LOCALVERSION" ]; then
	LOCALVERSION=$KERNEL_LOCALVERSION
	export LOCALVERSION
fi

# TOOLCHAIN selects the compiler suite. LLVM=1 makes Kbuild use clang, ld.lld
# and the llvm-* binutils; CROSS_COMPILE still sets clang's --target triple.
# The config carries CONFIG_LTO_NONE, so neither path sets up LTO.
case "$TOOLCHAIN" in
clang)
	CC=clang
	HOSTCC=clang
	MK=(make -C "$SRC" O="$OUT" ARCH=arm64 CROSS_COMPILE="$CROSS_COMPILE" \
		LLVM=1 LLVM_IAS=1 -j"$JOBS")
	for cmd in clang ld.lld llvm-ar llvm-nm llvm-objcopy llvm-objdump llvm-strip; do
		command -v "$cmd" >/dev/null 2>&1 ||
			{ echo "kernel/build.sh: $cmd not found (needed for TOOLCHAIN=clang)" >&2; exit 1; }
	done
	;;
gcc)
	# HOSTCC must stay the host compiler: the kernel's build tools run on this
	# machine, only the target objects are cross-compiled.
	CC=${CROSS_COMPILE}gcc
	HOSTCC=gcc
	MK=(make -C "$SRC" O="$OUT" ARCH=arm64 CROSS_COMPILE="$CROSS_COMPILE" -j"$JOBS")
	command -v "$CC" >/dev/null 2>&1 ||
		{ echo "kernel/build.sh: $CC not found (needed for TOOLCHAIN=gcc)" >&2; exit 1; }
	;;
*)
	echo "kernel/build.sh: unknown TOOLCHAIN=$TOOLCHAIN (clang or gcc)" >&2
	exit 1
	;;
esac

# A warm ccache turns a rebuild after a config or patch change from a full
# compile into a cache run. It does not affect the output.
HAVE_CCACHE=0
if [ "${CCACHE_DISABLE:-0}" != 1 ] && command -v ccache >/dev/null 2>&1; then
	HAVE_CCACHE=1
	MK+=(CC="ccache $CC" HOSTCC="ccache $HOSTCC")
fi

mkdir -p "$WORK" "$OUT"

if [ ! -d "$SRC/.git" ]; then
	git init -q "$SRC"
	git -C "$SRC" remote add origin "$KERNEL_GIT"
	# A shallow fetch of the commit needs uploadpack.allowReachableSHA1InWant on
	# the server; fall back to the tag when it isn't allowed.
	git -C "$SRC" fetch -q --depth 1 origin "$KERNEL_COMMIT" 2>/dev/null ||
		git -C "$SRC" fetch -q --depth 1 origin tag v7.3
	git -C "$SRC" checkout -q --detach "$KERNEL_COMMIT"
fi

if ! git -C "$SRC" rev-parse --verify -q "$KERNEL_COMMIT^{commit}" >/dev/null; then
	echo "kernel/build.sh: $SRC has no commit $KERNEL_COMMIT" >&2
	echo "  remove $SRC to fetch it again" >&2
	exit 1
fi
BASE=$(git -C "$SRC" rev-parse "$KERNEL_COMMIT^{commit}")

# Deterministic build: the kernel embeds these in its version string and in
# sections that would otherwise change with the clock.
if [ -z "${SOURCE_DATE_EPOCH:-}" ]; then
	SOURCE_DATE_EPOCH=$(git -C "$SRC" show -s --format=%ct "$BASE")
fi
export SOURCE_DATE_EPOCH
# Declared first so a failed date(1) is not masked by export, which always succeeds
KBUILD_BUILD_TIMESTAMP=$(date -u -d "@$SOURCE_DATE_EPOCH" '+%Y-%m-%d %H:%M:%S')
export KBUILD_BUILD_TIMESTAMP
export KBUILD_BUILD_USER=${KBUILD_BUILD_USER:-op9}
export KBUILD_BUILD_HOST=${KBUILD_BUILD_HOST:-op9-build}
export KBUILD_BUILD_VERSION=${KBUILD_BUILD_VERSION:-1}
export TZ=UTC

# The series is applied once per (base, patch set). The marker is only written
# after git am succeeds, so an interrupted or failed run is redone from the base
# commit instead of silently building whatever was applied.
WANT=$(cat "$PATCHES"/*.patch | sha256sum | cut -d' ' -f1)
MARKER="$WORK/patches.sha256"
STAMP="$BASE $WANT"
if [ "$(cat "$MARKER" 2>/dev/null || true)" != "$STAMP" ]; then
	# Everything below this point rewrites the source tree, so refuse to run over
	# local changes unless the caller says so.
	if [ -n "$(git -C "$SRC" status --porcelain)" ] && [ "${KERNEL_FORCE_RESET:-}" != 1 ]; then
		echo "kernel/build.sh: $SRC has local changes, refusing to reset it" >&2
		git -C "$SRC" status --short | sed 's/^/  /' >&2
		echo "  commit or stash them, or set KERNEL_FORCE_RESET=1 to discard them" >&2
		exit 1
	fi
	rm -f "$MARKER"
	git -C "$SRC" am --abort 2>/dev/null || true
	git -C "$SRC" reset -q --hard "$BASE"
	git -C "$SRC" clean -qfd
	git -C "$SRC" -c user.name=op9-build -c user.email=op9-build@localhost \
		am -q "$PATCHES"/*.patch
	echo "$STAMP" > "$MARKER"
fi

# Optional: bake the addresses in. The release build leaves them zeroed.
if [ -n "${WIFI_MAC:-}" ]; then
	sed -i "s/local-mac-address = \[[0-9a-f ]*\];/local-mac-address = [$WIFI_MAC];/" \
		"$SRC/arch/arm64/boot/dts/qcom/sm8350-oneplus-common.dtsi"
fi

if [ -n "${BT_ADDR:-}" ]; then
	# Device trees store this address in reverse
	BT_LE=$(echo "$BT_ADDR" | tr ' ' '\n' | tac | tr '\n' ' ' | sed 's/ $//')
	sed -i "s/local-bd-address = \[[0-9a-f ]*\];/local-bd-address = [$BT_LE];/" \
		"$SRC/arch/arm64/boot/dts/qcom/sm8350-oneplus-common.dtsi"
fi

# Replace the built config only when it differs, so a rerun that changed nothing
# does not restart Kconfig and touch the tree.
if ! cmp -s "$HERE/op9.config" "$OUT/.config"; then
	cp "$HERE/op9.config" "$OUT/.config"
fi
# The embedded-DTB paths are baked into .config, so they must stay relative: a
# build in /tmp/a would otherwise differ from one in /tmp/b. The assembler
# resolves them against $OUT, which is where the DTBs are copied.
"${MK[@]}" olddefconfig
for want in \
	'CONFIG_ARM64_OP9_BUILTIN_DTB=y' \
	'CONFIG_ARM64_OP9_BUILTIN_DTB_PATH="op9-builtin.dtb"' \
	'CONFIG_ARM64_OP9_BUILTIN_DTB_2=y' \
	'CONFIG_ARM64_OP9_BUILTIN_DTB_PATH_2="op9-builtin-lemonade.dtb"'
do
	grep -qx "$want" "$OUT/.config" ||
		{ echo "kernel/build.sh: op9.config lost $want" >&2; exit 1; }
done
# The shipped config must build into the kernel it claims: no LTO, which is the
# combination verified to boot here.
grep -q '^CONFIG_LTO_NONE=y' "$OUT/.config" ||
	{ echo "kernel/build.sh: op9.config enabled LTO" >&2; exit 1; }
# The shipped config has no debug info (CONFIG_DEBUG_INFO_NONE): it only inflates
# Image, and a build artifact that depends on nothing else is easier to compare.
# Assert it, so an edit that flips it back fails the build instead of shipping a
# multi-hundred-MB Image.
grep -q '^CONFIG_DEBUG_INFO_NONE=y' "$OUT/.config" ||
	{ echo "kernel/build.sh: debug info is still enabled" >&2; exit 1; }

# The kernel carries its own device trees, so build those first. Both phones'
# trees are embedded and the kernel picks one from what the bootloader reports.
"${MK[@]}" qcom/sm8350-oneplus-lemonadep.dtb qcom/sm8350-oneplus-lemonade.dtb
# The built-in DTB object is built from these files, so copying unconditionally
# would touch them and force a relink of vmlinux on every rerun.
copy_if_different() {
	cmp -s "$1" "$2" || cp "$1" "$2"
}
copy_if_different "$OUT/arch/arm64/boot/dts/qcom/sm8350-oneplus-lemonadep.dtb" "$OUT/op9-builtin.dtb"
copy_if_different "$OUT/arch/arm64/boot/dts/qcom/sm8350-oneplus-lemonade.dtb" "$OUT/op9-builtin-lemonade.dtb"
"${MK[@]}" Image modules
rm -rf "$WORK/modroot"
"${MK[@]}" modules_install INSTALL_MOD_PATH="$WORK/modroot" INSTALL_MOD_STRIP=1

# What went into this build, for the release notes and for anyone rebuilding it.
krel=$(cat "$OUT/include/config/kernel.release")
{
	echo "kernel_release=$krel"
	echo "base_commit=$BASE"
	echo "base_tag=v7.3"
	echo "patch_series_sha256=$WANT"
	echo "patch_count=$(ls "$PATCHES"/*.patch | wc -l)"
	echo "config_sha256=$(sha256sum "$HERE/op9.config" | cut -d' ' -f1)"
	echo "source_date_epoch=$SOURCE_DATE_EPOCH"
	echo "toolchain=$TOOLCHAIN"
	if [ "$TOOLCHAIN" = clang ]; then
		echo "compiler=$($CC --version | head -1)"
		echo "linker=$(ld.lld --version)"
		echo "lto=thin"
	else
		echo "compiler=$($CC --version | head -1)"
		echo "lto=none"
	fi
	echo "ccache=$HAVE_CCACHE"
	# An address-baked build is not reproducible from the repository alone.
	echo "wifi_mac=${WIFI_MAC:-none}"
	echo "bt_addr=${BT_ADDR:-none}"
} > "$OUT/build-manifest.txt"

sha256sum "$OUT/arch/arm64/boot/Image" > "$OUT/Image.sha256"

echo "Image:    $OUT/arch/arm64/boot/Image"
echo "Modules:  $WORK/modroot"
echo "Manifest: $OUT/build-manifest.txt"
cat "$OUT/build-manifest.txt"
