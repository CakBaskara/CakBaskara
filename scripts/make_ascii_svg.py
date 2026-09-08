"""Turn a photo into an ASCII portrait SVG that types itself in, row by row.

  python scripts/make_ascii_svg.py --photo photo.png --preview
  python scripts/make_ascii_svg.py --photo photo.png --crop "120,140,660,900"

ASCII art only has brightness to work with, so a busy background competes with
the face. Two ways out: crop tighter, or fade the background with --vignette
(or cut it out properly with --nobg, which needs rembg installed).
"""
import argparse
import hashlib
import json
import os
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageOps

ROOT = Path(__file__).resolve().parent.parent
STATIC = os.environ.get("STATIC") == "1"

WIDTH, HEIGHT = 300, 420
PAD = 10
FS = 5.0                 # font size
CHAR_W = FS * 0.6        # monospace character width
LINE_H = FS * 1.0
RAMP = " .`:-=+*cs#%@"


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def placeholder(seed, size=420):
    """Soft identicon standing in for a photo, deterministic from the seed."""
    h = hashlib.sha256(seed.encode("utf-8")).digest()
    img = Image.new("L", (size, size), 245)
    d = ImageDraw.Draw(img)
    d.ellipse((size * .28, size * .12, size * .72, size * .56), fill=70)    # head
    d.ellipse((size * .12, size * .55, size * .88, size * 1.25), fill=110)  # shoulders
    cells = 7
    step = size // cells
    for gy in range(cells):
        for gx in range((cells + 1) // 2):
            if h[(gy * 4 + gx) % len(h)] & 1:
                shade = 150 + (h[(gy + gx) % len(h)] % 60)
                for x in (gx, cells - 1 - gx):
                    d.rectangle((x * step, gy * step, x * step + step - 2,
                                 gy * step + step - 2), fill=shade)
    return img


def strip_background(img):
    """Cut the subject out with rembg, if it is installed."""
    try:
        from rembg import remove
    except ImportError:
        raise SystemExit(
            "[x] --nobg needs rembg: pip install rembg\n"
            "    (or use --vignette / a tighter --crop instead)"
        )
    out = remove(img.convert("RGBA"))
    flat = Image.new("RGBA", out.size, (255, 255, 255, 255))
    return Image.alpha_composite(flat, out).convert("RGB")


def vignette(gray, strength):
    """Fade toward white outside a centred ellipse, so the background drops out."""
    a = np.asarray(gray, dtype=np.float32) / 255.0
    h, w = a.shape
    yy, xx = np.mgrid[0:h, 0:w]
    # normalised distance from centre; 1.0 sits on the inscribed ellipse
    r = np.sqrt(((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 2)) ** 2)
    fade = np.clip((r - 0.62) / 0.38, 0, 1) * strength     # soft edge, not a hard cut
    a = a + (1.0 - a) * fade
    return Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8), "L")


def to_rows(img, cols, gamma, invert, max_rows, vig):
    img = ImageOps.grayscale(img)
    img = ImageOps.autocontrast(img, cutoff=2)
    if vig > 0:
        img = vignette(img, vig)
    w, h = img.size

    ratio = (h / w) * (CHAR_W / LINE_H)
    rows = max(1, int(round(cols * ratio)))
    if rows > max_rows:                  # too tall, so narrow it instead
        cols = max(8, int(max_rows / ratio))
        rows = max(1, int(round(cols * ratio)))
    img = img.resize((cols, rows), Image.LANCZOS)

    a = np.asarray(img, dtype=np.float32) / 255.0
    a = np.clip(a, 0, 1) ** gamma
    if not invert:
        a = 1.0 - a                      # dark pixels become dense characters
    idx = np.clip((a * (len(RAMP) - 1)).round().astype(int), 0, len(RAMP) - 1)
    return ["".join(RAMP[i] for i in row) for row in idx]


def main():
    cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    t = cfg["theme"]

    ap = argparse.ArgumentParser()
    ap.add_argument("--photo", help="path to a jpg/png")
    ap.add_argument("--gamma", type=float, default=1.0,
                    help="<1 cleans the background, >1 strengthens the face")
    ap.add_argument("--invert", action="store_true", help="for dark backgrounds")
    ap.add_argument("--cols", type=int, default=int((WIDTH - 2 * PAD) / CHAR_W))
    ap.add_argument("--crop", help="crop the photo: x,y,w,h in pixels")
    ap.add_argument("--vignette", type=float, default=0.0, metavar="N",
                    help="0-1, fade the background outside a centred oval")
    ap.add_argument("--nobg", action="store_true", help="remove the background (needs rembg)")
    ap.add_argument("--preview", action="store_true", help="print the ASCII to the terminal")
    args = ap.parse_args()

    if args.photo:
        img = Image.open(args.photo)
        if img.mode == "RGBA":                      # flatten transparency onto white
            bg = Image.new("RGBA", img.size, (255, 255, 255, 255))
            img = Image.alpha_composite(bg, img)
    else:
        print("[i] no --photo given, using a placeholder")
        img = placeholder(cfg["username"] or "anon")

    if args.crop:
        x, y, w, h = (int(v) for v in args.crop.split(","))
        img = img.crop((x, y, x + w, y + h))

    if args.nobg:
        img = strip_background(img)

    top_margin = 34
    max_rows = int((HEIGHT - top_margin - PAD) / LINE_H)
    rows = to_rows(img, args.cols, args.gamma, args.invert, max_rows, args.vignette)
    ncols = len(rows[0])

    if args.preview:
        print(chr(10).join(rows))

    art_h = len(rows) * LINE_H
    top = max(top_margin, (HEIGHT - art_h) / 2 + LINE_H)
    row_w = ncols * CHAR_W
    left = (WIDTH - row_w) / 2          # centred horizontally

    defs, texts = [], []
    for n, line in enumerate(rows):
        y = top + n * LINE_H
        if STATIC:
            texts.append('<text x="%.1f" y="%.1f" xml:space="preserve">%s</text>'
                         % (left, y, esc(line)))
            continue
        defs.append(
            '<clipPath id="r%d"><rect x="%.1f" y="%.1f" width="0" height="%.1f">'
            '<animate attributeName="width" from="0" to="%.1f" dur="0.5s" '
            'begin="%.2fs" fill="freeze" calcMode="spline" '
            'keySplines="0.2 0.7 0.3 1" keyTimes="0;1"/></rect></clipPath>'
            % (n, left, y - LINE_H, LINE_H + 1, row_w, 0.15 + n * 0.045)
        )
        texts.append('<text clip-path="url(#r%d)" x="%.1f" y="%.1f" xml:space="preserve">%s</text>'
                     % (n, left, y, esc(line)))

    svg = """<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="ui-monospace,SFMono-Regular,Consolas,monospace">
  <style>
    text {{ fill: {fg}; font-size: {fs}px; letter-spacing: 0; }}
    .hdr {{ fill: {muted}; font-size: 12px; }}
    .acc {{ fill: {accent}; }}
  </style>
  <defs>
{defs}
  </defs>
  <rect x="0" y="0" width="{W}" height="{H}" rx="10" fill="{bg}"/>
  <rect x=".5" y=".5" width="{W1}" height="{H1}" rx="10" fill="none" stroke="{border}"/>
  <text class="hdr" x="{PAD}" y="24"><tspan class="acc">{handle}</tspan> ~ $ ./portrait</text>
{texts}
</svg>
""".format(
        W=WIDTH, H=HEIGHT, W1=WIDTH - 1, H1=HEIGHT - 1, PAD=PAD, fs=FS,
        bg=t["bg"], fg=t["fg"], muted=t["muted"], accent=t["accent"], border=t["border"],
        handle=esc(cfg["handle"]),
        defs="\n".join("    " + d for d in defs),
        texts="\n".join("  " + x for x in texts),
    )

    out = ROOT / "assets" / "portrait-ascii.svg"
    out.write_text(svg, encoding="utf-8")
    print("[ok] %s (%d cols x %d rows)" % (out, ncols, len(rows)))


if __name__ == "__main__":
    main()
