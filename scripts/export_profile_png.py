"""Export the README's current summary, portrait, and separate badges as an HD PNG."""
import argparse
import base64
import html
import json
import math
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import resvg_py

from make_info_card import BADGE_DISPLAY_SIZE
from tech_icons import ICONS

ROOT = Path(__file__).resolve().parent.parent
SVG_NS = "{http://www.w3.org/2000/svg}"
ET.register_namespace("", SVG_NS[1:-1])
CANVAS_WIDTH = 940
PAGE_PAD = 12
CELL_PAD_X, CELL_PAD_Y = 14, 8
LABEL_HEIGHT = 24
ICON_GAP = 4
TOOLBOX_INDENT = 24


def freeze_svg(svg):
    root = ET.fromstring(svg)
    # PNG captures the final frame: reveal the ASCII clip widths and CSS rows.
    for parent in root.iter():
        for child in list(parent):
            if child.tag in (SVG_NS + "animate", SVG_NS + "set"):
                if child.get("attributeName") and child.get("to"):
                    parent.set(child.get("attributeName"), child.get("to"))
                parent.remove(child)
        if parent.tag == SVG_NS + "style" and parent.text:
            parent.text = re.sub(r"opacity:\s*0\b", "opacity: 1", parent.text)
            parent.text = re.sub(r"\banimation(?:-[\w]+)?\s*:[^;{}]+;?", "", parent.text)
        if parent.get("style"):
            parent.set("style", re.sub(r"\banimation(?:-[\w]+)?\s*:[^;{}]+;?", "", parent.get("style")))
    # Reveal standalone badge animations too; their vector geometry stays intact.
    style = ET.SubElement(root, SVG_NS + "style")
    style.text = '.ln, .row, .c, .badge, .cur { opacity: 1; transform: none; animation: none; }'
    return ET.tostring(root, encoding="utf-8")


def static_image(name, x, y, width, height, assets, element_id):
    frozen = freeze_svg((assets / name).read_text(encoding="utf-8"))
    encoded = base64.b64encode(frozen).decode("ascii")
    # Separate SVG image documents keep each component's CSS rules isolated.
    return (
        '<image id="%s" x="%g" y="%g" width="%g" height="%g" '
        'href="data:image/svg+xml;base64,%s"/>'
        % (html.escape(element_id, quote=True), x, y, width, height, encoded)
    )


def image_size(assets, name, display_width):
    root = ET.parse(assets / name).getroot()
    _, _, width, height = (float(value) for value in root.get("viewBox").split())
    return display_width, display_width * height / width


def compose_profile(cfg, assets):
    """Compose a fixed-width static counterpart of the README, not a browser screenshot."""
    title = html.escape(cfg.get("profile_title") or cfg["name"] + " Profile")
    background, border = cfg["theme"]["bg"], cfg["theme"]["border"]
    table_width = CANVAS_WIDTH - PAGE_PAD * 2
    left_width = table_width * 0.35
    right_width = table_width - left_width
    portrait_w, portrait_h = image_size(assets, "portrait-ascii.svg", min(300, left_width - 2 * CELL_PAD_X))
    summary_w, summary_h = image_size(assets, "info-summary.svg", min(560, right_width - 2 * CELL_PAD_X))
    summary_x = PAGE_PAD + left_width + CELL_PAD_X
    portrait_x = PAGE_PAD + (left_width - portrait_w) / 2
    group_layout = []
    toolbox_height = 0
    icons_per_row = max(1, int((summary_w - 2 * TOOLBOX_INDENT + ICON_GAP) / (BADGE_DISPLAY_SIZE + ICON_GAP)))
    icon_line_height = max(24, BADGE_DISPLAY_SIZE + 4)
    for group in cfg.get("toolbox", []):
        if not group["items"]:
            continue
        for slug in group["items"]:
            if slug not in ICONS:
                raise ValueError("Unknown toolbox icon: " + slug)
        group_layout.append((group, toolbox_height))
        toolbox_height += LABEL_HEIGHT + math.ceil(len(group["items"]) / icons_per_row) * icon_line_height

    content_height = summary_h + (4 + toolbox_height if group_layout else 0)
    table_y = 50
    table_height = max(portrait_h, content_height) + 2 * CELL_PAD_Y
    portrait_y = table_y + (table_height - portrait_h) / 2
    summary_y = table_y + (table_height - content_height) / 2
    toolbox_y = summary_y + summary_h + 4
    toolbox = []
    for group_index, (group, offset) in enumerate(group_layout):
        x, y = summary_x + TOOLBOX_INDENT, toolbox_y + offset
        toolbox.append('<text x="%g" y="%g" fill="%s" font-family="Arial,sans-serif" font-size="12" font-weight="700">%s</text>'
                       % (x, y + 16, cfg["theme"]["fg"], html.escape(group["label"])))
        for index, slug in enumerate(group["items"]):
            icon_x = x + (index % icons_per_row) * (BADGE_DISPLAY_SIZE + ICON_GAP)
            icon_y = y + LABEL_HEIGHT + (index // icons_per_row) * icon_line_height
            toolbox.append(static_image("toolbox/" + slug + ".svg", icon_x, icon_y,
                                        BADGE_DISPLAY_SIZE, BADGE_DISPLAY_SIZE, assets,
                                        "badge-%d-%d-%s" % (group_index, index, slug)))

    heatmap_y = table_y + table_height + 16
    heatmap_w, heatmap_h = image_size(assets, "contrib-heatmap.svg", table_width)
    canvas_height = math.ceil(heatmap_y + heatmap_h + 16)
    return '''<svg xmlns="http://www.w3.org/2000/svg" width="940" height="{height}" viewBox="0 0 940 {height}">
  <title>{title}</title>
  <desc>Static HD profile export with centered ASCII portrait and separate {icon_size}-pixel toolbox icons.</desc>
  <rect width="940" height="{height}" fill="{background}"/>
  <text x="470" y="28" text-anchor="middle" fill="#e6edf3" font-family="Arial,sans-serif" font-size="18" font-weight="700">{title}</text>
  <rect id="profile-frame" x="12.5" y="50.5" width="915" height="{frame_height}" fill="none" stroke="{border}"/>
  <path d="M{divider_x} 50.5V{frame_bottom}" stroke="{border}"/>
  {portrait}
  <g id="profile-details">
    {summary}
    {toolbox}
  </g>
  {heatmap}
</svg>'''.format(
        title=title, background=background, border=border, height=canvas_height,
        icon_size=BADGE_DISPLAY_SIZE, frame_height=table_height - 1,
        divider_x=PAGE_PAD + left_width, frame_bottom=table_y + table_height - 0.5,
        portrait=static_image("portrait-ascii.svg", portrait_x, portrait_y, portrait_w, portrait_h, assets, "portrait"),
        summary=static_image("info-summary.svg", summary_x, summary_y, summary_w, summary_h, assets, "summary"),
        toolbox="\n    ".join(toolbox),
        heatmap=static_image("contrib-heatmap.svg", PAGE_PAD, heatmap_y, heatmap_w, heatmap_h, assets, "heatmap"),
    )


def main():
    cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--width", type=int, default=3840, help="output width in pixels (default: 3840)")
    parser.add_argument("--output", type=Path, default=ROOT / "exports" / (cfg["username"] + "-profile-HD.png"))
    args = parser.parse_args()
    if args.width < CANVAS_WIDTH:
        parser.error("--width must be at least %d pixels" % CANVAS_WIDTH)

    svg = compose_profile(cfg, ROOT / "assets")
    png = resvg_py.svg_to_bytes(svg_string=svg, width=args.width)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(png)
    print("[ok] " + str(args.output))


if __name__ == "__main__":
    main()
