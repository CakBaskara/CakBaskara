"""Load unmodified, pinned Simple Icons geometry for the profile toolbox.

`icons/catalog.json` is the single registry: badge colors, the default toolbox
category, and the repository signals that `audit_skills.py` uses for detection.
"""
import json
import xml.etree.ElementTree as ET
from pathlib import Path

ICON_DIR = Path(__file__).resolve().parent / "icons"
SVG_NS = "{http://www.w3.org/2000/svg}"
CATEGORIES = ("Languages", "Frameworks", "Data", "Tools")
CATALOG = json.loads((ICON_DIR / "catalog.json").read_text(encoding="utf-8"))


def load_icon(slug, bg, fg):
    root = ET.parse(ICON_DIR / (slug + ".svg")).getroot()
    paths = root.findall(SVG_NS + "path")
    if root.get("viewBox") != "0 0 24 24" or len(paths) != 1:
        raise ValueError("Expected one complete 24x24 logo path: " + slug)
    return {
        "title": root.findtext(SVG_NS + "title"),
        "bg": bg,
        "fg": fg,
        "path": paths[0].attrib["d"],
    }


ICONS = {slug: load_icon(slug, entry["bg"], entry["fg"]) for slug, entry in CATALOG.items()}
