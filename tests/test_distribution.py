"""Keep the public template's licensing and supply-chain safeguards intact."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class DistributionTests(unittest.TestCase):
    def test_repository_has_reuse_and_security_policies(self):
        self.assertIn("MIT License", (ROOT / "LICENSE").read_text(encoding="utf-8"))
        self.assertTrue((ROOT / "SECURITY.md").is_file())
        self.assertIn("CC0-1.0", (ROOT / "scripts" / "icons" / "SOURCES.md").read_text(encoding="utf-8"))

    def test_runtime_dependencies_are_exactly_pinned(self):
        lines = (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()
        requirements = [line for line in lines if line and not line.startswith("#")]
        self.assertTrue(all(re.fullmatch(r"[a-zA-Z0-9_-]+==[^\s]+", line) for line in requirements))
        requests_version = next(line.split("==", 1)[1] for line in requirements if line.startswith("requests=="))
        self.assertGreaterEqual(tuple(map(int, requests_version.split("."))), (2, 33, 0))

    def test_workflow_actions_use_immutable_full_shas(self):
        workflow = (ROOT / ".github" / "workflows" / "update-profile-art.yml").read_text(encoding="utf-8")
        uses = re.findall(r"^\s*- uses:\s+([^\s#]+)", workflow, flags=re.MULTILINE)
        self.assertTrue(uses)
        self.assertTrue(all(re.search(r"@[0-9a-f]{40}$", action) for action in uses))
        self.assertIn("permissions:\n  contents: read", workflow)
        self.assertIn("    permissions:\n      contents: write", workflow)
        self.assertIn("pull_request:", workflow)
        self.assertIn("Run tests without write access", workflow)

    def test_dependabot_tracks_python_and_workflow_dependencies(self):
        config = (ROOT / ".github" / "dependabot.yml").read_text(encoding="utf-8")
        self.assertIn("package-ecosystem: pip", config)
        self.assertIn("package-ecosystem: github-actions", config)

    def test_generated_pngs_stay_local(self):
        self.assertIn("exports/", (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines())


if __name__ == "__main__":
    unittest.main()
