# Hardware notes

What was found while bringing up this phone, for anyone working on SM8350 or similar devices.

## Boot

- The bootloader (ABL) rejects mainline-style device trees. It has to apply the stock DTBO to real
  downstream nodes. So the image carries the stock DTBs, and `CONFIG_ARM64_OP9_BUILTIN_DTB` swaps in
  the mainline one at boot.
- Images must be boot header v2 with an uncompressed `Image`. `scripts/mkboot.sh` is the reference:
  it also carries the tested cmdline. `pmbootstrap` defaults to header v3, which ABL rejects, so a
  postmarketOS image has to be repacked through `scripts/op9-boot-image.sh` before flashing.
- The firmware runs the Gunyah hypervisor. Its watchdog resets the phone after about 10 seconds
  unless it's handled early in boot.
- The boot GPT is on a UFS LUN with 4096-byte sectors and only 96 entries. Don't let `sgdisk` rewrite
  it. `tools/op9-slot.c` edits just the slot attribute bits.

## Components

The OnePlus 9 Pro (`lemonadep`) is the phone everything here was developed on. What differs on the
OnePlus 9 (`lemonade`) is listed in the next section.

| Part | Details |
|---|---|
| Panel | Samsung AMB670YF01, DSC command mode |
| Touch | Synaptics S3908, I2C4 at `0x4b`; GPIO 197 is an eGPIO |
| GPU | Adreno 660 |
| Wi-Fi and Bluetooth | QCA6490 v1, driven as a WCN6855 in `ath11k` with trimmed firmware memory |
| Speakers | 2x NXP TFA9874, I2C19 at `0x34` (top) and `0x35` (bottom) |
| Codec | WCD9380 over SoundWire; phone mics are DMIC1 and DMIC3 |
| Alert slider | 2x IST8801 hall sensors, I2C15 at `0x19` (up) and `0x18` (down), IRQ GPIOs 50 and 51 |
| Vibration | Awinic AW8697, I2C17 at `0x5a`, reset GPIO 75, 170 Hz motor |
| Flash | PM8350C flash controller, channels 1 and 2 |
| NFC | NXP SN100T, I2C15 at `0x28`, NCI 2.0; IRQ GPIO 87, enable GPIO 62, firmware GPIO 86 |
| Fingerprint | Goodix optical G3S, driven only by TrustZone secure apps; enroll blocked by boot-time secure storage, see [FINGERPRINT](FINGERPRINT.md) |
| Battery gauge | BQ28Z610, 2 cells in series |
| Wireless charging | IDT P9415 receiver at `0x3b` and HL7227 charge pump at `0x51`, on the I2C at `0x980000`; no drivers, the charger firmware handles basic power. PM8350C GPIO 2 turns the receiver off when high: the bootloader sets it if USB is attached at boot, and the battery driver keeps it off while USB is attached |
| Main camera | Sony IMX789, 3-trio C-PHY, AK7377 focus at `0x0c` |
| Ultrawide | Sony IMX766, C-PHY, LC898229 focus at `0x72` |
| Telephoto | OmniVision OV08A10, 2-lane D-PHY, AK7377 focus at `0x0f` |
| Mono | GalaxyCore GC02M1B, 1-lane |
| Front camera | Sony IMX471 |
| Sensors | On the SLPI, reached with hexagonrpcd and libssc |
| Modem | Integrated in the SM8350, runs `modem.mbn` with the carrier configs from `modem_pr`; storage from `modemst1`, `modemst2`, `fsg` and `fsc` through `rmtfs`. Voice, SMS, data, SIM and location services over QRTR |
| USB-C audio switch | FSA4480 on the SBU lines, for analog headset adapters |

## OnePlus 9 (`lemonade`)

Not "the 9 Pro with one camera fewer": the panel, the touch controller and the main sensor are all
different parts. These values were read from an LE2115 on Android 14 with
`/sys/firmware/devicetree/base`, not inferred from the 9 Pro.

| Part | OnePlus 9 | Notes |
|---|---|---|
| Bootloader identity | `oplus,dtsi_no = <0x4d67 0x4d71 0x5176>`, `ro.boot.prjname=19825` | `0x4d67` (19815) is shared with the 9 Pro; `0x4d71` is 19825 and `0x5176` is 20854. The model string is `Qualcomm Technologies, Inc. Lahaina MTP lemonadev` |
| Panel | Samsung **AMB655X**, 1080x2400, DSC command mode, 60 and 120 Hz | Stock also ships `ams662zs01` and BOE `nt37701` trees, so other units may differ. 24 bpp, 70x151 mm, `vout-gpios` on GPIO 25, normal brightness 0–2047 (default 360), HBM (`0x53=0xe0`) 3240–4095 |
| Panel timings | 120 Hz: hfp 52, hbp 24, hpw 24, vfp 4, vbp 8, vpw 4. 60 Hz: same but vfp 1208 | DSC slices 540x30 at both rates; clock 1102000000; `0x60 = 0x00` (60 Hz) / `0x10` (120 Hz) |
| Touch | Samsung **S6SY792**, I2C at `0x990000` bus, address `0x48`, IRQ GPIO 23, reset GPIO 22, 2.8 V enable GPIO 74 | 16 TX x 36 RX. Same command and event protocol as the S6SY761 |
| Touch rails | `vdd` 3.0 V (`pm8350c_l3`), `avdd` 1.8 V (`pm8350c_l8`) | Reads as 1.8 V/2.8 V in the vendor tree; see the caveat below |
| Main camera | Sony **IMX689** (`cci0_i2c0` @ `0x1a`, CSIPHY1 C-PHY, MCLK0 GPIO 100, reset GPIO 16) | `semco_imx689`: AVDD GPIO 196, DVDD GPIO 66, `lc898229` VCM @ `0x72`, `24c128` EEPROM @ `0x50`, rotation 90 |
| Ultrawide | Sony **IMX766** (`cci0_i2c1` @ `0x1a`, CSIPHY2 C-PHY, MCLK1 GPIO 101, reset GPIO 106) | AVDD GPIO 93, DVDD GPIO 97, `ak7375c` VCM @ `0x74` (matching `sunny_imx766_ak7375c` / EEPROM `0xe9`; some units use `lc898229` @ `0x72`), `24c128` EEPROM @ `0x51`, rotation 90 |
| Telephoto | **none** | The 9 Pro's OV08A10 has no equivalent here; `pm8008j` is unpopulated |
| Mono | GalaxyCore **GC02M1B** (`cci1_i2c0` @ `0x37`, CSIPHY0 1-lane, MCLK2 GPIO 102, reset GPIO 167) | AVDD GPIO 195, rotation 90 |
| Front camera | Sony **IMX471** (`cci1_i2c1` @ `0x10`, CSIPHY5 4-lane, MCLK3 GPIO 103, reset GPIO 115) | VANA GPIO 125, `24c64` EEPROM @ `0x54`, rotation 270 |
| SLPI sensors | `oplus-sensor` node from `lemonadev` DTBO | Uses `lemonade` `sensors/registry` calibration (version 4) from `persist` |
| Charging / wireless | `pmic_glink` (`oplus,fuel-gauge`, OTG boost / wireless-RX GPIOs) | LE2115 / `lemonadev` includes IDT P9415 15 W wireless RX support; regional variants without coil may differ |
| Splash | Reserved `splash_region` at `0xe4d00000`, 1080x2400 | Not the 9 Pro's 1080x2412 scaled mode |
| USB | Product string reports "OnePlus 9" (`otg` role-switch defaulting to `peripheral`) | Same gadget and NCM setup |

Caveat on the touch rails: the vendor node names `vcc_1v8` and `vdd_2v8`, but this driver inverts
the usual naming, so what is wired where still has to be confirmed by reading the controller's
ID registers after the first boot. If touch does not probe, check these two supplies first.

## Things that cost a lot of time

- **Memory scaling:** mainline `sm8350.dtsi` had no bandwidth monitors, no CPU or L3 votes, and no GPU
  memory path, so DDR stayed slow under load (3–4 GB/s memcpy). 4K60 video then made the video
  firmware time out while parsing VP9 headers.
- **CPU capacity:** `sm8350.dtsi` had no `capacity-dmips-mhz`, so every core reported the same capacity
  and browser work landed on A55s by chance. Energy-aware scheduling then made scrolling worse, so
  `rootfs/etc/sysctl.d/90-op9-sched.conf` turns it off.
- **Firmware log:** gen1 Iris firmware reports useful errors if you send `HFI_PROPERTY_SYS_DEBUG_CONFIG`.
  That's what exposed the VP9 timeout.
- **Display flashes:** in command mode with autorefresh, `CTL_START` never fires, so flip events
  went out before the flush latched and the compositor painted over the buffer being scanned out.
- **Wi-Fi firmware crashes:** PCIe had no interconnect votes, so the link starved once boot votes
  were dropped.
- **Sleep drain:** the MI2S bit clock was never stopped in the DSP, so the ADSP couldn't sleep.
- **USB replug:** charger detection takes over DP/DM and leaves the PHY in a state that stops
  re-enumeration, so the PHY datapath has to be reclaimed.
- **OTG:** the charger firmware keeps Type-C sink-only until the AP sets the OnePlus-specific properties.
- **Bluetooth address:** the chip has none, so the kernel leaves the controller unconfigured and BlueZ
  sees nothing. `btmgmt --index 0 public-addr` configures it at runtime. Stock reads it from the
  modem over QMI, and so does `op9-addresses`: `qmicli -p -d qrtr://0 --dms-get-mac-address=bt`
  (and `=wlan` for Wi-Fi) returns the addresses byte-reversed, about 6 s into boot after `rmtfs`,
  without ModemManager.
- **Modem bring-up:** the kernel side was complete; the modem only needed `rmtfs`, `tqftpserv` and
  ModemManager in userspace. Three things stock's radio layer does that nothing on Linux did:
  open the SIM's provisioning session (without it ModemManager reports "GW primary session index
  unknown"), answer the modem's request on QMI service 770 to bring up the `ims` data connection
  before IMS registers (`81voltd`), and register as the location service's "master client" with a
  fixed key before starting GPS (otherwise every start request fails with GeneralError).
- **Call audio:** the voice stream never reaches the AP. It's routed inside the audio DSP, like stock's
  `voicemmode1-call`: from the modem to TERT_MI2S_RX (the speaker amplifiers) and from
  TX_CODEC_DMA_TX_3 (the microphones). Opening the hostless VoiceMMode1 PCM starts the session.
- **Earpiece:** it's the top TFA9874 in stock's "receiver" profile: boost converter off, input 6 dB
  down, speaker gain code 13, low-noise mode, bottom amplifier off.
- **Stock speaker tuning:** the TFA9874 has no DSP of its own (`tfa98xx.cnt` carries a
  `9874_dummy.patch`). Stock's speaker protection, EQ and multiband DRC are NXP's algorithm running
  in the Qualcomm audio DSP, configured with the container's `.msg` files over APR, with the
  amplifiers' current/voltage feedback routed back to it. Running it on mainline would need that
  whole AFE path; Linux uses the PipeWire limiter instead.
- **Stock camera colour:** each `com.qti.tuned.<module>.bin` is a byte-packed Chromatix file. Its
  `cc13` colour matrices are 56-byte entries: colour-temperature start and end (float32), the 3x3
  matrix (float32, rows R, G, B) and three offsets. The libcamera tuning files in `rootfs/` use the
  normal-light set of each sensor.
- **Panel:** the AMB670YF01 has Display P3 primaries, and stock does its colour modes in the
  display engine (its panel colour-mode commands are empty). High-brightness mode is `0x53 = 0xe0`
  with brightness 3538-4095; stock leaves panel revisions (ID2, DCS `0xdb`) below 3 out of it.
- **Unsafe register access:** reading unclocked display or LPASS registers from Linux, for example
  through `/dev/mem`, hangs the phone. Only use `tools/bringup/regdump.c` if you know the clocks are on.
- **A held-in-reset peripheral looks like a broken bus.** The OnePlus 9's touchscreen returned
  `EIO` for every address on its I2C bus, with `gpi 900000.dma-controller: Error in Transaction`
  and `geni_i2c 990000.i2c: GPI transfer failed: -5`, because the driver's reset pulse left the
  `GPIO_ACTIVE_LOW` line asserted. The tell is a control read: a *missing* device answers `ENXIO`
  ("No such device or address"), while a bus that cannot move a byte answers `EIO`. Reach for
  `tools/bringup/i2c-probe.c` before blaming the bus.
- **GENI serial engines differ.** Read `GENI_IF_DISABLE_RO` (`+0x64`) before assuming FIFO mode is
  available: on the OnePlus 9 `i2c4` (SE4, `0x990000`) it reads `0x1`, so that engine can only do
  GPI DMA, while `i2c1` (SE1, `0x984000`) reads `0x0` and uses the FIFO. That matters when
  debugging, because a failing GPI transfer aborts in the engine and never reports a NACK.
