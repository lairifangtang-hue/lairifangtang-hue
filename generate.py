from __future__ import annotations

import datetime as dt
import json
import os
import textwrap
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

ROOT = Path(__file__).resolve().parent
TEMPLATE_DIR = ROOT / "templates"
ASCII_PATH = ROOT / "assets" / "ascii.txt"
OUTPUT_DIR = ROOT / "generated"

PROFILE = {
    "name": "Your Name",
    "username": "YOUR_GITHUB_USERNAME",
    "role": "Software / AI Engineer",
    "location": "Singapore",
    "focus": ["AI Agents", "Machine Learning", "Graph Learning"],
    "stack": ["Python", "TypeScript", "PyTorch", "Next.js"],
    "interests": ["World Models", "Agents", "Robotics"],
}

SVG_DIMENSIONS = {"width": 1200, "height": 900, "line_height": 24}
LABEL_WIDTH = 16
VALUE_WIDTH = 34

THEMES = {
    "dark": {
        "page_bg": "#0b1118",
        "panel_bg": "#111923",
        "panel_border": "#263241",
        "panel_glow_start": "#161f2b",
        "panel_glow_end": "#111923",
        "ascii_bg": "#0d141d",
        "ascii_accent": "#8fb7ff",
        "text": "#d9e2f0",
        "muted": "#8a98ad",
        "red": "#f07178",
        "yellow": "#e6c07b",
        "green": "#98c379",
    },
    "light": {
        "page_bg": "#f3f5f7",
        "panel_bg": "#ffffff",
        "panel_border": "#d8dee5",
        "panel_glow_start": "#f8fafc",
        "panel_glow_end": "#ffffff",
        "ascii_bg": "#f8fafc",
        "ascii_accent": "#335f9f",
        "text": "#1f2937",
        "muted": "#66758a",
        "red": "#e46a75",
        "yellow": "#c59235",
        "green": "#4c9a5f",
    },
}

FONT_FAMILY = (
    "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "
    "'Liberation Mono', 'Courier New', monospace"
)

GRAPHQL_QUERY = """
query ProfileSummary($login: String!, $cursor: String, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    followers {
      totalCount
    }
    repositories(
      ownerAffiliations: OWNER
      isFork: false
      privacy: PUBLIC
      first: 100
      after: $cursor
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
""".strip()


def join_items(values: list[str]) -> str:
    return " · ".join(item.strip() for item in values if item.strip())


def resolve_username() -> str:
    configured = str(PROFILE.get("username", "")).strip()
    if configured and configured != "YOUR_GITHUB_USERNAME":
        return configured
    return os.getenv("GITHUB_REPOSITORY_OWNER", configured).strip()


def load_ascii_art() -> list[str]:
    return ASCII_PATH.read_text(encoding="utf-8").rstrip("\n").splitlines() or [""]


def post_github_graphql(query: str, variables: dict[str, object], token: str) -> dict[str, object]:
    payload = json.dumps({"query": query, "variables": variables}).encode("utf-8")
    request = urllib.request.Request(
        "https://api.github.com/graphql",
        data=payload,
        headers={
            "Authorization": "Bearer " + token,
            "Content-Type": "application/json",
            "User-Agent": "profile-svg-generator",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        response_data = json.load(response)

    if response_data.get("errors"):
        messages = ", ".join(error.get("message", "Unknown GitHub API error") for error in response_data["errors"])
        raise RuntimeError(messages)

    return response_data["data"]


def unavailable_stats(reason: str) -> dict[str, object]:
    current_year = dt.datetime.now(dt.UTC).year
    return {
        "repositories": "unavailable",
        "followers": "unavailable",
        "stars": "unavailable",
        "contributions": "unavailable",
        "commits": "unavailable",
        "pull_requests": "unavailable",
        "issues": "unavailable",
        "year": current_year,
        "status": reason,
    }


def fetch_github_stats(username: str) -> dict[str, object]:
    token = os.getenv("GITHUB_TOKEN", "").strip()
    if not username:
        return unavailable_stats("Set PROFILE['username'] or GITHUB_REPOSITORY_OWNER to enable GitHub stats.")
    if username == "YOUR_GITHUB_USERNAME":
        return unavailable_stats("Replace the placeholder username to enable GitHub stats.")
    if not token:
        return unavailable_stats("No GITHUB_TOKEN available.")

    now = dt.datetime.now(dt.UTC)
    start = dt.datetime(now.year, 1, 1, tzinfo=dt.UTC)
    end = dt.datetime(now.year + 1, 1, 1, tzinfo=dt.UTC)
    cursor = None
    total_stars = 0
    repositories = 0
    followers = 0
    contributions = 0
    commits = 0
    pull_requests = 0
    issues = 0

    try:
        while True:
            data = post_github_graphql(
                GRAPHQL_QUERY,
                {
                    "login": username,
                    "cursor": cursor,
                    "from": start.isoformat(),
                    "to": end.isoformat(),
                },
                token,
            )
            user = data.get("user")
            if not user:
                raise RuntimeError(f"GitHub user '{username}' was not found.")

            repo_connection = user["repositories"]
            repositories = int(repo_connection["totalCount"])
            total_stars += sum(int(node.get("stargazerCount", 0)) for node in repo_connection.get("nodes", []))
            followers = int(user["followers"]["totalCount"])

            contribution_data = user["contributionsCollection"]
            contributions = int(contribution_data["contributionCalendar"]["totalContributions"])
            commits = int(contribution_data["totalCommitContributions"])
            pull_requests = int(contribution_data["totalPullRequestContributions"])
            issues = int(contribution_data["totalIssueContributions"])

            page_info = repo_connection["pageInfo"]
            if not page_info["hasNextPage"]:
                break
            cursor = page_info["endCursor"]
    except urllib.error.HTTPError as error:
        return unavailable_stats(f"GitHub API request failed ({error.code}).")
    except urllib.error.URLError:
        return unavailable_stats("GitHub API request failed due to a network error.")
    except RuntimeError as error:
        return unavailable_stats(str(error))

    return {
        "repositories": repositories,
        "followers": followers,
        "stars": total_stars,
        "contributions": contributions,
        "commits": commits,
        "pull_requests": pull_requests,
        "issues": issues,
        "year": now.year,
        "status": "Live GitHub GraphQL data",
    }


def format_value(value: object) -> str:
    if isinstance(value, int):
        return f"{value:,}"
    return str(value)


def format_kv_lines(label: str, value: object) -> list[str]:
    wrapped = textwrap.wrap(
        format_value(value),
        width=VALUE_WIDTH,
        break_long_words=True,
        break_on_hyphens=False,
    ) or [""]
    prefix = f"{label}:".ljust(LABEL_WIDTH)
    return [
        f"{prefix if index == 0 else ' ' * LABEL_WIDTH}{segment}"
        for index, segment in enumerate(wrapped)
    ]


def build_info_lines(username: str, stats: dict[str, object]) -> list[str]:
    profile_rows = [
        ("Name", PROFILE["name"]),
        ("Role", PROFILE["role"]),
        ("Location", PROFILE["location"]),
        ("Focus", join_items(PROFILE["focus"])),
        ("Stack", join_items(PROFILE["stack"])),
        ("Interests", join_items(PROFILE["interests"])),
    ]
    github_rows = [
        ("Repositories", stats["repositories"]),
        ("Followers", stats["followers"]),
        ("Stars", stats["stars"]),
        ("Contribs", stats["contributions"]),
        ("Commits (yr)", stats["commits"]),
        ("PRs (yr)", stats["pull_requests"]),
        ("Issues (yr)", stats["issues"]),
    ]
    activity_rows = [
        ("Last Updated", dt.datetime.now(dt.UTC).strftime("%Y-%m-%d %H:%M UTC")),
        ("Data Source", stats["status"]),
    ]

    lines = [f"{username or 'profile'}@github", "────────────────────────", "", "Profile", "────────────────────────"]
    for label, value in profile_rows:
        lines.extend(format_kv_lines(label, value))

    lines.extend(["", "GitHub", "────────────────────────"])
    for label, value in github_rows:
        lines.extend(format_kv_lines(label, value))

    lines.extend(["", "Activity", "────────────────────────"])
    for label, value in activity_rows:
        lines.extend(format_kv_lines(label, value))
    return lines


def render_svg(theme_name: str, ascii_lines: list[str], info_lines: list[str]) -> str:
    environment = Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        autoescape=select_autoescape(enabled_extensions=("svg", "xml")),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    template = environment.get_template("profile.svg.j2")
    return template.render(
        width=SVG_DIMENSIONS["width"],
        height=SVG_DIMENSIONS["height"],
        line_height=SVG_DIMENSIONS["line_height"],
        font_family=FONT_FAMILY,
        ascii_lines=ascii_lines,
        info_lines=info_lines,
        theme=THEMES[theme_name],
        card_title="GitHub profile terminal card",
        card_description="A terminal-style summary card rendered as SVG for a GitHub profile README.",
    )


def validate_svg(path: Path) -> None:
    ET.parse(path)


def main() -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)
    username = resolve_username()
    ascii_lines = load_ascii_art()
    stats = fetch_github_stats(username)
    info_lines = build_info_lines(username, stats)

    for theme_name in THEMES:
        output_path = OUTPUT_DIR / f"profile-{theme_name}.svg"
        output_path.write_text(render_svg(theme_name, ascii_lines, info_lines), encoding="utf-8")
        validate_svg(output_path)
        print(f"Generated {output_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
