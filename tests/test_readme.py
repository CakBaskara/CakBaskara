"""Keep profile pictures non-linked and each configured icon independently named."""
import hashlib
import json
import shutil
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from make_info_card import BADGE_DISPLAY_SIZE, render_info_card, write_info_assets
from refresh_readme import refresh_readme
from tech_icons import ICONS


class ReadmeTests(unittest.TestCase):
    def setUp(self):
        self.cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
        # A copied repository intentionally clears its inherited toolbox. Keep
        # these fixtures independent of the current owner's personal choices.
        self.cfg["toolbox"] = [
            {"label": "Languages", "items": ["python", "typescript", "javascript"]},
            {"label": "Frameworks", "items": ["nextdotjs", "react"]},
            {"label": "Data", "items": ["numpy", "pandas", "postgresql"]},
            {"label": "Tools", "items": ["git", "githubactions", "docker", "n8n", "gnubash"]},
        ]
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        shutil.copy2(ROOT / "README.md", self.root / "README.md")
        write_info_assets(self.cfg, self.root)
        for name in ("portrait-ascii.svg", "contrib-heatmap.svg"):
            (self.root / "assets" / name).write_text('<svg/>', encoding="utf-8")

    def build(self):
        (self.root / "config.json").write_text(json.dumps(self.cfg), encoding="utf-8")
        refresh_readme(self.root)
        return BeautifulSoup((self.root / "README.md").read_text(encoding="utf-8"), "html.parser")

    def test_all_images_are_unlinked_pictures_with_per_icon_tooltips(self):
        soup = self.build()
        self.assertIsNone(soup.find("a"))
        self.assertIsNone(soup.find(["h1", "h2", "h3", "h4", "h5", "h6"]))
        slugs = [slug for group in self.cfg["toolbox"] for slug in group["items"]]
        self.assertEqual(len(soup.find_all("img")), 3 + len(slugs))
        for image in soup.find_all("img"):
            self.assertEqual(image.parent.name, "picture")
            self.assertRegex(image["src"], r"\?v=[0-9a-f]{16}$")
        badges = soup.select('img[title]')
        self.assertEqual([image["title"] for image in badges], [ICONS[slug]["title"] for slug in slugs])
        for slug, badge in zip(slugs, badges):
            self.assertEqual(badge["alt"], ICONS[slug]["title"])
            size = str(BADGE_DISPLAY_SIZE)
            self.assertEqual((badge["width"], badge["height"]), (size, size))
            self.assertLess(BADGE_DISPLAY_SIZE, 28)
            self.assertTrue(badge["src"].startswith("assets/toolbox/" + slug + ".svg?v="))
            svg = ET.parse(self.root / "assets" / "toolbox" / (slug + ".svg"))
            self.assertEqual(svg.find('.//{http://www.w3.org/2000/svg}path').get("d"), ICONS[slug]["path"])

    def test_portrait_is_centered_in_a_proportional_column(self):
        soup = self.build()
        left, right = soup.select('table > tr > td')
        self.assertEqual((left['width'], right['width']), ('35%', '65%'))
        self.assertEqual(left['align'], 'center')
        self.assertEqual((left['valign'], right['valign']), ('middle', 'middle'))

    def test_single_badge_change_only_updates_its_own_url(self):
        self.build()
        readme = self.root / "README.md"
        before = readme.read_text(encoding="utf-8")
        badge = self.root / "assets" / "toolbox" / "python.svg"
        old = badge.read_text(encoding="utf-8")
        new = old.replace('</svg>', '<!-- updated -->\n</svg>')
        badge.write_text(new, encoding="utf-8")
        self.build()
        old_hash = hashlib.sha256(old.encode()).hexdigest()[:16]
        new_hash = hashlib.sha256(new.encode()).hexdigest()[:16]
        self.assertEqual(before.replace(old_hash, new_hash), readme.read_text(encoding="utf-8"))

    def test_empty_toolbox_does_not_inherit_badges(self):
        self.cfg["toolbox"] = []
        soup = self.build()
        self.assertEqual(len(soup.find_all("img")), 3)
        self.assertEqual(soup.select("img[title]"), [])
        self.assertIsNone(soup.find("sub"))

    def test_labels_are_escaped_and_unmanaged_content_is_preserved(self):
        self.cfg["profile_title"] = 'Alice <test> & Bob'
        self.cfg["toolbox"][0]["label"] = '<a href="https://example.invalid">Languages</a>'
        readme = self.root / "README.md"
        readme.write_text('Custom introduction\n\n' + readme.read_text(encoding="utf-8") + '\nCustom footer\n', encoding="utf-8")
        soup = self.build()
        self.assertEqual(soup.find("strong").get_text(), self.cfg["profile_title"])
        self.assertEqual(soup.find("sub").get_text(), self.cfg["toolbox"][0]["label"])
        self.assertIsNone(soup.find("a"))
        text = readme.read_text(encoding="utf-8")
        self.assertTrue(text.startswith("Custom introduction\n"))
        self.assertTrue(text.endswith("\nCustom footer\n"))

    def test_summary_omits_icons_but_combined_export_keeps_them(self):
        namespace = {"svg": "http://www.w3.org/2000/svg"}
        summary = ET.fromstring(render_info_card(self.cfg, include_toolbox=False))
        full = ET.fromstring(render_info_card(self.cfg))
        self.assertEqual(summary.findall('.//svg:path', namespace), [])
        count = sum(len(group["items"]) for group in self.cfg["toolbox"])
        self.assertEqual(len(full.findall('.//svg:path', namespace)), count)
        self.assertLess(int(summary.get("height")), int(full.get("height")))
        self.assertEqual(full.get("height"), "420")


if __name__ == "__main__":
    unittest.main()
