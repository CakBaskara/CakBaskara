"""Render assets/contributions.json into an animated heatmap SVG (diagonal reveal)."""
import json
import os
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC = os.environ.get("STATIC") == "1"

CELL, GAP = 12, 3
STEP = CELL + GAP
PAD_L, PAD_T = 34, 42          # PAD_T shrinks when the prompt line is off
WIDTH = 860
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
DAY_LABELS = {1: "Mon", 3: "Wed", 5: "Fri"}
PROMPT_TPL = '  <text class="ttl" x="%d" y="24"><tspan class="acc">%s</tspan> ~ $ git log --graph --all</text>'


def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def main():
    cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    theme = cfg["theme"]
    show_prompt = cfg.get("show_prompt", True)
    pad_t = PAD_T if show_prompt else 24
    palette = ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"]

    data = json.loads((ROOT / "assets" / "contributions.json").read_text(encoding="utf-8"))
    days = data["days"]

    # group into week columns: a new column starts every Sunday
    weeks, cur = [], []
    for d in days:
        y, m, dd = (int(x) for x in d["date"].split("-"))
        wd = (date(y, m, dd).weekday() + 1) % 7  # 0 = Sunday
        if wd == 0 and cur:
            weeks.append(cur)
            cur = []
        d = dict(d, wd=wd)
        cur.append(d)
    if cur:
        weeks.append(cur)
    weeks = weeks[-53:]

    grid_w = len(weeks) * STEP - GAP
    grid_h = 7 * STEP - GAP
    foot_y = pad_t + grid_h + 34
    height = foot_y + 44

    cells, month_labels, seen_months = [], [], set()
    max_diag = 0
    for wi, week in enumerate(weeks):
        for d in week:
            x = PAD_L + wi * STEP
            y = pad_t + d["wd"] * STEP
            diag = wi + d["wd"] * 2          # diagonal sweep, top-left -> bottom-right
            max_diag = max(max_diag, diag)
            delay = "" if STATIC else ' style="animation-delay:%.2fs"' % (diag * 0.022)
            cells.append(
                '<rect class="c" x="%d" y="%d" width="%d" height="%d" rx="2.5" fill="%s"%s>'
                '<title>%s: %d contributions</title></rect>'
                % (x, y, CELL, CELL, palette[min(d["level"], 4)], delay, d["date"], d["count"])
            )
        first = week[0]
        mo = int(first["date"].split("-")[1])
        if mo not in seen_months and wi < len(weeks) - 2:
            seen_months.add(mo)
            month_labels.append(
                '<text class="lbl" x="%d" y="%d">%s</text>'
                % (PAD_L + wi * STEP, pad_t - 8, MONTHS[mo - 1])
            )

    day_labels = [
        '<text class="lbl" x="%d" y="%d">%s</text>' % (4, pad_t + i * STEP + CELL - 2, t)
        for i, t in DAY_LABELS.items()
    ]

    total = sum(d["count"] for d in days)
    active = sum(1 for d in days if d["count"] > 0)
    best = max((d["count"] for d in days), default=0)

    # longest streak
    streak = cur_streak = 0
    for d in days:
        cur_streak = cur_streak + 1 if d["count"] > 0 else 0
        streak = max(streak, cur_streak)

    # lay the legend out from the right edge, reserving room for the "More"
    # label so it sits beside the swatches instead of on top of them
    legend = []
    MORE_W = 36
    lx = WIDTH - 24 - MORE_W - (4 * STEP + CELL)
    for i, c in enumerate(palette):
        legend.append(
            '<rect x="%d" y="%d" width="%d" height="%d" rx="2.5" fill="%s"/>'
            % (lx + i * STEP, foot_y + 12, CELL, CELL, c)
        )

    anim = "" if STATIC else """
    .c { opacity: 0; transform-box: fill-box; transform-origin: center;
         animation: pop .5s ease-out forwards; }
    @keyframes pop {
      from { opacity: 0; transform: translateY(-4px) scale(.4); }
      to   { opacity: 1; transform: none; }
    }
    .row { opacity: 0; animation: fade .6s ease-out forwards; }
    @keyframes fade { to { opacity: 1; } }"""

    fade_delay = "" if STATIC else ' style="animation-delay:%.2fs"' % (max_diag * 0.022 + .2)

    svg = """<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="ui-monospace,SFMono-Regular,Consolas,monospace">
  <style>
    .bg   {{ fill: {bg}; }}
    .lbl  {{ fill: {muted}; font-size: 10px; }}
    .ttl  {{ fill: {fg}; font-size: 13px; }}
    .acc  {{ fill: {accent}; font-size: 13px; }}
    .foot {{ fill: {muted}; font-size: 11px; }}{anim}
  </style>
  <rect class="bg" x="0" y="0" width="{W}" height="{H}" rx="10"/>
  <rect x=".5" y=".5" width="{W1}" height="{H1}" rx="10" fill="none" stroke="{border}"/>
{header}
  {months}
  {daylbl}
  {cells}
  <g class="row"{fd}>
    <text class="foot" x="{PL}" y="{FY}">{total} contributions in the last year · {active} active {dayword} · longest streak {streak} {streakword} · best day {best}</text>
    <text class="foot" x="{PL}" y="{FY2}">last updated {today}</text>
    <text class="foot" x="{LEGX}" y="{FY2}" text-anchor="end">Less</text>
    {legend}
    <text class="foot" x="{MOREX}" y="{FY2}">More</text>
  </g>
</svg>
""".format(
        W=WIDTH, H=height, W1=WIDTH - 1, H1=height - 1, W2=WIDTH - 24,
        PL=PAD_L, FY=foot_y, FY2=foot_y + 22, LEGX=lx - 8,
        MOREX=lx + 4 * STEP + CELL + 8,
        bg=theme["bg"], fg=theme["fg"], muted=theme["muted"],
        accent=theme["accent"], border=theme["border"],
        handle=esc(cfg["handle"]), anim=anim, fd=fade_delay,
        header=(PROMPT_TPL % (PAD_L, esc(cfg["handle"]))) if show_prompt else "",
        months="\n  ".join(month_labels), daylbl="\n  ".join(day_labels),
        cells="\n  ".join(cells), legend="\n    ".join(legend),
        total=total, active=active, streak=streak, best=best,
        dayword="day" if active == 1 else "days",
        streakword="day" if streak == 1 else "days",
        today=date.today().isoformat(),
    )

    out = ROOT / "assets" / "contrib-heatmap.svg"
    out.write_text(svg, encoding="utf-8")
    print("[ok] %s (%dx%d, %d cells)" % (out, WIDTH, height, sum(len(w) for w in weeks)))


if __name__ == "__main__":
    main()
