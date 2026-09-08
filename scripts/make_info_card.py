"""Kartu info gaya neofetch, tiap baris fade+slide masuk bergantian."""
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC = os.environ.get("STATIC") == "1"

WIDTH, HEIGHT = 560, 420
PAD = 26
LINE = 30
KEY_W = 108


def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def main():
    cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    t = cfg["theme"]
    rows = cfg["info"]

    y = PAD + 30
    lines = []
    i = 0

    def add(markup, step=LINE):
        nonlocal y, i
        delay = "" if STATIC else ' style="animation-delay:%.2fs"' % (0.12 + i * 0.09)
        lines.append('<g class="ln"%s>%s</g>' % (delay, markup))
        y += step
        i += 1

    header = esc(cfg["name"])
    add('<text class="acc b" x="%d" y="%d">%s</text>' % (PAD, y, header))
    add('<text class="mut" x="%d" y="%d">%s</text>' % (PAD, y, "-" * min(46, len(header) * 2)), step=LINE + 4)

    for k, v in rows:
        add(
            '<text class="key" x="%d" y="%d">%s</text>'
            '<text class="val" x="%d" y="%d">%s</text>'
            % (PAD, y, esc(k), PAD + KEY_W, y, esc(v))
        )

    # baris palet warna ala neofetch
    y += 10
    swatches = ["#39d353", "#26a641", "#006d32", "#58a6ff",
                "#bc8cff", "#f778ba", "#ffa657", "#8b949e"]
    add("".join(
        '<rect x="%d" y="%d" width="16" height="10" rx="2" fill="%s"/>' % (PAD + n * 20, y - 9, c)
        for n, c in enumerate(swatches)
    ))

    anim = "" if STATIC else """
    .ln { opacity: 0; animation: in .55s cubic-bezier(.2,.7,.3,1) forwards; }
    @keyframes in { from { opacity: 0; transform: translateX(-10px); } to { opacity: 1; transform: none; } }
    .cur { animation: blink 1.05s steps(1) infinite; }
    @keyframes blink { 50% { opacity: 0; } }"""

    cur_delay = "" if STATIC else ' style="animation-delay:%.2fs"' % (0.12 + i * 0.09)

    svg = """<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="ui-monospace,SFMono-Regular,Consolas,monospace">
  <style>
    .key {{ fill: {accent}; font-size: 15px; }}
    .val {{ fill: {fg};     font-size: 15px; }}
    .mut {{ fill: {muted};  font-size: 15px; }}
    .acc {{ fill: {accent}; font-size: 18px; }}
    .b   {{ font-weight: 700; }}{anim}
  </style>
  <rect x="0" y="0" width="{W}" height="{H}" rx="10" fill="{bg}"/>
  <rect x=".5" y=".5" width="{W1}" height="{H1}" rx="10" fill="none" stroke="{border}"/>
  <text class="mut" x="{PAD}" y="{TY}"><tspan class="acc">{handle}</tspan> ~ $ neofetch</text>
  {lines}
  <g class="ln"{cd}>
    <text class="mut" x="{PAD}" y="{CY}"><tspan class="acc">{handle}</tspan> ~ $ <tspan class="cur">&#9608;</tspan></text>
  </g>
</svg>
""".format(
        W=WIDTH, H=HEIGHT, W1=WIDTH - 1, H1=HEIGHT - 1, PAD=PAD, TY=PAD + 8,
        CY=min(y + LINE + 4, HEIGHT - PAD + 4),
        bg=t["bg"], fg=t["fg"], muted=t["muted"], accent=t["accent"], border=t["border"],
        handle=esc(cfg["handle"]), anim=anim, cd=cur_delay,
        lines="\n  ".join(lines),
    )

    out = ROOT / "assets" / "info-card.svg"
    out.write_text(svg, encoding="utf-8")
    print("[ok] %s (%dx%d)" % (out, WIDTH, HEIGHT))


if __name__ == "__main__":
    main()
