"""Verify the HD export follows the current, separately rendered README components."""
import base64
import copy
import io
import json
import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

import resvg_py
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from export_profile_png import compose_profile, freeze_svg
from make_info_card import BADGE_DISPLAY_SIZE
from tech_icons import ICONS

NS = '{http://www.w3.org/2000/svg}'


class ExportPngTests(unittest.TestCase):
    def setUp(self):
        self.assets = ROOT / 'assets'
        self.cfg = json.loads((ROOT / 'config.json').read_text(encoding='utf-8'))
        self.cfg['toolbox'] = [
            {'label': 'Languages', 'items': ['python', 'typescript', 'javascript']},
            {'label': 'Tools', 'items': ['githubactions', 'docker']},
        ]

    def test_export_uses_current_summary_and_individually_sized_badges(self):
        root = ET.fromstring(compose_profile(self.cfg, self.assets))
        images = {node.get('id'): node for node in root.iter(NS + 'image')}
        self.assertEqual(len(images), 8)
        summary = base64.b64decode(images['summary'].get('href').split(',', 1)[1])
        self.assertEqual(summary, freeze_svg((self.assets / 'info-summary.svg').read_text(encoding='utf-8')))
        for image_id, image in images.items():
            if not image_id.startswith('badge-'):
                continue
            self.assertEqual(float(image.get('width')), BADGE_DISPLAY_SIZE)
            self.assertEqual(float(image.get('height')), BADGE_DISPLAY_SIZE)
            embedded = ET.fromstring(base64.b64decode(image.get('href').split(',', 1)[1]))
            slug = image_id.split('-', 3)[3]
            self.assertEqual(embedded.find('.//' + NS + 'path').get('d'), ICONS[slug]['path'])

    def test_portrait_is_centered_and_every_component_fits(self):
        root = ET.fromstring(compose_profile(self.cfg, self.assets))
        frame = root.find(".//*[@id='profile-frame']")
        portrait = root.find(".//*[@id='portrait']")
        frame_center = float(frame.get('y')) + float(frame.get('height')) / 2
        portrait_center = float(portrait.get('y')) + float(portrait.get('height')) / 2
        self.assertAlmostEqual(frame_center, portrait_center, places=3)
        left_center = 12 + (940 - 24) * 0.35 / 2
        self.assertAlmostEqual(float(portrait.get('x')) + float(portrait.get('width')) / 2, left_center)
        for image in root.iter(NS + 'image'):
            self.assertGreaterEqual(float(image.get('x')), 0)
            self.assertGreaterEqual(float(image.get('y')), 0)
            self.assertLessEqual(float(image.get('x')) + float(image.get('width')), float(root.get('width')))
            self.assertLessEqual(float(image.get('y')) + float(image.get('height')), float(root.get('height')))

    def test_long_toolbox_wraps_and_empty_toolbox_omits_badges(self):
        cfg = copy.deepcopy(self.cfg)
        cfg['toolbox'] = [{'label': 'Many icons', 'items': ['python'] * 20}]
        root = ET.fromstring(compose_profile(cfg, self.assets))
        icons = [node for node in root.iter(NS + 'image') if node.get('id', '').startswith('badge-')]
        self.assertEqual(len(icons), 20)
        self.assertGreater(len({node.get('y') for node in icons}), 1)
        self.assertTrue(all(float(node.get('x')) + float(node.get('width')) < 940 - 12 for node in icons))
        cfg['toolbox'] = []
        root = ET.fromstring(compose_profile(cfg, self.assets))
        self.assertEqual(len(list(root.iter(NS + 'image'))), 3)

    def test_final_frame_reveals_ascii_and_rasterizes_badge(self):
        frozen = ET.fromstring(freeze_svg((self.assets / 'portrait-ascii.svg').read_text(encoding='utf-8')))
        self.assertEqual(frozen.findall('.//' + NS + 'animate'), [])
        for rect in frozen.findall('.//' + NS + 'clipPath/' + NS + 'rect'):
            self.assertGreater(float(rect.get('width')), 0)
        svg = freeze_svg((self.assets / 'toolbox/python.svg').read_text(encoding='utf-8')).decode('utf-8')
        png = resvg_py.svg_to_bytes(svg_string=svg, width=BADGE_DISPLAY_SIZE)
        image = Image.open(io.BytesIO(png)).convert('RGBA')
        self.assertEqual(image.size, (BADGE_DISPLAY_SIZE, BADGE_DISPLAY_SIZE))
        self.assertEqual(image.getchannel('A').getbbox(), (0, 0, BADGE_DISPLAY_SIZE, BADGE_DISPLAY_SIZE))

    def test_custom_owner_title_and_labels_are_escaped(self):
        self.cfg['profile_title'] = 'Alice & Bob <Profile>'
        self.cfg['toolbox'][0]['label'] = 'Languages <test>'
        root = ET.fromstring(compose_profile(self.cfg, self.assets))
        self.assertEqual(root.find(NS + 'title').text, self.cfg['profile_title'])
        self.assertIn('Languages <test>', [node.text for node in root.iter(NS + 'text')])


if __name__ == '__main__':
    unittest.main()
