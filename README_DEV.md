# Developer Notes

## Overview

This repository generates a terminal-inspired GitHub profile card as SVG and displays it from `README.md`.

The generator:

1. loads editable profile metadata from `generate.py`
2. reads ASCII art from `assets/ascii.txt`
3. fetches GitHub statistics with the GraphQL API when authentication is available
4. renders both dark and light SVG variants from `templates/profile.svg.j2`
5. writes the final assets to `generated/`

## File Layout

```text
/
├── README.md
├── README_DEV.md
├── generate.py
├── requirements.txt
├── assets/
│   └── ascii.txt
├── generated/
│   ├── profile-dark.svg
│   └── profile-light.svg
├── templates/
│   └── profile.svg.j2
└── .github/
    └── workflows/
        └── update-profile.yml
```

## Editing Profile Information

Update the `PROFILE` object near the top of `/home/runner/work/lairifangtang-hue/lairifangtang-hue/generate.py`.

The default values are placeholders on purpose:

- `name`
- `username`
- `role`
- `location`
- `focus`
- `stack`
- `interests`

Set `username` to your real GitHub username to enable live GitHub stats.

## Replacing ASCII Art

Edit `/home/runner/work/lairifangtang-hue/lairifangtang-hue/assets/ascii.txt`.

Each line is rendered as monospace terminal output on the left side of the card. Keep the artwork reasonably narrow so it fits the sidebar comfortably.

## GitHub API Authentication

The generator reads `GITHUB_TOKEN` from the environment.

- In GitHub Actions, `${{ secrets.GITHUB_TOKEN }}` is enough for the current workflow.
- For local runs, use a personal token if you want live stats.
- If authentication is missing, the generator still succeeds and renders the card with graceful fallback text instead of fake data.

## GitHub Stats Scope

The generator uses the GitHub GraphQL API for:

- owned repository count
- follower count
- total stars across owned, non-fork repositories
- total contributions this calendar year
- commit contribution count this calendar year
- pull request contribution count this calendar year
- issue contribution count this calendar year

The contribution fields are intentionally labeled as year-to-date because GitHub exposes them naturally through `contributionsCollection(from:, to:)`.

## Running Locally

From the repository root:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python generate.py
```

This writes:

- `/home/runner/work/lairifangtang-hue/lairifangtang-hue/generated/profile-dark.svg`
- `/home/runner/work/lairifangtang-hue/lairifangtang-hue/generated/profile-light.svg`

## Automatic Updating

The workflow at `/home/runner/work/lairifangtang-hue/lairifangtang-hue/.github/workflows/update-profile.yml`:

- runs once per day
- supports manual `workflow_dispatch`
- installs Python dependencies
- regenerates the SVG files
- commits only the generated SVG files when they actually changed

It does not create empty commits.

## Visual Customization

Primary customization points:

- `PROFILE` in `generate.py` for content
- `THEMES` in `generate.py` for color and typography tokens
- `Layout` in `generate.py` for sizing and spacing
- `templates/profile.svg.j2` for overall SVG structure

## Troubleshooting

### Stats show as unavailable

Check:

- `PROFILE["username"]` is not the placeholder value
- `GITHUB_TOKEN` is set
- the token has permission to query your profile data

### SVG looks crowded

Reduce the width of long values in `PROFILE`, simplify the ASCII art, or adjust `Layout` dimensions in `generate.py`.

### Workflow runs but nothing updates

If the generated SVG output is identical, the workflow intentionally skips the commit step.

### Local validation fails

Reinstall dependencies with `pip install -r requirements.txt` and rerun `python generate.py`. The script validates both generated SVG XML and workflow YAML during generation.
