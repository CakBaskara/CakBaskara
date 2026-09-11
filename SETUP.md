# Profile art — how it works

All the motion lives inside the SVG files. GitHub strips `<script>` and almost
all inline CSS from READMEs, but it still renders SVGs embedded via `<img>`,
animations included (CSS keyframes + SMIL). So there are no third-party badge
services here — everything is generated inside this repo.

## 1. Reuse for your GitHub account

Create a public repository from this template named **exactly like your GitHub
username**, or fork/copy it into that repository. Open **Actions → update profile
art → Run workflow** to initialize it immediately. GitHub disables workflows in
forks by default, so enable Actions first when using a fork. A push to the default
branch also builds the profile; the workflow does not assume the branch is `main`.

With `auto_owner: true` (the default), `python build.py` detects the owner from
`GITHUB_REPOSITORY_OWNER` in Actions, then `GH_USER` for a local override, then the
GitHub `origin` remote, then `config.json`. It never uses the account that clicked
Run workflow. No personal access token or per-owner code changes are needed.

On the first build for a different owner, the public GitHub name, location, bio,
contact link, avatar and contribution calendar replace the previous owner's
content. The README heading changes too. The theme stays the same, but inherited
toolbox skills are cleared: add your own in `config.json`. Later builds preserve
your customized text, toolbox and portrait. Profile fields are imported once,
when ownership changes, rather than overwriting your edits every day.

The new avatar replaces the inherited portrait even with `--skip-portrait`.
Public profile/avatar fetch failures fail the build so it can be retried. A
calendar fetch failure can keep a previous calendar only for the same owner;
sample contributions are generated only with explicit `--demo`.

For a fixed profile hosted under someone else's repository, set `auto_owner` to
`false` and fill in `username` manually. When cloning locally, point `origin` at
your own GitHub repository before building.

GitHub setup reference: [enabling workflows on a fork](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#workflows-in-forked-repositories).

## 2. Customize config.json

```json
{
  "auto_owner": true,             // follow the repository owner
  "username": "yourname",        // used to scrape the contribution calendar
  "portrait_owner": "yourname",  // updated after rendering the portrait
  "profile_title": "Your Name Profile",
  "name": "Your Name",
  "handle": "you@github",        // name used in the fake shell prompt
  "show_prompt": false,          // draw those prompt lines at all
  "info": [["Now", "..."], ...], // neofetch card rows, add or remove freely
  "toolbox": [
    {"label": "Languages", "items": ["python", "typescript"]},
    {"label": "Tools", "items": ["git", "githubactions", "docker"]}
  ],
  "theme": { ... }               // colors
}
```

Supported toolbox slugs are `python`, `c`, `cplusplus`, `typescript`,
`javascript`, `nextdotjs`, `react`, `numpy`, `pandas`, `postgresql`, `git`,
`githubactions`, `docker`, `n8n`, and `gnubash`. Unknown slugs fail the build instead of drawing a
misleading fallback icon.

### The fake shell prompts

`show_prompt` controls every simulated terminal line at once — the header on
each of the three cards plus the blinking cursor at the bottom of the info
card. Set it to `true` and they all come back; the cards reflow to make room,
so nothing overlaps either way.

The centered title between the `profile-title` markers in `README.md` is generated
from `profile_title`; edit that config field to change it. It uses ordinary bold
text, not a heading, so GitHub does not add a clickable heading permalink.
The cards and toolbox between the `profile-body` markers are generated too;
edit `config.json` rather than that HTML. Content outside these markers is preserved.

## 3. Generate

Use Python 3.11 or newer.

```bash
pip install -r requirements.txt

python build.py                     # adapt owner, refresh cards, preserve existing portrait
python build.py --photo photo.png   # with a real photo
python build.py --refresh-portrait  # regenerate from your public GitHub avatar
```

Individual scripts if you want to run one at a time:

| Script | Output |
|---|---|
| `scripts/fetch_contributions.py` | `assets/contributions.json` (scraped, no token needed) |
| `scripts/render_heatmap_svg.py` | `assets/contrib-heatmap.svg` |
| `scripts/make_info_card.py` | `assets/info-card.svg`, `assets/info-summary.svg`, `assets/toolbox/*.svg` |
| `scripts/make_ascii_svg.py` | `assets/portrait-ascii.svg` |
| `scripts/prepare_profile.py` | owner-specific `config.json` (run by `build.py`) |
| `scripts/refresh_readme.py` | README title, non-linked pictures, icon tooltips, and cache versions (run by `build.py`) |

Use `build.py` for complete owner adaptation. After running an individual renderer,
run `python scripts/refresh_readme.py` to refresh README image versions. Each SVG
URL includes a hash of its contents; only changed images receive a new URL. This
avoids reusing the old image cache without routinely purging GitHub's shared cache.

For verification, install `pip install -r requirements-dev.txt` and run
`python -m unittest discover -s tests -v`. This checks owner adaptation, pinned
logo source integrity, and actual SVG rendering bounds for every icon.

All toolbox logos are vendored SVGs from one pinned Simple Icons revision in
`scripts/icons/`; normal builds need no icon download or font-symbol substitution.
The README uses a separate `<picture><img ...></picture>` for every image: GitHub's
README renderer leaves these unlinked instead of auto-linking bare `<img>` tags.
Each toolbox image has its own `title` (native hover tooltip) and `alt` (accessible
name), such as `Python` or `GitHub Actions`. Tooltips require a hover-capable device;
touchscreens do not reliably show native title tooltips. This prevents navigation
on a normal click, but does not prevent saving images or using the browser's context menu.
README badges display at 34 px, using the same vector geometry as the combined
card. Each badge fades and slides in once, staggered after the description rows;
`STATIC=1` and the device's reduced-motion preference disable badge animation.
The portrait is centered vertically beside the description and toolbox, with
35% / 65% column proportions. ASCII rows have an explicit SVG text length so
font fallback cannot shrink the text grid toward one side of the frame.
The combined `info-card.svg` remains available as a standalone card;
one flattened SVG or PNG embedded as an image cannot provide separate icon tooltips.

Run `python scripts/preview_icons.py` after rendering the card to inspect the
ignored local previews `preview-icons.png` and `preview-info-card.png`.
The same command also writes `preview-portrait.png` with the type-in animation
fully revealed. These raster previews check SVG geometry, not GitHub's HTML layout.

Set `STATIC=1` to render a motionless version, useful for thumbnails:

```bash
STATIC=1 python build.py
```

### Export the profile as an HD PNG

After installing `requirements-dev.txt`, run `python scripts/export_profile_png.py`.
This updates `exports/<username>-profile-HD.png` at 3840 pixels wide, using the
current `info-summary.svg`, individually sized toolbox SVGs, centered portrait,
and contribution heatmap. The height adapts to the description and toolbox;
the old combined `info-card.svg` is not used for this export.

The PNG is a fixed-width static composition, not a browser screenshot or an
animated/interactive image. All entry animations are resolved to their final frame.
Use `--width 7680` for a larger export or `--output path.png` to choose another file.
Run the export again after profile changes; the daily workflow does not regenerate PNGs.

### Regenerating the portrait

To center the existing ASCII character grid without replacing the portrait or
reprocessing its source photo, run `python scripts/make_ascii_svg.py --reflow-existing`,
then `python scripts/refresh_readme.py` to update its cache version.

The portrait is **not** refreshed by the daily workflow, so rerun it by hand
whenever you change the photo. The command currently in use:

```bash
python scripts/make_ascii_svg.py --photo foto.png --crop "235,385,560,750" --nobg --gamma 1.4
```

The source photo is deliberately kept out of the repo (see `.gitignore`) — only
the ASCII result is public.

| Option | What it does |
|---|---|
| `--crop "x,y,w,h"` | Crop to head and shoulders. This matters more than anything else. |
| `--gamma` | Below 1.0 cleans up the background but washes out the face; above 1.0 does the reverse. |
| `--nobg` | Cut the background out before converting. The single biggest win on a busy photo. |
| `--vignette N` | 0-1, fades the background out behind a centred oval. Cheap stand-in when `rembg` is unavailable. |
| `--invert` | For photos shot against a dark background. |
| `--cols` | Character columns; more means finer detail. |
| `--preview` | Print the ASCII to the terminal so you can check it without opening a browser. |

The workflow: run with `--preview`, look at it in the terminal, adjust `--crop`
and `--gamma` until it reads well, then commit.

ASCII art has only brightness to work with, so a textured background lands in
the same character range as hair and reads as noise. `--nobg` solves this
properly — it needs two extra packages that aren't in `requirements.txt`
because they're large:

```bash
pip install rembg onnxruntime
```

The first run downloads a ~176 MB model to `~/.u2net/` and caches it. With the
background gone, the face loses internal contrast, so pair it with a gamma
around 1.4 — below 1.2 the face goes flat, above 1.6 it turns into a dark blob.

## 4. Put it on your profile repo

Your GitHub profile repo is the one named **exactly like your username**
(`yourname/yourname`), public, with a `README.md` at the root.

```bash
git init && git add . && git commit -m "profile art"
git branch -M main
git remote add origin https://github.com/USERNAME/USERNAME.git
git push -u origin main
```

## 5. Daily auto-refresh

`.github/workflows/update-profile-art.yml` runs every day at 06:17 UTC,
regenerates the heatmap and info card, updates README image versions, and commits
only if something changed. Owner adaptation and an initial avatar conversion run
automatically for copies. The existing owner's custom portrait is preserved.
Automated commits use the repository owner as both author and committer, with a
GitHub noreply email. Commit messages contain only the subject, with no body or
`Co-authored-by` trailer.

The workflow grants only `contents: write` to its `GITHUB_TOKEN`; personal
repositories need no broader default permission. An organization policy can
still forbid write tokens, in which case an organization administrator must
allow this workflow to commit generated assets.

Scheduled copies wait for a short repository-specific delay before fetching,
and temporary GitHub or rate-limit responses are retried with bounded backoff.

Template copies start independent histories. Dependabot keeps Python packages
and workflow Actions current, but rendering-script improvements are not copied
automatically. Review newer template commits before updating an existing copy.

## Notes on the README

- GitHub strips `style=` attributes in READMEs — use `<br>` for spacing.
- The profile title is bold text without a heading permalink.
- Widths are 300 + 560 = 860 so the cards line up with the heatmap.
- SVG animations replay on every image load, they don't loop.
