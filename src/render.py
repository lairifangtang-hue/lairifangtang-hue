"""Renderer: CardLayout -> standalone SVG string.

Constraints baked in (GitHub README sanitizer):
- presentation attributes only; no <style>, no class attributes, no scripts
- system font stack via font-family attribute (no external fonts)
- one optional SMIL pulse on the glyph hub (pure SVG animation is allowed);
  the static card remains fully meaningful without it
- every dynamic string is XML-escaped at emit time
"""
from __future__ import annotations

import typing as t
from xml.sax.saxutils import escape as xml_escape

from . import glyph as glyph_mod
from .layout import CardLayout

FONT_STACK = (
    "ui-monospace, SFMono-Regular, 'Cascadia Mono', 'Segoe UI Mono', "
    "Menlo, 'Liberation Mono', monospace"
)

# role -> resolved hex per theme at render time
DARK = {
    "bg": "#0d1117",
    "panel": "#161b22",
    "fg": "#e6edf3",
    "muted": "#8b949e",
    "accent": "#7ee2a8",
    "dim": "#6e7681",
    "edge": "#30363d",
    "glyph_letter": "#e6edf3",
    "glyph_edge": "#3d5245",
    "glyph_sat": "#7ee2a8",
}

LIGHT = {
    "bg": "#f6f8fa",
    "panel": "#ffffff",
    "fg": "#1f2328",
    "muted": "#59636e",
    "accent": "#1a7f37",
    "dim": "#8c959f",
    "edge": "#d0d7de",
    "glyph_letter": "#1f2328",
    "glyph_edge": "#b6d3bf",
    "glyph_sat": "#1a7f37",
}


def esc(text: str) -> str:
    return xml_escape(text, {'"': "&quot;", "'": "&#x27;"})


def _fmt(value: float) -> str:
    return f"{value:.1f}".rstrip("0").rstrip(".") or "0"


def render(
    layout: CardLayout,
    handle: str,
    theme: t.Dict[str, str],
    *,
    pulse: bool = True,
    alt: str = "GitHub profile card",
) -> str:
    gx, gy, gscale = layout.glyph_box
    g = glyph_mod.build(handle)
    W, H = layout.width, layout.height

    parts: t.List[str] = []
    add = parts.append

    add(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{_fmt(W)}" '
        f'height="{_fmt(H)}" viewBox="0 0 {_fmt(W)} {_fmt(H)}" '
        f'role="img" alt="{esc(alt)}" '
        f'font-family="{esc(FONT_STACK)}">'
    )
    add(f'<title>{esc(alt)}</title>')
    add(f'<desc>{esc("Terminal-style profile card for " + handle)}</desc>')

    # panel
    rx = 14.0
    add(f'<rect width="{_fmt(W)}" height="{_fmt(H)}" rx="{_fmt(rx)}" fill="{theme["panel"]}"/>')
    add(
        f'<rect x="0.5" y="0.5" width="{_fmt(W - 1)}" height="{_fmt(H - 1)}" '
        f'rx="{_fmt(rx)}" fill="none" stroke="{theme["edge"]}" stroke-width="1"/>'
    )

    # window chrome: three small dots, quiet
    for i, col in enumerate(("edge", "edge", "accent")):
        add(
            f'<circle cx="{_fmt(20 + i * 16)}" cy="20" r="4" '
            f'fill="{theme[col]}" fill-opacity="0.55"/>'
        )

    # glyph ------------------------------------------------------------
    add(
        f'<g transform="translate({_fmt(gx)},{_fmt(gy)}) scale({_fmt(gscale)})">'
    )
    for edge in g.edges:
        add(
            f'<line x1="{_fmt(edge.a.x)}" y1="{_fmt(edge.a.y)}" '
            f'x2="{_fmt(edge.b.x)}" y2="{_fmt(edge.b.y)}" '
            f'stroke="{theme["glyph_edge"]}" stroke-width="1.4"/>'
        )
    for sat in g.satellites:
        fill = theme["glyph_sat"]
        opacity = ' fill-opacity="0.9"' if False else ""
        add(f'<circle cx="{_fmt(sat.x)}" cy="{_fmt(sat.y)}" r="{_fmt(sat.r)}" fill="{fill}"/>')
    add(
        f'<circle cx="{_fmt(g.hub.x)}" cy="{_fmt(g.hub.y)}" r="{_fmt(g.hub.r)}" '
        f'fill="{theme["glyph_sat"]}">'
    )
    if pulse:
        add(
            f'<animate attributeName="r" values="{_fmt(g.hub.r)};{_fmt(g.hub.r + 2.2)};'
            f'{_fmt(g.hub.r)}" dur="2.8s" repeatCount="indefinite"/>'
        )
    add("</circle>")
    for node in g.letters:
        add(
            f'<circle cx="{_fmt(node.x)}" cy="{_fmt(node.y)}" r="{_fmt(node.r)}" '
            f'fill="{theme["panel"]}" stroke="{theme["glyph_letter"]}" stroke-width="1.6"/>'
        )
        add(
            f'<text x="{_fmt(node.x)}" y="{_fmt(node.y + 6.0)}" text-anchor="middle" '
            f'font-size="20" font-weight="600" fill="{theme["glyph_letter"]}">'
            f'{esc(node.label)}</text>'
        )
    add("</g>")

    # text ---------------------------------------------------------------
    for span in layout.spans:
        attrs = [
            f'x="{_fmt(span.x)}"',
            f'y="{_fmt(span.y)}"',
            f'font-size="{_fmt(span.size)}"',
            f'font-weight="{span.weight}"',
            f'fill="{theme[span.fill]}"',
        ]
        if span.opacity is not None:
            attrs.append(f'fill-opacity="{span.opacity}"')
        add(f'<text {" ".join(attrs)}>{esc(span.text)}</text>')

    for (x1, y1, x2) in layout.rules:
        add(
            f'<line x1="{_fmt(x1)}" y1="{_fmt(y1)}" x2="{_fmt(x2)}" y2="{_fmt(y1)}" '
            f'stroke="{theme["edge"]}" stroke-width="1"/>'
        )

    add("</svg>")
    return "\n".join(parts)


def render_dark(layout: CardLayout, handle: str, **kw: t.Any) -> str:
    return render(layout, handle, DARK, **kw)


def render_light(layout: CardLayout, handle: str, **kw: t.Any) -> str:
    return render(layout, handle, LIGHT, **kw)
