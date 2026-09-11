"""Audit the owner's public repositories and add newly detected toolbox skills.

  python scripts/audit_skills.py             # scan and update config.json
  python scripts/audit_skills.py --dry-run   # report only

Additions only: listed skills are never moved or removed, and a skill that has
been in the toolbox once stays out after you delete it from config.json.
Forks, empty repositories and the profile repository itself are ignored.
"""
import argparse
import collections
import copy
import fnmatch
import hashlib
import json
import os
import re
import tomllib
from pathlib import Path
from urllib.parse import quote

import requests

try:
    from .github_http import api_headers, get as github_get
    from .prepare_profile import save_config
    from .tech_icons import CATALOG, CATEGORIES
except ImportError:  # direct execution: python scripts/audit_skills.py
    from github_http import api_headers, get as github_get
    from prepare_profile import save_config
    from tech_icons import CATALOG, CATEGORIES

ROOT = Path(__file__).resolve().parent.parent
API = "https://api.github.com"
STATE_FILE = Path("assets") / "skills-audit.json"
MAX_REPOS = 100
MAX_FILES_PER_REPO = 30
MAX_FILE_BYTES = 512 * 1024
SKIP_DIRS = {"node_modules", "bower_components", "vendor", "third_party", ".venv", "venv",
             "site-packages", "__pycache__", "dist", "build", ".next"}
NPM_MANIFESTS = ("package.json",)
PYPI_MANIFESTS = ("requirements*.txt", "requirements*.in", "pyproject.toml", "Pipfile",
                  "environment.yml", "environment.yaml")
DEFAULTS = {"enabled": True, "min_repos": 1, "min_language_share": 0.05,
            "max_per_group": 14, "exclude_repos": []}
REQUIREMENT = re.compile(r"\s*([A-Za-z0-9][A-Za-z0-9._-]*)")


def settings(cfg):
    options = dict(DEFAULTS)
    options.update(cfg.get("skill_audit") or {})
    return options


def catalog_digest(min_share, catalog=CATALOG):
    # Changing detection rules invalidates every cached repository result.
    rules = json.dumps([catalog, min_share], sort_keys=True)
    return hashlib.sha256(rules.encode("utf-8")).hexdigest()[:16]


def path_matches(path, pattern):
    """Match basename patterns anywhere; patterns with a slash match a path suffix."""
    if "/" in pattern:
        return fnmatch.fnmatchcase(path, pattern) or fnmatch.fnmatchcase(path, "*/" + pattern)
    return fnmatch.fnmatchcase(path.rsplit("/", 1)[-1], pattern)


def normalize_pypi(name):
    return re.sub(r"[-_.]+", "-", name).lower()


def requirement_name(spec):
    match = REQUIREMENT.match(spec) if isinstance(spec, str) else None
    return normalize_pypi(match.group(1)) if match else None


def npm_packages(text):
    try:
        data = json.loads(text)
    except ValueError:
        return set()
    names = set()
    for key in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"):
        section = data.get(key) if isinstance(data, dict) else None
        if isinstance(section, dict):
            names.update(name.lower() for name in section)
    return names


def _table(value):
    return value if isinstance(value, dict) else {}


def pypi_packages(path, text):
    name = path.rsplit("/", 1)[-1]
    specs, names = [], set()
    if name in ("pyproject.toml", "Pipfile"):
        try:
            data = tomllib.loads(text)
        except tomllib.TOMLDecodeError:
            return set()
        if name == "Pipfile":
            for key in ("packages", "dev-packages"):
                names.update(_table(data.get(key)))
        else:
            project = _table(data.get("project"))
            groups = list(_table(project.get("optional-dependencies")).values())
            groups += list(_table(data.get("dependency-groups")).values())
            specs = list(project.get("dependencies") or [])
            for group in groups:
                specs.extend(group if isinstance(group, list) else [])
            poetry = _table(_table(data.get("tool")).get("poetry"))
            tables = [poetry.get("dependencies"), poetry.get("dev-dependencies")]
            tables += [_table(group).get("dependencies") for group in _table(poetry.get("group")).values()]
            for table in tables:
                names.update(_table(table))
    elif name.startswith("environment."):
        specs = [line.split("-", 1)[1] for line in text.splitlines() if line.strip().startswith("-")]
    else:
        for line in text.splitlines():
            line = line.split("#", 1)[0].strip()
            if line and not line.startswith("-"):
                specs.append(line)
    names = {normalize_pypi(name) for name in names}
    names.update(filter(None, map(requirement_name, specs)))
    return names


def wanted_files(paths, catalog=CATALOG):
    """Dependency manifests and rule files worth downloading, shallowest first."""
    patterns = set(NPM_MANIFESTS + PYPI_MANIFESTS)
    for entry in catalog.values():
        for rule in entry["detect"].get("contains", []):
            patterns.update(rule["files"])
    selected = [path for path in paths if any(path_matches(path, pattern) for pattern in patterns)]
    return sorted(selected, key=lambda path: (path.count("/"), path))[:MAX_FILES_PER_REPO]


def detect_repo(languages, paths, read_file, catalog=CATALOG, min_share=DEFAULTS["min_language_share"]):
    """Return (skills, languages without an icon) for one repository."""
    total = sum(languages.values())
    used = {name for name, size in languages.items() if total and size / total >= min_share}
    texts = {}
    for path in wanted_files(paths, catalog):
        text = read_file(path)
        if text is not None:
            texts[path] = text
    npm, pypi = set(), set()
    for path, text in texts.items():
        if any(path_matches(path, pattern) for pattern in NPM_MANIFESTS):
            npm |= npm_packages(text)
        elif any(path_matches(path, pattern) for pattern in PYPI_MANIFESTS):
            pypi |= pypi_packages(path, text)
    basenames = {path.rsplit("/", 1)[-1] for path in paths}

    def has_file(pattern):
        if "/" in pattern:
            return any(path_matches(path, pattern) for path in paths)
        return bool(fnmatch.filter(basenames, pattern))

    def contains(rule):
        return any(re.search(rule["pattern"], text) for path, text in texts.items()
                   if any(path_matches(path, pattern) for pattern in rule["files"]))

    skills, known = set(), set()
    for slug, entry in catalog.items():
        rules = entry["detect"]
        known.update(rules.get("languages", []))
        if (used & set(rules.get("languages", []))
                or npm & set(rules.get("npm", []))
                or pypi & {normalize_pypi(name) for name in rules.get("pypi", [])}
                or any(has_file(pattern) for pattern in rules.get("files", []))
                or any(contains(rule) for rule in rules.get("contains", []))):
            skills.add(slug)
    return skills, used - known


def list_repos(owner, get=github_get):
    repos, page = [], 1
    while len(repos) < MAX_REPOS:
        batch = get("%s/users/%s/repos?type=owner&sort=pushed&per_page=100&page=%d"
                    % (API, quote(owner), page), headers=api_headers(), timeout=20).json()
        repos.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    return repos[:MAX_REPOS]


def scan_repo(repo, get=github_get, min_share=DEFAULTS["min_language_share"]):
    base = API + "/repos/" + repo["full_name"]
    languages = get(base + "/languages", headers=api_headers(), timeout=20).json()
    try:
        tree = get("%s/git/trees/%s?recursive=1" % (base, quote(repo["default_branch"])),
                   headers=api_headers(), timeout=30).json()
    except requests.HTTPError as error:
        if error.response is None or error.response.status_code not in (404, 409):
            raise
        tree = {}  # empty repository or missing default branch
    blobs = {item["path"]: item for item in tree.get("tree", [])
             if item.get("type") == "blob" and not SKIP_DIRS.intersection(item["path"].split("/")[:-1])}

    def read_file(path):
        if blobs[path].get("size", 0) > MAX_FILE_BYTES:
            return None
        # Rate limits and outages propagate so a partial scan is never cached.
        response = get(base + "/git/blobs/" + blobs[path]["sha"],
                       headers=api_headers("application/vnd.github.raw+json"), timeout=20)
        return response.content.decode("utf-8", "replace")

    return detect_repo(languages, list(blobs), read_file, min_share=min_share)


def merge_toolbox(cfg, counts, known, options):
    """Append detected skills that are neither listed nor previously known."""
    toolbox = cfg.setdefault("toolbox", [])
    listed = {slug for group in toolbox for slug in group.get("items", [])}
    order = list(CATALOG)
    candidates = sorted(
        (slug for slug, count in counts.items()
         if slug in CATALOG and count >= options["min_repos"] and slug not in listed | known),
        key=lambda slug: (-counts[slug], order.index(slug)),
    )

    def rank(label):
        folded = [category.casefold() for category in CATEGORIES]
        return folded.index(label.casefold()) if label.casefold() in folded else None

    def group_for(label):
        for group in toolbox:
            if group.get("label", "").casefold() == label.casefold():
                return group
        # Missing standard groups keep the Languages, Frameworks, Data, Tools order.
        earlier = [index for index, group in enumerate(toolbox)
                   if rank(group.get("label", "")) is not None and rank(group["label"]) < rank(label)]
        group = {"label": label, "items": []}
        toolbox.insert(earlier[-1] + 1 if earlier else 0, group)
        return group

    added = []
    for slug in candidates:
        group = group_for(CATALOG[slug]["category"])
        if len(group["items"]) < options["max_per_group"]:
            group["items"].append(slug)
            added.append(slug)
    return added


def load_state(path, owner):
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        state = {}
    if state.get("owner", "").casefold() != owner.casefold():
        state = {}  # a copied repository must not inherit the previous owner's audit
    return state


def audit_skills(cfg, root=ROOT, get=github_get, environ=None, dry_run=False):
    """Scan public repositories and return the config with new skills appended."""
    options = settings(cfg)
    if not options["enabled"]:
        return cfg
    env = os.environ if environ is None else environ
    owner = cfg["username"]
    state_path = root / STATE_FILE
    state = load_state(state_path, owner)
    digest = catalog_digest(options["min_language_share"])
    cache = state.get("repos", {}) if state.get("catalog") == digest else {}
    try:
        repos = list_repos(owner, get)
    except requests.RequestException as error:
        print("[warn] skill audit skipped: %s" % error)
        return cfg

    excluded = {owner.casefold(), env.get("GITHUB_REPOSITORY", "").rpartition("/")[2].casefold()}
    excluded.update(name.casefold() for name in options["exclude_repos"])
    scanned = {}
    for repo in repos:
        name = repo["name"]
        if repo.get("fork") or not repo.get("size") or name.casefold() in excluded:
            continue
        cached = cache.get(name)
        if cached and cached.get("pushed_at") == repo.get("pushed_at"):
            scanned[name] = cached
            continue
        try:
            skills, unmatched = scan_repo(repo, get, options["min_language_share"])
        except requests.RequestException as error:
            print("[warn] skill audit could not scan %s: %s" % (name, error))
            if cached:
                scanned[name] = cached
            continue
        scanned[name] = {"pushed_at": repo.get("pushed_at"), "skills": sorted(skills),
                         "languages_without_icon": sorted(unmatched)}

    counts = collections.Counter(slug for entry in scanned.values() for slug in entry["skills"])
    listed = {slug for group in cfg.get("toolbox", []) for slug in group.get("items", [])}
    known = set(state.get("known", [])) | listed
    updated = copy.deepcopy(cfg)
    added = merge_toolbox(updated, counts, known, options)
    unmatched = sorted({lang for entry in scanned.values() for lang in entry["languages_without_icon"]})
    print("[ok] skill audit scanned %d public repositories; detected: %s"
          % (len(scanned), ", ".join(sorted(counts)) or "nothing"))
    if unmatched:
        print("[info] languages without a catalog icon: " + ", ".join(unmatched))
    if dry_run:
        print("[dry-run] would add: " + (", ".join(added) or "nothing"))
        return cfg

    new_state = {"owner": owner, "catalog": digest, "known": sorted(known | set(added)),
                 "repos": dict(sorted(scanned.items()))}
    text = json.dumps(new_state, ensure_ascii=False, indent=2) + "\n"
    if not state_path.exists() or state_path.read_text(encoding="utf-8") != text:
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(text, encoding="utf-8")
    if added:
        save_config(updated, root)
        print("[ok] skill audit added: " + ", ".join(added))
    return updated


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true", help="report without writing files")
    args = parser.parse_args()
    cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    audit_skills(cfg, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
