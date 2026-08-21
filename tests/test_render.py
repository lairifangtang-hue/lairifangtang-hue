"""XML escaping and renderer output safety."""
import unittest

from src import layout as layout_mod
from src import render as render_mod
from xml.etree import ElementTree as ET

from .helpers import make_config, make_data


def build_layout(cfg=None, data=None):
    cfg = cfg or make_config()
    data = data or make_data()
    return layout_mod.lay_out(
        cfg,
        data,
        signal_text="diffusion-model-mnist · 3mo ago",
        generated_text="2026-08-22",
        languages_text="Python · TypeScript · Jupyter Notebook",
    )


class Escaping(unittest.TestCase):
    def test_esc_function(self):
        esc = render_mod.esc('<&"\'')
        self.assertEqual(esc, "&lt;&amp;&quot;&#x27;")

    def test_dynamic_data_with_markup_is_escaped(self):
        cfg = make_config()
        cfg.featured_projects[0].note = '<script>alert("x")</script> & more'
        lay = build_layout(cfg=cfg)
        dark = render_mod.render_dark(lay, "wei")
        self.assertNotIn("<script>", dark)
        self.assertIn("&lt;script&gt;", dark)
        ET.fromstring(dark)  # still valid XML

    def test_quote_and_ampersand_in_banner(self):
        cfg = make_config()
        cfg.identity.handle = 'we"i & co'
        lay = build_layout(cfg=cfg)
        svg = render_mod.render_dark(lay, 'we"i & co')
        ET.fromstring(svg)
        self.assertNotIn('we"i', svg)


class RendererOutput(unittest.TestCase):
    def test_basic_shape(self):
        lay = build_layout()
        svg = render_mod.render_dark(lay, "wei")
        self.assertTrue(svg.startswith("<svg"))
        self.assertTrue(svg.endswith("</svg>"))
        root = ET.fromstring(svg)
        self.assertEqual(root.tag, "{http://www.w3.org/2000/svg}svg")
        self.assertIn("viewBox", root.attrib)

    def test_no_banned_constructs(self):
        for theme_svg in (
            render_mod.render_dark(build_layout(), "wei"),
            render_mod.render_light(build_layout(), "wei"),
        ):
            low = theme_svg.lower()
            for bad in ("<script", "foreignobject", "javascript:", "xlink:href", "<style", "@import"):
                self.assertNotIn(bad, low)

    def test_dark_and_light_differ(self):
        lay = build_layout()
        dark = render_mod.render_dark(lay, "wei")
        light = render_mod.render_light(lay, "wei")
        self.assertNotEqual(dark, light)
        # dark panel is darker than light panel
        self.assertIn("#161b22", dark)
        self.assertIn("#ffffff", light)

    def test_pulse_is_static_safe(self):
        lay = build_layout()
        with_pulse = render_mod.render_dark(lay, "wei", pulse=True)
        without = render_mod.render_dark(lay, "wei", pulse=False)
        self.assertIn("<animate", with_pulse)
        self.assertNotIn("<animate", without)
        ET.fromstring(with_pulse)
        ET.fromstring(without)

    def test_deterministic_output(self):
        lay = build_layout()
        a = render_mod.render_dark(lay, "wei")
        b = render_mod.render_dark(lay, "wei")
        self.assertEqual(a, b)


class LayoutEdgeCases(unittest.TestCase):
    def test_empty_featured_projects(self):
        cfg = make_config(featured_projects=[])
        lay = build_layout(cfg=cfg)
        texts = [s.text for s in lay.spans]
        self.assertNotIn("SELECTED WORK", texts)

    def test_missing_optional_fields(self):
        cfg = make_config()
        cfg.identity.role = None
        cfg.identity.base = None
        cfg.identity.affiliation = None
        cfg.now.building = None
        data = make_data(location=None, company=None, signal=None)
        lay = build_layout(cfg=cfg, data=data)
        svg = render_mod.render_dark(lay, "wei")
        ET.fromstring(svg)
        texts = [s.text for s in lay.spans]
        # fallback role inferred from languages present
        self.assertIn("Role", texts)

    def test_long_repo_description_truncated(self):
        cfg = make_config()
        cfg.featured_projects[0].note = None
        data = make_data()
        for r in data.repos:
            if r.name == "Zero-shot-Agent":
                object.__setattr__(r, "description", "x" * 500)
        lay = build_layout(cfg=cfg, data=data)
        for span in lay.spans:
            self.assertLessEqual(len(span.text), 80)

    def test_wrap_hard_splits_long_words(self):
        lines = layout_mod.wrap("a" * 100, 30)
        self.assertTrue(all(len(ln) <= 30 for ln in lines))
        self.assertEqual("".join(lines).replace(" ", ""), "a" * 100)

    def test_wrap_greedy(self):
        self.assertEqual(layout_mod.wrap("aaa bbb ccc", 7), ["aaa bbb", "ccc"])
        self.assertEqual(layout_mod.wrap("", 10), [])

    def test_truncate(self):
        self.assertEqual(layout_mod.truncate("abcdef", 4), "abc…")
        self.assertEqual(layout_mod.truncate("ab", 4), "ab")


if __name__ == "__main__":
    unittest.main()
