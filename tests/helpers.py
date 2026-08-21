"""Shared test helpers: config factory + fixture data."""
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config import ProfileConfig  # noqa: E402
from src.models import ProfileData, RepoInfo, Signal  # noqa: E402


def make_config(**overrides) -> ProfileConfig:
    """A realistic, valid config with optional top-level overrides."""
    raw = {
        "identity": {
            "login": "lairifangtang-hue",
            "handle": "wei",
            "role": "AI · Software · Research",
            "base": "Singapore",
            "affiliation": "NUS",
            "since": "2025-09",
        },
        "focus": ["AI Agents", "World Models", "Graph ML", "Embodied Intelligence"],
        "now": {
            "building": "agent workflow tooling",
            "learning": "world models & planning",
            "exploring": "graph learning for agents",
            "reading": "Playing Games with a Single World Model",
        },
        "featured_projects": [
            {"repo": "Zero-shot-Agent", "note": "zero-shot agent experiments"},
            {"repo": "wanderink-blog", "note": "typescript · ink-inspired writing space"},
            {"repo": "diffusion-model-mnist", "note": "diffusion models from scratch, MNIST"},
            {"repo": "attention-mechanisms-showcase", "note": "attention variants, side by side"},
        ],
        "languages": {"window_days": 365, "max": 4, "exclude_forks": True},
        "metrics": {"stars": False, "followers": False, "commits": False},
    }
    raw.update(overrides)
    return ProfileConfig.from_mapping(raw)


def make_data(**overrides) -> ProfileData:
    """A ProfileData shaped like the real account's normalized data."""
    repos = [
        RepoInfo(
            name="wanderink-blog",
            description="typescript writing space",
            language="TypeScript",
            html_url="https://github.com/lairifangtang-hue/wanderink-blog",
            pushed_at="2026-01-18T12:30:34Z",
            fork=False,
            archived=False,
            stars=0,
        ),
        RepoInfo(
            name="diffusion-model-mnist",
            description="diffusion models from scratch, MNIST",
            language="Python",
            html_url="https://github.com/lairifangtang-hue/diffusion-model-mnist",
            pushed_at="2026-03-27T15:50:50Z",
            fork=False,
            archived=False,
            stars=0,
        ),
        RepoInfo(
            name="attention-mechanisms-showcase",
            description="attention variants side by side",
            language="Python",
            html_url="https://github.com/lairifangtang-hue/attention-mechanisms-showcase",
            pushed_at="2026-02-10T13:49:03Z",
            fork=False,
            archived=False,
            stars=0,
        ),
        RepoInfo(
            name="SoAI-2026-AI-Algorithmic-Trading-Competition",
            description="starter template fork",
            language=None,
            html_url="https://github.com/lairifangtang-hue/SoAI-2026-AI-Algorithmic-Trading-Competition",
            pushed_at="2026-05-14T09:55:17Z",
            fork=True,
            archived=False,
            stars=0,
        ),
        RepoInfo(
            name="Zero-shot-Agent",
            description="zero-shot agent experiments",
            language=None,
            html_url="https://github.com/lairifangtang-hue/Zero-shot-Agent",
            pushed_at="2025-12-03T12:38:34Z",
            fork=False,
            archived=False,
            stars=0,
        ),
        RepoInfo(
            name="lairifangtang-hue",
            description="introduction",
            language=None,
            html_url="https://github.com/lairifangtang-hue/lairifangtang-hue",
            pushed_at="2026-08-21T15:56:43Z",
            fork=False,
            archived=False,
            stars=0,
        ),
    ]
    base = dict(
        handle="lairifangtang-hue",
        location="Singapore",
        company="NUS",
        blog=None,
        created_at="2025-09-12T10:58:39Z",
        repos=repos,
        languages=["TypeScript", "Python", "Jupyter Notebook"],
        signal=Signal(repo="Zero-shot-Agent", at="2025-12-03T12:38:34Z"),
    )
    base.update(overrides)
    return ProfileData(**base)


class TestCase(unittest.TestCase):
    pass
