"""Rebuild every SVG asset in one go.

  python build.py                   # adapts to the repository owner
  python build.py --photo me.jpg    # also regenerate the portrait from a photo
  python build.py --skip-audit      # keep the toolbox exactly as configured
"""
import argparse
import subprocess
import sys
from pathlib import Path

from scripts.audit_skills import audit_skills
from scripts.prepare_profile import prepare_profile, save_config

ROOT = Path(__file__).resolve().parent


def run(script, *extra):
    cmd = [sys.executable, str(ROOT / "scripts" / script), *extra]
    print("$", " ".join(cmd[1:]))
    if subprocess.call(cmd) != 0:
        sys.exit("[x] failed at %s" % script)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--photo")
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--skip-portrait", action="store_true")
    ap.add_argument("--refresh-portrait", action="store_true", help="regenerate from the owner's GitHub avatar")
    ap.add_argument("--skip-audit", action="store_true", help="do not scan repositories for new toolbox skills")
    args, rest = ap.parse_known_args()

    if args.skip_portrait and (args.photo or args.refresh_portrait or rest):
        ap.error("--skip-portrait cannot be combined with portrait options")
    cfg = prepare_profile()
    if not (args.demo or args.skip_audit):
        cfg = audit_skills(cfg)
    run("fetch_contributions.py", *(["--demo"] if args.demo else []))
    run("render_heatmap_svg.py")
    run("make_info_card.py")
    portrait_missing = not (ROOT / "assets" / "portrait-ascii.svg").exists()
    owner_changed = cfg.get("portrait_owner", "").casefold() != cfg["username"].casefold()
    # A copied portrait must be replaced even when --skip-portrait is requested.
    if portrait_missing or owner_changed or args.photo or args.refresh_portrait or rest:
        source = ["--photo", args.photo] if args.photo else ([] if args.demo else ["--github-avatar"])
        run("make_ascii_svg.py", *source, *rest)
        cfg["portrait_owner"] = cfg["username"]
        save_config(cfg)
    run("refresh_readme.py")
    print("\n[done] see the assets/ folder")


if __name__ == "__main__":
    main()
