"""Layout: measurement and word-wrapping for the profile card.

Layout is the only place that knows about character metrics. It converts a
fully-normalized model into positioned text lines so the renderer can stay
pure presentation. All widths are estimated from a conservative monospace
ratio and re-checked against real font metrics at test time.

Card geometry targets mobile readability: a ~620px-wide card keeps body
text at >= 9px when GitHub scales it into a ~360px phone viewport.
"""
from __future__ import annotations

import typing as t
from dataclasses import dataclass, field

from .config import ProfileConfig
from .models import ProfileData

# ---------------------------------------------------------------- metrics
CHAR_W_RATIO = 0.62          # advance width / font size, conservative mono
LINE_H_RATIO = 1.55          # line height / font size

PAD_X = 28.0                 # card inner padding
PAD_Y = 26.0
GUTTER = 38.0                # gap between glyph column and text column
GLYPH_SCALE = 0.78           # glyph module is 196 wide; scale to fit
BODY_SIZE = 15.5
LABEL_SIZE = 13.0
TITLE_SIZE = 16.0
BANNER_SIZE = 18.0
SECTIONS = ("identity", "now", "projects", "signal")
SECTION_GAP = 22.0


@dataclass(frozen=True)
class Span:
    """One run of text at a place in the card."""

    x: float
    y: float
    text: str
    size: float
    weight: str = "normal"
    fill: str = "fg"          # theme role: fg / muted / accent / dim / bg
    opacity: t.Optional[float] = None


@dataclass
class CardLayout:
    """Result of laying the card out."""

    width: float
    height: float
    spans: t.List[Span] = field(default_factory=list)
    rules: t.List[t.Tuple[float, float, float]] = field(default_factory=list)
    glyph_box: t.Tuple[float, float, float] = (0.0, 0.0, 1.0)
    banner: str = ""
    links: t.List[t.Tuple[float, float, str, str]] = field(default_factory=list)

    def span_count(self) -> int:
        return len(self.spans)


def text_width(text: str, size: float) -> float:
    return len(text) * size * CHAR_W_RATIO


def wrap(text: str, max_chars: int) -> t.List[str]:
    """Greedy word wrap; hard-splits unbreakable runs (URLs, long names)."""
    if not text:
        return []
    out: t.List[str] = []
    for raw_line in text.split("\n"):
        for word in raw_line.split(" "):
            if not word:
                continue
            # hard-split words that cannot fit on a line of their own
            while len(word) > max_chars:
                out.append(word[:max_chars])
                word = word[max_chars:]
            if not word:
                continue
            if out and not out[-1].endswith("\x00") and len(out[-1]) + 1 + len(word) <= max_chars:
                out[-1] = out[-1] + " " + word
            elif out and out[-1].endswith("\x00"):
                out[-1] = out[-1][:-1] + " " + word
                if len(out[-1]) > max_chars:  # defensive; shouldn't happen
                    out.append(word)
            else:
                out.append(word)
    return out


def truncate(text: str, max_chars: int, ellipsis: str = "…") -> str:
    if len(text) <= max_chars:
        return text
    cut = text[: max_chars - 1].rstrip()
    return cut + ellipsis


# ---------------------------------------------------------------- content
def identity_rows(cfg: ProfileConfig, data: ProfileData) -> t.List[t.Tuple[str, str]]:
    ident = cfg.identity
    rows: t.List[t.Tuple[str, str]] = []
    role = ident.role or _infer_role(data)
    if role:
        rows.append(("Role", role))
    base = ident.base or data.location
    if base:
        rows.append(("Base", base))
    affil = ident.affiliation or data.company
    if affil:
        rows.append(("Affil", affil))
    if cfg.focus:
        for i in range(0, len(cfg.focus), 2):
            chunk = " · ".join(cfg.focus[i : i + 2])
            rows.append(("Focus", chunk) if i == 0 else ("", chunk))
    site = ident.website or data.blog
    if site:
        rows.append(("Site", truncate(site, 30)))
    return rows


def _infer_role(data: ProfileData) -> t.Optional[str]:
    langs = {l.lower() for l in data.languages}
    if not langs:
        return None
    if any(l in langs for l in ("python", "jupyter notebook")) and any(
        l in langs for l in ("typescript", "javascript")
    ):
        return "AI · Software · Research"
    if any(l in langs for l in ("python", "jupyter notebook")):
        return "AI · Research"
    return "Software"


def now_rows(cfg: ProfileConfig) -> t.List[t.Tuple[str, str]]:
    n = cfg.now
    rows = []
    if n.building:
        rows.append(("Building", n.building))
    if n.learning:
        rows.append(("Learning", n.learning))
    if n.exploring:
        rows.append(("Exploring", n.exploring))
    if n.reading:
        rows.append(("Reading", n.reading))
    return rows


def project_rows(cfg: ProfileConfig, data: ProfileData) -> t.List[t.Tuple[str, str, str]]:
    """(name, display-description, url) for featured projects, in config order."""
    out = []
    for fp in cfg.featured_projects:
        repo = data.repo(fp.repo)
        note = fp.note
        if repo is None:
            desc = note or "—"
            url = ""
        else:
            desc = note if note else (repo.description or "")
            url = repo.html_url
        out.append((fp.repo, desc or "—", url))
    return out


# ---------------------------------------------------------------- layout
def lay_out(
    cfg: ProfileConfig,
    data: ProfileData,
    *,
    signal_text: t.Optional[str] = None,
    generated_text: str = "",
    languages_text: str = "",
) -> CardLayout:
    from . import glyph as glyph_mod

    body_lh = BODY_SIZE * LINE_H_RATIO

    glyph_w = glyph_mod.BOX_W * GLYPH_SCALE
    text_x0 = PAD_X + glyph_w + GUTTER
    usable_w = 620.0 - text_x0 - PAD_X          # text column width
    label_gutter = 10 * BODY_SIZE * CHAR_W_RATIO + 10.0
    value_x = text_x0 + label_gutter
    max_value_chars = max(12, int((usable_w - label_gutter) / (BODY_SIZE * CHAR_W_RATIO)))

    spans: t.List[Span] = []
    rules: t.List[t.Tuple[float, float, float]] = []

    def section_header(y: float, title: str) -> float:
        spans.append(Span(text_x0, y, title, TITLE_SIZE, "600", "muted", 0.92))
        rules.append((text_x0, y + 8.0, text_x0 + usable_w))
        return y + TITLE_SIZE * 1.2 + 12.0

    def kv_rows(y: float, rows: t.List[t.Tuple[str, str]]) -> float:
        for label, value in rows:
            lines = wrap(value, max_value_chars)
            first = True
            for ln in lines:
                if first and label:
                    spans.append(Span(text_x0, y, label, BODY_SIZE, "400", "accent"))
                spans.append(Span(value_x, y, ln, BODY_SIZE, "400", "fg"))
                first = False
                y += body_lh
        return y

    # -- banner / handle ------------------------------------------------
    handle = cfg.identity.handle or data.handle
    banner = f"{handle}@github"
    spans.append(Span(text_x0, PAD_Y + BANNER_SIZE * 0.9, banner, BANNER_SIZE, "600", "fg"))
    y = PAD_Y + BANNER_SIZE * 1.9

    # -- identity --------------------------------------------------------
    y = section_header(y, "IDENTITY")
    y = kv_rows(y, identity_rows(cfg, data))
    y += SECTION_GAP

    # -- now -------------------------------------------------------------
    if now_rows(cfg):
        y = section_header(y, "NOW")
        y = kv_rows(y, now_rows(cfg))
        y += SECTION_GAP

    # -- projects ----------------------------------------------------------
    prows = project_rows(cfg, data)
    if prows:
        y = section_header(y, "SELECTED WORK")
        name_chars = int(usable_w / (BODY_SIZE * CHAR_W_RATIO)) - 2
        desc_chars = max(10, int((usable_w - 20.0) / (BODY_SIZE * CHAR_W_RATIO)))
        for name, desc, url in prows:
            spans.append(Span(text_x0, y, "●", BODY_SIZE, "400", "accent"))
            spans.append(
                Span(text_x0 + 18.0, y, truncate(name, name_chars), BODY_SIZE, "600", "fg")
            )
            y += body_lh
            spans.append(
                Span(text_x0 + 18.0, y, truncate(desc, desc_chars), BODY_SIZE * 0.92, "400", "muted")
            )
            y += body_lh * 0.96
        y += SECTION_GAP

    # -- signal ----------------------------------------------------------
    y = section_header(y, "SIGNAL")
    sig_rows: t.List[t.Tuple[str, str]] = []
    if languages_text:
        sig_rows.append(("Langs", languages_text))
    if signal_text:
        sig_rows.append(("Last", signal_text))
    if generated_text:
        sig_rows.append(("Updated", generated_text))
    y = kv_rows(y, sig_rows)
    y += SECTION_GAP

    glyph_h = glyph_mod.BOX_H * GLYPH_SCALE
    height = max(y, PAD_Y * 2 + glyph_h) + PAD_Y * 0.4
    width = 620.0

    return CardLayout(
        width=width,
        height=height,
        spans=spans,
        rules=rules,
        glyph_box=(PAD_X, (height - glyph_h) / 2.0, GLYPH_SCALE),
        banner=banner,
    )
