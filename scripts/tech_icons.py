"""Load unmodified, pinned Simple Icons geometry for the profile toolbox."""
import xml.etree.ElementTree as ET
from pathlib import Path

ICON_DIR = Path(__file__).resolve().parent / "icons"
SVG_NS = "{http://www.w3.org/2000/svg}"
STYLES = {
    "python": ("#3776AB", "#FFD343"),
    "c": ("#A8B9CC", "#111111"),
    "cplusplus": ("#00599C", "#ffffff"),
    "typescript": ("#3178C6", "#ffffff"),
    "javascript": ("#F7DF1E", "#111111"),
    "nextdotjs": ("#000000", "#ffffff"),
    "react": ("#20232A", "#61DAFB"),
    "numpy": ("#013243", "#4DABCF"),
    "pandas": ("#150458", "#E70488"),
    "postgresql": ("#4169E1", "#ffffff"),
    "git": ("#F05032", "#ffffff"),
    "githubactions": ("#2088FF", "#ffffff"),
    "docker": ("#2496ED", "#ffffff"),
    "n8n": ("#EA4B71", "#ffffff"),
    "gnubash": ("#4EAA25", "#ffffff"),
}


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


ICONS = {slug: load_icon(slug, *colors) for slug, colors in STYLES.items()}
