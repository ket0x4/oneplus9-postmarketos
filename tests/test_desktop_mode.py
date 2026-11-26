#!/usr/bin/env python3
"""Tests for the pure parts of the desktop-mode scripts.

    python3 tests/test_desktop_mode.py

These cover the logic that fails silently on the phone and cannot be checked by
reading a log: the EDID parsing that decides what mutter calls a monitor, the
monitors.xml it writes, the keyboard/trackpad regions, and the settings that are
saved before a switch and put back after it.

The scripts have no .py suffix, so they are loaded by path. They import gi
(GLib/Gio/Gtk/Adw/GUdev) at module level; CI installs python3-gi for this job.
Anything that needs a compositor, DRM or /dev/uinput is not touched here.
"""

import importlib.util
import os
import sys
import unittest
import xml.etree.ElementTree as ET
from importlib.machinery import SourceFileLoader

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BIN = os.path.join(ROOT, "rootfs", "usr", "local", "bin")


def load(name, filename):
    """Import a script by path, the way Python would import a module."""
    spec = importlib.util.spec_from_loader(name, SourceFileLoader(name, filename))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


desktop = load("op9_desktop", os.path.join(BIN, "op9-desktop"))
touch = load("op9_desktop_input", os.path.join(BIN, "op9-desktop-input"))


def make_edid(vendor="TXD", product="HDMI", serial="", width=1920, height=1080, rate=60.0,
              blank_h=280, blank_v=45, header=True):
    """A 128-byte EDID block, laid out the way a real one is.

    Only the fields op9-desktop reads are meaningful: the header, the vendor id
    at bytes 8-9, the product/serial numbers, and the first detailed timing
    descriptor in the four 18-byte slots at 54..126.
    """
    e = bytearray(128)
    if header:
        e[0:8] = bytes.fromhex("00ffffffffffff00")
    # Packed manufacturer id: three five-bit letters, 'A' = 1.
    packed = 0
    for ch in vendor:
        packed = (packed << 5) | (ord(ch) - 64)
    e[8] = (packed >> 8) & 0xFF
    e[9] = packed & 0xFF
    e[10:12] = (0x1234).to_bytes(2, "little")      # product code, when no 0xFC descriptor
    e[12:16] = (0).to_bytes(4, "little")           # serial number 0 -> "unknown"

    # Detailed timing descriptor: pixel clock in 10 kHz units, then the active and
    # blanking sizes packed the way EDID stores them.
    clock = int(rate * (width + blank_h) * (height + blank_v) / 10000)
    d = bytearray(18)
    d[0] = clock & 0xFF
    d[1] = (clock >> 8) & 0xFF
    d[2] = width & 0xFF
    d[3] = blank_h & 0xFF
    d[4] = ((width >> 8) & 0xF) << 4 | ((blank_h >> 8) & 0xF)
    d[5] = height & 0xFF
    d[6] = blank_v & 0xFF
    d[7] = ((height >> 8) & 0xF) << 4 | ((blank_v >> 8) & 0xF)
    e[54:72] = d

    # Descriptor tags for the name (0xFC) and serial number (0xFF). An empty
    # serial means no 0xFF descriptor at all, which is how most sinks look: the
    # parser then falls back to the numeric serial at bytes 12-15.
    def text_descriptor(tag, text):
        block = bytearray(18)
        block[3] = tag
        body = (text + "\n").encode("cp437")[:13]
        block[5:5 + len(body)] = body
        return block

    e[72:90] = text_descriptor(0xFC, product)
    if serial:
        e[90:108] = text_descriptor(0xFF, serial)
    return bytes(e)


class EdidTests(unittest.TestCase):
    def test_vendor_product_and_mode(self):
        ident = desktop.parse_edid(make_edid())
        self.assertIsNotNone(ident)
        vendor, product, serial, mode = ident
        self.assertEqual(vendor, "TXD")
        self.assertEqual(product, "HDMI")
        self.assertEqual(serial, "unknown")
        width, height, rate = mode
        self.assertEqual((width, height), (1920, 1080))

    def test_refresh_is_close_to_what_was_encoded(self):
        # The clock is rounded to 10 kHz when packed, so allow a little slack.
        _, _, _, (_, _, rate) = desktop.parse_edid(make_edid(rate=60.0))
        self.assertAlmostEqual(rate, 60.0, delta=0.5)

    def test_serial_descriptor_is_used_when_present(self):
        _, _, serial, _ = desktop.parse_edid(make_edid(serial="ABC123"))
        self.assertEqual(serial, "ABC123")

    def test_missing_header_is_rejected(self):
        self.assertIsNone(desktop.parse_edid(make_edid(header=False)))

    def test_short_block_is_rejected(self):
        self.assertIsNone(desktop.parse_edid(make_edid()[:64]))
        self.assertIsNone(desktop.parse_edid(b""))

    def test_no_detailed_timing_means_no_mode(self):
        # A DVI/HDMI sink that only advertises modes in the extension block: the
        # first descriptor is a monitor-range one (clock 0), so there is no mode.
        e = bytearray(make_edid())
        e[54:72] = bytes(18)
        ident = desktop.parse_edid(bytes(e))
        self.assertIsNotNone(ident)
        self.assertIsNone(ident[3])


class MonitorsXmlTests(unittest.TestCase):
    def test_lease_and_disabled_are_written_for_the_panel(self):
        # mutter rejects the whole file unless a monitor offered for lease is also
        # listed as disabled, which is what made desktop mode open on the phone screen.
        root = ET.Element("monitors", version="2")
        conf = ET.SubElement(root, "configuration")
        lm = ET.SubElement(conf, "logicalmonitor")
        monitor = ET.SubElement(lm, "monitor")
        desktop.spec_xml(monitor, ("DP-1", "TXD", "HDMI", "unknown"))
        desktop.spec_xml(ET.SubElement(conf, "disabled"), ("DSI-1", "unknown", "unknown", "unknown"))
        desktop.spec_xml(ET.SubElement(conf, "forlease"), ("DSI-1", "unknown", "unknown", "unknown"))
        disabled = desktop.spec_key(conf.find("disabled/monitorspec"))
        forlease = desktop.spec_key(conf.find("forlease/monitorspec"))
        self.assertEqual(disabled, forlease)
        self.assertEqual(disabled[0], "DSI-1")
        self.assertEqual(desktop.spec_key(conf.find("logicalmonitor/monitor/monitorspec"))[0], "DP-1")

    def test_spec_key_matches_what_mutter_compares(self):
        parent = ET.Element("parent")
        desktop.spec_xml(parent, ("DP-1", "TXD", "HDMI", "unknown"))
        self.assertEqual(desktop.spec_key(parent.find("monitorspec")),
                         ("DP-1", "TXD", "HDMI", "unknown"))


class LayoutTests(unittest.TestCase):
    W, H = 2400, 1080        # landscape, the way the phone panel is held

    def test_keyboard_covers_the_screen(self):
        regions = touch.layout("keyboard", self.W, self.H)
        self.assertTrue(regions)
        right = max(r.x + r.w for r in regions)
        bottom = max(r.y + r.h for r in regions)
        self.assertAlmostEqual(right, self.W, delta=1)
        self.assertAlmostEqual(bottom, self.H, delta=1)

    def test_keyboard_has_the_keys_a_desktop_needs(self):
        labels = {r.label for r in touch.layout("keyboard", self.W, self.H) if r.kind == "key"}
        for key in ("Esc", "Tab", "Enter", "Space", "Shift", "Ctrl", "Super", "Alt", "Backspace"):
            self.assertIn(key, labels)

    def test_every_key_has_a_linux_keycode(self):
        for r in touch.layout("keyboard", self.W, self.H):
            if r.kind == "key":
                self.assertIn(r.code, touch.K.values(), f"{r.label} has no keycode")

    def test_keyboard_and_trackpad_do_not_overlap(self):
        regions = touch.layout("keyboard-trackpad", self.W, self.H)
        keys = [r for r in regions if r.kind == "key"]
        pads = [r for r in regions if r.kind == "pad"]
        self.assertEqual(len(pads), 1)
        pad = pads[0]
        for key in keys:
            self.assertFalse(key.hit(pad.x + pad.w / 2, pad.y + pad.h / 2))
        self.assertGreater(pad.y, max(r.y + r.h for r in keys))

    def test_off_mode_has_no_regions(self):
        self.assertEqual(touch.layout("off", self.W, self.H), [])

    def test_trackpad_covers_the_whole_screen(self):
        regions = touch.layout("trackpad", self.W, self.H)
        self.assertEqual(len(regions), 1)
        self.assertEqual((regions[0].x, regions[0].y, regions[0].w, regions[0].h),
                         (0, 0, self.W, self.H))

    def test_hit_testing_is_half_open(self):
        region = touch.Region("key", 10, 10, 20, 20)
        self.assertTrue(region.hit(10, 10))
        self.assertTrue(region.hit(29.9, 29.9))
        self.assertFalse(region.hit(30, 20))


class AutoModeTests(unittest.TestCase):
    """resolve() picks a layout from the keyboards and mice attached."""

    def resolve_with(self, keyboard, mouse):
        original = touch.attached_keyboard_mouse
        touch.attached_keyboard_mouse = lambda: (keyboard, mouse)
        try:
            return touch.resolve("auto")
        finally:
            touch.attached_keyboard_mouse = original

    def test_nothing_attached_gives_keyboard_and_trackpad(self):
        self.assertEqual(self.resolve_with(False, False), "keyboard-trackpad")

    def test_keyboard_only_gives_trackpad(self):
        self.assertEqual(self.resolve_with(True, False), "trackpad")

    def test_mouse_only_gives_keyboard(self):
        self.assertEqual(self.resolve_with(False, True), "keyboard")

    def test_both_attached_turns_the_screen_off(self):
        self.assertEqual(self.resolve_with(True, True), "off")

    def test_an_explicit_mode_is_not_resolved(self):
        for mode in touch.MODES:
            self.assertEqual(touch.resolve(mode), mode)


class ConfigTests(unittest.TestCase):
    def test_default_mode_is_keyboard_and_trackpad(self):
        # A stored file with no mode: the phone should come up usable, not dark.
        original = desktop.CONFIG
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            desktop.CONFIG = os.path.join(tmp, "config.json")
            try:
                self.assertEqual(desktop.load_config()["mode"], "keyboard-trackpad")
                self.assertTrue(desktop.load_config()["ask"])
            finally:
                desktop.CONFIG = original

    def test_an_unknown_mode_falls_back(self):
        original = desktop.CONFIG
        import json
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            desktop.CONFIG = os.path.join(tmp, "config.json")
            try:
                with open(desktop.CONFIG, "w") as f:
                    json.dump({"mode": "no-such-mode", "ask": False}, f)
                config = desktop.load_config()
                self.assertEqual(config["mode"], "keyboard-trackpad")
                self.assertFalse(config["ask"])
            finally:
                desktop.CONFIG = original

    def test_config_round_trips(self):
        original = desktop.CONFIG
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            desktop.CONFIG = os.path.join(tmp, "config.json")
            try:
                desktop.save_config({"mode": "trackpad", "ask": False})
                self.assertEqual(desktop.load_config(), {"mode": "trackpad", "ask": False})
            finally:
                desktop.CONFIG = original


class SettingsTests(unittest.TestCase):
    """The three settings that are saved and put back, and the two that are not.

    This runs against a memory GSettings backend, so it never touches the
    developer's or the CI runner's real settings.
    """

    def setUp(self):
        import tempfile
        self.tmp = tempfile.TemporaryDirectory()
        self.saved_env = os.environ.get("GSETTINGS_BACKEND")
        os.environ["GSETTINGS_BACKEND"] = "memory"
        self.saved_state = desktop.SAVED_STATE
        desktop.SAVED_STATE = os.path.join(self.tmp.name, "restore-settings.json")

    def tearDown(self):
        desktop.SAVED_STATE = self.saved_state
        self.tmp.cleanup()
        if self.saved_env is None:
            os.environ.pop("GSETTINGS_BACKEND", None)
        else:
            os.environ["GSETTINGS_BACKEND"] = self.saved_env

    def require_schemas(self):
        """Skip when the schemas aren't installed.

        Gio.Settings.new() on an unknown schema is a fatal GLib error, not an
        exception, so the schema list has to be consulted before constructing one.
        """
        from gi.repository import Gio
        source = Gio.SettingsSchemaSource.get_default()
        for schema, _, _ in desktop.SAVED_SETTINGS + desktop.DESKTOP_SETTINGS:
            if source is None or source.lookup(schema, True) is None:
                self.skipTest(f"settings schema {schema} is not installed")

    def test_only_the_three_saved_keys_are_restored(self):
        names = {f"{s} {k}" for s, k, _ in desktop.SAVED_SETTINGS}
        self.assertEqual(names, {
            "org.gnome.desktop.lockdown disable-lock-screen",
            "org.gnome.settings-daemon.plugins.power sleep-inactive-battery-type",
            "org.gnome.settings-daemon.plugins.power sleep-inactive-ac-type",
        })
        # The on-screen keyboard and the button layout are rewritten by Phosh on
        # every start, so desktop mode must not save or restore them.
        for schema, key, _ in desktop.DESKTOP_SETTINGS:
            self.assertNotIn(f"{schema} {key}", names)

    def test_apply_then_restore_returns_the_original_values(self):
        self.require_schemas()
        from gi.repository import Gio
        keys = [(s, k) for s, k, _ in desktop.SAVED_SETTINGS]
        wanted = {(s, k): v.print_(False) for s, k, v in desktop.SAVED_SETTINGS}

        def snapshot():
            return {(s, k): Gio.Settings.new(s).get_value(k).print_(False) for s, k in keys}

        before = snapshot()
        desktop.apply_desktop_settings()
        # Every saved key is now at the value desktop mode wants. (This is not the
        # same as "changed": sleep-inactive-ac-type is already 'nothing' on some
        # installs, and asserting a change would fail there for no good reason.)
        self.assertEqual(snapshot(), wanted)
        desktop.restore_settings()
        self.assertEqual(snapshot(), before)
        self.assertFalse(os.path.exists(desktop.SAVED_STATE))

    def test_restore_without_a_saved_file_is_a_no_op(self):
        self.require_schemas()
        before = os.path.exists(desktop.SAVED_STATE)
        desktop.restore_settings()          # must not raise
        self.assertEqual(os.path.exists(desktop.SAVED_STATE), before)


if __name__ == "__main__":
    unittest.main(verbosity=2)
