#!/bin/bash
# Populates an existing postmarketOS edge (systemd + Phosh) rootfs with what this
# port needs: the kernel modules from kernel/build.sh, the phone's firmware and
# sensor calibration, and the rootfs/ overlay. It also builds the static helper
# tools those units run.
#
# It does NOT create the image or the sparse userdata file. Make the base image
# with `pmbootstrap install`, then run this against its mounted root, and repack
# the boot image with scripts/op9-boot-image.sh (ABL rejects pmbootstrap's boot
# header). GUIDE.md has the whole sequence.
#
# Usage:
#   ./postmarketos/build-pmos-image.sh <output-dir>
#
# No device argument: one kernel and one rootfs overlay serve both phones. The
# firmware lives under qcom/sm8350/OnePlus/lemonade for both (that path is in the
# shared sm8350-oneplus-common.dtsi, not per board), and ALSA picks the 9 or 9 Pro
# voice setup by card name.
#
# Environment:
#   FW_TAR   firmware/calibration archive   (default ../rootfs-build/op9-firmware.tar.zst)
#   MOD_DIR  kernel module tree             (default ./work/modroot)
#
# Produces, in <output-dir>:
#   bin-stage/                      the helper binaries, ready to install
#   populate-mounted-rootfs.sh      installs them and the overlay into a mounted rootfs

set -euo pipefail

HERE=$(dirname "$(realpath "$0")")
REPO=$(realpath "$HERE/..")
OUTDIR=$(realpath -m "${1:-$REPO/../rootfs-build/pmos}")
FW_TAR="${FW_TAR:-$REPO/../rootfs-build/op9-firmware.tar.zst}"
MOD_DIR="${MOD_DIR:-$REPO/work/modroot}"

mkdir -p "$OUTDIR"

echo "=== [1/5] Checking prerequisites ==="
for cmd in aarch64-linux-gnu-gcc zstd; do
	command -v "$cmd" >/dev/null 2>&1 || { echo "Missing required tool: $cmd" >&2; exit 1; }
done

if [ ! -f "$FW_TAR" ]; then
	echo "Missing firmware archive: $FW_TAR" >&2
	echo "Back up /lib/firmware and /usr/share/qcom from the phone first (see GUIDE.md)." >&2
	exit 1
fi

if [ ! -d "$MOD_DIR/lib/modules" ] && [ ! -d "$MOD_DIR/usr/lib/modules" ]; then
	echo "Kernel modules not found in $MOD_DIR — building kernel + modules first..."
	"$REPO/kernel/build.sh" "$REPO/work"
fi

echo "=== [2/5] Building the static helper tools ==="
BIN_STAGE="$OUTDIR/bin-stage"
mkdir -p "$BIN_STAGE"
# Rebuild only when the source is newer than the binary: a rerun of this script
# to refresh the rootfs should not recompile five programs that did not change.
build_tool() {
	local src=$1 out=$2
	shift 2
	if [ -x "$out" ] && [ "$out" -nt "$src" ]; then
		return 0
	fi
	aarch64-linux-gnu-gcc -static -O2 -o "$out" "$src" "$@"
}
build_tool "$REPO/tools/touchboost.c" "$BIN_STAGE/touchboost"
build_tool "$REPO/tools/alert-slider.c" "$BIN_STAGE/alert-slider"
build_tool "$REPO/tools/op9-slot.c" "$BIN_STAGE/op9-slot"
build_tool "$REPO/tools/op9-hdr.c" "$BIN_STAGE/op9-hdr" -lm
# hexagonrpcd is not built here: postmarketos/pmaports/community/hexagonrpc
# packages it, with the registry-write patches.

echo "=== [3/5] Writing the rootfs population helper ==="
cat > "$OUTDIR/populate-mounted-rootfs.sh" <<EOF
#!/bin/bash
# Run as root with the target postmarketOS rootfs mounted at \$1
set -euo pipefail
MNT=\$(realpath "\$1")
[ -d "\$MNT/etc" ] || { echo "\$MNT does not look like a mounted rootfs" >&2; exit 1; }

echo "-> Installing kernel modules..."
mkdir -p "\$MNT/lib/modules"
if [ -d "$MOD_DIR/usr/lib/modules" ]; then
	cp -a "$MOD_DIR/usr/lib/modules/"* "\$MNT/lib/modules/"
else
	cp -a "$MOD_DIR/lib/modules/"* "\$MNT/lib/modules/"
fi
chown -R 0:0 "\$MNT/lib/modules"

echo "-> Extracting device firmware & sensor calibration..."
tar --zstd -xf "$FW_TAR" -C "\$MNT"
chown -R 0:0 "\$MNT/lib/firmware" "\$MNT/usr/share/qcom" 2>/dev/null || true
# hexagonrpcd runs as fastrpc and the DSP writes into the sensor registry, so that
# tree cannot stay root-owned. Check the image's own passwd, not the host's: the
# user comes from hexagonrpc's sysusers file.
if grep -q '^fastrpc:' "\$MNT/etc/passwd" 2>/dev/null; then
	chown -R fastrpc:fastrpc "\$MNT/usr/share/qcom/sm8350/OnePlus" 2>/dev/null || true
else
	echo "  warning: the image has no fastrpc user; the sensors will not start." >&2
	echo "  Install postmarketos/pmaports/community/hexagonrpc into it first." >&2
fi
# Both phones' device trees ask for qcom/sm8350/OnePlus/lemonade (the path is in
# the shared sm8350-oneplus-common.dtsi, not per board), so the 9 Pro's firmware
# belongs there too. That is OnePlus's own directory layout, not a device name.
ln -sfn volte "\$MNT/lib/firmware/qcom/sm8350/OnePlus/lemonade/modem_pr/mcfg/configs/mcfg_sw/generic/OPLUS_EXP/PU/VoLTE" 2>/dev/null || true

echo "-> Copying rootfs/ configurations, udev rules, ALSA UCM2, TuneD profiles & systemd units..."
# Excluded: the speaker-protection filter chain (Alpine has no swh-plugins, so the
# LADSPA limiter can't load) and phosh.service (postmarketOS ships its own).
tar -C "$REPO/rootfs" \
    --exclude='etc/pipewire/pipewire.conf.d/op9-speaker-protection.conf' \
    --exclude='etc/systemd/system/phosh.service' \
    --exclude='etc/systemd/system/phosh.service.d' \
    -cf - . | tar -C "\$MNT" --no-same-owner -xf -
mkdir -p "\$MNT/usr/share/libcamera/ipa/softisp" "\$MNT/etc/phosh" "\$MNT/etc/systemd/system.conf.d" "\$MNT/etc/systemd/user.conf.d"
cp -a "\$MNT/usr/share/libcamera/ipa/simple/"*.yaml "\$MNT/usr/share/libcamera/ipa/softisp/" 2>/dev/null || true
cat > "\$MNT/etc/systemd/system.conf.d/10-alpine-path.conf" <<'PATHEOF'
[Manager]
DefaultEnvironment=PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
PATHEOF
cp "\$MNT/etc/systemd/system.conf.d/10-alpine-path.conf" "\$MNT/etc/systemd/user.conf.d/10-alpine-path.conf"
[ -s "\$MNT/etc/machine-id" ] || tr -d '-' < /proc/sys/kernel/random/uuid > "\$MNT/etc/machine-id"
[ -s "\$MNT/etc/locale.conf" ] || echo "LANG=C.UTF-8" > "\$MNT/etc/locale.conf"
rm -f "\$MNT/usr/lib/systemd/system/sysinit.target.wants/systemd-firstboot.service" \
      "\$MNT/etc/systemd/system/usb-gadget.target.wants/usb-signaller.service"
ln -sfn /dev/null "\$MNT/etc/systemd/system/usb-signaller.service"

install -m 755 "$BIN_STAGE/touchboost" "\$MNT/usr/local/bin/touchboost"
install -m 755 "$BIN_STAGE/alert-slider" "\$MNT/usr/local/bin/alert-slider"
install -m 755 "$BIN_STAGE/op9-slot" "\$MNT/usr/local/bin/op9-slot"
chmod +x "\$MNT/usr/local/bin/"* "\$MNT/etc/tuned/profiles/"*/script.sh 2>/dev/null || true
chown -R 0:0 "\$MNT/etc" "\$MNT/usr/local" "\$MNT/usr/share/alsa" "\$MNT/usr/share/libcamera" 2>/dev/null || true

echo "-> Enabling the OnePlus 9 systemd services..."
mkdir -p "\$MNT/etc/systemd/system/multi-user.target.wants" "\$MNT/etc/systemd/system/timers.target.wants" "\$MNT/etc/systemd/user/default.target.wants"
for svc in op9-addresses.service op9-boot-successful.service op9-lockup-watch.service op9-sim-provision.service op9-sunlight-hbm.service rtc-offset.service touchboost.service usb-gadget-ensure.service; do
	ln -sfn "/etc/systemd/system/\$svc" "\$MNT/etc/systemd/system/multi-user.target.wants/\$svc"
done
ln -sfn "/etc/systemd/system/rtc-offset-save.timer" "\$MNT/etc/systemd/system/timers.target.wants/rtc-offset-save.timer"
for usvc in op9-alert-slider.service op9-callaudio.service op9-charge-status.service mmsd-tng.service; do
	ln -sfn "/etc/systemd/user/\$usvc" "\$MNT/etc/systemd/user/default.target.wants/\$usvc"
done

echo "-> Done populating \$MNT!"
EOF
chmod +x "$OUTDIR/populate-mounted-rootfs.sh"
echo "Helper script generated at: $OUTDIR/populate-mounted-rootfs.sh"
