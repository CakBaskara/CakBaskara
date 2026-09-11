"""Check repository skill detection and the additions-only toolbox merge."""
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.audit_skills import (DEFAULTS, STATE_FILE, audit_skills, detect_repo, merge_toolbox,
                                  pypi_packages)
from scripts.tech_icons import CATALOG, CATEGORIES, ICONS

API = "https://api.github.com"


class FakeGitHub:
    """Serve canned REST responses and record every requested URL."""

    def __init__(self, repos, repo_data):
        self.repos, self.repo_data, self.urls = repos, repo_data, []

    def __call__(self, url, headers=None, timeout=None):
        self.urls.append(url)
        if "/users/" in url:
            return Mock(json=Mock(return_value=self.repos))
        name = url.split("/repos/", 1)[1].split("/")[1]
        languages, files = self.repo_data[name]
        if url.endswith("/languages"):
            return Mock(json=Mock(return_value=languages))
        if "/git/trees/" in url:
            tree = [{"path": path, "type": "blob", "sha": "sha-" + path, "size": len(text)}
                    for path, text in files.items()]
            return Mock(json=Mock(return_value={"tree": tree}))
        path = url.rsplit("/git/blobs/sha-", 1)[1]
        return Mock(content=files[path].encode("utf-8"))


def repo(name, pushed="2026-01-01T00:00:00Z", **extra):
    return {"name": name, "full_name": "alice/" + name, "default_branch": "main",
            "pushed_at": pushed, "size": 10, "fork": False, **extra}


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.cfg = {"username": "alice", "toolbox": [{"label": "Languages", "items": ["python"]}]}
        (self.root / "config.json").write_text(json.dumps(self.cfg), encoding="utf-8")

    def tearDown(self):
        self.directory.cleanup()

    def config(self):
        return json.loads((self.root / "config.json").read_text(encoding="utf-8"))

    def test_catalog_has_complete_detection_metadata(self):
        self.assertGreaterEqual(len(CATALOG), 60)
        self.assertLessEqual(len(CATALOG), 100)
        self.assertEqual(set(CATALOG), set(ICONS))
        for slug, entry in CATALOG.items():
            with self.subTest(icon=slug):
                self.assertIn(entry["category"], CATEGORIES)
                self.assertRegex(entry["bg"], r"^#[0-9A-Fa-f]{6}$")
                self.assertRegex(entry["fg"], r"^#[0-9A-Fa-f]{6}$")
                self.assertLessEqual(set(entry["detect"]), {"languages", "npm", "pypi", "files", "contains"})
                for rule in entry["detect"].get("contains", []):
                    re.compile(rule["pattern"])

    def test_detects_languages_dependencies_and_files(self):
        files = {
            "package.json": json.dumps({"dependencies": {"react": "19"}, "devDependencies": {"next": "16"}}),
            "api/requirements.txt": "pandas>=2  # numpy is only a comment\n-r base.txt\nScikit_Learn==1.7\n",
            "docker-compose.yml": "services:\n  flows:\n    image: n8nio/n8n\n",
            ".github/workflows/ci.yml": "on: push\n",
        }
        skills, unmatched = detect_repo({"Python": 900, "Shell": 20, "COBOL": 300},
                                        list(files), files.get)
        self.assertEqual(skills, {"python", "react", "nextdotjs", "pandas", "scikitlearn", "n8n",
                                  "docker", "githubactions", "nodedotjs"})
        self.assertEqual(unmatched, {"COBOL"})

    def test_reads_every_python_dependency_format(self):
        pyproject = """
[project]
dependencies = ["FastAPI[standard]>=0.115", "numpy"]
[project.optional-dependencies]
ml = ["torch"]
[dependency-groups]
dev = ["pytest"]
[tool.poetry.dependencies]
Django = "^5"
[tool.poetry.group.data.dependencies]
polars = "*"
"""
        self.assertEqual(pypi_packages("pyproject.toml", pyproject),
                         {"fastapi", "numpy", "torch", "pytest", "django", "polars"})
        self.assertEqual(pypi_packages("Pipfile", '[packages]\nflask = "*"\n[dev-packages]\npytest = "*"\n'),
                         {"flask", "pytest"})
        self.assertEqual(pypi_packages("pyproject.toml", "not = [valid"), set())

    def test_merge_only_appends_unknown_skills(self):
        cfg = {"toolbox": [{"label": "Tools", "items": ["git"]}, {"label": "Languages", "items": ["python"]}]}
        added = merge_toolbox(cfg, {"python": 3, "go": 1, "react": 2, "docker": 1, "rust": 5},
                              known={"rust"}, options=DEFAULTS)
        self.assertEqual(added, ["react", "go", "docker"])
        # Existing groups keep their custom order; a new group follows Languages.
        self.assertEqual(cfg["toolbox"], [
            {"label": "Tools", "items": ["git", "docker"]},
            {"label": "Languages", "items": ["python", "go"]},
            {"label": "Frameworks", "items": ["react"]},
        ])

    def test_merge_respects_thresholds_and_group_capacity(self):
        cfg = {"toolbox": [{"label": "languages", "items": ["python", "c"]}]}
        options = dict(DEFAULTS, min_repos=2, max_per_group=3)
        added = merge_toolbox(cfg, {"go": 2, "rust": 2, "zig": 1}, known=set(), options=options)
        self.assertEqual(added, ["go"])
        self.assertEqual(cfg["toolbox"], [{"label": "languages", "items": ["python", "c", "go"]}])

    def test_audit_adds_new_skills_and_keeps_removed_ones_out(self):
        fake = FakeGitHub(
            [repo("app"), repo("alice"), repo("forked", fork=True), repo("empty", size=0)],
            {"app": ({"Go": 100}, {"package.json": '{"dependencies": {"react": "19"}}'})},
        )
        cfg = audit_skills(self.cfg, self.root, get=fake, environ={})
        self.assertEqual(self.config(), cfg)
        self.assertEqual(cfg["toolbox"], [
            {"label": "Languages", "items": ["python", "go"]},
            {"label": "Frameworks", "items": ["react"]},
            {"label": "Tools", "items": ["nodedotjs"]},
        ])
        self.assertFalse(any("/repos/alice/alice" in url or "forked" in url or "empty" in url for url in fake.urls))
        state = json.loads((self.root / STATE_FILE).read_text(encoding="utf-8"))
        self.assertEqual(state["known"], ["go", "nodedotjs", "python", "react"])
        self.assertEqual(state["repos"]["app"]["skills"], ["go", "nodedotjs", "react"])

        # The owner deletes two skills by hand: an audited one and an original one.
        cfg["toolbox"] = [{"label": "Languages", "items": ["go"]}, {"label": "Tools", "items": ["nodedotjs"]}]
        (self.root / "config.json").write_text(json.dumps(cfg), encoding="utf-8")
        fake.urls.clear()
        again = audit_skills(cfg, self.root, get=fake, environ={})
        self.assertEqual(again, cfg)
        self.assertEqual(len(fake.urls), 1, "an unchanged repository must be served from the cache")

    def test_pushed_repository_is_rescanned(self):
        fake = FakeGitHub([repo("app")], {"app": ({"Go": 100}, {})})
        audit_skills(self.cfg, self.root, get=fake, environ={})
        fake.repos = [repo("app", pushed="2026-02-01T00:00:00Z")]
        fake.repo_data["app"] = ({"Go": 100, "Rust": 100}, {})
        cfg = audit_skills(self.config(), self.root, get=fake, environ={})
        self.assertEqual(cfg["toolbox"][0]["items"], ["python", "go", "rust"])

    def test_failures_leave_config_untouched(self):
        before = (self.root / "config.json").read_bytes()
        offline = Mock(side_effect=requests.ConnectionError("offline"))
        self.assertEqual(audit_skills(self.cfg, self.root, get=offline, environ={}), self.cfg)
        self.assertFalse((self.root / STATE_FILE).exists())

        # A repository that fails mid-scan is neither counted nor cached.
        def rate_limited(url, headers=None, timeout=None):
            if "/users/" in url:
                return Mock(json=Mock(return_value=[repo("app")]))
            raise requests.HTTPError("rate limited")

        self.assertEqual(audit_skills(self.cfg, self.root, get=rate_limited, environ={}), self.cfg)
        self.assertEqual((self.root / "config.json").read_bytes(), before)
        self.assertEqual(json.loads((self.root / STATE_FILE).read_text(encoding="utf-8"))["repos"], {})

    def test_new_owner_does_not_inherit_audit_state(self):
        (self.root / STATE_FILE).parent.mkdir()
        (self.root / STATE_FILE).write_text(json.dumps({"owner": "someone-else", "known": ["go"]}))
        fake = FakeGitHub([repo("app")], {"app": ({"Go": 100}, {})})
        cfg = audit_skills(self.cfg, self.root, get=fake, environ={})
        self.assertEqual(cfg["toolbox"][0]["items"], ["python", "go"])

    def test_disabled_and_dry_run_write_nothing(self):
        fake = FakeGitHub([repo("app")], {"app": ({"Go": 100}, {})})
        disabled = dict(self.cfg, skill_audit={"enabled": False})
        self.assertIs(audit_skills(disabled, self.root, get=fake, environ={}), disabled)
        self.assertEqual(fake.urls, [])
        self.assertEqual(audit_skills(self.cfg, self.root, get=fake, environ={}, dry_run=True), self.cfg)
        self.assertFalse((self.root / STATE_FILE).exists())


if __name__ == "__main__":
    unittest.main()
