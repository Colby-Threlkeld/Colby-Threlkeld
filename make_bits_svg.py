"""Build an animated SVG of the figure drawn in 0/1 bits.

Usage: python make_bits_svg.py <image> <out.svg> [cols]

Animation (pure CSS inside the SVG, so GitHub plays it in a README):
  1. Rows "decode" in from top to bottom.
  2. Short runs of bits keep flipping between two random bit patterns.
  3. A soft gold scan line sweeps down the figure.
"""
import random
import sys

import numpy as np
from PIL import Image
from scipy import ndimage

SRC, OUT = sys.argv[1], sys.argv[2]
COLS = int(sys.argv[3]) if len(sys.argv) > 3 else 110

FONT = 9.0           # px
CW = FONT * 0.6      # monospace advance
LH = FONT * 1.05     # line height
PAD = 14
SEG = 8              # bits per independently flipping run
rng = random.Random(7)

# ---------- figure mask (same cues as the text version) ----------
im = Image.open(SRC).convert("RGB")
a = np.asarray(im).astype(float) / 255
mx, mn = a.max(2), a.min(2)
s = (mx - mn) / np.maximum(mx, 1e-6)
mask = ((mx < 0.86) & (s < 0.72)) | ((s < 0.2) & (mx > 0.85))
mask[795:] = False
mask = ndimage.binary_closing(mask, iterations=2)
lab, n = ndimage.label(mask)
sizes = ndimage.sum(mask, lab, range(1, n + 1))
mask = ndimage.binary_fill_holes(lab == 1 + np.argmax(sizes))
ys, xs = np.where(mask)
y0, y1, x0, x1 = ys.min() - 2, ys.max() + 3, xs.min() - 2, xs.max() + 3
m = mask[y0:y1, x0:x1]
rgb = a[y0:y1, x0:x1]
h, w = m.shape
ROWS = int(h / w * COLS * CW / LH)

ms = np.asarray(Image.fromarray((m * 255).astype(np.uint8)).resize((COLS, ROWS), Image.BOX)) / 255
cs = np.asarray(Image.fromarray((rgb * 255).astype(np.uint8)).resize((COLS, ROWS), Image.LANCZOS)).astype(float) / 255

# ---------- colour: keep the photo's hue, re-light for a dark card ----------
def tone(c):
    r, g, b = c
    lum = 0.299 * r + 0.587 * g + 0.114 * b
    sat = max(c) - min(c)
    # brightness ramp: dark suit -> dim, white hair/hands -> near white
    t = np.clip((lum - 0.35) / 0.65, 0, 1) ** 1.3
    base = 0.28 + 0.72 * t
    if sat > 0.42 and r > g * 1.2:          # sash / blood: warm orange
        out = (1.0, 0.55, 0.25)
    elif t > 0.8:                            # hair, hands, shirt
        out = (1.0, 0.98, 0.9)
    else:                                    # suit: warm grey
        out = (0.95, 0.88, 0.7)
    return tuple(int(255 * min(1, v * base)) for v in out)

def q(col, step=24):
    return tuple(min(255, (v // step) * step + step // 2) for v in col)

grid = [[None] * COLS for _ in range(ROWS)]
for y in range(ROWS):
    for x in range(COLS):
        if ms[y, x] >= 0.4:
            grid[y][x] = q(tone(cs[y, x]))

palette = sorted({c for row in grid for c in row if c})
cls = {c: f"c{i}" for i, c in enumerate(palette)}

def bits(k):
    return "".join(rng.choice("01") for _ in range(k))

def runs_html(cols, x_start, pattern):
    """tspans grouping same-colour cells; spaces for gaps."""
    out, cur, buf = [], None, ""
    for i, c in enumerate(cols):
        ch = pattern[i] if c else " "
        key = cls[c] if c else None
        if key != cur and buf:
            out.append(f'<tspan class="{cur}">{buf}</tspan>' if cur else buf)
            buf = ""
        cur = key
        buf += ch
    if buf:
        out.append(f'<tspan class="{cur}">{buf}</tspan>' if cur else buf)
    return "".join(out)

# ---------- build rows ----------
body = []
first = next(y for y in range(ROWS) if any(grid[y]))
last = max(y for y in range(ROWS) if any(grid[y]))
N_TIMINGS = 10
for y in range(first, last + 1):
    row = grid[y]
    if not any(row):
        continue
    ty = PAD + (y - first + 1) * LH
    delay = (y - first) * 0.022
    segs = []
    x = 0
    while x < COLS:
        if row[x] is None:
            x += 1
            continue
        start = x
        while x < COLS and row[x] is not None and x - start < SEG:
            x += 1
        chunk = row[start:x]
        px = PAD + start * CW
        t = rng.randrange(N_TIMINGS)
        tl = f'textLength="{len(chunk) * CW:.1f}" lengthAdjust="spacing"'
        segs.append(
            f'<g class="f t{t}">'
            f'<text class="A" x="{px:.1f}" y="{ty:.1f}" {tl}>{runs_html(chunk, start, bits(len(chunk)))}</text>'
            f'<text class="B" x="{px:.1f}" y="{ty:.1f}" {tl}>{runs_html(chunk, start, bits(len(chunk)))}</text>'
            f"</g>"
        )
    body.append(f'<g class="row" style="animation-delay:{delay:.2f}s">{"".join(segs)}</g>')

W = PAD * 2 + COLS * CW
H = PAD * 2 + (last - first + 2) * LH

# ---------- background twinkles (echo the photo's sparkles) ----------
spark = []
for i in range(46):
    sx, sy = rng.uniform(6, W - 12), rng.uniform(6, H - 6)
    spark.append(
        f'<text class="s" x="{sx:.0f}" y="{sy:.0f}" '
        f'style="animation-delay:{rng.uniform(0, 6):.2f}s;animation-duration:{rng.uniform(3, 7):.1f}s">'
        f'{rng.choice("01")}</text>'
    )

timing_css = []
for t in range(N_TIMINGS):
    dur = rng.uniform(1.6, 4.5)
    d = rng.uniform(0, 4)
    timing_css.append(
        f".t{t} .A{{animation:fa {dur:.2f}s steps(1) {d:.2f}s infinite}}"
        f".t{t} .B{{animation:fb {dur:.2f}s steps(1) {d:.2f}s infinite}}"
    )

colour_css = "".join(f".{k}{{fill:rgb{c}}}" for c, k in cls.items())

svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W:.0f} {H:.0f}" width="{W:.0f}" height="{H:.0f}" role="img" aria-label="Animated figure drawn in binary digits">
<style>
text{{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,"Liberation Mono",monospace;font-size:{FONT}px;white-space:pre}}
.row{{opacity:0;animation:in .5s ease-out forwards}}
@keyframes in{{0%{{opacity:0;transform:translateX(-3px)}}100%{{opacity:1;transform:none}}}}
.B{{opacity:0}}
@keyframes fa{{0%{{opacity:1}}50%{{opacity:0}}}}
@keyframes fb{{0%{{opacity:0}}50%{{opacity:1}}}}
.s{{fill:#e8b923;opacity:0;animation:tw 5s ease-in-out infinite}}
@keyframes tw{{0%,100%{{opacity:0}}50%{{opacity:.45}}}}
.scan{{animation:scan 6s linear 2s infinite;opacity:0}}
@keyframes scan{{0%{{transform:translateY(-40px);opacity:0}}8%{{opacity:1}}85%{{opacity:1}}100%{{transform:translateY({H:.0f}px);opacity:0}}}}
@media (prefers-reduced-motion:reduce){{*{{animation:none!important}}.row{{opacity:1}}}}
{colour_css}
{''.join(timing_css)}
</style>
<defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1">
<stop offset="0" stop-color="#e8b923" stop-opacity="0"/><stop offset=".5" stop-color="#e8b923" stop-opacity=".16"/><stop offset="1" stop-color="#e8b923" stop-opacity="0"/>
</linearGradient></defs>
<rect width="100%" height="100%" rx="12" fill="#0d1117"/>
{''.join(spark)}
{''.join(body)}
<rect class="scan" x="0" y="0" width="{W:.0f}" height="40" fill="url(#g)"/>
</svg>
"""
open(OUT, "w", encoding="utf-8").write(svg)
print(f"{COLS}x{last - first + 1} cells, {len(palette)} colours, {len(svg) / 1024:.0f} KB -> {OUT}")
