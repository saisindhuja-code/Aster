"""Character asset definitions and layer resolution (Qt-free so it can be tested).

Layer stack (bottom → top), all PNGs share one canvas size (720 x 960 shipped):
    characters/aster/hair_back.png
    outfits/<outfit>/back.png        (optional: cape, hood)
    characters/aster/head.png
    outfits/<outfit>/body.png        (required for the outfit to be "available")
    characters/aster/hair_front.png
    expressions/<expression>.png     (or <expression>_blink.png while blinking)
    outfits/<outfit>/top.png         (optional: crown, glasses, hat)

A complete hand-drawn frame can override the layers:
    characters/aster/sprites/<outfit>/<expression>.png  (and <expression>_blink.png)
"""
from __future__ import annotations

import os

from .. import paths

OUTFITS = {
    "royal_black_gold": "Black & Gold Royal",
    "royal_academy": "Royal Academy Uniform",
    "casual_hoodie": "Casual Hoodie",
    "study": "Study Prince",
    "winter": "Winter Coat",
    "sleepwear": "Sleepwear",
}
# v2-compatible labels (written to the old 'outfit' setting so Aster v2 still shows something sensible)
V2_LABELS = {
    "royal_black_gold": "Royal uniform", "royal_academy": "Royal uniform", "casual_hoodie": "Casual hoodie",
    "study": "Study prince", "winter": "Winter coat", "sleepwear": "Sleepwear",
}

EXPRESSIONS = ["idle", "happy", "smug", "curious", "thinking", "sleepy", "focused", "encouraging"]
MODES = ["Normal", "Focus", "Study", "Coding", "Rest"]


def outfit_status(outfit: str, root: str | None = None) -> dict:
    root = root or paths.ASSETS_DIR
    d = os.path.join(root, "outfits", outfit)
    sprites = os.path.join(root, "characters", "aster", "sprites", outfit)
    has_body = os.path.exists(os.path.join(d, "body.png"))
    has_sprites = os.path.isdir(sprites) and any(f.endswith(".png") for f in os.listdir(sprites))
    return {"id": outfit, "label": OUTFITS.get(outfit, outfit), "available": has_body or has_sprites,
            "missing": [] if (has_body or has_sprites) else [os.path.join("assets", "outfits", outfit, "body.png")]}


def layers_for(outfit: str, expression: str, blink: bool = False, root: str | None = None) -> tuple[list[str], list[str]]:
    """Return (existing layer paths in draw order, missing required files)."""
    root = root or paths.ASSETS_DIR
    expr = expression if expression in EXPRESSIONS else "idle"
    sprite_dir = os.path.join(root, "characters", "aster", "sprites", outfit)
    for name in ([f"{expr}_blink.png"] if blink else []) + [f"{expr}.png"]:
        p = os.path.join(sprite_dir, name)
        if os.path.exists(p):
            return [p], []
    c = os.path.join(root, "characters", "aster")
    o = os.path.join(root, "outfits", outfit)
    e = os.path.join(root, "expressions")
    expr_file = os.path.join(e, f"{expr}_blink.png") if blink else os.path.join(e, f"{expr}.png")
    if blink and not os.path.exists(expr_file):
        expr_file = os.path.join(e, f"{expr}.png")
    stack = [
        (os.path.join(c, "hair_back.png"), True),
        (os.path.join(o, "back.png"), False),
        (os.path.join(c, "head.png"), True),
        (os.path.join(o, "body.png"), True),
        (os.path.join(c, "hair_front.png"), True),
        (expr_file, True),
        (os.path.join(o, "top.png"), False),
    ]
    existing = [p for p, _ in stack if os.path.exists(p)]
    missing = [os.path.relpath(p, os.path.dirname(root)) for p, req in stack if req and not os.path.exists(p)]
    return existing, missing
