"""Check source integrity and rendered geometry, including truncated Docker paths."""
import hashlib
import io
import json
import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

import resvg_py
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from make_info_card import ICON_SIZE, LOGO_SIZE, icon_markup
from tech_icons import ICON_DIR, ICONS


class IconTests(unittest.TestCase):
    def test_vendored_logos_match_pinned_sources(self):
        manifest = json.loads((ICON_DIR / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(set(manifest["sha256"]), set(ICONS))
        for slug, expected in manifest["sha256"].items():
            with self.subTest(icon=slug):
                svg = (ICON_DIR / (slug + ".svg")).read_text(encoding="utf-8")
                self.assertEqual(hashlib.sha256(svg.encode("utf-8")).hexdigest(), expected)

    def test_every_configured_badge_uses_a_vector_logo(self):
        cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
        for group in cfg.get("toolbox", []):
            for slug in group["items"]:
                with self.subTest(icon=slug):
                    badge = ET.fromstring(icon_markup(slug, 0, 0))
                    self.assertEqual(len(badge.findall("path")), 1)
                    self.assertEqual(badge.find("path").get("d"), ICONS[slug]["path"])
                    self.assertIsNone(badge.find("text"))

    def test_all_logo_shapes_render_at_full_size_inside_the_badge(self):
        # XML parsing alone misses malformed path commands. Rasterize the geometry
        # without the badge background and inspect its actual painted bounds.
        zoom = 10
        for slug in ICONS:
            with self.subTest(icon=slug):
                badge = ET.fromstring(icon_markup(slug, 0, 0))
                badge.remove(badge.find("rect"))
                svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 28 28">' + ET.tostring(badge, encoding="unicode") + '</svg>'
                png = resvg_py.svg_to_bytes(svg_string=svg, width=ICON_SIZE * zoom, skip_system_fonts=True)
                bounds = Image.open(io.BytesIO(png)).convert("RGBA").getchannel("A").getbbox()
                self.assertIsNotNone(bounds, "Logo rendered blank")
                left, top, right, bottom = bounds
                inset = (ICON_SIZE - LOGO_SIZE) * zoom / 2
                self.assertGreaterEqual(left, inset - 1)
                self.assertGreaterEqual(top, inset - 1)
                self.assertLessEqual(right, (ICON_SIZE * zoom) - inset + 1)
                self.assertLessEqual(bottom, (ICON_SIZE * zoom) - inset + 1)
                self.assertGreaterEqual(max(right - left, bottom - top), LOGO_SIZE * zoom - 2,
                                        "Logo is truncated or incorrectly scaled")


if __name__ == "__main__":
    unittest.main()
