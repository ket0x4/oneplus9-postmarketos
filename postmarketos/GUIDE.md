# OnePlus 9 (`lemonade` / LE2115) and 9 Pro (`lemonadep`) — postmarketOS (`edge` + `systemd` + Phosh)

This folder holds what it takes to run the **mainline Linux 7.3 kernel built from this repository
(patches `0001–0167`)** and all of the OnePlus 9 / 9 Pro hardware services (**display at 120/60 Hz
with HBM and Natural colour, S6SY792/S3908 touch at up to 360 Hz plus `touchboost`, audio with
`op9-callaudio`, SLPI sensors, all four cameras with autofocus, Wi-Fi/BT addresses from
`op9-addresses`, the modem stack with LTE/5G NR and VoLTE (`81voltd`) and GPS, and `tuned-ppd`
power profiles**) on **postmarketOS `edge` (`systemd` + Phosh)**.

> **Status:** this guide is a record of bring-up, and postmarketOS is the only supported route.
> The steps have never been replayed from scratch; expect to troubleshoot.
> The KDE Plasma 6 / RDP sections (9 and 10) were tried on the phone but the files they describe
> **are not in this repository** — they are kept here as notes only.

---

## 1. Why postmarketOS?

1. **The mobile packages are in the official repositories (`apk`)**:
   - `rmtfs`, `tqftpserv`, `qrtr`, `81voltd`, `mmsd-tng`, `mobile-config-firefox`, `phosh`, `phoc`,
     `squeekboard`, `feedbackd`, `gnome-calls`, `chatty`, `iio-sensor-proxy`, `tuned` and `tuned-ppd`
     are all available as ready binaries, so nothing has to be built by hand.
2. **The mobile stack is tested together**:
   - postmarketOS builds and tests the whole mobile stack at once, so a soname transition in a
     desktop package (`icu`, `libsoup`, `openssl`, `ffmpeg`) doesn't break the mobile services.
3. **`systemd` support**:
   - postmarketOS `edge` uses **`systemd`** for Phosh and GNOME Mobile. Every unit under
     [rootfs/etc/systemd/](../rootfs/etc/systemd) therefore runs unchanged: `op9-addresses`,
     `op9-sim-provision`, `op9-callaudio`, `touchboost`, `op9-sunlight-hbm`, `op9-boot-successful`,
     `rtc-offset` and `usb-gadget-ensure`.

---

## 2. What's here

| File / folder | What it is |
|---|---|
| [GUIDE.md](GUIDE.md) | This install and port guide |
| [pmos-kconfig.fragment](pmos-kconfig.fragment) | Extra kernel options for postmarketOS. They are already in [kernel/op9.config](../kernel/op9.config); the fragment is only for starting from a reduced config (see [§3](#3-the-kernel-linux-73-and-what-postmarketos-needs)) |
| [build-pmos-image.sh](build-pmos-image.sh) | Builds the static helper tools (`touchboost`, `alert-slider`, `op9-slot`) and writes `populate-mounted-rootfs.sh`, which installs the `7.3.0-op9+` modules, device firmware and `rootfs/` services into a mounted postmarketOS rootfs |
| [apk-triggers/](apk-triggers/) | The apk trigger that regenerates the no-splash launchers after an install (replaces the old pacman hook) |
| [pmaports/](pmaports/) | Device packages for both phones plus the patched `libcamera`, `phoc`, `wlroots0.20`, `modemmanager`, `81voltd`, `hexagonrpc`, `iio-sensor-proxy` and the quick settings |

---

## 3. The kernel (Linux 7.3) and what postmarketOS needs

The 167-patch Linux 7.3 kernel ([patches/kernel/](../patches/kernel)) already covers the hardware.
[kernel/op9.config](../kernel/op9.config) also has what postmarketOS userland needs
(`cryptsetup` / `dm-crypt`, `iwd`, `f2fs`, `squashfs`):

- `CONFIG_DM_CRYPT=y` and `CONFIG_CRYPTO_XTS=y` (postmarketOS full-disk encryption and `kconfig check`)
- `CONFIG_CRYPTO_USER_API_HASH=y` and `CONFIG_CRYPTO_USER_API_SKCIPHER=y` (crypto API for `iwd` and `cryptsetup`)
- `CONFIG_F2FS_FS=y`, `CONFIG_F2FS_FS_XATTR=y`, `CONFIG_F2FS_FS_POSIX_ACL=y` (`f2fs` rootfs alongside `ext4`)
- `CONFIG_SQUASHFS_ZSTD=y` and `CONFIG_SQUASHFS_XZ=y`

[pmos-kconfig.fragment](pmos-kconfig.fragment) repeats these options. `kernel/op9.config` is the
single source of truth; use the fragment only when starting from a different base config.

The config is also pruned to this hardware. Only the sm8350 platform is selected (`ARCH_QCOM`), and
drivers for other SoCs, GPUs, Bluetooth vendors, Ethernet vendors, RAID/SAS HBAs, ATA, MTD, CAN, DVB
and audio platforms for other SoCs are off, so the build and the module tree carry what the phone
actually probes. Nothing the device tree asks for is removed: the Adreno/MSM display stack, WCN6855
Wi-Fi and Bluetooth (`ath11k`, `btqca`), UFS, USB/Type-C with the FSA4480 mux, fastrpc/QRTR for the
DSPs, the WCD9380/TFA9874 audio path, the IMX/OV camera sensors and the AW8697 haptics stay.

Wireless and filesystem drivers are kept in full, because both are plausible add-ons in desktop
mode: the common USB Wi-Fi adapters are modules (`mt7601u`, `mt76x0u`/`mt76x2u`, `mt7921u`/`mt7925u`,
`rtl8xxxu`, `rtw88`/`rtw89`, `ath9k_htc`, `rt2800usb`, `brcmfmac`, `mwifiex`, `rsi` and others), as
are `btrfs`, `exFAT`, `NTFS3`, `9p` and NFS, so a USB dongle or an external disk works.

> **Important (`initramfs`)**: our boot image ([initramfs/init](../initramfs/init)) brings up USB
> NCM (`172.16.42.1`) with a rescue shell, mounts `/dev/op9/userdata` at `/sysroot` and
> `switch_root`s into `/sysroot/sbin/init` (`systemd`). That is how the postmarketOS rootfs on
> `userdata` boots without touching `boot_a` again. The initramfs tries `ext4`, `f2fs` and
> `squashfs` as the root filesystem.

---

## 4. Before installing: backup, firmware and calibration

> **This erases the phone and can brick it.** Read every step before starting.
> **Never write to** `xbl`, `persist`, `modem`, the EFS partitions or `param`.

### 4.1 Back up the partitions

Copy every partition to your PC first. At the very least:

```sh
for p in persist modem_a modem_b modemst1 modemst2 fsg fsc boot_a boot_b \
         vendor_boot_a vendor_boot_b dtbo_a dtbo_b vbmeta_a vbmeta_b; do
    adb shell su -c "dd if=/dev/block/bootdevice/by-name/$p" > "$p.img"
done
```

`persist` and the EFS partitions are unique to your phone and exist nowhere else.

### 4.2 Firmware and calibration

A clean postmarketOS install wipes `userdata`, so make sure the running phone's
`/lib/firmware/qcom/sm8350/OnePlus/lemonade/`, `/lib/firmware/ath11k/`, `/lib/firmware/qca/` and
`/usr/share/qcom/sm8350/OnePlus/lemonade/` are archived on your PC as
`../rootfs-build/op9-firmware.tar.zst`:

```sh
ssh root@172.16.42.1 'tar -C / -cf - \
    lib/firmware/qcom/sm8350/OnePlus/lemonade \
    lib/firmware/ath11k/WCN6855 \
    lib/firmware/qca \
    usr/share/qcom/sm8350/OnePlus/lemonade' | zstd -T0 -o ../rootfs-build/op9-firmware.tar.zst
```

Note the `lemonade` in those paths: it is where OnePlus's own firmware layout puts the directory on
both phones, not a board name. The shared `sm8350-oneplus-common.dtsi` asks for it on the 9 Pro too.

---

## 5. Building the postmarketOS `edge` (Phosh + `systemd`) rootfs

### Step 1: make a base image with `pmbootstrap`

1. Set up the `pmbootstrap` work directory (`device: oneplus-lemonade` or `oneplus-lemonadep`,
   `ui: phosh`, `systemd: yes`, `channel: edge`):
   ```sh
   pmbootstrap init
   ```
   *(Answer Channel: `edge`, Vendor: `oneplus`, Codename: `lemonade` or `lemonadep`, UI: `phosh`,
   systemd: `yes`.)*

2. Build the image with the extra packages this port needs:
   ```sh
   pmbootstrap install --no-fde \
       --add="rmtfs,tqftpserv,qrtr,qmi-utils,81voltd,mmsd-tng,tuned,tuned-ppd,alsa-ucm-conf,alsa-utils,libcamera,libcamera-tools,pipewire-tools,wireplumber,mobile-config-firefox,firefox,calls,chatty,gnome-contacts,loupe,iotas,fastfetch,bluez,iwd,networkmanager-wifi,networkmanager-wwan,python3,py3-gobject3,py3-dbus,py3-cairo,libqmi,libqrtr-glib,gnome-shell,gnome-shell-session,mutter,gdm"
   ```
   The last four names are what desktop mode runs (`op9-desktop.service` → `gnome-session` →
   `gnome-shell`). `postmarketos-ui-phosh` ships Phosh only and explicitly excludes the `-mobile`
   GNOME variants, so nothing else pulls them, and `gdctl` (used for the display layout) comes from
   `mutter`. Without `gnome-shell` the chooser still appears, but starting desktop mode leaves no
   shell. `gdm` is needed too: `gnome-shell` imports its `Gdm` typelib and `org.gnome.login-screen`
   schema. Installing it pulls `gdm-systemd`, but greetd already owns
   `display-manager.service`, so apk refuses to preset GDM over it and Phosh keeps the seat.
   `py3-cairo` draws the keyboard and trackpad on the phone screen; without it `op9-desktop-input`
   leases the panel and leaves it dark.

3. Copy the resulting rootfs image
   (`~/.local/var/pmbootstrap/chroot_native/home/pmos/rootfs/oneplus-lemonade.img`) into the working
   folder and mount its second partition (the root filesystem):
   ```sh
   mkdir -p ../rootfs-build/pmos/mnt
   cp ~/.local/var/pmbootstrap/chroot_native/home/pmos/rootfs/oneplus-lemonade.img \
       ../rootfs-build/pmos/pmos-disk.img
   LOOP=$(sudo losetup --find --show --partscan ../rootfs-build/pmos/pmos-disk.img)
   # in a pmbootstrap image p1 = /boot, p2 = / (ext4)
   sudo e2fsck -fy "${LOOP}p2" || true
   sudo resize2fs "${LOOP}p2"
   sudo mount "${LOOP}p2" ../rootfs-build/pmos/mnt
   ```

### Step 2: install the kernel modules, firmware and services

First build the kernel, which also writes `work/build/build-manifest.txt` (the base commit, the
patch-series hash and the config hash) and `Image.sha256`:

```sh
kernel/build.sh work
```

The build is reproducible: the same inputs and the same compiler and linker versions give the same
`Image`, and it never reads the clock or the build machine's paths. It builds with GCC and
`CONFIG_LTO_NONE`, the combination that boots on this phone; `TOOLCHAIN=clang` selects a ThinLTO
build, which compiles but does not boot here (it dies before the ramoops console comes up, so there
is no log to read). `build-manifest.txt` records the compiler and linker versions, so a mismatch
there explains it if a rebuild does not match. `ccache` is used when installed, which only speeds
rebuilds up. Rebuild a release tag and compare against the `Image.sha256` in its assets to check it.
If `work/linux` already exists with local changes, the build refuses to reset it — commit or stash
them, or set `KERNEL_FORCE_RESET=1` to discard them.

Then run [build-pmos-image.sh](build-pmos-image.sh), and the `populate-mounted-rootfs.sh` it writes,
to fill the mounted rootfs. There is no device argument: one kernel and one `rootfs/` overlay serve
both phones. The firmware lives under `qcom/sm8350/OnePlus/lemonade/` for both (see 4.2), and ALSA
picks the 9 or 9 Pro voice setup by card name.

```sh
./postmarketos/build-pmos-image.sh ../rootfs-build/pmos
sudo ../rootfs-build/pmos/populate-mounted-rootfs.sh ../rootfs-build/pmos/mnt
```

That installs:
- the `/lib/modules/7.3.0-op9+` kernel modules,
- `/lib/firmware/qcom/sm8350/OnePlus/lemonade/`, `ath11k`, `qca` and
  `/usr/share/qcom/sm8350/OnePlus/lemonade/sensors/` (including the `PU/VoLTE -> volte` symlink),
- every `udev` rule in [rootfs/](../rootfs), the ALSA UCM2 setup (`OnePlus/lemonade` and
  `OnePlus/lemonadep`, plus `VoiceMMode1`), the WirePlumber camera rules, the `imx689.yaml` colour
  matrix, the `tuned` profiles (`op9-powersave`, `op9-balanced`, `op9-performance`) and the `systemd`
  units,
- the statically built `touchboost`, `alert-slider` and `op9-slot` binaries.

`hexagonrpcd` is not built by that script: the `hexagonrpc` package from
[pmaports/community/hexagonrpc/](pmaports/community/hexagonrpc/) provides it, with the registry-write
patches the sensors need.

> **Note (the `fastrpc` user and the sensors)**: the
> [hexagonrpcd-sdsp.service.d/op9-registry.conf](../rootfs/etc/systemd/system/hexagonrpcd-sdsp.service.d/op9-registry.conf)
> drop-in starts `hexagonrpcd` with `-R /usr/share/qcom/sm8350/OnePlus/lemonade` (the registry
> subdirectory is looked up under that root). The directory has to be owned by `fastrpc`, or the DSP
> can't read its registry. The populate script does that inside the mounted root; if you do it by
> hand, use the same path.

### Step 3: turn the root partition (`${LOOP}p2`) into a sparse image for `userdata`

Our `initramfs/init` mounts `/dev/op9/userdata` directly as `ext4`, so extract `${LOOP}p2` on its own
and convert it to an Android sparse image (`pmos-userdata.simg`):

```sh
sudo umount ../rootfs-build/pmos/mnt
sudo dd if="${LOOP}p2" of=../rootfs-build/pmos/pmos-root.img bs=4M status=progress
sudo losetup -d "$LOOP"
e2fsck -fy ../rootfs-build/pmos/pmos-root.img || true
img2simg ../rootfs-build/pmos/pmos-root.img ../rootfs-build/pmos/pmos-userdata.simg
```

---

## 6. Flashing and first boot

0. **Try it before writing anything.** `fastboot boot` changes nothing on the phone and must be sent
   **once** (repeating bootloader commands in a loop can change the active slot). The screen may stay
   black; that proves nothing — look for the USB network instead:
   ```sh
   fastboot boot ../rootfs-build/op9-boot.img
   sudo ip addr add 172.16.42.2/24 dev <usb interface>
   telnet 172.16.42.1     # unauthenticated root shell while in the initramfs
   ```
   That shell only exists in the initramfs. If it doesn't appear, your model may need different
   device tree IDs.

1. Put the phone in fastboot mode (`adb`/ssh: `systemctl reboot bootloader`, or Volume Down + Power):
   ```sh
   fastboot flash boot_a ../rootfs-build/op9-boot.img
   # IMPORTANT: the OnePlus 9 ABL skips sparse chunks over 512 MB (768 MB by default)
   # without writing them, in 0.007 s, so always pass -S 256M:
   fastboot -S 256M flash userdata ../rootfs-build/pmos/pmos-userdata.simg
   fastboot set_active a
   fastboot reboot
   ```
1b. **Test a new kernel on the spare slot first.** A kernel that does not reach userspace looks
   exactly like a bootloop at the logo, and the panic log may never be written (clang ThinLTO builds
   here die before the ramoops console exists). Write the candidate to `boot_b`, boot it, and keep
   `boot_a` as the known-good image:
   ```sh
   fastboot flash boot_b <candidate.img>
   fastboot set_active b
   fastboot reboot
   ```
   If it does not come up, `fastboot set_active a` switches back. Two rules make the test valid:
   - **The modules must match the kernel.** `CONFIG_MODVERSIONS` is off, so a module built from a
     different config loads without complaint and corrupts the running kernel. Build the candidate
     with `KERNEL_LOCALVERSION=-test`, install `work/modroot/lib/modules/<release>` on the phone
     (a separate directory, next to the installed one) and only then boot it. Without that
     separation a boot loop means nothing about the kernel itself.
   - **LTO does not boot here.** `CONFIG_LTO_CLANG_THIN` builds cleanly but hangs at the logo with no
     pstore record, so `kernel/op9.config` ships `CONFIG_LTO_NONE` and GCC, which is the combination
     verified on hardware.
2. Once it boots, connect over USB NCM at `172.16.42.1` and grow `userdata` to the full disk size
   (`101 GB`):
   ```sh
   ssh <user>@172.16.42.1
   sudo resize2fs /dev/op9/userdata
   ```
3. **Don't skip `op9-slot`.** On every boot `op9-boot-successful` tells the bootloader, through
   `op9-slot`, that the slot booted fine. Without it the bootloader counts down that slot's retries;
   after about seven boots it marks the slot unbootable and switches to the other one, which looks
   **like a brick**. The build script installs the binary and `populate-mounted-rootfs.sh` enables the
   service; check it anyway:
   ```sh
   sudo op9-slot show     # the slot you booted should say successful=1
   ```
4. Enable and check the modem and power services:
   ```sh
   sudo systemctl enable --now qrtr-ns rmtfs tqftpserv op9-addresses op9-sim-provision \
       81voltd ModemManager tuned tuned-ppd usb-gadget-ensure
   systemctl --user enable --now op9-callaudio mmsd-tng op9-alert-slider op9-charge-status
   ```

---

## 7. The patched packages for these phones

The stock postmarketOS packages bring the system up, but the hardware fixes developed for this port
need the APKBUILDs under [pmaports/community/](pmaports/community/). Each one replaces the matching
postmarketOS package (`replaces`), so `apk upgrade` won't quietly put the unpatched one back.

```sh
# with pmbootstrap, for the phone:
for p in hexagonrpc wlroots0.20 libcamera iio-sensor-proxy phoc modemmanager 81voltd \
         op9-quick-settings; do
    pmbootstrap build --arch=aarch64 "$p"
done
pmbootstrap install --add="hexagonrpc,libcamera,iio-sensor-proxy,phoc,modemmanager,81voltd,op9-quick-settings"
```

| Package | Patch | Why |
|---|---|---|
| `modemmanager` | [0001-shared-qmi-register-as-LOC-master-client…](pmaports/community/modemmanager/0001-shared-qmi-register-as-LOC-master-client-before-star.patch) | Registers as the QMI `LOC` master client before starting the SM8350's GPS engine; without it every position request returns `GeneralError` |
| `81voltd` | [0001-qvd-connection-reconnect-IMS-bearer…](pmaports/community/81voltd/0001-qvd-connection-reconnect-IMS-bearer-if-dropped-remot.patch) | Reconnects the `ims` bearer within 2 s when it drops during a 4G ↔ 5G transition (VoLTE) |
| `libcamera` | 4 patches | IMX689/IMX766/IMX471/GC02M1B gain helpers, centred debayer for the scaled path, contrast-detect autofocus, a greyscale path for the mono camera |
| `iio-sensor-proxy` | [iio-sensor-proxy-op9.patch](pmaports/community/iio-sensor-proxy/iio-sensor-proxy-op9.patch) | The SSC sensors came up late, so clients were told there were none; availability is broadcast once known |
| `phoc` | [phoc-op9.patch](pmaports/community/phoc/phoc-op9.patch) | Rotating back left a 3 s layout timeout and a black screen |
| `wlroots0.20` | [0001-Revert-layer-shell-error…](pmaports/community/wlroots/0001-Revert-layer-shell-error-on-0-dimension-without-anch.patch) | Phosh's home bar creates a 0-dimension surface, which aborts the client |
| `hexagonrpc` | 2 patches | Let the DSP write its sensor registry (not packaged in Alpine at all) |
| `op9-quick-settings` | — | The 360 Hz touch and Natural colour quick settings, for Phosh (C plugins) and Plasma Mobile (QML) |

The [81-iio-sensor-proxy-op9.rules](../rootfs/etc/udev/rules.d/81-iio-sensor-proxy-op9.rules) rule
needs `KERNEL=="fastrpc-*"`: postmarketOS enumerates `fastrpc-adsp` before `fastrpc-sdsp`, so
`ACCEL_MOUNT_MATRIX` has to apply to both.

---

## 8. Extra fixes verified on a live install

Points confirmed on a OnePlus 9 (`LE2115`) running postmarketOS `edge` with `systemd`:

1. **systemd `PATH` and first boot (`systemd-firstboot`)**:
   - systemd 262 doesn't keep `/bin` and `/sbin` in its default service `PATH`, so add
     `DefaultEnvironment=PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin` through
     `/etc/systemd/{system,user}.conf.d/10-alpine-path.conf` (the populate script writes both).
   - `initramfs/init` creates `/etc/machine-id` (including the `uninitialized` case),
     `/etc/locale.conf` and `/etc/localtime` on first boot and clears the
     `systemd-firstboot.service` blocker.
2. **Wi-Fi firmware (`updates/ath11k/WCN6855`)**:
   - The stock WCN6855 `amss.bin`/`m3.bin`/`board.bin`/`regdb.bin` must land in
     `/lib/firmware/updates/ath11k/WCN6855/hw2.0` and `hw2.1`, or `ath11k_pci` times out with `-110`.
3. **PipeWire and `op9-speaker-protection.conf`**:
   - Alpine has no `swh-plugins` (`sc4_1882.so`), so the speaker-protection filter chain isn't copied
     into the postmarketOS rootfs (`build-pmos-image.sh` excludes it).
4. **Plasma 6 Mobile (`postmarketos-ui-plasma-mobile` + `plasma-desktop`)**:
   - Write the user name to `/etc/default_user`; the `plasma-mobile.service` generator reads it.
   - `kde-telephony-daemon` (`plasma-dialer`) talks `libcallaudio-0.1.so.0` →
     `org.mobian_project.CallAudio` directly, so our `op9-callaudio` service works with it unchanged.
   - To keep the top bar out of the punch-hole camera, set `statusBarHeight=132`,
     `statusBarRightPadding=126` and `statusBarLeftPadding=24` under `[Panels][WhenOnTop]` in
     `~/.config/plasmamobilerc`.
5. **Faster boot and shutdown**:
   - `fwupd.service` (mask it), `NetworkManager-wait-online.service`, `diag-router.service`,
     `hexagonrpcd-adsp-*` and `systemd-boot-*`/`tpm2-*` can be disabled, and adding
     `DefaultTimeoutStopSec=5s` to `/etc/systemd/{system,user}.conf.d/20-fast-shutdown.conf` shortens
     a reboot noticeably.
   - The `tuned` profiles (`op9-powersave`, `op9-balanced`, `op9-performance`) apply Wi-Fi power save
     (the interface is discovered, whatever it is called), PCIe runtime PM (`auto`) and `devfreq`
     `polling_interval` (`100 ms` / `50 ms` / `20 ms`).

---

## 9. USB-C HDMI docks and full KDE Plasma 6 desktop mode

> The KDE/Plasma files in this section (service units, the `op9-rdp-desktop*` scripts, the nftables
> rules) are **not in this repository**; they were local setups tried on the phone.

1. **Kernel patches (`0166` and `0167`):**
   - `patches/kernel/0166-usb-typec-ucsi-preserve-altmode-mux-when-partner-fla.patch`: while
     `PARTNER_FLAG_ALT_MODE` is set, `typec_ucsi` (`ucsi.c`) no longer resets the shared QMP combo PHY
     mux back to `TYPEC_STATE_USB` (`USB3_ONLY`). That fixes the 2-second PHY reset loop and
     `disp_cc_mdss_dp_link_clk status stuck at 'off'` (`-EBUSY`) on USB-C DP+USB docks.
   - `patches/kernel/0167-drm-msm-dp-fix-USB-C-DP-AltMode-hotplug-and-PHY-re.patch`: stops the
     repeated AUX probing and the KWin freeze in `msm_dp_bridge_detect()` / `msm_dp_hpd_plug_handle()`,
     runs `msm_dp_aux_reset()` on out-of-band USB-C DP AltMode, and cleans up with `phy_power_off()`
     when the link clock fails.
2. **Full Plasma 6 desktop on an external TV or monitor (`op9-desktop.service`):**
   - Choosing **Start Desktop** from the popup that appears when a USB-C HDMI dock is attached opens a
     full desktop on `tty7` with `PLASMA_DEFAULT_SHELL=org.kde.plasma.desktop` and
     `XDG_CONFIG_DIRS=/etc/xdg` (`kscreen-doctor output.DP-1.enable output.DP-1.priority.1
     output.DSI-1.disable`).
   - `op9-desktop-input` presents the phone's touchscreen as a landscape **keyboard plus multi-touch
     trackpad** (in `auto` mode it turns the screen off if an external USB or wireless keyboard and
     mouse are attached). Unplugging the dock brings `plasma-mobile.service` back on `tty1` within 3 s.
   - `systemsettings` (and `flatpak-kcm`) should be installed for the desktop settings.

## 10. A virtual (headless) full KDE Plasma 6 desktop over RDP

> These components are **not in this repository** either; they are local setup notes.

While Plasma Mobile keeps running untouched on the phone's screen, an isolated `kwin_wayland
--virtual` (`1920x1080`, `Scale: 1`) + `plasmashell` (`org.kde.plasma.desktop`) + `krdpserver
--plasma` session can run in the background on TCP `3389`:

- **Required packages:** `krdp`, `krdp-systemd`, `openssl`, `systemsettings`
- **Service and commands:**
  - `/usr/local/bin/op9-rdp-desktop-run` starts an isolated Plasma desktop plus `krdpserver` with its
    own `dbus-run-session` under `/run/user/1000/op9-rdp-desktop` (it shares the PipeWire/PulseAudio
    sockets and generates a self-signed TLS certificate at `~/.config/op9-rdp-desktop/krdp.{crt,key}`
    on first run).
  - `~/.config/systemd/user/op9-rdp-desktop.service` is off by default (started on demand, and it uses
    no RAM or battery while stopped).
  - `/usr/local/bin/op9-rdp-desktop {start|stop|restart|status}`
- **Plasma Mobile quick setting:**
  - `/usr/share/plasma/quicksettings/org.op9.quicksetting.rdpdesktop/` (`RDP Desktop` — `On (:3389)` /
    `Off`), added to the front of `enabledQuickSettings` in `~/.config/plasmamobilerc`. The source is
    in this repository: [op9-quick-settings](pmaports/community/op9-quick-settings).
- **Firewall (`/etc/nftables.d/60-op9-rdp.nft`):** TCP `3389` is accepted only on `wlan*`, `eth*`,
  `en*` (and `usb*`) interfaces; it is closed on cellular (`wwan*`).
- **Connecting from a PC (the RDP graphics pipeline, `/gfx`, is required):**

  ```sh
  xfreerdp3 /v:<phone-ip> /u:<user> /p:<password> /cert:ignore /gfx /dynamic-resolution
  ```

  (In Remmina, pick colour depth **`GFX RFX (32 bpp)`** or **`GFX AVC420`**.)
