"""GitHub API normalization: forks/archived filtering, languages, signal, time."""
import unittest
from datetime import datetime, timedelta, timezone

from src import normalize
from src.config import ProfileConfig

from .helpers import make_data


NOW = datetime(2026, 8, 22, 4, 0, 0, tzinfo=timezone.utc)


class RepoInfos(unittest.TestCase):
    def test_basic_normalization(self):
        items = [
            {
                "name": "a",
                "description": "desc",
                "language": "Python",
                "html_url": "https://github.com/x/a",
                "pushed_at": "2026-01-01T00:00:00Z",
                "fork": False,
                "archived": False,
                "stargazers_count": 3,
            }
        ]
        repos = normalize.repo_infos(items)
        self.assertEqual(len(repos), 1)
        self.assertEqual(repos[0].name, "a")
        self.assertEqual(repos[0].stars, 3)
        self.assertFalse(repos[0].fork)

    def test_missing_name_skipped(self):
        repos = normalize.repo_infos([{"description": "no name"}])
        self.assertEqual(repos, [])

    def test_junk_entries_skipped(self):
        repos = normalize.repo_infos(["str", None, 42])
        self.assertEqual(repos, [])


class Languages(unittest.TestCase):
    def test_forks_and_archived_excluded(self):
        repos = make_data().repos
        # wanderink-blog is non-fork; SoAI is a fork
        langs = normalize.aggregate_languages(
            repos,
            {
                "wanderink-blog": {"TypeScript": 100},
                "SoAI-2026-AI-Algorithmic-Trading-Competition": {"Python": 10000},
            },
            now=NOW,
            window_days=365,
            exclude_forks=True,
            max_languages=4,
        )
        self.assertEqual(langs, ["TypeScript"])

    def test_recent_window_preferred(self):
        repos = make_data().repos
        # window of 1 day: nothing recent -> falls back to the full pool
        langs = normalize.aggregate_languages(
            repos,
            {"wanderink-blog": {"TypeScript": 10}, "diffusion-model-mnist": {"Python": 5}},
            now=NOW,
            window_days=1,
            exclude_forks=True,
            max_languages=4,
            login="lairifangtang-hue",
        )
        self.assertIn("TypeScript", langs)
        self.assertIn("Python", langs)

    def test_recent_window_wins_when_data_exists(self):
        repos = make_data().repos
        # window of 200 days (cutoff 2026-01-23): wanderink-blog (2026-01-18)
        # and Zero-shot-Agent (2025-12-03) both fall outside, so only the
        # in-window repos' languages count.
        langs = normalize.aggregate_languages(
            repos,
            {
                "wanderink-blog": {"TypeScript": 10},
                "diffusion-model-mnist": {"Python": 5},
                "Zero-shot-Agent": {"Rust": 900},
            },
            now=NOW,
            window_days=200,
            exclude_forks=True,
            max_languages=4,
            login="lairifangtang-hue",
        )
        self.assertIn("Python", langs)
        self.assertNotIn("TypeScript", langs)
        self.assertNotIn("Rust", langs)

    def test_max_languages(self):
        repos = make_data().repos
        langs = normalize.aggregate_languages(
            repos,
            {
                "wanderink-blog": {"TypeScript": 10},
                "diffusion-model-mnist": {"Python": 5},
                "attention-mechanisms-showcase": {"Jupyter Notebook": 3},
                "Zero-shot-Agent": {"Rust": 2},
            },
            now=NOW,
            window_days=365,
            exclude_forks=True,
            max_languages=2,
        )
        self.assertEqual(len(langs), 2)
        self.assertEqual(langs, ["TypeScript", "Python"])


class Signal(unittest.TestCase):
    def test_work_event_wins(self):
        events = [
            {"type": "WatchEvent", "repo": {"name": "x/y"}, "created_at": "2026-08-20T00:00:00Z"},
            {"type": "PushEvent", "repo": {"name": "lairifangtang-hue/diffusion-model-mnist"},
             "created_at": "2026-08-19T00:00:00Z"},
        ]
        sig = normalize.recent_signal(events, [], now=NOW)
        self.assertEqual(sig.repo, "diffusion-model-mnist")

    def test_watch_only_falls_back_to_repos(self):
        events = [
            {"type": "WatchEvent", "repo": {"name": "x/y"}, "created_at": "2026-08-20T00:00:00Z"},
        ]
        sig = normalize.recent_signal(events, make_data().repos, now=NOW,
                                      login="lairifangtang-hue")
        # latest pushed non-fork, non-profile repo
        self.assertEqual(sig.repo, "diffusion-model-mnist")

    def test_profile_repo_excluded_from_fallback(self):
        repos = [r for r in make_data().repos if r.name != "lairifangtang-hue"]
        sig = normalize.recent_signal([], repos + [], now=NOW)
        self.assertNotEqual(sig.repo, "lairifangtang-hue")

    def test_no_activity_returns_none(self):
        self.assertIsNone(normalize.recent_signal([], [], now=NOW))

    def test_renamed_repo_signal_uses_event_repo(self):
        events = [
            {"type": "PushEvent", "repo": {"name": "lairifangtang-hue/Renamed-Repo"},
             "created_at": "2026-08-20T00:00:00Z"},
        ]
        sig = normalize.recent_signal(events, make_data().repos, now=NOW)
        self.assertEqual(sig.repo, "Renamed-Repo")


class TimeFormatting(unittest.TestCase):
    def test_relative_times(self):
        cases = [
            ("2026-08-22T03:59:30Z", "just now"),
            ("2026-08-22T03:30:00Z", "30m ago"),
            ("2026-08-22T01:00:00Z", "3h ago"),
            ("2026-08-19T04:00:00Z", "3d ago"),
            ("2026-06-01T00:00:00Z", "2mo ago"),
            ("2024-08-22T04:00:00Z", "2y ago"),
        ]
        for iso, expected in cases:
            self.assertEqual(normalize.relative_time(iso, NOW), expected, iso)

    def test_invalid_iso_is_none(self):
        self.assertIsNone(normalize.relative_time("not-a-date", NOW))
        self.assertIsNone(normalize.relative_time(None, NOW))

    def test_month_year(self):
        self.assertEqual(normalize.month_year("2025-09-12T10:58:39Z"), "2025-09")
        self.assertIsNone(normalize.month_year(None))


class BuildProfileData(unittest.TestCase):
    def test_end_to_end(self):
        cfg = ProfileConfig.from_mapping({})
        data = normalize.build_profile_data(
            login="lairifangtang-hue",
            user_payload={"location": "Singapore", "company": "NUS",
                          "created_at": "2025-09-12T10:58:39Z"},
            repo_payloads=[
                {"name": "a", "language": "Python", "pushed_at": "2026-08-01T00:00:00Z",
                 "fork": False, "archived": False, "html_url": "u"},
                {"name": "b", "language": "TypeScript", "pushed_at": "2026-07-01T00:00:00Z",
                 "fork": False, "archived": False, "html_url": "u"},
            ],
            languages_by_repo={"a": {"Python": 10}, "b": {"TypeScript": 5}},
            event_payloads=[
                {"type": "PushEvent", "repo": {"name": "lairifangtang-hue/b"},
                 "created_at": "2026-08-20T00:00:00Z"},
            ],
            cfg=cfg,
            now=NOW,
        )
        self.assertEqual(data.handle, "lairifangtang-hue")
        self.assertEqual(data.signal.repo, "b")
        self.assertEqual(data.languages[:2], ["Python", "TypeScript"])
        self.assertEqual(data.location, "Singapore")


if __name__ == "__main__":
    unittest.main()
