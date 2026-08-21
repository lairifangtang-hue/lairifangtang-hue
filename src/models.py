"""Typed data model for the profile system."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class RepoInfo:
    """A public repository as shown on the card."""

    name: str
    description: str | None
    language: str | None
    html_url: str
    pushed_at: str | None  # ISO 8601
    fork: bool
    archived: bool
    stars: int  # retained for future metrics; never rendered by default


@dataclass(frozen=True)
class Signal:
    """The most recent trace of activity."""

    repo: str | None
    at: str | None  # ISO 8601


@dataclass
class ProfileData:
    """Everything the layout needs, after normalization."""

    handle: str
    location: str | None = None
    company: str | None = None
    blog: str | None = None
    created_at: str | None = None
    repos: list[RepoInfo] = field(default_factory=list)
    languages: list[str] = field(default_factory=list)
    signal: Signal | None = None

    def repo(self, name: str) -> RepoInfo | None:
        for r in self.repos:
            if r.name == name:
                return r
        return None
