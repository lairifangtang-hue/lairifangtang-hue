"""Configuration loading and validation for the profile generator.

All human-maintained content lives in profile.config.yml; the renderer never
hardcodes personal data. Missing optional fields degrade gracefully (the row
is simply omitted, with sane fallbacks to live GitHub profile fields).
"""
from __future__ import annotations

from dataclasses import dataclass, field
import pathlib
import typing as t

import yaml


class ConfigError(ValueError):
    """Raised when profile.config.yml is missing, malformed or invalid."""


@dataclass
class Identity:
    login: t.Optional[str] = None        # GitHub account used for API fetches
    handle: t.Optional[str] = None       # display handle, shown as handle@github
    display_name: t.Optional[str] = None
    role: t.Optional[str] = None
    base: t.Optional[str] = None
    affiliation: t.Optional[str] = None
    website: t.Optional[str] = None
    since: t.Optional[str] = None


@dataclass
class NowCfg:
    building: t.Optional[str] = None
    learning: t.Optional[str] = None
    exploring: t.Optional[str] = None
    reading: t.Optional[str] = None


@dataclass
class FeaturedProject:
    repo: str
    note: t.Optional[str] = None


@dataclass
class LanguagesCfg:
    window_days: int = 365
    max: int = 4
    exclude_forks: bool = True


@dataclass
class MetricsCfg:
    """Vanity metrics stay off until they are worth showing."""

    stars: bool = False
    followers: bool = False
    commits: bool = False


@dataclass
class ProfileConfig:
    identity: Identity = field(default_factory=Identity)
    focus: t.List[str] = field(default_factory=list)
    now: NowCfg = field(default_factory=NowCfg)
    featured_projects: t.List[FeaturedProject] = field(default_factory=list)
    languages: LanguagesCfg = field(default_factory=LanguagesCfg)
    metrics: MetricsCfg = field(default_factory=MetricsCfg)

    # ------------------------------------------------------------------
    @classmethod
    def load(cls, path: t.Union[str, pathlib.Path]) -> "ProfileConfig":
        path = pathlib.Path(path)
        try:
            text = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            raise ConfigError(f"config not found: {path}") from None
        try:
            raw = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            raise ConfigError(f"config is not valid YAML: {exc}") from None
        if raw is None:
            raw = {}
        if not isinstance(raw, dict):
            raise ConfigError("config root must be a mapping")
        return cls.from_mapping(raw)

    # ------------------------------------------------------------------
    @classmethod
    def from_mapping(cls, raw: dict) -> "ProfileConfig":
        if not isinstance(raw, dict):
            raise ConfigError("config root must be a mapping")
        ident_raw = _mapping(raw, "identity")
        now_raw = _mapping(raw, "now")
        lang_raw = _mapping(raw, "languages")
        metrics_raw = _mapping(raw, "metrics")

        identity = Identity(
            login=_opt_str(ident_raw, "login", "identity"),
            handle=_opt_str(ident_raw, "handle", "identity"),
            display_name=_opt_str(ident_raw, "display_name", "identity"),
            role=_opt_str(ident_raw, "role", "identity"),
            base=_opt_str(ident_raw, "base", "identity"),
            affiliation=_opt_str(ident_raw, "affiliation", "identity"),
            website=_opt_str(ident_raw, "website", "identity"),
            since=_opt_str(ident_raw, "since", "identity"),
        )

        now = NowCfg(
            building=_opt_str(now_raw, "building", "now"),
            learning=_opt_str(now_raw, "learning", "now"),
            exploring=_opt_str(now_raw, "exploring", "now"),
            reading=_opt_str(now_raw, "reading", "now"),
        )

        fp_raw = raw.get("featured_projects")
        if fp_raw is None:
            fp_raw = []
        if not isinstance(fp_raw, list):
            raise ConfigError("featured_projects must be a list")
        featured: t.List[FeaturedProject] = []
        for i, item in enumerate(fp_raw):
            if isinstance(item, str):
                name = item.strip()
                if name:
                    featured.append(FeaturedProject(repo=name))
            elif isinstance(item, dict):
                name = _opt_str(item, "repo", f"featured_projects[{i}]")
                if not name:
                    raise ConfigError(f"featured_projects[{i}].repo is required")
                featured.append(
                    FeaturedProject(
                        repo=name,
                        note=_opt_str(item, "note", f"featured_projects[{i}]"),
                    )
                )
            else:
                raise ConfigError(
                    f"featured_projects[{i}] must be a string or a mapping"
                )

        languages = LanguagesCfg(
            window_days=_positive_int(lang_raw, "window_days", 365, "languages"),
            max=_bounded_int(lang_raw, "max", 4, 1, 8, "languages"),
            exclude_forks=_bool(lang_raw, "exclude_forks", True, "languages"),
        )

        metrics = MetricsCfg(
            stars=_bool(metrics_raw, "stars", False, "metrics"),
            followers=_bool(metrics_raw, "followers", False, "metrics"),
            commits=_bool(metrics_raw, "commits", False, "metrics"),
        )

        return cls(
            identity=identity,
            focus=_str_list(raw, "focus"),
            now=now,
            featured_projects=featured,
            languages=languages,
            metrics=metrics,
        )


# ----------------------------------------------------------------------
def _mapping(raw: dict, key: str) -> dict:
    val = raw.get(key)
    if val is None:
        return {}
    if not isinstance(val, dict):
        raise ConfigError(f"{key} must be a mapping")
    return val


def _opt_str(mapping: dict, key: str, where: str) -> t.Optional[str]:
    val = mapping.get(key)
    if val is None:
        return None
    if not isinstance(val, str):
        raise ConfigError(f"{where}.{key} must be a string")
    val = val.strip()
    return val or None


def _str_list(raw: dict, key: str) -> t.List[str]:
    val = raw.get(key)
    if val is None:
        return []
    if not isinstance(val, list) or not all(isinstance(x, str) for x in val):
        raise ConfigError(f"{key} must be a list of strings")
    return [x.strip() for x in val if x.strip()]


def _positive_int(mapping: dict, key: str, default: int, where: str) -> int:
    val = mapping.get(key, default)
    if not isinstance(val, int) or isinstance(val, bool) or val <= 0:
        raise ConfigError(f"{where}.{key} must be a positive integer")
    return val


def _bounded_int(mapping: dict, key: str, default: int, lo: int, hi: int, where: str) -> int:
    val = mapping.get(key, default)
    if not isinstance(val, int) or isinstance(val, bool) or not (lo <= val <= hi):
        raise ConfigError(f"{where}.{key} must be an integer in [{lo}, {hi}]")
    return val


def _bool(mapping: dict, key: str, default: bool, where: str) -> bool:
    val = mapping.get(key, default)
    if not isinstance(val, bool):
        raise ConfigError(f"{where}.{key} must be a boolean")
    return val
