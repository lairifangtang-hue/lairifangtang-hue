"""Pure normalization: raw GitHub API payloads -> models. No I/O.

Everything here is deterministic and trivially testable: fork/archived
filtering, recent-window language aggregation, the "last signal" heuristic
and time formatting.
"""
from __future__ import annotations

import typing as t
from datetime import datetime, timedelta, timezone

from .config import ProfileConfig
from .models import ProfileData, RepoInfo, Signal

# Event types that represent actual work (watching a repo does not).
WORK_EVENTS = {
    "PushEvent",
    "CreateEvent",
    "PullRequestEvent",
    "PullRequestReviewEvent",
    "IssuesEvent",
    "IssueCommentEvent",
    "CommitCommentEvent",
    "ReleaseEvent",
    "PublicEvent",
}


def parse_iso(iso: t.Optional[str]) -> t.Optional[datetime]:
    if not iso or not isinstance(iso, str):
        return None
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def repo_infos(items: t.List[dict]) -> t.List[RepoInfo]:
    out = []
    for item in items:
        if not isinstance(item, dict) or not item.get("name"):
            continue
        out.append(
            RepoInfo(
                name=item["name"],
                description=item.get("description"),
                language=item.get("language"),
                html_url=item.get("html_url") or "",
                pushed_at=item.get("pushed_at"),
                fork=bool(item.get("fork")),
                archived=bool(item.get("archived")),
                stars=int(item.get("stargazers_count") or 0),
            )
        )
    return out


def aggregate_languages(
    repos: t.List[RepoInfo],
    langs_by_repo: t.Dict[str, dict],
    *,
    now: datetime,
    window_days: int = 365,
    exclude_forks: bool = True,
    max_languages: int = 4,
    login: str = "",
) -> t.List[str]:
    """Top languages, preferring repos touched within the window.

    Falls back to lifetime aggregation when the window is empty. Small
    numbers are meaningless, so percentages are never computed. The profile
    repo itself never counts (refreshing your own card is not language use).
    """
    pool = [r for r in repos if not r.archived]
    if exclude_forks:
        pool = [r for r in pool if not r.fork]
    if login:
        pool = [r for r in pool if r.name != login]

    cutoff = now - timedelta(days=window_days)
    recent = [
        r
        for r in pool
        if (parse_iso(r.pushed_at) or datetime.min.replace(tzinfo=timezone.utc)) >= cutoff
    ]
    if recent:
        pool = recent

    totals: t.Dict[str, int] = {}
    for r in pool:
        for lang, nbytes in (langs_by_repo.get(r.name) or {}).items():
            totals[lang] = totals.get(lang, 0) + int(nbytes)

    ranked = sorted(totals, key=lambda lang: (-totals[lang], lang))
    return ranked[:max_languages]


def recent_signal(
    events: t.List[dict], repos: t.List[RepoInfo], *, now: datetime, login: str = ""
) -> t.Optional[Signal]:
    """Latest genuine activity: newest work event, else newest push.

    The profile repo itself is excluded from the fallback — refreshing your
    own card is not a signal worth showing.
    """
    for event in events:
        if not isinstance(event, dict):
            continue
        if event.get("type") not in WORK_EVENTS:
            continue
        repo_name = (event.get("repo") or {}).get("name") or ""
        repo = repo_name.split("/")[-1]
        if repo and repo != login:
            return Signal(repo=repo, at=event.get("created_at"))

    candidates = [
        r
        for r in repos
        if r.pushed_at
        and not r.archived
        and not r.fork
        and r.name != login
    ]
    if not candidates:
        return None
    latest = max(candidates, key=lambda r: r.pushed_at or "")
    return Signal(repo=latest.name, at=latest.pushed_at)


def relative_time(iso: t.Optional[str], now: datetime) -> t.Optional[str]:
    dt = parse_iso(iso)
    if dt is None:
        return None
    seconds = max(0.0, (now - dt).total_seconds())
    if seconds < 60:
        return "just now"
    minutes = seconds / 60
    if minutes < 60:
        return f"{int(minutes)}m ago"
    hours = minutes / 60
    if hours < 24:
        return f"{int(hours)}h ago"
    days = hours / 24
    if days < 30:
        return f"{int(days)}d ago"
    if days < 365:
        return f"{int(days // 30)}mo ago"
    return f"{int(days // 365)}y ago"


def month_year(iso: t.Optional[str]) -> t.Optional[str]:
    dt = parse_iso(iso)
    if dt is None:
        return None
    return dt.strftime("%Y-%m")


def build_profile_data(
    *,
    login: str,
    user_payload: dict,
    repo_payloads: t.List[dict],
    languages_by_repo: t.Dict[str, dict],
    event_payloads: t.List[dict],
    cfg: ProfileConfig,
    now: datetime,
) -> ProfileData:
    repos = repo_infos(repo_payloads)
    owned = [
        r
        for r in repos
        if not r.fork and not r.archived and r.name != login
    ]
    languages = aggregate_languages(
        owned,
        {r.name: (languages_by_repo.get(r.name) or {}) for r in owned},
        now=now,
        window_days=cfg.languages.window_days,
        exclude_forks=cfg.languages.exclude_forks,
        max_languages=cfg.languages.max,
        login=login,
    )
    signal = recent_signal(event_payloads, repos, now=now, login=login)
    return ProfileData(
        handle=login,
        location=user_payload.get("location"),
        company=user_payload.get("company"),
        blog=(user_payload.get("blog") or None),
        created_at=user_payload.get("created_at"),
        repos=repos,
        languages=languages,
        signal=signal,
    )
