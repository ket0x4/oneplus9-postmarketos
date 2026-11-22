# Status

Tested on one T-Mobile LE2127 running kernel 7.3 with this patch series.

## OnePlus 9 (`lemonade`)

The kernel now carries a second device tree for the OnePlus 9 and picks between the two at boot
(patch 0149). What that tree describes, and how it was measured, is in
[HARDWARE](HARDWARE.md#oneplus-9-lemonade).

Verified live on an LE2115 (kernel `7.3.0-op9+ #13`, patches 0001–0167):

- **Boot & slot**: `boot_a` (`active=1`, `successful=1` marked by `op9-boot-successful` /
  `op9-slot`), no reset or watchdog bite.
- **Device tree selection**: `op9: oplus,dtsi_no = 0x4d71 0x4d67 0x5176`, then
  `op9: OnePlus 9, using the second embedded device tree`.
- **Storage & swap**: all five UFS LUNs; `/dev/op9/userdata` online-expanded to `101G` (`89G` free)
  and `/dev/zram0` (`3.4G` zstd swap) active.
- **USB & gadget**: `18d1:d001` NCM + serial (`172.16.42.1`), SSH and NAT internet sharing active.
- **Display**: Samsung **AMB655X** DRM panel driver binds on `ae94000.dsi.0`, exposed in
  `wlr-randr` as `DSI-1` (`70x151 mm`, `1080x2400` at `120 Hz` preferred/current and `60 Hz`, scale
  `3.0`), `vout-gpios` (GPIO 25), `max_brightness` `2047`, and `hbm`/`hbm_active` sysfs (`0x53 =
  0xe0` across `3240–4095`). Patch 0161 guards backlight DCS writes while the panel is unprepared,
  eliminating wake-time `EPROTO` / `EINVAL` errors.
- **Touch**: Samsung **S6SY792** (`0x3792`, 10 slots) works cleanly; `tools/touchboost.c` (updated to
  auto-detect by `INPUT_PROP_DIRECT` + multitouch abs bits) runs as an active service. Patch `0165`
  adds the `report_rate` sysfs attribute (`120`, `240` or `360` Hz via register `0x45` from stock
  `sec-s6sy792`), controlled by both `op9-quick-settings` (`op9-touch-rate-quick-setting`, Phosh)
  and its Plasma Mobile `Touch 360 Hz` tile, and
  `tuned` (`360` Hz in `op9-performance`, `120` Hz in `op9-balanced` / `op9-powersave`).
- **Phosh 0.59 desktop & apps**: GDM replaced with `phosh` (`display-manager.service -> phosh.service`);
  `phoc-op9` (`0.59.0-1`), `wlroots0.20-op9` (`0.20.2-1`), `squeekboard`, `feedbackd`,
  `xdg-desktop-portal-phosh`, `gnome-keyring` (PAM `pam_gnome_keyring.so`), `op9-alert-slider`,
  `op9-charge-status`, `op9-sunlight-hbm`, `op9-no-splash`, everyday mobile apps (`gnome-calls`,
  `chatty`, `gnome-contacts`, `gnome-clocks`, `gnome-calendar`, `gnome-weather`, `gnome-maps`,
  `gnome-calculator`, `iotas`, `loupe`, `showtime`, `decibels`, `gnome-text-editor`, `file-roller`,
  `resources`, `fastfetch`), Firefox 160 with `mobile-config-firefox` 5.5.2, and
  `op9-quick-settings` (built
  against Phosh `0.59.0`, exposing both `op9-touch-rate-quick-setting` 120/360 Hz and
  `op9-natural-colour-quick-setting` P3→sRGB toggles) all installed and running with `0` failed
  system or user units.
- **Wi-Fi & Bluetooth**: `op9-addresses` reads the phone's own Wi-Fi and Bluetooth MAC addresses from
  modem DMS at boot and caches `/var/lib/op9/addresses`. `ath11k_pci` (`wcn6855 hw2.1`) connects
  `wlp1s0` on the real hardware MAC; BlueZ `hci0` (`48:74:12:4F:C8:4C`) powers on cleanly (`Powered:
  yes`) and performs LE/classic discovery scans.
- **Audio & haptics**: `OnePlus 9` ALSA card (`wcd938x` + dual `tfa9874`, including `VoiceMMode1` PCM
  `hw:0,3`) and PipeWire Speakers / Headphones / Built-in microphones + `op9_speaker_protection` filter
  chain active; `aw8697` haptics bound and active.
- **SLPI sensors**: `hexagonrpcd-sdsp` (`hexagonrpc-op9`) + `iio-sensor-proxy-op9` (`3.9-1`) with
  `lemonadev` `oplus-sensor` node (patch 0157) and staged `persist` registry stream live
  accelerometer, ambient light, proximity and compass readings in `monitor-sensor`.
- **Alert slider & buttons**: `OnePlus Alert Slider` (`op9-alert-slider`), power and volume keys work.
- **Power profiles (`tuned` + `tuned-ppd`)**: `tuned` (`2.28.0-1`) and `tuned-ppd` (`2.28.0-1`) map
  Phosh Quick Settings and GNOME Settings power profiles (`power-saver`, `balanced`, `performance`)
  via `/etc/tuned/ppd.conf` to three Snapdragon 888 (`SM8350`) profiles in
  `rootfs/etc/tuned/profiles/` (`op9-powersave`, `op9-balanced`, `op9-performance`) controlling
  Cortex-A55/A78/X1 `qcom-cpufreq-hw` frequency bounds & `schedutil` rate limits, Adreno 660 and UFS
  `devfreq` limits, `kernel.sched_energy_aware` (EAS on in `op9-powersave`, capacity-aware `0` in
  `op9-balanced` / `op9-performance`), `kernel.nmi_watchdog=0`, `vm.dirty_writeback_centisecs`, and
  `wlp1s0` Wi-Fi power-save.
- **Modem, SIM, VoLTE/IMS bearer, mobile data & GPS**:
  - `qrtr` (`1.2-1`), `rmtfs` (`1.1.r84-1`, running read-only `-r -P -s`), `tqftpserv` (`1.1.r117-1`,
    with `PU/VoLTE -> volte` symlink in `modem_pr` so all `oem_sw.txt` paths resolve), `81voltd`
    (`1.2.0.r28-1`), `modemmanager-op9` / `libmm-glib-op9` (`1.24.2-1`), `mmsd-tng` (`2.6.4-1`),
    `op9-sim-provision` and `op9-callaudio` all active on cold boot with `0` failed units.
  - Note: on the very first boot with an empty `/var/lib/tqftpserv/`, the modem scans all `mcfg_sw.mbn`
    files over `tqftpserv` (~3 minutes) while reporting DMS `Mode: 'shutting-down'` and UIM
    `Application state: 'detected'` until it selects and activates the SIM's carrier config
    (`TR_Telekom`, `0xA01EA09`). On subsequent cold boots, `op9-sim-provision` activates the USIM
    session in ~8 s and `ModemManager` registers automatically.
  - Verified live with a Turk Telekom SIM (`28603`): registers on **LTE** (`eutran-1` / `eutran-3`, 15
    MHz, 80–99% signal) and **5G NR** (`nr5g-78`, 100 MHz), `81voltd` (with
    `0001-qvd-connection-reconnect-IMS-bearer-if-dropped-remot.patch`) automatically brings up and
    auto-reconnects the multiplexed IPv6 `ims` bearer (`qmapmux0.0`/`qmapmux0.1`, `2a02:2010::/64`, MTU
    1500) across 4G↔5G transitions, and incoming/outgoing **VoLTE calls**, **SMS**, **mobile data**
    (`apn: internet`) and **GPS** all work on hardware. Keep the mode set to **`4G, 5G (Preferred:
    5G)`** (`allowed: 4g, 5g; preferred: 5g`) so 5G `n78` (100 MHz) is used for data while 4G LTE
    remains allowed for EPS Fallback on voice calls; selecting `5G Only` (`allowed: 5g`) forbids LTE
    fallback and blocks calls on networks without VoNR.
- **All four cameras & VCMs**:
  - Patch `0162` resets `i2c-qcom-cci` on runtime resume (`cci_reset`) after `TITAN_TOP_GDSC`
    power collapse so all four sensors and their EEPROMs (`0x50`, `0x51`, `0x54`) probe reliably.
  - Patch `0163` unwinds `s_stream(0)` in `qcom-camss` `video_start_streaming()` on failure so
    subsequent captures don't inherit stale `s_stream_enabled` state.
  - Patch `0164` wires OnePlus 9 ultrawide `wide_vcm` to `asahi-kasei,ak7375` at `0x74` (matching
    stock `sunny_imx766_ak7375c` / EEPROM `0xe9`), alongside `lc898229` at `0x72` on main IMX689.
  - Every sensor driver must load, or none appears: CAMSS's v4l2 async notifier waits for all of
    them, so one missing module (a `modprobe.d` blacklist on `gc02m1b`, say) leaves the notifier
    pending and registers no camera at all — empty mediatopology, "No sensor found". The
    `op9-cameras.conf` `modules-load.d` drop-in loads them explicitly for this reason.
  - Live `cam -l` and 3-frame `cam` captures succeeded on all 4 sensors with zero kernel warnings or
    I2C/VCM errors: Main **IMX689** (`3992x3000-ABGR8888`, 29.86–30.16 fps), Ultrawide **IMX766**
    (`4088x3072-ABGR8888`, 29.82–31.39 fps), Front **IMX471** (`1920x1088-ABGR8888`, 28.89–28.90
    fps), and Mono **GC02M1B** (raw `1600x1200-R10_CSI2P`, 29.37–30.22 fps). WirePlumber (`wpctl
    status`) exposes `Main Camera`, `Ultrawide Camera` and `Front Camera` (mono hidden by
    `52-op9-camera.conf`).

- **USB-C DisplayPort / HDMI dock, USB host & KDE Plasma 6 Desktop mode**:
  - Patch `0166` (`drivers/usb/typec/ucsi/ucsi.c`) stops `ucsi_glink` / `typec_ucsi` from resetting
    the shared QMP combo PHY mux back to `TYPEC_STATE_USB` (`QMPPHY_MODE_USB3_ONLY`) when
    `UCSI_CONSTAT_PARTNER_FLAG_ALT_MODE` is set, fixing the 2-second `USB3DP -> USB3_ONLY` flap and
    `disp_cc_mdss_dp_link_clk status stuck at 'off'` (`-EBUSY`) on USB-C DP+USB docks.
  - Patch `0167` (`drivers/gpu/drm/msm/dp/`) fixes redundant AUX re-probing in
    `msm_dp_bridge_detect()` / `msm_dp_hpd_plug_handle()`, enables `msm_dp_aux_reset()` on
    out-of-band USB-C DP AltMode timeouts, and releases `phy_power_on()` on link clock failure.
  - Live-verified on a multi-port USB-C HDMI dock (`OUI 00-10-fa cHDMIb`, USB 2.0/3.0 hubs,
    Realtek `r8152` Ethernet, microSD reader, 2.4 GHz wireless KB+mouse dongle): `DP-1` trains
    cleanly at HBR2 (`540000 kHz`, 2 lanes) and drives **`1920x1080@60`** full **KDE Plasma 6
    Desktop** (`op9-desktop.service` + `op9-desktop-input` touchpad/keyboard on `DSI-1`).
  - Also supports an on-demand **headless virtual Full KDE Plasma 6 Desktop over RDP**
    (`op9-rdp-desktop.service`, `kwin_wayland --virtual` + `krdpserver --plasma` on TCP `3389`,
    isolated from Plasma Mobile) with a Plasma Mobile Quick Settings toggle
    (`org.op9.quicksetting.rdpdesktop`, source in [op9-quick-settings](../postmarketos/pmaports/community/op9-quick-settings)).
  - **Plasma 6 and the RDP session are not in this repository.** `rootfs/` ships the GNOME/Phosh
    desktop-mode helpers only; the Plasma units and `op9-rdp-desktop*` scripts were a local setup on
    the test phone and are recorded here as what the kernel patches make possible, not as shipped
    components.

### Bring-up fixes added on the 9

1. **Splash clocks & `FB_SIMPLE`**: Switched from `DRM_SIMPLEDRM` to `FB_SIMPLE` and held all ten
   display clocks (patch 0154), and kept the rotator RCG off XO (patch 0155).
2. **`dwc3` early probe**: Built in `TYPEC` and `PHY_QCOM_QMP_COMBO` and temporarily pinned `usb_1_dwc3`
   to `peripheral` before moving shared `otg` role switching back to `common.dtsi` (patches 0154, 0157).
3. **S6SY792 reset polarity**: Released active-low reset at the end of `s6sy761` reset pulses instead
   of leaving it asserted (patch 0156).
4. **AMB655X panel & wake backlight**: Added `vout-gpios`, 60/120 Hz `mode_set`, 0–2047 normal range
   and HBM sysfs (patch 0158), plus `prepared` guard in backlight updates (patch 0161).
5. **IMX689 & all four cameras**: Added IMX689 (`0x0689`, 4000x3000@30 / 2000x1128@30 C-PHY) to
   `imx789.c` + `imx689.yaml` + `CameraSensorHelperImx689`, wired all 4 OnePlus 9 cameras (patches
   0159–0160), added CCI runtime-resume reset (patch 0162), `camss` unwind fix (patch 0163), and
   ultrawide AK7375C VCM at `0x74` (patch 0164).
6. **USB-C DP AltMode docks**: Preserved `QMPPHY_MODE_USB3DP` across `typec_ucsi` notifications
   when `PARTNER_FLAG_ALT_MODE` is set (patch 0166) and fixed `msm_dp` hotplug detect, AUX reset,
   and PHY error cleanup (patch 0167).

### Still untested / pending validation on the 9

- **Wireless charging coil**: `pmic_glink` wireless-RX GPIOs match `lemonadev` (LE2115 carries
  P9415 15 W RX), not yet tested on a wireless pad; regional variants without coil may differ.

## OnePlus 9 Pro

The modem features (mobile data, calls, SMS, MMS, GPS and call audio), the earpiece, the speaker
limiter and charging to full were tested on the current series. Wi-Fi, sleep, video decoding, Bluetooth,
vibration, the flashlight, NFC card detection, the buttons, the alert slider and wireless charging
were tested after memory scaling was added, before the modem was running. The other features were
tested on earlier builds of the series and haven't been rerun since. The stock-tuning features of
2026-11-08 (see below) were checked on the phone through registers, metadata and frame captures;
how they look and sound hasn't been judged in daylight or by ear yet.

## Numbers

| Measurement | Result |
|---|---|
| Memory copy, prime core | About 17 GB/s, 142 ns latency |
| 4K60 VP9 in Firefox, on battery | 5 runs of about 2 minutes: 0 firmware rejections |
| Dropped frames in those runs | 158–321 of about 7,000, mostly in the first 45 seconds |
| 4K60 VP9 on YouTube's mobile site | 32 dropped of 2,145 in the player's own stats |
| Firefox scrolling test, 30 s of a heavy page | 116 fps, up from 109–114; stalls over 100 ms 0–1, down from 1–6 |
| Sleep (s2idle), before the modem was running | About 40–44 mA, roughly 1.5 days of standby (estimate) |
| Overnight standby, modem running, no SIM | 41 mA average over 3 h 19 min unplugged, including 16 min awake before the idle suspend; then one uninterrupted 3 h sleep |
| GPS cold start, outdoors, no assistance data | 12 satellites in view after 45 s, fix after 65 s |
| USB 3 flash drive | 94.5 MB/s read |
| Swap | 5.4 GB of zram (zstd), compressed in RAM |
| Charging | 8.84 V at up to 2.77 A on a 25 W charger; 64% to 100% in 58 min, then stops, with the charger running the phone (+10 mA at the battery) |
| Wireless charging, from a Galaxy S26 Ultra's reverse charging | About 2.2 W in; up to +97 mA at the battery with the phone idle |

## Known problems

- **Sleep:** the chip doesn't reach its deepest sleep state, and "deep" suspend wakes by itself, so
  `s2idle` is used. The 40–44 mA figure was measured before the modem was running. With the modem
  running and no SIM, standby measured 41 mA, so the modem itself costs nothing measurable. Standby
  with a SIM registered for data and VoLTE hasn't been measured yet. `qcom_stats` in debugfs shows which
  subsystem keeps the chip out of its deepest state.
- **Wireless charging:** the temperature limits haven't been seen to trigger on wireless, since the
  phone stayed under 38 °C. They use the same code as USB. Using OTG while on a wireless charger isn't
  handled. Stock's faster wireless charging needs drivers for the P9415 and HL7227 chips.
- **Charging to full:** as stock, to 4.43 V per cell (8.86 V), stopping when the gauge reports full or
  under 125 mA, and recharging 100 mV per cell lower. From full until unplugged the battery shows
  "Full" at 100%, then falls to the gauge's value at 1% a minute, like Android's UI. Cell voltages
  aren't read, so the limits use half the pack voltage, where stock uses the higher cell. Phosh
  marks a full battery on its charger with Adwaita's "charged" icon, which also has a lightning
  bolt. fastfetch shows no status for a full battery and doesn't count a USB or wireless charger,
  so `rootfs/etc/xdg/fastfetch/config.jsonc` gets its battery line from `op9-battery-line`.
- **After charging:** the phone doesn't sleep while a charger is attached. If the idle timer already
  fired during that time, the phone stays awake with the screen off until it's next used, at about
  53 mA instead of about 40.
- **Charging notification:** Phosh lets any notification be swiped away, so it comes back silently
  within 5 seconds.
- **YouTube in Firefox:** the mobile page clips its left edge at the default zoom. Zooming that site
  to 80% fixes it. The cause wasn't measured. Wikipedia, BBC News and a test page fit correctly.
- **Waydroid:** Android can't use the cameras, phone calls or Bluetooth directly. Some apps refuse to
  run because Waydroid doesn't pass Google's device integrity checks. Waydroid also makes the camera
  and video decoder devices readable and writable by every user. Android 17 wasn't tried: no ARM64
  image exists, and others report its window never appears on Waydroid 1.6.3.
- **Docks:** two USB-C DisplayPort docks (one a Dell) gave working USB 3, Ethernet, keyboard and
  mouse, but no display. With `pmic_glink_altmode` logging on, the charger firmware reported only
  USB (SVID 0xff00) for the whole 18 minutes a dock was attached, never DisplayPort (0xff01). A
  USB-C to HDMI adapter goes from USB to DisplayPort with HPD within 1.5 s. The difference is the
  power role: the phone powers the adapter, so it is USB host and source from the start, while a
  dock charges the phone, so the phone has to swap to host first. The firmware doesn't seem to
  look for alternate modes after that swap. UCSI reports no alternate modes for either device, so
  Linux can't request one. Turn the logging on with `options pmic_glink_altmode dyndbg=+p` in
  `/etc/modprobe.d/`.
- **Steam:** x86 programs run through FEX without its library forwarding ("thunks", which need an
  x86 cross compiler to build), so games' graphics drivers run emulated too. Steam's first start,
  before the phone had swap, filled all 11 GB with its Chromium interface and froze the phone for
  minutes until the kernel killed a process. It hasn't been retried with zram yet. Half-Life 2's
  Linux version was played; no frame rates were measured.
- **GPU:** one GPU fault with recovery was seen in the compositor, before the memory scaling work.
  A second one on 2026-11-05 started when the GPU woke to dim the screen: the GMU stopped answering
  (`Timeout waiting for GMU OOB set GPU_SET`), the GPU faulted, and after the reset Phosh no longer
  answered the power key and the phone never suspended. It then drew about three times its awake idle
  current, screen off, for three hours until it was reset by hand. The cause isn't known. The
  kernel now reports hung tasks (3 minutes in D state), soft lockups and workqueue stalls, and
  `op9-lockup-watch` reboots after the report has reached the journal, with an immediate reset
  if shutdown hangs on the stuck task. Every reset on this phone clears RAM, so ramoops can't
  keep a panic log. Kernel panics (`rootfs/etc/sysctl.d/90-op9-lockup.conf`) are only the fallback
  for when userspace can't run. GPU crash dumps are saved to `/var/lib/op9-devcoredump`. Don't
  set `/sys/kernel/reboot/mode` to `warm`: that reboot hung twice in firmware.
- **Boot:** `systemd-backlight` sometimes fails at startup.
- **Driver unloading:** don't unload `qcom_iris` after a decoder hang, or `ath11k_pci` after a failed
  crash recovery. Either can hang shutdown, so reboot instead.
- **Clock:** the PMIC real-time clock is read-only, so `rtc-offset` stores an offset in a file.
- **GPS:** geoclue reports an accuracy of 0 m for modem fixes, because it doesn't compute accuracy
  from this modem's NMEA, so apps treat every fix as exact. Fixes measured outdoors stayed within
  about 11 m of their average. There's no assisted GPS yet, so a cold start takes about a minute;
  ModemManager can inject XTRA assistance data and set a SUPL server, which hasn't been tried.
- **Modem without a SIM:** the modem keeps running. Standby averaged 41 mA that way, the same as
  before the modem was brought up.
- **Modem storage is read-only:** `rmtfs` runs with `-r`, so the modem's writes to its storage
  stay in memory and the EFS partitions can never be changed from Linux. Anything the modem wants
  to remember across reboots is lost. This is deliberate; don't "fix" it.
- **SIM slots:** `op9-sim-provision` opens a session for the first USIM in slot 1 only. The second
  slot and eSIM haven't been tried. A SIM inserted while running needs the services restarted.
- **Call audio:** only the earpiece and speaker are routed during a call. A wired headset needs a
  voice route to the codec's RX path and a jack check in `op9-callaudio`. Bluetooth is harder: the
  call stays inside the audio DSP and never reaches PipeWire, so HFP can't carry it without a DSP
  Bluetooth port or a loopback through a host PCM. `op9-callaudio` also expects the phone's sound
  card at index 0, which a USB audio device or an HDMI adapter can shift.
- **Addresses:** `op9-addresses` reads the Wi-Fi and Bluetooth addresses from the modem at boot
  (`qmicli --dms-get-mac-address`, which answers about 6 s into boot once `rmtfs` has started the
  modem), so one kernel serves every phone. Without the modem services, Wi-Fi has the firmware's
  placeholder address and Bluetooth no adapter. The stock DTB blob the bootloader insists on is
  OnePlus's, so releases ship Image, modules and initramfs, and the boot image is packed on the
  user's PC from their own `vendor_boot.img`.
- **Headphone path:** opening the headphone output logs a SoundWire "port collision" on the RX
  bus. Speaker playback is unaffected. Not yet checked with an analog headset attached, including
  stock's HiFi amplifier mode and headset mic gain from the stock-tuning work.
- **Camera order:** libcamera's camera numbers change between boots, so `cam -c 4` isn't always the
  main camera. Use the camera's ID (for the main camera `/base/soc@0/cci@ac4f000/i2c-bus@0/camera@1a`),
  and PipeWire's `node.name`, not its description, for `pipewiresrc target-object=`. After an app has
  used a camera, WirePlumber keeps its media device locked, so `cam` reports it busy until
  WirePlumber is stopped.

## Desktop mode

Plugging in a display (tested with a USB-C to HDMI adapter and a Samsung TV) opens a chooser on the
phone. Start desktop stops Phosh and its apps and runs a full GNOME session on the external
display. Unplugging, or no display showing up within 20 s, brings Phosh back. The choice can be
remembered.

The phone screen can be a tenkeyless keyboard with a trackpad below it, a keyboard, a trackpad, or
off, held in landscape with its top to the left. Automatic picks one from the USB and Bluetooth
keyboards and mice attached (a mouse's extra "keyboard" interface doesn't count).
`op9-desktop-input` grabs the touchscreen and feeds a virtual multi-touch touchpad, so libinput
gives it tap-to-click, two-finger scrolling and gestures, and a virtual keyboard where each finger
holds its key. It draws the layout on the panel in a dark style, and pressed keys light up. A touch
that starts on the trackpad keeps moving the pointer over the whole screen until it lifts, the keys
included. The vibration motor ticks for each key, gives a softer tick when a tap counts as a click,
and a faint ripple every 3 mm a finger travels on the trackpad.

- The panel is a DRM lease: GNOME's `monitors.xml` and `gdctl` offer it for lease, and
  `op9-desktop-lease` takes the lease over Wayland (`wp_drm_lease_v1`) and hands its file descriptor
  to `op9-desktop-input`. It hands it over again if the daemon restarts.
- Phosh and GNOME share the user's settings, so desktop mode keeps its own on-screen keyboard and
  window-button settings: each side saves the other's values when it starts. Otherwise GNOME pops
  up a keyboard on the TV for every text field, or Phosh's keyboard stays hidden.
- Patch 0145 makes the haptics driver play each effect at its strength; before it, every vibration
  was the same.

- `op9-desktop` is both the chooser under Phosh and the helper under GNOME. It writes GNOME's
  `monitors.xml` from the display's EDID before starting, so GNOME never opens on the phone first.
- Between the two compositors, the kernel console redrew itself onto every screen and left planes
  that mutter can't move off it. `op9-kms-reset` unbinds the console and detaches leftover planes.
- Patch 0144 keeps DP off the mixers and CTL the panel needs. Without it, the panel came back on
  other blocks after desktop mode and never drew a frame until a reboot.
- GNOME scans out linear buffers: 10-bit UBWC-compressed ones showed black on DP.
- Not done yet: docks (see Known problems) and MST hubs. The haptics driver uses the motor's
  continuous mode only; the chip's waveform modes would give crisper clicks.

## Stock tuning

Hardware tuning copied from stock (a dump of LineageOS's vendor files and OnePlus's kernel source):

| Area | What runs now | How it was checked |
|---|---|---|
| Cameras | Stock's colour correction matrices for the main, ultrawide, telephoto and front cameras, from the Chromatix tuning, in the libcamera tuning files | Frames through PipeWire, as Snapshot gets them, with and without: mean saturation 0.47 → 0.61 (main) and 0.54 → 0.63 (front) in a room lit by monitors and a torch |
| Display | High-brightness mode (600–800 nits, stock's sunlight boost) switched on above 10,000 lux by `op9-sunlight-hbm`; the slider's range is unchanged | Panel registers read back: `0x53` = `0xe0` and level 4095 in HBM, `0x28` and 2047 after |
| Display | Optional Natural colour: sRGB mapped onto the panel's Display P3 gamut by the display engine's colour matrix (patch 0148). Vivid, the panel's native gamut, stays the default | DSPPs reserved for the built-in display; switching logs no errors. Not yet judged by eye |
| Touch | Optional 360 Hz report rate (stock: 120 Hz, 360 Hz in game mode), patch 0146 | The controller accepts the setting; the rate hasn't been timed |
| Headphones | Stock's class-H HiFi amplifier mode and headset mic gain (ADC2 12, about 3 dB more) | Mixer values read back; not listened to |

The Natural colour and 360 Hz settings are quick settings (`postmarketos/pmaports/community/op9-quick-settings`),
for both Phosh and Plasma Mobile
that remember their state. Not copied, and why:

- **Speaker processing:** stock's speaker protection, EQ and multiband DRC are NXP's algorithm in
  the audio DSP, fed with the amplifiers' current and voltage, not something the amplifiers do. The
  PipeWire limiter stays. See [HARDWARE.md](HARDWARE.md).
- **Camera image quality:** stock's denoising, sharpening, tone mapping, HDR and night modes run in
  Qualcomm's Spectra ISP and CamX, which mainline doesn't drive. libcamera's software ISP gets the
  colour matrices only. In dim light stock uses less saturated matrices, but libcamera can't switch
  matrices by light level, so the normal-light ones are used throughout.
- **Brightness curve:** stock maps its slider to panel levels 0–1695 (about 500 nits) and uses
  1696–2047 only from automatic brightness; mainline's slider covers 0–2047 directly.

## Fingerprint reader

The under-display Goodix G3S is driven entirely by Qualcomm TrustZone secure apps — `goodixfp` for
the sensor and `keymaster64`'s gatekeeper for the auth token an enroll needs — with the display's
bright flash synced to each scan. A native attempt got the secure apps loading and running on
mainline (a custom `qcom_qseecom_mobile` driver plus the RPMB and file-system listeners they call
back into) and made the secure-storage relay work reliably. Enrollment is blocked one layer deeper:
the gatekeeper's RPMB-backed storage was last written by stock OxygenOS, and TrustZone's
anti-rollback — a version baseline it reads at secure boot and caches — rejects it on mainline, with
no way to reset it from Linux. The secure app does run with an unlocked bootloader, since fingerprint
unlock worked on this phone under LineageOS. The open path is a userspace gatekeeper that mints the
auth token without that storage. The full write-up, including the RPMB UNIT ATTENTION fix, is in
[FINGERPRINT.md](FINGERPRINT.md).

## Next

1. Measure standby with a SIM registered for data and VoLTE, then reach deeper sleep, including
   cutting touch power
2. Call audio through wired headsets, then Bluetooth
3. Assisted GPS for faster fixes, and real accuracy figures through geoclue
4. A prebuilt root filesystem tarball in the releases, now that one kernel serves every phone,
   and the install replayed from scratch with it
5. Get a display from USB-C docks
6. Test an analog USB-C headset and a Bluetooth headset's microphone
7. Judge the stock camera colours in daylight, tune the sunlight HBM thresholds outdoors, time the
   360 Hz touch rate, then improve camera quality and check video recording
8. Add a user-facing NFC app (`neard` isn't packaged for postmarketOS)
9. Build the `postmarketos/pmaports/` packages in CI on an ARM runner, so the guide's package
   steps are checked on every change
