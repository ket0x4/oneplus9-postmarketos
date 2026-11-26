# Patch status

The kernel series is 167 patches on Linux 7.3. Most of them describe hardware
that works and are only waiting for someone to send them upstream; the ones
marked below are the ones that are **not** ready, and the README warns about
them for a reason: they run on this port, but they are not in a state to be
proposed as they are.

`grep -l '^Subject: \[PATCH[^]]*\] \(WIP\|HACK\|UNFINISHED\|UNTESTED\)' patches/kernel/*.patch`
lists them; this file says which is which and why.

## What the markers mean

| Marker | Meaning |
|---|---|
| `WIP` | The feature works on the phone but the series is not finished: further patches in the same area are still expected, or the design would change before submission |
| `HACK` | Deliberately wrong in a way that makes the hardware work here: a vendor behaviour guessed from a downstream tree, a check relaxed, a value hard-coded for this phone. These are the ones that must **not** be sent upstream as they are |
| `UNFINISHED` | Started but known incomplete; the driver or node does not do everything its name suggests |
| `UNTESTED` | Believed correct but never exercised on hardware |

## The patches

| Patch | Marker | Subject |
|---|---|---|
| `0006` | UNFINISHED | firmware: Add synaptics tcm oncell fw loader driver |
| `0008` | UNFINISHED | arm64: dts: qcom: sm8350-lemonade(p): More feature bringup |
| `0007` | UNTESTED | arm64: dts: qcom: sm8350: Add 4pin config for uart18 node |
| `0010` | HACK | OnePlus 9 Pro bring-up: built-in DTB, Gunyah wdt, splash autorefresh |
| `0017` | HACK | drm/msm/dpu: keep command mode panels refreshed with autorefresh |
| `0024` | HACK | usb: dwc3/femto: reclaim the USB2 PHY datapath from charger detection |
| `0025` | HACK | power: qcom_battmgr: allow skipping the ADSP battery on OnePlus 9 Pro |
| `0033` | HACK | mfd: qcom-pm8008: allow boards without an interrupt line |
| `0077` | HACK | drm/msm/dpu: flush command mode commits between autorefreshes |
| `0079` | HACK | soc: qcom: describe the OnePlus sensors to the SLPI |
| `0081` | HACK | power: qcom_battmgr: OnePlus OTG and raw USB property debugfs |
| `0083` | HACK | phy: qcom: snps-femto-v2: reclaim DP/DM in host mode too |
| `0084` | HACK | power: qcom_battmgr: OnePlus OTG: enable the wireless RX path too |
| `0086` | HACK | clk: qcom: dispcc-sm8250: don't park the MDP, AHB and VSYNC RCGs at boot |
| `0091` | HACK | power: qcom_battmgr: OnePlus charging policy for USB-C PD |
| `0093` | HACK | power: qcom_battmgr: don't carry the input limit between chargers |
| `0098` | HACK | drm/msm/dpu: hold autorefresh flip events until the flush is latched |
| `0139` | HACK | arm64: rebuild the OnePlus 9 Pro built-in DTB object when the DTB changes |
| `0141` | HACK | power: supply: core: let an extension replace a supply's own properties |
| `0150` | HACK | soc: qcom: handle the OnePlus 9 in the bring-up splash path |
| `0015` | WIP | wifi: ath11k: bring-up of QCA6490 v1 (HSP 1.1) silicon |
| `0016` | WIP | drm/panel: add Samsung AMB670YF01 and enable MSM DSI on OnePlus 9 Pro |
| `0036` | WIP | arm64: dts: qcom: sm8350-oneplus: camera PMICs and front IMX471 |
| `0053` | WIP | arm64: dts: qcom: sm8350-oneplus-lemonadep: main camera |
| `0055` | WIP | arm64: dts: qcom: sm8350-oneplus-lemonadep: ultrawide camera |
| `0058` | WIP | arm64: dts: qcom: sm8350-oneplus-lemonadep: camera EEPROMs, IMX789 binned link rate |
| `0060` | WIP | arm64: dts: qcom: sm8350-oneplus-lemonadep: telephoto camera |
| `0062` | WIP | arm64: dts: qcom: sm8350-oneplus-lemonadep: mono camera, rear module rotations |
| `0063` | WIP | arm64: dts: qcom: sm8350-oneplus-lemonadep: main camera focus motor |
| `0065` | WIP | arm64: dts: qcom: sm8350-oneplus-lemonadep: ultrawide focus motor |
| `0067` | WIP | arm64: dts: qcom: sm8350-oneplus-lemonadep: telephoto focus motor |
| `0068` | WIP | wifi: ath11k: more QCA6490 v1 bring-up knobs |
| `0070` | WIP | wifi: ath11k: QCA6490 v1 comes up (scan works) |
| `0071` | WIP | arm64: dts: qcom: sm8350-oneplus-lemonadep: Wi-Fi MAC address |
| `0072` | WIP | wifi: ath11k: run QCA6490 v1 as WCN6855, data path works |
| `0073` | WIP | wifi: ath11k: no firmware assisted suspend on QCA6490 v1 |
| `0075` | WIP | wifi: ath11k: let QCA6490 v1 suspend again |
| `0076` | WIP | drm/panel: amb670yf01: run at 120 Hz |
| `0080` | WIP | wifi: ath11k: settle the QCA6490 v1 configuration, drop bring-up knobs |
| `0082` | WIP | arm64: dts: qcom: sm8350-oneplus-lemonadep: OTG VBUS boost GPIO |
| `0087` | WIP | drm/msm/dsi: phy: 7nm: adopt a PLL left running by the bootloader |
| `0088` | WIP | arm64: dts: qcom: sm8350-oneplus-lemonadep: hold the splash clocks in simple-framebuffer |
| `0092` | WIP | drm/panel: amb670yf01: expose 1440x3216 and 1080x2412 at 60/90/120 Hz |
| `0105` | WIP | arm64: dts: qcom: sm8350-oneplus-lemonadep: Bluetooth address |

## What this means in practice

- **Camera device trees** (`0036`, `0053`–`0067`, `0071`, `0082`, `0088`, `0105`) are marked WIP
  because they were written per-sensor and split by sensor rather than by logical change. They work
  and are tested; upstream wants them folded into the board DTS.
- **`qcom_battmgr` HACKs** (`0025`, `0081`, `0084`, `0091`, `0093`) carry OnePlus charging policy
  that belongs in a power-supply extension, not in the driver. `0141` exists to make that possible,
  and `0111`/`0142`/`0113` are the parts already shaped for upstream.
- **The ath11k QCA6490 series** (`0015`, `0068`, `0070`, `0072`, `0073`, `0075`, `0080`) is the
  largest WIP cluster: the chip is not supported upstream and this runs it as a WCN6855 with
  firmware quirks.
- **Display HACKs** (`0017`, `0077`, `0098`, `0086`) work around the DPU's command-mode refresh and
  clock parking. They are the most likely to become unnecessary as the driver improves, and the
  most awkward to justify upstream in their current form.

Anything not in the table above is a normal patch: it does what its subject says, and nothing in it
is flagged as temporary. That does not mean it is ready to post, only that it is not marked as
known-incomplete.
