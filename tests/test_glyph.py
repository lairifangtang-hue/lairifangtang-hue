"""Glyph determinism and structure."""
import unittest

from src import glyph


class GlyphTests(unittest.TestCase):
    def test_same_handle_same_glyph(self):
        a = glyph.build("lairifangtang-hue")
        b = glyph.build("lairifangtang-hue")
        self.assertEqual(
            [(n.x, n.y, n.r, n.label) for n in a.satellites],
            [(n.x, n.y, n.r, n.label) for n in b.satellites],
        )

    def test_different_handle_different_glyph(self):
        a = glyph.build("lairifangtang-hue")
        b = glyph.build("someone-else")
        sa = [(n.x, n.y) for n in a.satellites]
        sb = [(n.x, n.y) for n in b.satellites]
        self.assertNotEqual(sa, sb)

    def test_structure(self):
        g = glyph.build("lairifangtang-hue")
        self.assertEqual([n.label for n in g.letters], ["W", "E", "I"])
        self.assertGreaterEqual(len(g.satellites), glyph.MIN_SATS)
        self.assertLessEqual(len(g.satellites), glyph.MAX_SATS)
        # triangle + spokes + satellites
        self.assertEqual(len(g.edges), 3 + 3 + len(g.satellites))

    def test_all_nodes_inside_box(self):
        for handle in ("lairifangtang-hue", "x", "a-much-longer-handle-name"):
            g = glyph.build(handle)
            for n in list(g.letters) + list(g.satellites) + [g.hub]:
                self.assertGreaterEqual(n.x, 0, handle)
                self.assertLessEqual(n.x, glyph.BOX_W, handle)
                self.assertGreaterEqual(n.y, 0, handle)
                self.assertLessEqual(n.y, glyph.BOX_H, handle)


if __name__ == "__main__":
    unittest.main()
