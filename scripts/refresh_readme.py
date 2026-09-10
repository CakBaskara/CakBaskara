"""Generate non-linked README pictures with per-icon native hover tooltips."""
import hashlib
import html
import json
import re
from pathlib import Path

from tech_icons import ICONS
from make_info_card import BADGE_DISPLAY_SIZE

ROOT = Path(__file__).resolve().parent.parent


def picture(root, name, width, alt, title=None):
    asset = root / "assets" / name
    # Git normalizes text line endings; keep Windows and Linux hashes equal.
    digest = hashlib.sha256(asset.read_text(encoding="utf-8").encode("utf-8")).hexdigest()[:16]
    source = html.escape("assets/" + name + "?v=" + digest, quote=True)
    attributes = ' src="%s" width="%d" alt="%s"' % (source, width, html.escape(alt, quote=True))
    if title is not None:
        # Top alignment removes the text-baseline descender space below an icon.
        # GitHub retains this image attribute while stripping inline CSS.
        attributes += ' height="%d" align="top" title="%s"' % (width, html.escape(title, quote=True))
    # GitHub auto-links bare <img>, but leaves images within <picture> unlinked.
    return '<picture><img' + attributes + '></picture>'


def profile_body(root, cfg):
    lines = [
        '<table align="center">',
        '  <tr>',
        '    <td width="35%" align="center" valign="middle">' + picture(root, "portrait-ascii.svg", 300, "ASCII portrait") + '</td>',
        '    <td width="65%" valign="middle">',
        '      ' + picture(root, "info-summary.svg", 560, "Profile information") + '<br>',
    ]
    for group in cfg.get("toolbox", []):
        if not group["items"]:
            continue
        lines.append('      &emsp;&ensp;<sub><b>' + html.escape(group["label"]) + '</b></sub><br>')
        icons = []
        for slug in group["items"]:
            title = ICONS[slug]["title"]
            icons.append(picture(root, "toolbox/" + slug + ".svg", BADGE_DISPLAY_SIZE, title, title=title))
        lines.append('      &emsp;&ensp;' + ' '.join(icons) + '<br>')
    lines.extend([
        '    </td>',
        '  </tr>',
        '</table>',
        '',
        '<p align="center">',
        '  ' + picture(root, "contrib-heatmap.svg", 860, "Contribution heatmap"),
        '</p>',
    ])
    return '\n'.join(lines)


def refresh_readme(root=ROOT):
    cfg = json.loads((root / "config.json").read_text(encoding="utf-8"))
    readme = root / "README.md"
    original = readme.read_text(encoding="utf-8")
    title = html.escape(cfg.get("profile_title") or cfg["name"] + " Profile")
    updated = re.sub(
        r"(<!-- profile-title:start -->).*?(<!-- profile-title:end -->)",
        # A normal text title avoids GitHub's clickable heading permalink.
        lambda match: match[1] + '\n<p align="center"><strong>' + title + "</strong></p>\n" + match[2],
        original, flags=re.DOTALL,
    )
    body = profile_body(root, cfg)
    updated, count = re.subn(
        r"(<!-- profile-body:start -->).*?(<!-- profile-body:end -->)",
        lambda match: match[1] + '\n' + body + '\n' + match[2],
        updated, flags=re.DOTALL,
    )
    if count != 1:
        raise ValueError("README must contain exactly one profile-body marker pair")
    if updated != original:
        readme.write_text(updated, encoding="utf-8")
    print("[ok] README title, non-linked pictures, tooltips, and image versions are current")


if __name__ == "__main__":
    refresh_readme()
