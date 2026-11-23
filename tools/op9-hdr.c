/*
 * op9-hdr - merge a burst of raw Bayer frames into one HDR/night still.
 *
 * Capture a burst from the CAMSS video node (the raw sensor stream, not the
 * processed PipeWire source), e.g. with v4l2-ctl or a few `cam` raw captures,
 * at different exposures. This tool aligns the frames, merges them with a
 * noise/saturation weighting, demosaics the result with Malvar-He-Cutler and
 * writes a PPM. It replaces the parts of stock's night mode that need several
 * frames: the software ISP can only see one.
 *
 * usage:
 *   op9-hdr --width W --height H --stride S [options] out.ppm frame.raw...
 *
 * options:
 *   --black N          sensor black level (default 64, 10-bit)
 *   --white N          saturation value (default 1023)
 *   --ev LIST          relative exposures, comma separated, one per frame
 *                      (default all 1; a frame captured 4x longer is 4)
 *   --pattern NAME     RGGB (default), BGGR, GRBG, GBRG
 *   --red-x N --red-y N  explicit CFA phase override
 *   --wb R,G,B         white balance gains applied after demosaicing (default 1,1,1)
 *   --gamma G          output gamma (default 1/2.2)
 *   --align N          alignment search radius in full-res pixels (default 24, 0 = off)
 *   --threads N        accepted for symmetry, the merge is single-threaded
 *
 * Frames are packed MIPI RAW10 (four pixels in five bytes), as the sensor emits
 * them; stride is the row size in bytes.
 */
#include <ctype.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

struct frame {
	const char *path;
	uint16_t *data;	/* width*height, black level included */
	float ev;
	int dx, dy;	/* shift relative to frame 0, in pixels */
};

struct opts {
	int width, height, stride;
	int black, white;
	int red_x, red_y;
	float wb[3];
	float gamma;
	float tone;	/* Reinhard strength: y = tone*x/(1+tone*x), 0 = off */
	int align;
};

static void die(const char *msg)
{
	fprintf(stderr, "op9-hdr: %s\n", msg);
	exit(1);
}

static uint16_t *read_raw(const char *path, const struct opts *o)
{
	FILE *f = fopen(path, "rb");
	if (!f) {
		perror(path);
		exit(1);
	}

	size_t need = (size_t)o->stride * o->height;
	uint8_t *buf = malloc(need);
	if (!buf)
		die("out of memory");
	if (fread(buf, 1, need, f) != need)
		die("short raw file");
	fclose(f);

	uint16_t *out = malloc((size_t)o->width * o->height * sizeof(*out));
	if (!out)
		die("out of memory");

	for (int y = 0; y < o->height; y++) {
		const uint8_t *row = buf + (size_t)y * o->stride;
		for (int x = 0; x < o->width; x += 4) {
			const uint8_t *p = row + x / 4 * 5;
			const uint8_t lsb = p[4];
			for (int i = 0; i < 4 && x + i < o->width; i++)
				out[(size_t)y * o->width + x + i] =
					(uint16_t)((p[i] << 2) | ((lsb >> (2 * i)) & 3));
		}
	}

	free(buf);
	return out;
}

/* Downsampled, normalised luma used for alignment. */
static float *luma_small(const struct frame *fr, const struct opts *o,
			 int *sw, int *sh, int ds)
{
	*sw = o->width / ds;
	*sh = o->height / ds;
	float *m = malloc((size_t)(*sw) * (*sh) * sizeof(*m));
	if (!m)
		die("out of memory");

	double mean = 0;
	for (int y = 0; y < *sh; y++) {
		for (int x = 0; x < *sw; x++) {
			double sum = 0;
			for (int j = 0; j < ds; j++)
				for (int i = 0; i < ds; i++)
					sum += fr->data[(size_t)(y * ds + j) * o->width +
							x * ds + i];
			m[(size_t)y * (*sw) + x] = (float)(sum / (ds * ds));
			mean += sum / (ds * ds);
		}
	}
	mean /= (double)(*sw) * (*sh);

	double var = 0;
	for (int i = 0; i < *sw * *sh; i++) {
		m[i] -= (float)mean;
		var += (double)m[i] * m[i];
	}
	double sd = sqrt(var / ((double)(*sw) * (*sh))) + 1e-6;
	for (int i = 0; i < *sw * *sh; i++)
		m[i] /= (float)sd;

	return m;
}

static void align_frame(struct frame *fr, const struct frame *ref, const struct opts *o)
{
	fr->dx = fr->dy = 0;
	if (o->align <= 0)
		return;

	/*
	 * Two-pixel cells average one full CFA period, so the luma keeps its
	 * structure at this scale and a shift of a few pixels is still visible.
	 * The SAD is subsampled to keep the search cheap on a phone.
	 */
	const int ds = 2;
	const int sub = 2;
	int sw, sh;
	float *a = luma_small(ref, o, &sw, &sh, ds);
	float *b = luma_small(fr, o, &sw, &sh, ds);
	int radius = o->align / ds + 1;
	if (radius > 10)
		radius = 10;

	double best = 1e300;
	for (int dy = -radius; dy <= radius; dy++) {
		for (int dx = -radius; dx <= radius; dx++) {
			double err = 0;
			int n = 0;
			for (int y = 0; y < sh; y += sub) {
				int yy = y + dy;
				if (yy < 0 || yy >= sh)
					continue;
				for (int x = 0; x < sw; x += sub) {
					int xx = x + dx;
					if (xx < 0 || xx >= sw)
						continue;
					double d = a[(size_t)yy * sw + xx] -
						   b[(size_t)y * sw + x];
					err += d * d;
					n++;
				}
			}
			if (n > (sw / sub) * (sh / sub) / 4 && err < best) {
				best = err;
				fr->dx = -dx * ds;
				fr->dy = -dy * ds;
			}
		}
	}

	/*
	 * The CFA repeats every two pixels: an odd shift would move a red sample
	 * onto a green site and mix channels. Round to the nearest even shift.
	 */
	fr->dx = (fr->dx / 2) * 2;
	fr->dy = (fr->dy / 2) * 2;

	free(a);
	free(b);
}

static inline float sample_shifted(const struct frame *fr, const struct opts *o,
				   int x, int y, int *ok)
{
	int sx = x + fr->dx;
	int sy = y + fr->dy;
	if (sx < 0 || sx >= o->width || sy < 0 || sy >= o->height) {
		*ok = 0;
		return 0.0f;
	}
	*ok = 1;
	return (float)fr->data[(size_t)sy * o->width + sx];
}

/* Merge the burst into a normalised linear CFA image. */
static float *merge(const struct frame *frames, int n, const struct opts *o)
{
	const float range = (float)(o->white - o->black);
	float *out = calloc((size_t)o->width * o->height, sizeof(*out));
	if (!out)
		die("out of memory");

	for (int y = 0; y < o->height; y++) {
		for (int x = 0; x < o->width; x++) {
			double sum = 0, wsum = 0;
			float fallback = 0;
			float fallback_raw = -1;

			for (int f = 0; f < n; f++) {
				int ok;
				float raw = sample_shifted(&frames[f], o, x, y, &ok);
				if (!ok)
					continue;

				float lin = (raw - o->black) / (range * frames[f].ev);
				float snr = (raw - o->black) / range;
				if (snr < 0.0f)
					snr = 0.0f;

				/* Reject saturated samples, favour brighter ones. */
				float sat = raw >= o->white - 1 ? 0.0f : 1.0f;
				float w = sat * (0.02f + snr);

				sum += (double)lin * w;
				wsum += w;

				if (raw > fallback_raw) {
					fallback_raw = raw;
					fallback = lin;
				}
			}

			out[(size_t)y * o->width + x] =
				wsum > 1e-6 ? (float)(sum / wsum) : fallback;
		}
	}

	return out;
}

/* Malvar-He-Cutler demosaic of a normalised CFA image. */
static void demosaic_mhc(const float *cfa, float *rgb, const struct opts *o)
{
	const int w = o->width, h = o->height;

	for (int y = 0; y < h; y++) {
		for (int x = 0; x < w; x++) {
			float n[25], pr[25];
			for (int j = 0; j < 5; j++) {
				for (int i = 0; i < 5; i++) {
					int px = x + i - 2, py = y + j - 2;
					int inside = px >= 0 && py >= 0 && px < w && py < h;
					pr[j * 5 + i] = (float)inside;
					n[j * 5 + i] = inside ? cfa[(size_t)py * w + px] : 0.0f;
				}
			}
			#define N(i, j) n[(j) * 5 + (i)]
			#define P(i, j) pr[(j) * 5 + (i)]
			float c = N(2, 2);
			float r, g, b;

			if ((x & 1) == o->red_x && (y & 1) == o->red_y) {
				float two = P(0, 2) * c - N(0, 2) + P(4, 2) * c - N(4, 2) +
					    P(2, 0) * c - N(2, 0) + P(2, 4) * c - N(2, 4);
				g = (2 * (N(2, 1) + N(1, 2) + N(3, 2) + N(2, 3)) + two) /
				    (2 * (P(2, 1) + P(1, 2) + P(3, 2) + P(2, 3)));
				b = (4 * (N(1, 1) + N(3, 1) + N(1, 3) + N(3, 3)) + 3 * two) /
				    (4 * (P(1, 1) + P(3, 1) + P(1, 3) + P(3, 3)));
				r = c;
			} else if ((x & 1) != o->red_x && (y & 1) != o->red_y) {
				float two = P(0, 2) * c - N(0, 2) + P(4, 2) * c - N(4, 2) +
					    P(2, 0) * c - N(2, 0) + P(2, 4) * c - N(2, 4);
				g = (2 * (N(2, 1) + N(1, 2) + N(3, 2) + N(2, 3)) + two) /
				    (2 * (P(2, 1) + P(1, 2) + P(3, 2) + P(2, 3)));
				r = (4 * (N(1, 1) + N(3, 1) + N(1, 3) + N(3, 3)) + 3 * two) /
				    (4 * (P(1, 1) + P(3, 1) + P(1, 3) + P(3, 3)));
				b = c;
			} else {
				float dv = N(1, 1) + N(3, 1) + N(0, 2) + N(4, 2) + N(1, 3) + N(3, 3);
				float dpv = P(1, 1) + P(3, 1) + P(0, 2) + P(4, 2) + P(1, 3) + P(3, 3);
				float dh = N(1, 1) + N(3, 1) + N(2, 0) + N(2, 4) + N(1, 3) + N(3, 3);
				float dph = P(1, 1) + P(3, 1) + P(2, 0) + P(2, 4) + P(1, 3) + P(3, 3);
				r = (8 * (N(1, 2) + N(3, 2)) +
				     (2 * dpv - P(2, 0) - P(2, 4)) * c -
				     2 * dv + N(2, 0) + N(2, 4)) /
				    (8 * (P(1, 2) + P(3, 2)));
				b = (8 * (N(2, 1) + N(2, 3)) +
				     (2 * dph - P(0, 2) - P(4, 2)) * c -
				     2 * dh + N(0, 2) + N(4, 2)) /
				    (8 * (P(2, 1) + P(2, 3)));
				g = c;
				if ((y & 1) != o->red_y) {
					float t = r; r = b; b = t;
				}
			}
			#undef N
			#undef P
			rgb[((size_t)y * w + x) * 3 + 0] = r * o->wb[0];
			rgb[((size_t)y * w + x) * 3 + 1] = g * o->wb[1];
			rgb[((size_t)y * w + x) * 3 + 2] = b * o->wb[2];
		}
	}
}

static void write_ppm(const char *path, const float *rgb, const struct opts *o)
{
	FILE *f = fopen(path, "wb");
	if (!f) {
		perror(path);
		exit(1);
	}
	fprintf(f, "P6\n%d %d\n255\n", o->width, o->height);

	const float gamma = o->gamma > 0.0f ? o->gamma : 1.0f;
	for (size_t i = 0; i < (size_t)o->width * o->height; i++) {
		unsigned char px[3];
		for (int c = 0; c < 3; c++) {
			float v = rgb[i * 3 + c];
			v = v < 0 ? 0 : v;
			/* Roll the >1 HDR values into [0,1) before the gamma. */
			if (o->tone > 0.0f)
				v = o->tone * v / (1.0f + o->tone * v);
			v = v > 1 ? 1 : v;
			v = powf(v, gamma);
			px[c] = (unsigned char)(v * 255.0f + 0.5f);
		}
		fwrite(px, 1, 3, f);
	}
	fclose(f);
}

static int parse_pattern(const char *s, int *rx, int *ry)
{
	if (!strcmp(s, "RGGB")) { *rx = 0; *ry = 0; }
	else if (!strcmp(s, "BGGR")) { *rx = 1; *ry = 1; }
	else if (!strcmp(s, "GRBG")) { *rx = 1; *ry = 0; }
	else if (!strcmp(s, "GBRG")) { *rx = 0; *ry = 1; }
	else return -1;
	return 0;
}

int main(int argc, char **argv)
{
	struct opts o = {
		.width = 0, .height = 0, .stride = 0,
		.black = 64, .white = 1023,
		.red_x = 0, .red_y = 0,
		.wb = { 1, 1, 1 }, .gamma = 1.0f / 2.2f, .tone = 1.0f, .align = 24,
	};
	float evs[32];
	int n_ev = 0;
	const char *out_path = NULL;
	const char **paths = calloc((size_t)argc, sizeof(*paths));
	int n_paths = 0;

	if (!paths)
		die("out of memory");

	for (int i = 1; i < argc; i++) {
		const char *a = argv[i];
		if (!strcmp(a, "--width")) o.width = atoi(argv[++i]);
		else if (!strcmp(a, "--height")) o.height = atoi(argv[++i]);
		else if (!strcmp(a, "--stride")) o.stride = atoi(argv[++i]);
		else if (!strcmp(a, "--black")) o.black = atoi(argv[++i]);
		else if (!strcmp(a, "--white")) o.white = atoi(argv[++i]);
		else if (!strcmp(a, "--red-x")) o.red_x = atoi(argv[++i]);
		else if (!strcmp(a, "--red-y")) o.red_y = atoi(argv[++i]);
		else if (!strcmp(a, "--gamma")) o.gamma = (float)atof(argv[++i]);
		else if (!strcmp(a, "--tone")) o.tone = (float)atof(argv[++i]);
		else if (!strcmp(a, "--align")) o.align = atoi(argv[++i]);
		else if (!strcmp(a, "--threads")) (void)argv[++i];
		else if (!strcmp(a, "--pattern")) {
			if (parse_pattern(argv[++i], &o.red_x, &o.red_y))
				die("unknown pattern");
		} else if (!strcmp(a, "--wb")) {
			if (sscanf(argv[++i], "%f,%f,%f", &o.wb[0], &o.wb[1], &o.wb[2]) != 3)
				die("bad --wb");
		} else if (!strcmp(a, "--ev")) {
			char *s = argv[++i], *tok;
			for (tok = strtok(s, ","); tok && n_ev < 32; tok = strtok(NULL, ","))
				evs[n_ev++] = (float)atof(tok);
		} else if (a[0] == '-') {
			fprintf(stderr, "op9-hdr: unknown option %s\n", a);
			return 1;
		} else if (!out_path) {
			out_path = a;
		} else {
			paths[n_paths++] = a;
		}
	}

	if (o.width <= 0 || o.height <= 0 || o.stride <= 0 ||
	    !out_path || n_paths == 0 || n_paths > 32) {
		fprintf(stderr, "usage: op9-hdr --width W --height H --stride S [options] out.ppm frame.raw...\n");
		return 1;
	}
	if (n_ev == 0)
		evs[n_ev++] = 1.0f;
	if (n_ev != n_paths)
		die("--ev needs one value per frame");

	struct frame *frames = calloc((size_t)n_paths, sizeof(*frames));
	if (!frames)
		die("out of memory");

	for (int i = 0; i < n_paths; i++) {
		frames[i].path = paths[i];
		frames[i].ev = evs[i] > 0 ? evs[i] : 1.0f;
		frames[i].data = read_raw(paths[i], &o);
	}

	for (int i = 1; i < n_paths; i++) {
		align_frame(&frames[i], &frames[0], &o);
		fprintf(stderr, "op9-hdr: frame %d shift %d,%d\n",
			i, frames[i].dx, frames[i].dy);
	}

	float *merged = merge(frames, n_paths, &o);
	float *rgb = malloc((size_t)o.width * o.height * 3 * sizeof(*rgb));
	if (!rgb)
		die("out of memory");

	demosaic_mhc(merged, rgb, &o);
	write_ppm(out_path, rgb, &o);

	for (int i = 0; i < n_paths; i++)
		free(frames[i].data);
	free(frames);
	free(merged);
	free(rgb);
	free(paths);

	fprintf(stderr, "op9-hdr: wrote %s from %d frame(s)\n", out_path, n_paths);
	return 0;
}
