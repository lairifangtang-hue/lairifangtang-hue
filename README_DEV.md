# Profile README generator

This repository renders a terminal-style GitHub profile card as SVG and embeds it in the public `README.md`.

## How it works

1. `generate.py` loads editable profile metadata from the `PROFILE` object near the top of the file.
2. It reads ASCII art from `assets/ascii.txt`.
3. It optionally fetches GitHub profile statistics from the GitHub GraphQL API.
4. It renders `templates/profile.svg.j2` into:
   - `generated/profile-dark.svg`
   - `generated/profile-light.svg`
5. The public `README.md` displays the correct theme automatically with a `<picture>` element.

## Edit profile information

Update the `PROFILE` object in `/home/runner/work/lairifangtang-hue/lairifangtang-hue/generate.py`:

- `name`
- `username`
- `role`
- `location`
- `focus`
- `stack`
- `interests`

You can keep placeholder values while iterating on the design.

## Replace the ASCII art

Edit `/home/runner/work/lairifangtang-hue/lairifangtang-hue/assets/ascii.txt`.

The generator reads the file as plain text, so you can swap in any monospace-friendly mark without touching the SVG template.

## GitHub API authentication

The generator uses the GitHub GraphQL API and expects:

- `GITHUB_TOKEN`

If `PROFILE["username"]` is still set to `YOUR_GITHUB_USERNAME`, the script also falls back to `GITHUB_REPOSITORY_OWNER` when available, which is useful inside GitHub Actions.

If authentication or a usable username is unavailable, generation still succeeds. The SVG is rendered with `unavailable` placeholders instead of fake statistics.

### Current data model

The GitHub statistics section currently includes:

- owned public non-fork repository count
- follower count
- total stars across owned public non-fork repositories
- contribution count for the current calendar year
- commit contribution count for the current calendar year
- pull request contribution count for the current calendar year
- issue contribution count for the current calendar year

Private or otherwise unavailable values are intentionally not guessed.

## Run locally

From the repository root:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export GITHUB_TOKEN=YOUR_TOKEN
python generate.py
```

If you do not set `GITHUB_TOKEN`, the script still runs and produces SVG files with placeholder `unavailable` GitHub stats.

## Automatic updates

`.github/workflows/update-profile.yml` runs:

- once per day on a cron schedule
- manually with `workflow_dispatch`

The workflow regenerates the SVG files and commits only the files in `generated/` when they change.

## Customize the visual layout

Adjust the following files:

- `generate.py` for layout constants, line wrapping, and theme tokens
- `templates/profile.svg.j2` for SVG structure and positioning
- `assets/ascii.txt` for the left-column art

## Troubleshooting

### The SVG shows `unavailable`

- verify `PROFILE["username"]` is correct, or set `GITHUB_REPOSITORY_OWNER`
- verify `GITHUB_TOKEN` is present
- check that the token can access the GraphQL API

### The layout feels cramped

- reduce the length of configured profile values
- adjust `LABEL_WIDTH`, `VALUE_WIDTH`, or `SVG_DIMENSIONS` in `generate.py`

### Workflow ran but nothing changed

That usually means the rendered SVG output was identical, so the workflow correctly skipped creating an empty commit.
