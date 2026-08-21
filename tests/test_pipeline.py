"""Failure safety: a failed generation must never overwrite previous SVGs."""
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "generate_profile.py"

GOOD_FIXTURE = {
    "user": {"login": "lairifangtang-hue", "location": "Singapore", "company": "NUS"},
    "repos": [
        {"name": "demo", "description": "a demo", "language": "Python",
         "html_url": "https://github.com/lairifangtang-hue/demo",
         "pushed_at": "2026-08-01T00:00:00Z", "fork": False, "archived": False}
    ],
    "languages": {"demo": {"Python": 1000}},
    "events": [],
}


def run_script(args, cwd):
    # run the COPY inside the sandbox dir, never the original repo's script
    script = pathlib.Path(cwd) / "scripts" / "generate_profile.py"
    return subprocess.run(
        [sys.executable, str(script), *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=120,
    )


class FailureSafety(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = pathlib.Path(self.tmp.name)
        # copy the real project files in
        for item in ("profile.config.yml", "README.md"):
            (self.dir / item).write_bytes((ROOT / item).read_bytes())
        (self.dir / "scripts").mkdir(exist_ok=True)
        (self.dir / "scripts" / "generate_profile.py").write_bytes(SCRIPT.read_bytes())
        src = self.dir / "src"
        src.mkdir()
        for py in (ROOT / "src").glob("*.py"):
            (src / py.name).write_bytes(py.read_bytes())

    def tearDown(self):
        self.tmp.cleanup()

    def _seed(self):
        """Generate once with a good fixture, remember the SVGs."""
        fixture = self.dir / "good.json"
        fixture.write_text(json.dumps(GOOD_FIXTURE), encoding="utf-8")
        result = run_script(["--offline", str(fixture)], self.dir)
        self.assertEqual(result.returncode, 0, result.stderr)
        dark = (self.dir / "assets/generated/profile-dark.svg").read_text(encoding="utf-8")
        light = (self.dir / "assets/generated/profile-light.svg").read_text(encoding="utf-8")
        return dark, light

    def test_api_failure_preserves_previous_svgs(self):
        dark_before, light_before = self._seed()

        # now a fixture that makes the pipeline explode mid-render
        bad = dict(GOOD_FIXTURE)
        bad["repos"] = []  # empty data -> refusal to render
        badfile = self.dir / "bad.json"
        badfile.write_text(json.dumps(bad), encoding="utf-8")
        result = run_script(["--offline", str(badfile)], self.dir)
        self.assertEqual(result.returncode, 1)
        self.assertIn("previous SVGs left untouched", result.stderr)

        dark_after = (self.dir / "assets/generated/profile-dark.svg").read_text(encoding="utf-8")
        light_after = (self.dir / "assets/generated/profile-light.svg").read_text(encoding="utf-8")
        self.assertEqual(dark_before, dark_after)
        self.assertEqual(light_before, light_after)

    def test_malformed_json_fixture_fails_cleanly(self):
        self._seed()
        broken = self.dir / "broken.json"
        broken.write_text("{ this is not json", encoding="utf-8")
        result = run_script(["--offline", str(broken)], self.dir)
        self.assertEqual(result.returncode, 1)
        self.assertTrue(
            (self.dir / "assets/generated/profile-dark.svg").exists(),
            "previous SVG still there",
        )

    def test_check_mode_validates_generated(self):
        self._seed()
        result = run_script(["--check"], self.dir)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("OK", result.stdout)

    def test_no_tmp_files_left_behind(self):
        self._seed()
        leftovers = list((self.dir / "assets/generated").glob("*.tmp"))
        self.assertEqual(leftovers, [])

    def test_regenerate_is_deterministic(self):
        self._seed()
        first = (self.dir / "assets/generated/profile-dark.svg").read_text(encoding="utf-8")
        fixture = self.dir / "good.json"
        result = run_script(["--offline", str(fixture)], self.dir)
        self.assertEqual(result.returncode, 0, result.stderr)
        second = (self.dir / "assets/generated/profile-dark.svg").read_text(encoding="utf-8")
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
