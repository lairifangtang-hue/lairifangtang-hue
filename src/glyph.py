"""Procedural identity glyph: a deterministic node-graph monogram.

The letters W, E and I sit at the vertices of a triangle around a small
accent hub. Satellite nodes are placed on an ellipse at slot angles chosen
by a hash of the handle — same handle, same glyph, forever; a different
handle yields a different topology. The glyph is decorative by design:
nothing essential is expressed only here (the right-hand column carries all
information), which keeps the card accessible.
"""
from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from typing import Optional

BOX_W, BOX_H = 196.0, 248.0
CX, CY = BOX_W / 2, 124.0
TRI_R = 84.0
LETTER_R = 17.0
HUB_R = 4.6
SAT_R = 2.6
RING_RX, RING_RY = 88.0, 110.0
_SLOTS = (30, 90, 150, 210, 270, 330)
MIN_SATS, MAX_SATS = 3, 4


@dataclass(frozen=True)
class GNode:
    x: float
    y: float
    r: float = 0.0
    label: Optional[str] = None
    kind: str = "dot"


@dataclass(frozen=True)
class GEdge:
    a: GNode
    b: GNode


@dataclass(frozen=True)
class Glyph:
    letters: tuple
    hub: GNode
    satellites: tuple
    edges: tuple

    @property
    def node_count(self) -> int:
        return len(self.letters) + 1 + len(self.satellites)

    @property
    def edge_count(self) -> int:
        return len(self.edges)


def _vertex(angle_deg: float, radius: float) -> tuple:
    a = math.radians(angle_deg)
    return (CX + radius * math.cos(a), CY - radius * math.sin(a))


def build(handle: str) -> Glyph:
    digest = hashlib.sha256(handle.encode("utf-8")).digest()
    chosen = [
        slot
        for i, slot in enumerate(_SLOTS)
        if (digest[i // 8] >> (i % 8)) & 1
    ]
    while len(chosen) < MIN_SATS:
        for slot in _SLOTS:
            if slot not in chosen:
                chosen.append(slot)
                break
    chosen = chosen[:MAX_SATS]

    # W bottom-left, E top, I bottom-right: the triangle reads "WEI" around.
    letters = (
        GNode(*_vertex(210, TRI_R), LETTER_R, "W", "letter"),
        GNode(*_vertex(90, TRI_R), LETTER_R, "E", "letter"),
        GNode(*_vertex(330, TRI_R), LETTER_R, "I", "letter"),
    )
    hub = GNode(CX, CY, HUB_R, None, "hub")

    edges = [
        GEdge(letters[0], letters[1]),
        GEdge(letters[1], letters[2]),
        GEdge(letters[0], letters[2]),
        GEdge(letters[0], hub),
        GEdge(letters[1], hub),
        GEdge(letters[2], hub),
    ]

    satellites = []
    for angle in chosen:
        a = math.radians(angle)
        sat = GNode(
            CX + RING_RX * math.cos(a),
            CY - RING_RY * math.sin(a),
            SAT_R,
            None,
            "satellite",
        )
        nearest = min(letters, key=lambda n: (n.x - sat.x) ** 2 + (n.y - sat.y) ** 2)
        edges.append(GEdge(sat, nearest))
        satellites.append(sat)

    return Glyph(
        letters=letters,
        hub=hub,
        satellites=tuple(satellites),
        edges=tuple(edges),
    )
