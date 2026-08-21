"""Config loading and validation."""
import unittest

from src.config import ConfigError, ProfileConfig

from .helpers import make_config


class ConfigLoading(unittest.TestCase):
    def test_full_config_loads(self):
        cfg = make_config()
        self.assertEqual(cfg.identity.login, "lairifangtang-hue")
        self.assertEqual(cfg.identity.handle, "wei")
        self.assertEqual(cfg.identity.role, "AI · Software · Research")
        self.assertEqual(len(cfg.focus), 4)
        self.assertEqual(cfg.now.building, "agent workflow tooling")
        self.assertEqual(len(cfg.featured_projects), 4)
        self.assertEqual(cfg.featured_projects[0].repo, "Zero-shot-Agent")
        self.assertEqual(cfg.languages.window_days, 365)
        self.assertFalse(cfg.metrics.stars)
        self.assertFalse(cfg.metrics.followers)
        self.assertFalse(cfg.metrics.commits)

    def test_empty_config_is_valid(self):
        cfg = ProfileConfig.from_mapping({})
        self.assertIsNone(cfg.identity.login)
        self.assertEqual(cfg.featured_projects, [])
        self.assertEqual(cfg.languages.max, 4)

    def test_yaml_file_roundtrip(self):
        import pathlib
        import tempfile

        text = """
identity:
  login: someone
  handle: some
focus: [a, b]
now:
  building: thing
featured_projects:
  - repo-one
  - repo: repo-two
    note: a note
"""
        with tempfile.TemporaryDirectory() as td:
            p = pathlib.Path(td) / "profile.config.yml"
            p.write_text(text, encoding="utf-8")
            cfg = ProfileConfig.load(p)
        self.assertEqual(cfg.identity.login, "someone")
        self.assertEqual(cfg.focus, ["a", "b"])
        self.assertEqual(cfg.now.building, "thing")
        self.assertEqual(cfg.featured_projects[0].repo, "repo-one")
        self.assertIsNone(cfg.featured_projects[0].note)
        self.assertEqual(cfg.featured_projects[1].note, "a note")

    def test_missing_file_raises(self):
        with self.assertRaises(ConfigError):
            ProfileConfig.load("C:/definitely/not/here/profile.config.yml")

    def test_invalid_yaml_raises(self):
        with tempfile_erroneous() as path:
            with self.assertRaises(ConfigError):
                ProfileConfig.load(path)

    def test_root_not_mapping_raises(self):
        with self.assertRaises(ConfigError):
            ProfileConfig.from_mapping(["not", "a", "dict"])

    def test_featured_projects_type_error(self):
        with self.assertRaises(ConfigError):
            ProfileConfig.from_mapping({"featured_projects": "nope"})

    def test_metrics_must_be_bool(self):
        with self.assertRaises(ConfigError):
            ProfileConfig.from_mapping({"metrics": {"stars": "yes"}})


def tempfile_erroneous():
    import contextlib
    import pathlib
    import tempfile

    @contextlib.contextmanager
    def cm():
        with tempfile.TemporaryDirectory() as td:
            p = pathlib.Path(td) / "bad.yml"
            p.write_text("identity: [unclosed", encoding="utf-8")
            yield p

    return cm()


if __name__ == "__main__":
    unittest.main()
