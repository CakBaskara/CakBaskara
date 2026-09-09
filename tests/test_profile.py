"""Check copied-repository identity, portrait replacement, and README cache versions."""
import copy
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import Mock, patch

import requests
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.prepare_profile import adapt_config, owner_from_remote, prepare_profile, resolve_owner
from scripts.refresh_readme import refresh_readme
from make_info_card import icon_markup
import fetch_contributions
import make_ascii_svg


class ProfileTests(unittest.TestCase):
    def setUp(self):
        self.cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
        self.cfg.update(auto_owner=True, username="original-owner", portrait_owner="original-owner",
                        name="Original Owner", handle="original-owner@github", profile_title="Original Owner Profile")

    def test_github_remote_formats(self):
        for remote in ("https://github.com/alice/profile.git", "git@github.com:alice/profile.git",
                       "ssh://git@github.com/alice/profile.git", "https://github.com/alice/profile/"):
            with self.subTest(remote=remote):
                self.assertEqual(owner_from_remote(remote), "alice")
        self.assertIsNone(owner_from_remote("https://github.com.evil.invalid/alice/profile.git"))

    def test_repository_owner_wins_over_actor_and_override(self):
        self.assertEqual(resolve_owner(self.cfg, environ={
            "GITHUB_REPOSITORY_OWNER": "alice", "GITHUB_ACTOR": "bob", "GH_USER": "carol",
        }), "alice")

    def test_local_origin_and_manual_mode(self):
        remote = subprocess.CompletedProcess([], 0, "git@github.com:alice/profile.git\n")
        with patch("scripts.prepare_profile.subprocess.run", return_value=remote):
            self.assertEqual(resolve_owner(self.cfg, environ={}), "alice")
        cfg = dict(self.cfg, auto_owner=False)
        self.assertEqual(resolve_owner(cfg, environ={"GITHUB_REPOSITORY_OWNER": "alice"}), cfg["username"])

    def test_new_owner_does_not_inherit_personal_claims(self):
        original = copy.deepcopy(self.cfg)
        cfg = adapt_config(self.cfg, "alice", {"name": "Alice", "location": "Bandung", "bio": "Builds tools"})
        self.assertEqual(self.cfg, original)
        self.assertEqual(cfg["username"], "alice")
        self.assertEqual(cfg["handle"], "alice@github")
        self.assertEqual(cfg["name"], "Alice")
        self.assertEqual(cfg["toolbox"], [])
        self.assertEqual(cfg["theme"], original["theme"])
        self.assertEqual(cfg["portrait_owner"], original["portrait_owner"])
        self.assertEqual(cfg["info"], [["Location", "Bandung"], ["Bio", "Builds tools"], ["Contact", "github.com/alice"]])

    def test_missing_and_long_profile_fields_fit(self):
        owner = "a" * 39
        cfg = adapt_config(self.cfg, owner, {"name": None, "location": None, "bio": "b" * 160})
        self.assertEqual(cfg["name"], owner)
        self.assertTrue(all(len(value) <= 43 for _, value in cfg["info"]))
        self.assertEqual(cfg["info"][-1], ["", owner])

    def test_adaptation_runs_once_and_preserves_later_customization(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config_path = root / "config.json"
            config_path.write_text(json.dumps(self.cfg), encoding="utf-8")
            with patch.dict(os.environ, {"GITHUB_REPOSITORY_OWNER": "alice"}), patch(
                "scripts.prepare_profile.fetch_profile", return_value={"name": "Alice"},
            ) as fetch:
                cfg = prepare_profile(root)
                cfg["name"] = "Custom Alice"
                config_path.write_text(json.dumps(cfg), encoding="utf-8")
                self.assertEqual(prepare_profile(root)["name"], "Custom Alice")
                fetch.assert_called_once_with("alice")

    def test_readme_hashes_change_only_for_changed_assets(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "assets").mkdir()
            (root / "config.json").write_text(json.dumps(dict(self.cfg, profile_title="Alice & Bob <test>")), encoding="utf-8")
            shutil.copy2(ROOT / "README.md", root / "README.md")
            for name in ("portrait-ascii.svg", "info-card.svg", "contrib-heatmap.svg"):
                (root / "assets" / name).write_bytes(name.encode())
            refresh_readme(root)
            first = (root / "README.md").read_bytes()
            self.assertIn(b"Alice &amp; Bob &lt;test&gt;", first)
            refresh_readme(root)
            self.assertEqual((root / "README.md").read_bytes(), first)
            (root / "assets" / "info-card.svg").write_bytes(b"updated")
            refresh_readme(root)
            second = (root / "README.md").read_bytes()
            old_hash = hashlib.sha256(b"info-card.svg").hexdigest()[:16].encode()
            new_hash = hashlib.sha256(b"updated").hexdigest()[:16].encode()
            self.assertEqual(first.replace(old_hash, new_hash), second)

    def test_changed_owner_replaces_inherited_portrait_even_when_skipped(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copytree(ROOT / "scripts", root / "scripts", ignore=shutil.ignore_patterns("__pycache__"))
            shutil.copytree(ROOT / "assets", root / "assets")
            for name in ("build.py", "README.md"):
                shutil.copy2(ROOT / name, root / name)
            cfg = adapt_config(self.cfg, "alice", {"name": "Alice", "location": "Bandung"})
            (root / "config.json").write_text(json.dumps(cfg), encoding="utf-8")
            old_portrait = (root / "assets" / "portrait-ascii.svg").read_bytes()
            env = dict(os.environ, GITHUB_REPOSITORY_OWNER="alice")
            command = [sys.executable, "build.py", "--demo", "--skip-portrait"]
            result = subprocess.run(command, cwd=root, env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertNotEqual(old_portrait, (root / "assets" / "portrait-ascii.svg").read_bytes())
            self.assertEqual(json.loads((root / "config.json").read_text())["portrait_owner"], "alice")
            self.assertEqual(json.loads((root / "assets" / "contributions.json").read_text())["username"], "alice")
            self.assertNotIn(self.cfg["username"], (root / "README.md").read_text(encoding="utf-8"))
            for svg in (root / "assets").glob("*.svg"):
                ET.parse(svg)
            before = {path.name: path.read_bytes() for path in (root / "assets").iterdir()}
            result = subprocess.run(command, cwd=root, env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(before, {path.name: path.read_bytes() for path in (root / "assets").iterdir()})

    def test_cache_version_is_independent_of_platform_line_endings(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "assets").mkdir()
            (root / "config.json").write_text(json.dumps(self.cfg), encoding="utf-8")
            shutil.copy2(ROOT / "README.md", root / "README.md")
            for name in ("portrait-ascii.svg", "info-card.svg", "contrib-heatmap.svg"):
                (root / "assets" / name).write_bytes(b"<svg>\r\n</svg>\r\n")
            refresh_readme(root)
            first = (root / "README.md").read_bytes()
            for asset in (root / "assets").iterdir():
                asset.write_bytes(b"<svg>\n</svg>\n")
            refresh_readme(root)
            self.assertEqual(first, (root / "README.md").read_bytes())

    def test_avatar_uses_the_configured_owner(self):
        avatar = io.BytesIO()
        Image.new("RGBA", (32, 32), (30, 60, 90, 128)).save(avatar, format="PNG")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "assets").mkdir()
            (root / "config.json").write_text(json.dumps(self.cfg), encoding="utf-8")
            with patch.object(make_ascii_svg, "ROOT", root), patch.object(sys, "argv", ["portrait", "--github-avatar"]), patch(
                "requests.get", return_value=Mock(content=avatar.getvalue()),
            ) as get:
                make_ascii_svg.main()
            get.assert_called_once_with("https://github.com/original-owner.png?size=420", timeout=20)
            ET.parse(root / "assets" / "portrait-ascii.svg")

    def test_failed_fetch_cannot_reuse_another_owner_or_demo_calendar(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "assets").mkdir()
            (root / "config.json").write_text(json.dumps(self.cfg), encoding="utf-8")
            cache_path = root / "assets" / "contributions.json"
            with patch.object(fetch_contributions, "ROOT", root), patch.object(sys, "argv", ["fetch"]), patch(
                "fetch_contributions.requests.get", side_effect=requests.RequestException("offline"),
            ):
                for owner, source in (("someone-else", "github"), ("original-owner", "demo")):
                    cache_path.write_text(json.dumps({"username": owner, "source": source, "days": [{"count": 1}]}))
                    with self.assertRaises(SystemExit):
                        fetch_contributions.main()
                cache_path.write_text(json.dumps({"username": "original-owner", "source": "github", "days": [{"count": 1}]}))
                before = cache_path.read_bytes()
                fetch_contributions.main()
                self.assertEqual(before, cache_path.read_bytes())

    def test_actions_and_docker_render_as_vectors(self):
        for slug in ("githubactions", "docker"):
            icon = ET.fromstring(icon_markup(slug, 0, 0))
            self.assertIsNotNone(icon.find("path"))
            self.assertIsNone(icon.find("text"))


if __name__ == "__main__":
    unittest.main()
