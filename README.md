# postmarketOS on the OnePlus 9 and 9 Pro

[![Kernel build](https://github.com/ket0x4/oneplus9-postmarketos/actions/workflows/kernel.yml/badge.svg)](https://github.com/ket0x4/oneplus9-postmarketos/actions/workflows/kernel.yml)
[![Tree checks](https://github.com/ket0x4/oneplus9-postmarketos/actions/workflows/checks.yml/badge.svg)](https://github.com/ket0x4/oneplus9-postmarketos/actions/workflows/checks.yml)

Mainline Linux 7.3 on the OnePlus 9 (`lemonade`) and OnePlus 9 Pro (`lemonadep`), both Snapdragon
888 / SM8350. No Android underneath: the kernel boots postmarketOS directly from its own initramfs.

One kernel image serves both phones. It carries both device trees and picks one from the project
number the bootloader reports, and it embeds nothing phone-specific: the Wi-Fi and Bluetooth
addresses are read from the modem at boot.

This runs on real phones and is usable as a daily driver, but it is not a distribution. There is no
installer and no prebuilt root filesystem, and installing wipes the phone.

## Read this first

- **Installing erases Android and everything on the phone.** Back up your partitions before
  starting, especially `persist` and the EFS partitions: they are unique to your phone and cannot be
  regenerated.
- **You can brick your phone.** No one here can repair it for you.
- **Never write to** `xbl`, `persist`, `modem`, the EFS partitions or `param`.
- **The install steps have never been replayed from scratch.** They are written from how these phones
  got here, so expect to troubleshoot.
- **One phone of each has been tested:** a T-Mobile LE2127 (9 Pro, project `2085A`) and an LE2115
  (OnePlus 9). Other models and regional variants may differ.

## Status

Tested with both the Phosh and the Plasma Mobile shells.

| Feature | State | Notes |
|---|---|---|
| Display | Works | 9 Pro: 1440x3216 and 1080x2412 up to 120 Hz. 9: 1080x2400 at 60 or 120 Hz. Sunlight boost switches on in bright light; a quick setting picks Natural (sRGB) or Vivid |
| Touch | Works | 10 points. A quick setting raises the report rate from 120 Hz to stock's 360 Hz |
| GPU | Works | OpenGL 4.6, ES 3.2, Vulkan 1.3 |
| Wi-Fi | Works | Up to 6 GHz, 160 MHz, with the phone's own address read from the modem at boot |
| Bluetooth | Works | Pairing and music tested with a headset; headset microphone untested. Bluetooth LE scanning works |
| USB-C | Works | Device and host modes, 5 Gbps USB 3 |
| HDMI over USB-C | Works | With a USB-C to HDMI adapter. Two USB-C docks gave USB 3 but no display |
| Desktop mode | Partial | A display offers a full desktop, with the phone screen as a keyboard and trackpad that vibrate under your fingers. Docks and MST hubs do not work |
| Charging | Works | USB-C PD, about 25 W, to stock's limits: stops at 100% and reports full until unplugged. Plugging in wakes the phone, and it stays awake while charging so the temperature limits keep running |
| Wireless charging | Partial | Slow, about 2 W, tested only on another phone's reverse charging. USB takes over if both are attached |
| Charging status | Works | The screen lights up with a buzz when charging starts; the lock screen shows type and speed |
| Speakers and microphones | Works | A limiter and high-pass filter guard the speakers where the plugins exist. Not stock's full speaker protection, which runs in the audio DSP |
| Earpiece | Works | The top speaker in stock's receiver profile. Loudness not yet judged by ear |
| Sensors | Works | Accelerometer, light, proximity, compass, auto-rotate |
| Video decoding | Works | H.264 and VP9 in hardware up to 4K60, including in Firefox. This chip has no AV1 hardware |
| Memory and CPU scaling | Works | DDR, LLCC and L3 scale with load, and the scheduler knows which cores are fast |
| Buttons | Works | Power, volume up, volume down |
| Alert slider | Works | Top silent, middle vibrate, bottom ring |
| Vibration | Works | Haptics through the shell's feedback, including keyboard ticks |
| Flashlight | Works | Quick setting with adjustable brightness |
| Cameras | Partial | Main, ultrawide, telephoto and front work with autofocus through libcamera's software ISP, using stock's colour matrices. The mono camera is raw only. Stock's denoise, sharpening and HDR run in the Spectra ISP, which mainline does not drive |
| NFC | Partial | The stack detects cards. No app is included, and tap-to-pay is not possible |
| Firefox | Works | Phone layout with mobile sites, and hardware video decoding. YouTube's mobile page clips its left edge unless zoomed to 80% |
| Android apps | Works | Waydroid with Android 13 (LineageOS 20): GPU acceleration, internet, sound and Google Play. A Stop Android launcher shuts it down |
| App launching | Works | No loading splash, since apps here usually open before it would be dismissed |
| Sleep | Partial | Sleeps and wakes at about 40 to 44 mA. The chip does not reach its deepest sleep state |
| USB-C analog headset | Partial | Routing is set up; untested without an analog adapter |
| Mobile data | Works | LTE, IPv4 and IPv6, tested on AT&T |
| Calls | Works | VoLTE both directions with audio through the earpiece; speaker and mute from the call screen. Headsets and Bluetooth are not routed during calls yet |
| SMS | Works | Sending and receiving over IMS |
| MMS | Works | Picture messages with mmsd-tng and Chatty |
| GPS | Works | Through geoclue. A first fix takes about a minute outdoors without assistance data, and fixes stay within about 11 m of each other |
| x86 games | Partial | Steam and Half-Life 2 run through the FEX emulator. Steam's interface is slow to start. Optional |
| Fingerprint | Not working | Driven entirely by TrustZone secure apps. They load on mainline, but enrollment hits a boot-time secure-storage wall. See the [write-up](docs/FINGERPRINT.md) |

More detail, including the exact checks behind each row, is in [docs/STATUS.md](docs/STATUS.md).

## What's here

| Folder | Contents |
|---|---|
| [`patches/`](patches) | Everything that changes someone else's source: `kernel/` is the 167-patch Linux 7.3 series, the rest are the pmaports patches (libcamera, phoc, wlroots, ModemManager, 81voltd, hexagonrpc, iio-sensor-proxy) |
| [`kernel/`](kernel) | The kernel config, the reproducible build script and the build manifest |
| [`initramfs/`](initramfs) | Early boot: a USB network and rescue shell, then the switch to the root filesystem |
| [`rootfs/`](rootfs) | udev rules, systemd units, ALSA UCM, WirePlumber and TuneD files to overlay onto a postmarketOS rootfs |
| [`postmarketos/`](postmarketos) | The pmaports packages (both device packages and the patched libcamera, phoc, wlroots, ModemManager, 81voltd, hexagonrpc, iio-sensor-proxy and quick settings), apk triggers, the image builder, and the [install guide](postmarketos/GUIDE.md) |
| [`firefox/`](firefox) | The FFmpeg patch and the shim that give Firefox hardware video decoding, and its settings |
| [`scripts/`](scripts) | Packing a boot image from a release and your own `vendor_boot.img`, and USB internet sharing |
| [`tools/`](tools) | The programs the phone runs (`touchboost`, `alert-slider`, `op9-slot`, `dmcreate`), `bringup/` probes for hardware debugging, and `generators/` for panel and sensor code |
| [`docs/`](docs) | [Status](docs/STATUS.md), [hardware notes](docs/HARDWARE.md) and the [fingerprint write-up](docs/FINGERPRINT.md) |

### Not included

Firmware is proprietary, so it is not here: you copy it from your own phone. So is the stock device
tree blob the bootloader insists on, which the boot image script takes from your `vendor_boot.img`.
Sensor calibration is specific to each phone, so that comes from your phone too.

## Getting started

Follow the [postmarketOS install guide](postmarketos/GUIDE.md). You need a Linux PC, an unlocked
bootloader, and experience recovering a phone from fastboot. Building the kernel yourself also needs
an `aarch64-linux-gnu` cross compiler; a [release](https://github.com/ket0x4/oneplus9-postmarketos/releases)
has a prebuilt one.

In short:

1. Build the kernel: `kernel/build.sh work`.
2. Have `pmbootstrap` make a Phosh or Plasma Mobile systemd image for `oneplus-lemonade` or
   `oneplus-lemonadep`.
3. Run `postmarketos/build-pmos-image.sh <dir>` and the `populate-mounted-rootfs.sh` it writes, to
   install the kernel modules, your firmware and the `rootfs/` overlay into the mounted image.
4. Repack the boot image through `scripts/op9-boot-image.sh`, because the bootloader rejects the
   header `pmbootstrap` writes.

The guide covers each step, the `/dev/op9/userdata` layout, the patched packages and the modem
stack.

## Reproducible builds

The same inputs give the same artifacts. Two builds of this kernel in different directories produce
byte-identical `Image` files. Everything that goes into a build is pinned, and nothing reads the
clock or the build machine's paths.

```sh
kernel/build.sh work                      # Image, modules, build-manifest.txt and Image.sha256
initramfs/busybox.sh work/busybox
initramfs/build.sh work/busybox work/initramfs.gz
```

- **The kernel base is a commit, not a tag.** `kernel/build.sh` pins Linux 7.3 by hash
  (`c03c1a14`), so a re-tagged or deleted tag upstream cannot change what gets built. Override with
  `KERNEL_COMMIT=`.
- **The patch series is hashed.** The build records the sha256 of `patches/kernel/*.patch` and only
  re-applies the series when it, or the base commit, changes. An interrupted run is redone from the
  base rather than building a half-applied tree.
- **The clock does not leak in.** `SOURCE_DATE_EPOCH` comes from the base commit's date and feeds
  both `KBUILD_BUILD_TIMESTAMP` and the initramfs archive. The initramfs is built with sorted
  entries, `cpio --reproducible` and `gzip -n`.
- **Debug info is off** in the shipped config, which keeps `Image` at about 39 MB instead of
  hundreds.
- **`work/build/build-manifest.txt`** records the base commit, the patch-series hash, the config
  hash, the timestamp and the compiler. Releases ship it and print it in their notes.
- **Third-party inputs are pinned:** busybox 1.37.0 and FFmpeg n9.0.2 with sha256 checksums, every
  pmaports source and patch with sha512, and the GitHub Actions by commit rather than by tag.

CI builds the initramfs twice and fails if the two differ. A full `Image` rebuild is left to the
release job, since it takes too long for every push; compare against the manifest's `Image.sha256`
when you rebuild a release.

If your source tree has local changes, `kernel/build.sh` refuses to reset it. Set
`KERNEL_FORCE_RESET=1` to discard them deliberately.

## Contributing

Reports from other models are the most useful thing anyone can send. Please open an issue with your
model number, your firmware version, and what happened, whether it worked or not.

## Patch quality

Many patches are marked `WIP` or `HACK`. They get these phones working but are not ready for
upstream. Review them before relying on them, and rework any you want to submit elsewhere.

## Credits

This builds on other people's work, and their authorship is kept in the patches:

- **Nia Espera** and **Caleb Connolly**, and the [sm8350-mainline](https://gitlab.com/sm8350-mainline)
  project, for the original port.
- **David Heidelberg** for the CAMSS C-PHY series.
- **Vsevolod Nevorotov** for the Synaptics TouchComm driver.
- **Stephan Gerhold**, **Richard Acayan**, **Vincent Knecht**, **Otto Pflüger**, **Bhushan Shah** and
  **Val Packett** for the q6voice call audio series, as carried by
  [sc7280-mainline](https://gitlab.com/sc7280-mainline) for the Fairphone 5.
- **postmarketOS** for 81voltd, mobile-config-firefox and the pmaports tree this builds on, and
  **linux-msm** for rmtfs, tqftpserv, qrtr and hexagonrpc.
- The Linux, postmarketOS, Alpine, Phosh, KDE and linux-msm communities.

Much of this port was written with Claude Code (Anthropic).

## License

GPL-2.0-only, matching the kernel. See [LICENSE](LICENSE). Patches for other projects are under
those projects' licenses.
