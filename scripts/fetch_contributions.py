"""Scrape the public GitHub contribution calendar, no token required.

Output: assets/contributions.json
  {"username": ..., "days": [{"date": "2025-01-01", "count": 3, "level": 2}, ...]}
"""
import argparse
import json
import random
import re
import sys
from datetime import date, timedelta
from pathlib import Path

from bs4 import BeautifulSoup

try:
    from .github_http import get as github_get
except ImportError:  # direct execution: python scripts/fetch_contributions.py
    from github_http import get as github_get

ROOT = Path(__file__).resolve().parent.parent
URL = "https://github.com/users/{user}/contributions"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (profile-art-bot)",
    "X-Requested-With": "XMLHttpRequest",
}


def parse_html(html):
    soup = BeautifulSoup(html, "html.parser")

    # GitHub keeps the count in <tool-tip for="cell-id">N contributions on ...</tool-tip>
    tips = {}
    for tip in soup.find_all("tool-tip"):
        target = tip.get("for")
        if not target:
            continue
        m = re.search(r"([\d,]+|No)\s+contribution", tip.get_text(" ", strip=True))
        if m:
            raw = m.group(1)
            tips[target] = 0 if raw == "No" else int(raw.replace(",", ""))

    days = []
    for td in soup.select("td.ContributionCalendar-day"):
        d = td.get("data-date")
        if not d:
            continue
        level = int(td.get("data-level") or 0)
        count = tips.get(td.get("id"))
        if count is None:
            # fallback: rough estimate from the level when no tooltip is present
            count = [0, 1, 3, 6, 10][min(level, 4)]
        days.append({"date": d, "count": count, "level": level})

    days.sort(key=lambda x: x["date"])
    return days


def demo_days():
    """Sample data so the pipeline can be tested without a real username."""
    rng = random.Random(7)
    today = date.today()
    start = today - timedelta(days=364)
    start -= timedelta(days=(start.weekday() + 1) % 7)  # rewind to Sunday
    out = []
    d = start
    while d <= today:
        weekend = d.weekday() >= 5
        count = max(0, int(rng.gauss(2 if weekend else 6, 4)))
        level = 0 if count == 0 else 1 if count < 3 else 2 if count < 7 else 3 if count < 12 else 4
        out.append({"date": d.isoformat(), "count": count, "level": level})
        d += timedelta(days=1)
    return out


def main():
    cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", default=cfg["username"])
    ap.add_argument("--demo", action="store_true", help="use sample data instead of scraping")
    args = ap.parse_args()

    user = args.user
    days = []

    if args.demo:
        print("[i] demo mode - using sample data")
        days = demo_days()
    else:
        try:
            r = github_get(URL.format(user=user), headers=HEADERS, timeout=20)
            days = parse_html(r.text)
        except Exception as e:  # noqa: BLE001
            print("[!] fetch failed (%s)" % e, file=sys.stderr)

        if not days:
            cached_path = ROOT / "assets" / "contributions.json"
            cached = json.loads(cached_path.read_text(encoding="utf-8")) if cached_path.exists() else {}
            if (cached.get("username", "").casefold() == user.casefold()
                    and cached.get("days") and cached.get("source") != "demo"):
                print("[!] keeping the same owner's last successful calendar", file=sys.stderr)
                return
            raise SystemExit("[x] No calendar for this owner; retry the build (sample data requires --demo)")

    out = ROOT / "assets" / "contributions.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"username": user, "source": "demo" if args.demo else "github", "days": days}, indent=1), encoding="utf-8")
    total = sum(d["count"] for d in days)
    print("[ok] %d days, %d contributions -> %s" % (len(days), total, out))


if __name__ == "__main__":
    main()
