from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from html import escape
import json
import os
from pathlib import Path
from textwrap import wrap
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

import yaml
from jinja2 import Environment, FileSystemLoader, select_autoescape


ROOT = Path(__file__).resolve().parent
TEMPLATES_DIR = ROOT / "templates"
GENERATED_DIR = ROOT / "generated"
ASCII_PATH = ROOT / "assets" / "ascii.txt"
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "update-profile.yml"

PROFILE = {
    "name": "Your Name",
    "username": "YOUR_GITHUB_USERNAME",
    "role": "Software / AI Engineer",
    "location": "Singapore",
    "focus": ["AI Agents", "Machine Learning", "Graph Learning"],
    "stack": ["Python", "TypeScript", "PyTorch", "Next.js"],
    "interests": ["World Models", "Agents", "Robotics"],
}

THEMES = {
    "dark": {
        "canvas": "#0d1117",
        "panel": "#161b22",
        "panel_glow_start": "#1f29371a",
        "panel_glow_end": "#11182700",
        "glow_opacity": "1",
        "border": "#30363d",
        "sidebar": "#0f141b",
        "sidebar_border": "#21262d",
        "foreground": "#e6edf3",
        "muted": "#8b949e",
        "accent": "#7d8590",
        "label": "#8b949e",
        "separator": "#30363d",
        "dot_red": "#ff7b72",
        "dot_yellow": "#d29922",
        "dot_green": "#3fb950",
        "font_family": "ui-monospace, SFMono-Regular, SFMono-Regular, Menlo, Consolas, Liberation Mono, monospace",
    },
    "light": {
        "canvas": "#f6f8fa",
        "panel": "#ffffff",
        "panel_glow_start": "#d0d7de22",
        "panel_glow_end": "#ffffff00",
        "glow_opacity": "1",
        "border": "#d0d7de",
        "sidebar": "#f6f8fa",
        "sidebar_border": "#d8dee4",
        "foreground": "#1f2328",
        "muted": "#59636e",
        "accent": "#57606a",
        "label": "#59636e",
        "separator": "#d8dee4",
        "dot_red": "#cf222e",
        "dot_yellow": "#9a6700",
        "dot_green": "#1a7f37",
        "font_family": "ui-monospace, SFMono-Regular, SFMono-Regular, Menlo, Consolas, Liberation Mono, monospace",
    },
}


@dataclass(frozen=True)
class Layout:
    width: int = 1080
    height: int = 780
    outer_margin: int = 28
    left_width: int = 250
    gap: int = 34
    content_top: int = 80
    content_height: int = 644
    ascii_font_size: int = 22
    ascii_line_height: int = 28

    @property
    def inner_width(self) -> int:
        return self.width - self.outer_margin * 2

    @property
    def inner_height(self) -> int:
        return self.height - self.outer_margin * 2

    @property
    def left_x(self) -> int:
        return self.outer_margin + 28

    @property
    def right_x(self) -> int:
        return self.left_x + self.left_width + self.gap


def join_items(values: list[str]) -> str:
    return " · ".join(value.strip() for value in values if value.strip()) or "—"


def is_placeholder_username(username: str) -> bool:
    normalized = username.strip().upper()
    return not normalized or normalized == "YOUR_GITHUB_USERNAME"


def github_graphql_request(query: str, variables: dict[str, Any], token: str) -> dict[str, Any]:
    body = json.dumps({"query": query, "variables": variables}).encode("utf-8")
    request = Request(
        "https://api.github.com/graphql",
        data=body,
        headers={
            "Authorization": "Bearer " + token,
            "Content-Type": "application/json",
            "Accept": "application/vnd.github+json",
            "User-Agent": "profile-readme-generator",
        },
        method="POST",
    )

    with urlopen(request, timeout=30) as response:
        payload = json.load(response)

    if "errors" in payload:
        messages = "; ".join(error.get("message", "Unknown GraphQL error") for error in payload["errors"])
        raise RuntimeError(messages)

    return payload["data"]


def fetch_github_stats(username: str, token: str | None) -> dict[str, str]:
    unavailable = {
        "repository_count": "Unavailable",
        "followers": "Unavailable",
        "stars": "Unavailable",
        "contributions": "Unavailable",
        "commit_contributions": "Unavailable",
        "pull_request_contributions": "Unavailable",
        "issue_contributions": "Unavailable",
        "scope": "Set PROFILE['username'] and GITHUB_TOKEN",
    }

    if is_placeholder_username(username):
        unavailable["scope"] = "Set PROFILE['username'] to enable live stats"
        return unavailable

    if not token:
        unavailable["scope"] = "GITHUB_TOKEN missing; rendered without live stats"
        return unavailable

    repo_query = """
    query($login: String!, $after: String) {
      user(login: $login) {
        repositories(
          first: 100
          after: $after
          ownerAffiliations: OWNER
          isFork: false
          orderBy: {field: UPDATED_AT, direction: DESC}
        ) {
          totalCount
          pageInfo {
            hasNextPage
            endCursor
          }
          nodes {
            stargazerCount
          }
        }
      }
    }
    """

    summary_query = """
    query($login: String!, $from: DateTime!, $to: DateTime!) {
      user(login: $login) {
        followers {
          totalCount
        }
        contributionsCollection(from: $from, to: $to) {
          contributionCalendar {
            totalContributions
          }
          totalCommitContributions
          totalPullRequestContributions
          totalIssueContributions
        }
      }
    }
    """

    try:
        stars = 0
        repo_count = 0
        cursor: str | None = None

        while True:
            repo_data = github_graphql_request(repo_query, {"login": username, "after": cursor}, token)
            user = repo_data.get("user")
            if not user:
                raise RuntimeError(f"GitHub user '{username}' was not found.")

            repositories = user["repositories"]
            repo_count = repositories["totalCount"]
            stars += sum(node.get("stargazerCount", 0) for node in repositories.get("nodes", []))

            page_info = repositories["pageInfo"]
            if not page_info["hasNextPage"]:
                break
            cursor = page_info["endCursor"]

        year_start = datetime.now(UTC).replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        summary_data = github_graphql_request(
            summary_query,
            {
                "login": username,
                "from": year_start.isoformat().replace("+00:00", "Z"),
                "to": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            },
            token,
        )
        summary_user = summary_data["user"]
        contributions = summary_user["contributionsCollection"]

        return {
            "repository_count": f"{repo_count:,}",
            "followers": f"{summary_user['followers']['totalCount']:,}",
            "stars": f"{stars:,}",
            "contributions": f"{contributions['contributionCalendar']['totalContributions']:,}",
            "commit_contributions": f"{contributions['totalCommitContributions']:,}",
            "pull_request_contributions": f"{contributions['totalPullRequestContributions']:,}",
            "issue_contributions": f"{contributions['totalIssueContributions']:,}",
            "scope": "Contribution metrics reflect the current calendar year",
        }
    except (HTTPError, URLError, TimeoutError, RuntimeError, KeyError) as exc:
        unavailable["scope"] = f"GitHub API unavailable: {exc}"
        return unavailable


def load_ascii_art(path: Path) -> list[str]:
    if not path.exists():
        raise FileNotFoundError(f"ASCII art file not found: {path}")
    return path.read_text(encoding="utf-8").splitlines() or [""]


def wrap_value(value: str, width: int = 43) -> list[str]:
    safe_value = " ".join(value.split())
    if not safe_value:
        return ["—"]
    return wrap(safe_value, width=width, break_long_words=True, break_on_hyphens=False) or ["—"]


def make_terminal_rows(profile: dict[str, Any], stats: dict[str, str], last_updated: str, layout: Layout, theme: dict[str, str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    y = 62
    line_height = 28
    column_gap = 188
    value_x = column_gap

    def add_separator(title: str) -> None:
        nonlocal y
        if rows:
            y += 8
        rows.append({"x": 0, "y": y, "text": title, "color": theme["muted"], "size": 17})
        y += 20
        rows.append({"x": 0, "y": y, "text": "─" * 30, "color": theme["separator"], "size": 17})
        y += 30

    def add_field(label: str, value: str) -> None:
        nonlocal y
        wrapped = wrap_value(value)
        for index, segment in enumerate(wrapped):
            label_text = f"{label:<12}" if index == 0 else " " * 12
            rows.append({"x": 0, "y": y, "text": label_text, "color": theme["label"], "size": 17})
            rows.append({"x": value_x, "y": y, "text": segment, "color": theme["foreground"], "size": 17})
            y += line_height

    add_separator("Profile")
    add_field("Role:", profile["role"])
    add_field("Location:", profile["location"])
    add_field("Focus:", join_items(profile["focus"]))
    add_field("Stack:", join_items(profile["stack"]))
    add_field("Interests:", join_items(profile["interests"]))

    add_separator("GitHub")
    add_field("Repos:", stats["repository_count"])
    add_field("Followers:", stats["followers"])
    add_field("Stars:", stats["stars"])
    add_field("Contribs:", f"{stats['contributions']} (YTD)")
    add_field("Commits:", f"{stats['commit_contributions']} (YTD)")
    add_field("Pull Req:", f"{stats['pull_request_contributions']} (YTD)")
    add_field("Issues:", f"{stats['issue_contributions']} (YTD)")

    add_separator("Activity")
    add_field("Updated:", last_updated)
    add_field("Source:", stats["scope"])

    return rows


def get_environment() -> Environment:
    environment = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(enabled_extensions=("j2", "svg", "xml"), default=True),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    environment.filters["escape_xml"] = escape
    return environment


def render_svg(theme_name: str, profile: dict[str, Any], ascii_lines: list[str], stats: dict[str, str], last_updated: str) -> str:
    layout = Layout()
    theme = THEMES[theme_name]
    header = f"{profile['username']}@github"
    info_rows = make_terminal_rows(profile, stats, last_updated, layout, theme)
    template = get_environment().get_template("profile.svg.j2")
    return template.render(
        profile=profile,
        theme=theme,
        layout=layout,
        header=header,
        ascii_lines=ascii_lines,
        info_rows=info_rows,
    )


def write_output(theme_name: str, svg: str) -> Path:
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    output_path = GENERATED_DIR / f"profile-{theme_name}.svg"
    output_path.write_text(svg, encoding="utf-8")
    return output_path


def validate_svg(path: Path) -> None:
    ET.parse(path)


def validate_workflow_yaml(path: Path) -> None:
    with path.open("r", encoding="utf-8") as handle:
        yaml.safe_load(handle)


def main() -> None:
    token = os.getenv("GITHUB_TOKEN")
    ascii_lines = load_ascii_art(ASCII_PATH)
    stats = fetch_github_stats(PROFILE["username"], token)
    last_updated = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")

    for theme_name in THEMES:
        svg = render_svg(theme_name, PROFILE, ascii_lines, stats, last_updated)
        output_path = write_output(theme_name, svg)
        validate_svg(output_path)

    validate_workflow_yaml(WORKFLOW_PATH)


if __name__ == "__main__":
    main()
