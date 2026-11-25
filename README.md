# postmarketOS on the OnePlus 9 and 9 Pro

[![Kernel build](https://github.com/ket0x4/oneplus9-postmarketos/actions/workflows/kernel.yml/badge.svg)](https://github.com/ket0x4/oneplus9-postmarketos/actions/workflows/kernel.yml)
[![Tree checks](https://github.com/ket0x4/oneplus9-postmarketos/actions/workflows/checks.yml/badge.svg)](https://github.com/ket0x4/oneplus9-postmarketos/actions/workflows/checks.yml)

Mainline Linux 7.3 on the OnePlus 9 (`lemonade`) and 9 Pro (`lemonadep`), both Snapdragon 888.
No Android underneath: the kernel boots postmarketOS from its own initramfs.

One kernel serves both phones. It carries both device trees, picks one from the project number the
bootloader reports, and embeds nothing phone-specific: the Wi-Fi and Bluetooth addresses are read
from the modem at boot.

Usable as a daily driver, but not a distribution. There is no installer and no prebuilt root
filesystem, and installing wipes the phone.

## Read this first

- **Installing erases Android and everything on the phone.** Back up first, especially `persist` and
  the EFS partitions: they are unique to your phone and cannot be regenerated.
- **You can brick your phone,** and no one here can repair it.
- **Never write to** `xbl`, `persist`, `modem`, the EFS partitions or `param`.
- **The install steps have never been replayed from scratch,** so expect to troubleshoot.
- **Tested on one of each:** a T-Mobile LE2127 (9 Pro) and an LE2115 (OnePlus 9). Other variants may
  differ.

## Status

Tested with both Phosh and Plasma Mobile.

**Works:** display (up to 120 Hz, sunlight boost, Natural or Vivid colour), 10-point touch with an
optional 360 Hz report rate, GPU (Vulkan 1.3), Wi-Fi 6, Bluetooth, USB 3 device and host mode, HDMI
over USB-C, charging to stock's limits with a charging notification, speakers, earpiece, sensors,
H.264 and VP9 video decoding in hardware, CPU and DDR scaling, buttons, alert slider, haptics,
flashlight, Android apps through Waydroid, mobile data, VoLTE calls, SMS and MMS through Chatty,
and GPS.

**Partial:** desktop mode (a display offers a full desktop, but docks and MST hubs do not work);
wireless charging (about 2 W, tested only on another phone's reverse charging); cameras (main,
ultrawide, telephoto and front work with autofocus and stock's colour matrices, and the software ISP
runs on the CPU with the optional denoise/unsharp pass off by default because it is too slow for
preview; stock's Spectra HDR, multi-frame noise reduction and tone mapping are still not driven, and
the greyscale mono camera is disabled, matching the Arch port); NFC (cards are detected,
there is no app and no tap-to-pay); sleep (40 to 44 mA, but not the chip's deepest state); USB-C
analog headsets (routed, untested with an adapter); x86 games through FEX (works, slow to start).

**Does not work:** the fingerprint reader. It is driven entirely by TrustZone secure apps, which load
on mainline but hit a boot-time secure-storage wall. See the [write-up](docs/FINGERPRINT.md).

[docs/STATUS.md](docs/STATUS.md) has the detail and the exact checks behind each item.

## What's here

| Folder | Contents |
|---|---|
| [`patches/`](patches) | Everything that modifies upstream source: `kernel/` is the 167-patch Linux 7.3 series, the rest are the pmaports patches |
| [`kernel/`](kernel) | The kernel config and a reproducible build script |
| [`initramfs/`](initramfs) | Early boot: USB network and rescue shell, then the root filesystem |
| [`rootfs/`](rootfs) | udev, systemd, ALSA, WirePlumber and TuneD overlay |
| [`postmarketos/`](postmarketos) | pmaports packages, the image builder and the [install guide](postmarketos/GUIDE.md) |
| [`scripts/`](scripts) | Packing a boot image and USB internet sharing |
| [`tools/`](tools) | Programs for the phone, `bringup/` probes and `generators/` |
| [`docs/`](docs) | [Status](docs/STATUS.md), [hardware notes](docs/HARDWARE.md) and the [fingerprint write-up](docs/FINGERPRINT.md) |

**Not included:** firmware, the stock device tree blob the bootloader insists on (taken from your
`vendor_boot.img`), and sensor calibration. All three come from your own phone.

## Getting started

Read the [install guide](postmarketos/GUIDE.md). You need a Linux PC, an unlocked bootloader, and
experience recovering a phone from fastboot.

1. `kernel/build.sh work` builds the kernel.
2. Let `pmbootstrap` make a Phosh or Plasma Mobile image for `oneplus-lemonade` or
   `oneplus-lemonadep`.
3. `postmarketos/build-pmos-image.sh <dir>`, then the `populate-mounted-rootfs.sh` it writes,
   installs the modules, your firmware and the `rootfs/` overlay into the mounted image.
4. `scripts/op9-boot-image.sh` repacks the boot image, because the bootloader rejects the header
   `pmbootstrap` writes.

## Reproducible builds

Two builds in different directories give byte-identical `Image` files when they use the same compiler
and linker version, which `work/build/build-manifest.txt` records. The kernel is built with GCC
(`aarch64-linux-gnu-gcc`) and `CONFIG_LTO_NONE`; a clang ThinLTO build is available
(`TOOLCHAIN=clang`) but that kernel does not boot on this phone, so it is not the default. The
kernel base is pinned by commit rather than tag, the patch series is hashed, `SOURCE_DATE_EPOCH`
comes from the base commit, debug info is off, modules are zstd-compressed, and every third-party
input has a checksum. `work/build/build-manifest.txt` records what went in, `kernel/build.sh` uses
`ccache` when it is installed (it only speeds rebuilds up), and CI builds the initramfs twice and
fails if the two differ.

If your source tree has local changes, `kernel/build.sh` refuses to reset it; set
`KERNEL_FORCE_RESET=1` to discard them.

## Contributing

Reports from other models are the most useful thing anyone can send. Open an issue with your model
number, firmware version and what happened.

Many patches are marked `WIP` or `HACK`: they work here but are not ready for upstream. Review them
before relying on them.

## Credits

Where a patch is someone else's, its authorship is kept in the patch's `From:` line.

**Prior ports of this hardware.** These two are why this one exists. Neither is a fork of the other:
they are independent efforts, and reading them made this port possible.

- **[LuCiLuna/oneplus9pro-arch](https://github.com/LuCiLuna/oneplus9pro-arch)**, maintained by
  **[LuCiLuna](https://github.com/LuCiLuna)** (Nex) — the original Arch Linux ARM port of the 9 Pro
  and the direct ancestor of this tree. The patch series, kernel config, initramfs, `rootfs/`
  overlay, most of the `tools/` programs and the boot-image packaging come from there, as does the
  reverse-engineering in [HARDWARE](docs/HARDWARE.md). This repository extends that work to the
  OnePlus 9, moves it to postmarketOS, and adds the reproducible build.
- **[bluelightsaber/oneplus9pro-postmarketos](https://github.com/bluelightsaber/oneplus9pro-postmarketos)**,
  maintained by **[bluelightsaber](https://github.com/bluelightsaber)** — an independent
  postmarketOS port that runs the 9 Pro as a headless server. Coming from the other direction, it
  reached the same conclusions about the boot chain, the A/B slot flags, USB host mode over a
  powered hub and the QCA6490/WCN6851 firmware; credit for that trail belongs there.

**Upstream work carried in the patches.**

- **Nia Espera** and **Caleb Connolly**, and the [sm8350-mainline](https://gitlab.com/sm8350-mainline)
  project, for the original device trees and drivers.
- **David Heidelberg** for the CAMSS C-PHY series, and **Vsevolod Nevorotov** for the Synaptics
  TouchComm driver.
- **Stephan Gerhold**, **Richard Acayan**, **Vincent Knecht**, **Otto Pflüger**, **Bhushan Shah** and
  **Val Packett** for the q6voice call audio series, as carried by
  [sc7280-mainline](https://gitlab.com/sc7280-mainline) for the Fairphone 5.
- **postmarketOS** for 81voltd, mobile-config-firefox and the pmaports tree this builds on, and
  **linux-msm** for rmtfs, tqftpserv, qrtr and hexagonrpc.
- The Linux, postmarketOS, Alpine, Phosh, KDE and linux-msm communities.

Much of this port was written with Claude Code (Anthropic).

## License

GPL-2.0-only, matching the kernel. See [LICENSE](LICENSE).
