"""Render local PNG previews for visual inspection: pip install -r requirements-dev.txt."""
import math
import xml.etree.ElementTree as ET
from pathlib import Path

import resvg_py

from make_info_card import BADGE_DISPLAY_SIZE, ICON_SIZE, esc, icon_markup
from tech_icons import ICONS

ROOT = Path(__file__).resolve().parent.parent


def revealed_portrait(svg):
    """Resolve the ASCII type-in clips to their final frame for a PNG preview."""
    namespace = '{http://www.w3.org/2000/svg}'
    ET.register_namespace('', namespace[1:-1])
    root = ET.fromstring(svg)
    for parent in root.iter():
        for child in list(parent):
            if child.tag == namespace + 'animate':
                parent.set(child.get('attributeName'), child.get('to'))
                parent.remove(child)
    return ET.tostring(root, encoding='unicode')


def main():
    width, height = 760, 70 + math.ceil(len(ICONS) / 4) * 140
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d">' % (width, height),
        '<rect width="100%" height="100%" fill="#0d1117"/>',
        '<text x="24" y="32" fill="#c9d1d9" font-size="18" font-family="sans-serif">Toolbox logos: actual size and 3x zoom</text>',
    ]
    for index, (slug, icon) in enumerate(ICONS.items()):
        x, y = 24 + (index % 4) * 184, 64 + (index // 4) * 140
        parts.append('<text x="%d" y="%d" fill="#c9d1d9" font-size="13" font-family="sans-serif">%s</text>' % (x, y, esc(icon["title"])))
        parts.append('<g transform="translate(%d %d) scale(%g)">%s</g>'
                     % (x, y + 42, BADGE_DISPLAY_SIZE / ICON_SIZE, icon_markup(slug, 0, 0)))
        parts.append('<g transform="translate(%d %d) scale(3)">%s</g>' % (x + 56, y + 16, icon_markup(slug, 0, 0)))
    parts.append('</svg>')
    (ROOT / "preview-icons.png").write_bytes(resvg_py.svg_to_bytes(svg_string="".join(parts)))
    # The rasterizer does not animate; make the existing fade-in rows visible.
    card = (ROOT / "assets" / "info-card.svg").read_text(encoding="utf-8")
    card = card.replace('.ln { opacity: 0;', '.ln { opacity: 1;')
    (ROOT / "preview-info-card.png").write_bytes(resvg_py.svg_to_bytes(svg_string=card, width=1120))
    portrait = (ROOT / "assets" / "portrait-ascii.svg").read_text(encoding="utf-8")
    (ROOT / "preview-portrait.png").write_bytes(resvg_py.svg_to_bytes(svg_string=revealed_portrait(portrait), width=600))
    print("[ok] preview-icons.png, preview-info-card.png, and preview-portrait.png")


if __name__ == "__main__":
    main()
