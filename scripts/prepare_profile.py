"""Bind a copied profile to its GitHub repository owner before rendering."""
import copy
import json
import os
import re
import subprocess
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
USERNAME = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?")


def owner_from_remote(remote):
    """Accept GitHub HTTPS, SSH and SCP-style origin URLs."""
    match = re.fullmatch(
        r"(?:https?://github\.com/|ssh://git@github\.com/|git@github\.com:)"
        r"([^/]+)/[^/]+/?", remote.strip(), re.IGNORECASE,
    )
    return match.group(1) if match else None


def resolve_owner(cfg, root=ROOT, environ=None):
    env = os.environ if environ is None else environ
    if not cfg.get("auto_owner", True):
        owner = cfg.get("username", "")
    else:
        # Never use GITHUB_ACTOR: a collaborator can trigger the owner's build.
        owner = env.get("GITHUB_REPOSITORY_OWNER") or env.get("GH_USER")
        if not owner:
            try:
                remote = subprocess.run(
                    ["git", "remote", "get-url", "origin"], cwd=root,
                    capture_output=True, text=True, check=True,
                ).stdout
                owner = owner_from_remote(remote)
            except (OSError, subprocess.CalledProcessError):
                pass
        owner = owner or cfg.get("username", "")
    if not USERNAME.fullmatch(owner):
        raise ValueError("Set a valid GitHub origin, GH_USER, or config.json username")
    return owner


def fetch_profile(owner):
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "profile-art-bot"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = "Bearer " + token
    response = requests.get(
        "https://api.github.com/users/" + owner, headers=headers, timeout=20,
    )
    response.raise_for_status()
    profile = response.json()
    if profile.get("login", "").casefold() != owner.casefold():
        raise ValueError("GitHub returned a different profile owner")
    return profile


def adapt_config(cfg, owner, profile):
    """Keep the visual theme, but never copy another owner's personal claims."""
    adapted = copy.deepcopy(cfg)
    name = " ".join((profile.get("name") or owner).split())
    adapted.update(
        username=owner,
        name=name[:43],
        handle=owner.lower() + "@github",
        profile_title=name + " Profile",
        toolbox=[],
    )
    info = []
    for label, value in (("Location", profile.get("location")), ("Bio", profile.get("bio"))):
        if value:
            value = " ".join(value.split())
            info.append([label, value if len(value) <= 43 else value[:40] + "..."])
    # Split only very long profile URLs so all valid GitHub usernames fit.
    contact = "github.com/" + owner
    info.extend([["Contact", contact]] if len(contact) <= 43 else
                [["Contact", "github.com/"], ["", owner]])
    adapted["info"] = info
    # portrait_owner deliberately stays unchanged until the new SVG is rendered.
    return adapted


def save_config(cfg, root=ROOT):
    (root / "config.json").write_text(
        json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
    )


def prepare_profile(root=ROOT):
    cfg = json.loads((root / "config.json").read_text(encoding="utf-8"))
    owner = resolve_owner(cfg, root)
    if owner.casefold() != cfg.get("username", "").casefold():
        cfg = adapt_config(cfg, owner, fetch_profile(owner))
        save_config(cfg, root)
        print("[ok] profile adapted to repository owner: " + owner)
    return cfg


if __name__ == "__main__":
    prepare_profile()
