# Profile art — how it works

All the motion lives inside the SVG files. GitHub strips `<script>` and almost
all inline CSS from READMEs, but it still renders SVGs embedded via `<img>`,
animations included (CSS keyframes + SMIL). So there are no third-party badge
services here — everything is generated inside this repo.

## 1. Fill in config.json

```json
{
  "username": "yourname",        // used to scrape the contribution calendar
  "name": "Your Name",
  "handle": "you@github",        // the fake shell prompt on each card
  "info": [["Now", "..."], ...], // neofetch card rows, add or remove freely
  "theme": { ... }               // colors
}
```

## 2. Generate

```bash
pip install -r requirements.txt

python build.py                     # everything, portrait falls back to a placeholder
python build.py --photo photo.png   # with a real photo
```

Individual scripts if you want to run one at a time:

| Script | Output |
|---|---|
| `scripts/fetch_contributions.py` | `assets/contributions.json` (scraped, no token needed) |
| `scripts/render_heatmap_svg.py` | `assets/contrib-heatmap.svg` |
| `scripts/make_info_card.py` | `assets/info-card.svg` |
| `scripts/make_ascii_svg.py` | `assets/portrait-ascii.svg` |

Set `STATIC=1` to render a motionless version, useful for thumbnails:

```bash
STATIC=1 python build.py
```

### Regenerating the portrait

The portrait is **not** refreshed by the daily workflow, so rerun it by hand
whenever you change the photo. The command currently in use:

```bash
python scripts/make_ascii_svg.py --photo foto.png --crop "190,385,655,570" --nobg --gamma 1.4
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

## 3. Put it on your profile repo

Your GitHub profile repo is the one named **exactly like your username**
(`yourname/yourname`), public, with a `README.md` at the root.

```bash
git init && git add . && git commit -m "profile art"
git branch -M main
git remote add origin https://github.com/USERNAME/USERNAME.git
git push -u origin main
```

## 4. Daily auto-refresh

`.github/workflows/update-profile-art.yml` runs every day at 06:17 UTC,
regenerates the heatmap and info card, and commits only if something changed.
The ASCII portrait is skipped on purpose — your photo doesn't change daily — so
commit the output of `make_ascii_svg.py` manually.

One repo setting to check once: **Settings → Actions → General → Workflow
permissions → Read and write permissions**, so the bot is allowed to commit.

## Notes on the README

- GitHub strips `style=` attributes in READMEs — use `<br>` for spacing.
- Use `<h3>` instead of `#` to avoid the underline rule.
- Widths are 300 + 560 = 860 so the cards line up with the heatmap.
- SVG animations replay on every image load, they don't loop.
