"""Neofetch-style info card; each row fades and slides in on a stagger."""
import json
import os
from pathlib import Path

from tech_icons import ICONS

ROOT = Path(__file__).resolve().parent.parent
STATIC = os.environ.get("STATIC") == "1"

WIDTH, HEIGHT = 560, 420
PAD = 26
LINE = 26
KEY_W = 108
ICON_SIZE = 28
ICON_GAP = 6
LOGO_SIZE = 20
CURSOR_TPL = ('  <g class="ln"%s>' + chr(10) +
              '    <text class="mut" x="%d" y="%d"><tspan class="acc">%s</tspan>'
              ' ~ $ <tspan class="cur">&#9608;</tspan></text>' + chr(10) +
              '  </g>' + chr(10))
PROMPT_TPL = '  <text class="mut" x="%d" y="%d"><tspan class="acc">%s</tspan> ~ $ neofetch</text>'


def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def icon_markup(slug, x, y):
    icon = ICONS[slug]
    base = (
        '<g><title>%s</title>'
        '<rect x="%d" y="%d" width="%d" height="%d" rx="7" fill="%s"/>'
        % (esc(icon["title"]), x, y, ICON_SIZE, ICON_SIZE, icon["bg"])
    )
    inset = (ICON_SIZE - LOGO_SIZE) / 2
    content = (
        '<path d="%s" fill="%s" transform="translate(%g %g) scale(%.8f)"/>'
        % (icon["path"], icon["fg"], x + inset, y + inset, LOGO_SIZE / 24)
    )
    return base + content + '</g>'


def render_info_card(cfg, include_toolbox=True):
    t = cfg["theme"]
    rows = cfg["info"]
    toolbox = cfg.get("toolbox", [])
    show_prompt = cfg.get("show_prompt", True)

    y = PAD + 30 if show_prompt else PAD + 18
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

    if include_toolbox and toolbox:
        y += 10
        for group in toolbox:
            icons = "".join(
                icon_markup(slug, PAD + n * (ICON_SIZE + ICON_GAP), y + 7)
                for n, slug in enumerate(group["items"])
            )
            add(
                '<text class="group" x="%d" y="%d">%s</text>%s'
                % (PAD, y, esc(group["label"]), icons),
                step=45,
            )
    elif include_toolbox:
        # Fallback for older configs without a toolbox.
        y += 10
        swatches = ["#39d353", "#26a641", "#006d32", "#58a6ff",
                    "#bc8cff", "#f778ba", "#ffa657", "#8b949e"]
        add("".join(
            '<rect x="%d" y="%d" width="16" height="10" rx="2" fill="%s"/>'
            % (PAD + n * 20, y - 9, c)
            for n, c in enumerate(swatches)
        ))

    # The README uses a compact summary and separate icons for per-icon tooltips.
    # Keep the original combined card for standalone SVG/PNG exports.
    height = HEIGHT if include_toolbox else y + (LINE + PAD if show_prompt else 0)

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
    .group {{ fill: {fg}; font-size: 11px; font-weight: 700; }}
    .b   {{ font-weight: 700; }}{anim}
  </style>
  <rect x="0" y="0" width="{W}" height="{H}" rx="10" fill="{bg}"/>
  <rect x=".5" y=".5" width="{W1}" height="{H1}" rx="10" fill="none" stroke="{border}"/>
{header}
  {lines}
{cursor}</svg>
""".format(
        W=WIDTH, H=height, W1=WIDTH - 1, H1=height - 1, PAD=PAD, TY=PAD + 8,
        bg=t["bg"], fg=t["fg"], muted=t["muted"], accent=t["accent"], border=t["border"],
        handle=esc(cfg["handle"]), anim=anim, cd=cur_delay,
        cursor=(CURSOR_TPL % (cur_delay, PAD, min(y + LINE + 4, height - PAD + 4),
                              esc(cfg["handle"]))) if show_prompt else "",
        header=(PROMPT_TPL % (PAD, PAD + 8, esc(cfg["handle"]))) if show_prompt else "",
        lines="\n  ".join(lines),
    )

    return svg


def render_badge(slug):
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 28 28">'
        + icon_markup(slug, 0, 0) + '</svg>\n'
    )


def write_info_assets(cfg, root=ROOT):
    assets = root / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    for name, include_toolbox in (("info-card.svg", True), ("info-summary.svg", False)):
        (assets / name).write_text(render_info_card(cfg, include_toolbox), encoding="utf-8")
    for group in cfg.get("toolbox", []):
        for slug in group["items"]:
            # Validate against the vendored icon registry before constructing a path.
            svg = render_badge(slug)
            directory = assets / "toolbox"
            directory.mkdir(exist_ok=True)
            (directory / (slug + ".svg")).write_text(svg, encoding="utf-8")
    print("[ok] Info card, README summary, and configured toolbox badges are current")


def main():
    cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    write_info_assets(cfg, ROOT)


if __name__ == "__main__":
    main()
