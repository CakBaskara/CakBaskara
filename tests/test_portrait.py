"""Keep the ASCII character grid centered without changing the owner's portrait."""
import io
import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

import resvg_py
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from make_ascii_svg import CHAR_W, center_existing_portrait
from preview_icons import revealed_portrait

NS = '{http://www.w3.org/2000/svg}'


class PortraitTests(unittest.TestCase):
    def setUp(self):
        self.source = (ROOT / 'assets' / 'portrait-ascii.svg').read_text(encoding='utf-8')

    def test_centering_preserves_characters_vertical_position_and_reveal_timing(self):
        before = ET.fromstring(self.source)
        after = ET.fromstring(center_existing_portrait(self.source))
        old_rows = [row for row in before.findall(NS + 'text') if row.get('class') != 'hdr']
        new_rows = [row for row in after.findall(NS + 'text') if row.get('class') != 'hdr']
        self.assertEqual([row.text for row in old_rows], [row.text for row in new_rows])
        self.assertEqual([row.get('y') for row in old_rows], [row.get('y') for row in new_rows])
        self.assertEqual([node.attrib for node in before.findall('.//' + NS + 'animate')],
                         [node.attrib for node in after.findall('.//' + NS + 'animate')])
        canvas_width = float(after.get('viewBox').split()[2])
        for row in new_rows:
            row_width = len(row.text or '') * CHAR_W
            self.assertEqual(float(row.get('textLength')), row_width)
            self.assertEqual(row.get('lengthAdjust'), 'spacingAndGlyphs')
            self.assertAlmostEqual(float(row.get('x')), (canvas_width - row_width) / 2)

    def test_reflow_is_idempotent(self):
        first = center_existing_portrait(self.source)
        self.assertEqual(first, center_existing_portrait(first))

    def test_non_ascii_svg_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'no generated ASCII rows'):
            center_existing_portrait('<svg xmlns="http://www.w3.org/2000/svg"/>')

    def test_revealed_portrait_has_balanced_horizontal_ink_bounds(self):
        # A fixed edge-to-edge row isolates font metrics from a particular
        # person's naturally asymmetric silhouette or custom photograph.
        fixture = ('<svg xmlns="http://www.w3.org/2000/svg" width="300" height="420" viewBox="0 0 300 420">'
                   '<text x="10.5" y="200" font-size="5" xml:space="preserve">'
                   + '#' * 93 + '</text></svg>')
        portrait = ET.fromstring(revealed_portrait(center_existing_portrait(fixture)))
        for family in ('monospace', 'serif'):
            with self.subTest(font=family):
                portrait.set('font-family', family)
                png = resvg_py.svg_to_bytes(svg_string=ET.tostring(portrait, encoding='unicode'), width=600)
                rendered = Image.open(io.BytesIO(png)).convert('RGBA')
                bounds = rendered.getchannel('A').getbbox()
                self.assertIsNotNone(bounds)
                left, _, right, _ = bounds
                self.assertLessEqual(abs(left - (rendered.width - right)), 4,
                                     'ASCII ink has unequal horizontal margins')


if __name__ == '__main__':
    unittest.main()
