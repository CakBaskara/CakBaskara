"""Bangun ulang semua aset SVG sekaligus.

  python build.py                 # pakai username dari config.json
  python build.py --photo me.jpg  # sekalian regenerate potret dari foto
"""
import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def run(script, *extra):
    cmd = [sys.executable, str(ROOT / "scripts" / script), *extra]
    print("$", " ".join(cmd[1:]))
    if subprocess.call(cmd) != 0:
        sys.exit("[x] gagal di %s" % script)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--photo")
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--skip-portrait", action="store_true")
    args, rest = ap.parse_known_args()

    run("fetch_contributions.py", *(["--demo"] if args.demo else []))
    run("render_heatmap_svg.py")
    run("make_info_card.py")
    if not args.skip_portrait:
        run("make_ascii_svg.py", *(["--photo", args.photo] if args.photo else []), *rest)
    print("\n[selesai] cek folder assets/")


if __name__ == "__main__":
    main()
