"""Refresh the managed heading and content-based image URLs without cache purges."""
import hashlib
import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ("portrait-ascii.svg", "info-card.svg", "contrib-heatmap.svg")


def refresh_readme(root=ROOT):
    cfg = json.loads((root / "config.json").read_text(encoding="utf-8"))
    readme = root / "README.md"
    original = readme.read_text(encoding="utf-8")
    title = html.escape(cfg.get("profile_title") or cfg["name"] + " Profile")
    updated = re.sub(
        r"(<!-- profile-title:start -->).*?(<!-- profile-title:end -->)",
        lambda match: match[1] + '\n<h3 align="center">' + title + "</h3>\n" + match[2],
        original, flags=re.DOTALL,
    )
    for name in ASSETS:
        asset = root / "assets" / name
        # Git normalizes text line endings; keep Windows and Linux hashes equal.
        digest = hashlib.sha256(asset.read_text(encoding="utf-8").encode("utf-8")).hexdigest()[:16]
        updated = re.sub(
            r"assets/" + re.escape(name) + r"(?:\?[^\s\"'<>)]*)?",
            lambda match, name=name, digest=digest: "assets/" + name + "?v=" + digest,
            updated,
        )
    if updated != original:
        readme.write_text(updated, encoding="utf-8")
    print("[ok] README heading and image versions are current")


if __name__ == "__main__":
    refresh_readme()
