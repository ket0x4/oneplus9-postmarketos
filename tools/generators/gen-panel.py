#!/usr/bin/env python3
"""Generate drivers/gpu/drm/panel/panel-samsung-<panel>.c from a downstream
OnePlus panel node, replaying its on-command sequence with the mainline
mipi_dsi_*_multi helpers.

usage: gen-panel.py <node-dir> <timing> <driver-name> <compatible> <panel-desc>
                    [--width-mm N] [--height-mm N] [--bl-max N] [--bl-default N]
                    [--lanes N] [--bpp N]

<node-dir> is a directory holding the properties of a qcom,mdss_dsi_* panel
node (a live /sys/firmware/devicetree/base node or an unpacked vendor DTB),
and <timing> is one of its qcom,mdss-dsi-display-timings children ('timing@0').

gen-amb670yf01.py is this script pinned to the OnePlus 9 Pro's panel; it is
kept because the driver it produced is cited in docs/HARDWARE.md.
"""
import argparse
import os
import sys


def read(path):
    try:
        with open(path, "rb") as f:
            return f.read()
    except OSError:
        return None


def u32s(blob):
    """A scalar device tree cell: one big-endian u32."""
    if blob is None or len(blob) < 4:
        return []
    return [int.from_bytes(blob[i:i + 4], "big") for i in range(0, len(blob) - 3, 4)]


def strings(blob):
    if blob is None:
        return []
    return [s.decode("utf-8", "replace") for s in blob.split(b"\0") if s]


def first(blob, default=0):
    v = u32s(blob)
    return v[0] if v else default


def decode(arr):
    """qcom,mdss-dsi-on-command is packed as:
       dtype last vc ack wait_ms len_hi len_lo payload...

    The property is a byte array, so it is consumed as bytes even when its
    length happens to be a multiple of four (dtc would print those as cells).
    """
    b = list(arr or b"")
    out, i = [], 0
    while i + 7 <= len(b):
        dtype, last, vc, ack, wait = b[i], b[i + 1], b[i + 2], b[i + 3], b[i + 4]
        n = (b[i + 5] << 8) | b[i + 6]
        payload = b[i + 7:i + 7 + n]
        if len(payload) < n:
            break
        out.append((dtype, last, wait, payload))
        i += 7 + n
    return out


def hexs(b):
    return ", ".join("0x%02x" % x for x in b)


def wait(ms):
    if not ms:
        return []
    if ms < 20:
        return ["\tmipi_dsi_usleep_range(&dsi_ctx, %d, %d);" % (ms * 1000, ms * 1000 + 1000)]
    return ["\tmipi_dsi_msleep(&dsi_ctx, %d);" % ms]


TEMPLATE = r'''// SPDX-License-Identifier: GPL-2.0-only
/*
 * %(desc)s
 *
 * Init sequence read back from the vendor device tree (timing %(timing)s)
 * with tools/gen-panel.py.
 */

#include <linux/backlight.h>
#include <linux/delay.h>
#include <linux/gpio/consumer.h>
#include <linux/module.h>
#include <linux/regulator/consumer.h>

#include <video/mipi_display.h>

#include <drm/display/drm_dsc.h>
#include <drm/display/drm_dsc_helper.h>
#include <drm/drm_mipi_dsi.h>
#include <drm/drm_modes.h>
#include <drm/drm_panel.h>
#include <drm/drm_probe_helper.h>

struct %(name)s {
	struct drm_panel panel;
	struct mipi_dsi_device *dsi;
	struct drm_dsc_config dsc;
	struct gpio_desc *reset_gpio;
	struct regulator_bulk_data *supplies;
};

static const struct regulator_bulk_data %(name)s_supplies[] = {
	{ .supply = "vddio" },	/* 1.8V */
	{ .supply = "vdd" },	/* 3.0V */
	{ .supply = "avdd" },	/* 5.5V */
};

static inline struct %(name)s *to_%(name)s(struct drm_panel *panel)
{
	return container_of(panel, struct %(name)s, panel);
}

static void %(name)s_reset(struct %(name)s *ctx)
{
	/* vendor qcom,mdss-dsi-reset-sequence: high 10ms, low 1ms, high 10ms */
	gpiod_set_value_cansleep(ctx->reset_gpio, 0);
	usleep_range(10000, 11000);
	gpiod_set_value_cansleep(ctx->reset_gpio, 1);
	usleep_range(1000, 2000);
	gpiod_set_value_cansleep(ctx->reset_gpio, 0);
	usleep_range(10000, 11000);
}

static void %(name)s_send_pps(struct %(name)s *ctx,
			      struct mipi_dsi_multi_context *dsi_ctx)
{
	u8 buf[1 + sizeof(struct drm_dsc_picture_parameter_set)];

	buf[0] = 0x9e;
	drm_dsc_pps_payload_pack((struct drm_dsc_picture_parameter_set *)&buf[1],
				 &ctx->dsc);
	mipi_dsi_dcs_write_buffer_multi(dsi_ctx, buf, sizeof(buf));
}

static int %(name)s_on(struct %(name)s *ctx)
{
	struct mipi_dsi_multi_context dsi_ctx = { .dsi = ctx->dsi };

	ctx->dsi->mode_flags |= MIPI_DSI_MODE_LPM;

%(on)s

	return dsi_ctx.accum_err;
}

static int %(name)s_enable(struct drm_panel *panel)
{
	struct %(name)s *ctx = to_%(name)s(panel);
	struct mipi_dsi_multi_context dsi_ctx = { .dsi = ctx->dsi };

	/* vendor qcom,mdss-dsi-post-on-backlight */
	mipi_dsi_dcs_set_display_on_multi(&dsi_ctx);

	return dsi_ctx.accum_err;
}

static int %(name)s_disable(struct drm_panel *panel)
{
	struct %(name)s *ctx = to_%(name)s(panel);
	struct mipi_dsi_multi_context dsi_ctx = { .dsi = ctx->dsi };

	ctx->dsi->mode_flags &= ~MIPI_DSI_MODE_LPM;

%(off)s

	return dsi_ctx.accum_err;
}

static int %(name)s_prepare(struct drm_panel *panel)
{
	struct %(name)s *ctx = to_%(name)s(panel);
	int ret;

	ret = regulator_bulk_enable(ARRAY_SIZE(%(name)s_supplies), ctx->supplies);
	if (ret < 0)
		return ret;

	if (ctx->reset_gpio)
		%(name)s_reset(ctx);

	ret = %(name)s_on(ctx);
	if (ret < 0) {
		if (ctx->reset_gpio)
			gpiod_set_value_cansleep(ctx->reset_gpio, 1);
		regulator_bulk_disable(ARRAY_SIZE(%(name)s_supplies), ctx->supplies);
		return ret;
	}

	return 0;
}

static int %(name)s_unprepare(struct drm_panel *panel)
{
	struct %(name)s *ctx = to_%(name)s(panel);

	if (ctx->reset_gpio)
		gpiod_set_value_cansleep(ctx->reset_gpio, 1);
	regulator_bulk_disable(ARRAY_SIZE(%(name)s_supplies), ctx->supplies);

	return 0;
}

static const struct drm_display_mode %(name)s_modes[] = {
%(modes)s
};

static int %(name)s_get_modes(struct drm_panel *panel,
			      struct drm_connector *connector)
{
	int i;

	for (i = 0; i < ARRAY_SIZE(%(name)s_modes); i++) {
		struct drm_display_mode *mode;

		mode = drm_mode_duplicate(connector->dev, &%(name)s_modes[i]);
		if (!mode)
			return -ENOMEM;
		if (i == 0)
			mode->type |= DRM_MODE_TYPE_PREFERRED;
		drm_mode_set_name(mode);
		drm_mode_probed_add(connector, mode);
	}

	connector->display_info.width_mm = %(name)s_modes[0].width_mm;
	connector->display_info.height_mm = %(name)s_modes[0].height_mm;

	return ARRAY_SIZE(%(name)s_modes);
}

static const struct drm_panel_funcs %(name)s_panel_funcs = {
	.prepare = %(name)s_prepare,
	.unprepare = %(name)s_unprepare,
	.enable = %(name)s_enable,
	.disable = %(name)s_disable,
	.get_modes = %(name)s_get_modes,
};

static int %(name)s_bl_update_status(struct backlight_device *bl)
{
	struct mipi_dsi_device *dsi = bl_get_data(bl);
	u16 brightness = backlight_get_brightness(bl);
	int ret;

	dsi->mode_flags &= ~MIPI_DSI_MODE_LPM;
	ret = mipi_dsi_dcs_set_display_brightness_large(dsi, brightness);
	dsi->mode_flags |= MIPI_DSI_MODE_LPM;

	return ret < 0 ? ret : 0;
}

static const struct backlight_ops %(name)s_bl_ops = {
	.update_status = %(name)s_bl_update_status,
};

static struct backlight_device *%(name)s_create_backlight(struct mipi_dsi_device *dsi)
{
	struct device *dev = &dsi->dev;
	const struct backlight_properties props = {
		.type = BACKLIGHT_RAW,
		.brightness = %(bl_default)d,
		.max_brightness = %(bl_max)d,
	};

	return devm_backlight_device_register(dev, dev_name(dev), dev, dsi,
					      &%(name)s_bl_ops, &props);
}

static int %(name)s_probe(struct mipi_dsi_device *dsi)
{
	struct device *dev = &dsi->dev;
	struct %(name)s *ctx;
	int ret;

	ctx = devm_drm_panel_alloc(dev, struct %(name)s, panel,
				   &%(name)s_panel_funcs, DRM_MODE_CONNECTOR_DSI);
	if (IS_ERR(ctx))
		return PTR_ERR(ctx);

	ret = devm_regulator_bulk_get_const(dev, ARRAY_SIZE(%(name)s_supplies),
					    %(name)s_supplies, &ctx->supplies);
	if (ret < 0)
		return dev_err_probe(dev, ret, "Failed to get regulators\n");

	ctx->reset_gpio = devm_gpiod_get_optional(dev, "reset", GPIOD_OUT_HIGH);
	if (IS_ERR(ctx->reset_gpio))
		return dev_err_probe(dev, PTR_ERR(ctx->reset_gpio),
				     "Failed to get reset-gpios\n");

	ctx->dsi = dsi;
	mipi_dsi_set_drvdata(dsi, ctx);

	dsi->lanes = %(lanes)d;
	dsi->format = MIPI_DSI_FMT_RGB888;
	dsi->mode_flags = MIPI_DSI_CLOCK_NON_CONTINUOUS;

	/* vendor qcom,mdss-dsi-lp11-init */
	ctx->panel.prepare_prev_first = true;

	ctx->panel.backlight = %(name)s_create_backlight(dsi);
	if (IS_ERR(ctx->panel.backlight))
		return dev_err_probe(dev, PTR_ERR(ctx->panel.backlight),
				     "Failed to create backlight\n");

	drm_panel_add(&ctx->panel);

	dsi->dsc = &ctx->dsc;
	ctx->dsc.dsc_version_major = %(dsc_major)d;
	ctx->dsc.dsc_version_minor = %(dsc_minor)d;
	ctx->dsc.slice_height = %(sh)d;
	ctx->dsc.slice_width = %(sw)d;
	ctx->dsc.slice_count = %(slice_count)d;
	ctx->dsc.bits_per_component = %(bpc)d;
	ctx->dsc.bits_per_pixel = %(bpp)d << 4;
	ctx->dsc.block_pred_enable = true;

	ret = devm_mipi_dsi_attach(dev, dsi);
	if (ret < 0) {
		drm_panel_remove(&ctx->panel);
		return dev_err_probe(dev, ret, "Failed to attach to DSI host\n");
	}

	return 0;
}

static void %(name)s_remove(struct mipi_dsi_device *dsi)
{
	struct %(name)s *ctx = mipi_dsi_get_drvdata(dsi);

	drm_panel_remove(&ctx->panel);
}

static const struct of_device_id %(name)s_of_match[] = {
	{ .compatible = "%(compatible)s" },
	{ /* sentinel */ }
};
MODULE_DEVICE_TABLE(of, %(name)s_of_match);

static struct mipi_dsi_driver %(name)s_driver = {
	.probe = %(name)s_probe,
	.remove = %(name)s_remove,
	.driver = {
		.name = "panel-samsung-%(name)s",
		.of_match_table = %(name)s_of_match,
	},
};
module_mipi_dsi_driver(%(name)s_driver);

MODULE_DESCRIPTION("%(desc)s");
MODULE_LICENSE("GPL");'''


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("node_dir")
    ap.add_argument("timing")
    ap.add_argument("driver_name")
    ap.add_argument("compatible")
    ap.add_argument("description")
    ap.add_argument("--width-mm", type=int, default=70)
    ap.add_argument("--height-mm", type=int, default=151)
    ap.add_argument("--bl-max", type=int, default=4095)
    ap.add_argument("--bl-default", type=int, default=1023)
    ap.add_argument("--lanes", type=int, default=4)
    ap.add_argument("--bpp", type=int, default=8)
    a = ap.parse_args()

    node = a.node_dir
    timings_dir = os.path.join(node, "qcom,mdss-dsi-display-timings")
    tim = os.path.join(timings_dir, a.timing)

    def g(k, t=None):
        return first(read(os.path.join(t or tim, "qcom,mdss-dsi-" + k)))

    def d(k, t=None):
        return first(read(os.path.join(t or tim, "qcom,mdss-dsc-" + k)))

    w, h = g("panel-width"), g("panel-height")
    hfp, hbp, hpw = g("h-front-porch"), g("h-back-porch"), g("h-pulse-width")
    vfp, vbp, vpw = g("v-front-porch"), g("v-back-porch"), g("v-pulse-width")
    fps = g("panel-framerate")
    sw, sh = d("slice-width"), d("slice-height")
    bpc, bpp = d("bit-per-component"), d("bit-per-pixel")
    if fps and fps > 255:
        fps //= 256
    if not w or not h:
        sys.exit("%s: no panel size in %s" % (a.timing, tim))

    def cmds(prop):
        out, cmds_list = [], decode(read(os.path.join(tim, prop)))
        for dtype, _last, ms, p in cmds_list:
            if p and p[0] == 0x9e:
                # Samsung takes the PPS via DCS 0x9e: send the one matching
                # our DSC config instead of the vendor's copy
                out.append("\t%s_send_pps(ctx, &dsi_ctx);" % a.driver_name)
            elif p == [0x11]:
                out.append("\tmipi_dsi_dcs_exit_sleep_mode_multi(&dsi_ctx);")
            elif p[:1] == [0x35]:
                out.append("\tmipi_dsi_dcs_set_tear_on_multi(&dsi_ctx, MIPI_DSI_TEAR_MODE_VBLANK);".replace(
                    "MIPI_DSI_TEAR_MODE_VBLANK", "MIPI_DSI_DCS_TEAR_MODE_VBLANK"))
            elif dtype in (0x05, 0x15, 0x39):
                out.append("\tmipi_dsi_dcs_write_seq_multi(&dsi_ctx, %s);" % hexs(p))
            else:
                print("warning: unhandled dtype %#x" % dtype, file=sys.stderr)
            out += wait(ms)
        return "\n".join(out)

    def mode(w, h, hfp, hbp, hpw, vfp, vbp, vpw, fps):
        return """\t{
\t\t.clock = (%d + %d + %d + %d) * (%d + %d + %d + %d) * %d / 1000,
\t\t.hdisplay = %d,
\t\t.hsync_start = %d,
\t\t.hsync_end = %d,
\t\t.htotal = %d,
\t\t.vdisplay = %d,
\t\t.vsync_start = %d,
\t\t.vsync_end = %d,
\t\t.vtotal = %d,
\t\t.width_mm = %d,
\t\t.height_mm = %d,
\t\t.type = DRM_MODE_TYPE_DRIVER,
\t},""" % (
            w, hfp, hpw, hbp, h, vfp, vpw, vbp, fps,
            w, w + hfp, w + hfp + hpw, w + hfp + hpw + hbp,
            h, h + vfp, h + vfp + vpw, h + vfp + vpw + vbp,
            a.width_mm, a.height_mm)

    # One mode per display-timings child, highest refresh first so the first
    # entry (the preferred mode) is the fastest one.
    modes = []
    for entry in sorted(os.listdir(timings_dir)):
        t = os.path.join(timings_dir, entry)
        if not os.path.isdir(t):
            continue
        mw, mh = g("panel-width", t), g("panel-height", t)
        if not mw or not mh:
            continue
        mfps = g("panel-framerate", t) or 60
        if mfps > 255:
            mfps //= 256
        modes.append((mfps, mode(mw, mh,
                                 g("h-front-porch", t), g("h-back-porch", t),
                                 g("h-pulse-width", t), g("v-front-porch", t),
                                 g("v-back-porch", t), g("v-pulse-width", t),
                                 mfps)))
    modes.sort(key=lambda m: -m[0])
    modes = "\n".join(m[1] for m in modes)

    print(TEMPLATE % dict(
        name=a.driver_name, compatible=a.compatible, desc=a.description,
        timing=a.timing, on=cmds("qcom,mdss-dsi-on-command"),
        off=cmds("qcom,mdss-dsi-off-command"),
        modes=modes,
        sw=sw, sh=sh, bpc=bpc, bpp=bpp, dsc_major=1, dsc_minor=1,
        slice_count=2, bl_max=a.bl_max, bl_default=a.bl_default,
        lanes=a.lanes))


if __name__ == "__main__":
    main()
