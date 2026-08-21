#!/usr/bin/env python3
"""Generate the profile SVGs and update README anchors.

Pipeline: fetch -> normalize -> model -> layout -> render -> atomic write.

Failure policy (Step 28/29 of the spec): any failure — network, rate limit,
malformed JSON, invalid config — aborts before anything is written. Previous
SVGs are always preserved; empty data never overwrites a good card.

Usage:
    python scripts/generate_profile.py            # fetch live data
    python scripts/generate_profile.py --offline fixtures.json
    python scripts/generate_profile.py --check    # validate existing SVGs
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import pathlib
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import github as gh          # noqa: E402
from src import layout as layout_mod  # noqa: E402
from src import normalize             # noqa: E402
from src import render as render_mod  # noqa: E402
from src.config import ConfigError, ProfileConfig  # noqa: E402
from src.models import ProfileData    # noqa: E402

CONFIG_PATH = ROOT / "profile.config.yml"
ASSETS_DIR = ROOT / "assets" / "generated"
DARK_PATH = ASSETS_DIR / "profile-dark.svg"
LIGHT_PATH = ASSETS_DIR / "profile-light.svg"
MAX_SVG_BYTES = 120_000
MIN_SVG_BYTES = 2_000
REQUIRED_MARKERS = ("<svg", "</svg>", "IDENTITY", "SIGNAL", "NOW")


class GenerationError(RuntimeError):
    pass


# ----------------------------------------------------------------- fetch
def fetch_live(client: gh.Client, login: str):
    user = client.user(login)
    repos = client.repos(login)
    owned = [r for r in repos if not r.get("fork") and not r.get("archived")]
    langs_by_repo = {}
    for r in owned:
        try:
            langs_by_repo[r["name"]] = client.languages(login, r["name"])
        except gh.GitHubError:
            langs_by_repo[r["name"]] = {}
    events = client.events(login)
    return user, repos, langs_by_repo, events


def fetch_offline(path: pathlib.Path):
    payload = json.loads(path.read_text(encoding="utf-8"))
    return (
        payload["user"],
        payload["repos"],
        payload.get("languages", {}),
        payload.get("events", []),
    )


# ---------------------------------------------------------------- render
def build_svgs(cfg: ProfileConfig, data: ProfileData, now: dt.datetime):
    languages_text = " · ".join(data.languages[: cfg.languages.max]) or None
    signal_text = None
    if data.signal and data.signal.repo:
        rel = normalize.relative_time(data.signal.at, now)
        signal_text = f"{data.signal.repo} · {rel}" if rel else data.signal.repo
    generated_text = now.strftime("%Y-%m-%d")

    layout = layout_mod.lay_out(
        cfg,
        data,
        signal_text=signal_text,
        generated_text=generated_text,
        languages_text=languages_text,
    )
    alt = (
        f"Terminal-style profile summary for {cfg.identity.handle or data.handle}: "
        "role, focus, current work and recent activity."
    )
    dark = render_mod.render_dark(layout, cfg.identity.handle or data.handle, alt=alt)
    light = render_mod.render_light(layout, cfg.identity.handle or data.handle, alt=alt)
    return dark, light


# ------------------------------------------------------------- validate
def validate_svg(text: str, what: str) -> None:
    import xml.etree.ElementTree as ET

    if not text or len(text) < MIN_SVG_BYTES:
        raise GenerationError(f"{what}: output suspiciously small ({len(text)} bytes)")
    if len(text) > MAX_SVG_BYTES:
        raise GenerationError(f"{what}: output too large ({len(text)} bytes)")
    for marker in REQUIRED_MARKERS:
        if marker not in text:
            raise GenerationError(f"{what}: required marker {marker!r} missing")
    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        raise GenerationError(f"{what}: invalid XML: {exc}") from None
    if root.tag != "{http://www.w3.org/2000/svg}svg":
        raise GenerationError(f"{what}: root element is not <svg>")
    # sanitizer compatibility: presentation attributes only
    banned = ("<script", "<foreignObject", "javascript:", "xlink:href", "@import")
    lowered = text.lower()
    for bad in banned:
        if bad.lower() in lowered:
            raise GenerationError(f"{what}: banned construct {bad!r} present")


# ----------------------------------------------------------------- write
def atomic_write(path: pathlib.Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        dir=str(path.parent), prefix=path.name + ".", suffix=".tmp"
    )
    tmp = pathlib.Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()


def replace_between(text: str, start: str, end: str, replacement: str) -> str:
    i = text.find(start)
    if i < 0:
        raise GenerationError(f"anchor {start!r} not found in README")
    j = text.find(end, i + len(start))
    if j < 0:
        raise GenerationError(f"anchor {end!r} not found in README")
    return text[:i] + start + replacement + text[j:]


def update_readme(dark_rel: str, light_rel: str) -> None:
    readme = ROOT / "README.md"
    text = readme.read_text(encoding="utf-8")
    block = (
        "\n"
        "<picture>\n"
        '  <source media="(prefers-color-scheme: dark)" srcset="./assets/generated/profile-dark.svg">\n'
        '  <img src="./assets/generated/profile-light.svg" alt="GitHub profile card" width="736">\n'
        "</picture>\n"
    )
    new = replace_between(text, "<!-- profile:svg:start -->", "<!-- profile:svg:end -->", block)
    readme.write_text(new, encoding="utf-8", newline="\n")


# ------------------------------------------------------------------ main
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--offline", type=pathlib.Path, default=None,
                    help="use a JSON fixture instead of the live API")
    ap.add_argument("--check", action="store_true",
                    help="validate already-generated SVGs and exit")
    args = ap.parse_args(argv)

    if args.check:
        for path, what in ((DARK_PATH, "dark"), (LIGHT_PATH, "light")):
            try:
                validate_svg(path.read_text(encoding="utf-8"), what)
            except FileNotFoundError:
                print(f"FAIL {what}: {path} missing")
                return 1
        print("OK: both SVGs valid")
        return 0

    now = dt.datetime.now(dt.timezone.utc)

    try:
        cfg = ProfileConfig.load(CONFIG_PATH)
    except ConfigError as exc:
        print(f"config error: {exc}", file=sys.stderr)
        return 1

    login = cfg.identity.login
    if not login:
        print("config error: identity.login is required", file=sys.stderr)
        return 1

    try:
        if args.offline:
            user, repos, langs, events = fetch_offline(args.offline)
        else:
            client = gh.Client()
            user, repos, langs, events = fetch_live(client, login)
        data = normalize.build_profile_data(
            login=login,
            user_payload=user,
            repo_payloads=repos,
            languages_by_repo=langs,
            event_payloads=events,
            cfg=cfg,
            now=now,
        )
        if not data.repos:
            raise GenerationError("no repositories returned — refusing to render")
        dark, light = build_svgs(cfg, data, now)
        validate_svg(dark, "dark")
        validate_svg(light, "light")
    except (gh.GitHubError, GenerationError) as exc:
        print(f"generation failed: {exc}", file=sys.stderr)
        print("previous SVGs left untouched", file=sys.stderr)
        return 1

    atomic_write(DARK_PATH, dark)
    atomic_write(LIGHT_PATH, light)
    update_readme(str(DARK_PATH), str(LIGHT_PATH))
    print(f"generated {DARK_PATH.relative_to(ROOT)} and {LIGHT_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
