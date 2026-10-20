"""
Aster artwork generator (developer tool — NOT needed to run the app).

Draws Aster, the anime prince, as layered vector art and renders each layer to
a transparent PNG.  All layers share one canvas (480 x 640 design units) so the
app can stack them:

    hair_back -> outfit back -> head -> outfit body -> expression -> hair_front -> outfit top

Usage (from the project folder):
    python tools/build_art.py            # renders PNGs into assets/
    python tools/build_art.py --svg      # also writes the .svg sources

Rendering backends (first one found is used):
    1. cairosvg  (pip install cairosvg)          — needs the Cairo DLL on Windows
    2. playwright (pip install playwright; playwright install chromium)

The finished PNGs are shipped with the app, so you only need this script if you
want to change or extend the artwork.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(ROOT, "assets")
W, H = 480, 640
SCALE = 1.5  # PNG pixels per design unit -> 720 x 960 PNGs

OL = "#2b2342"          # outline
SKIN = "#fdebe3"
SKIN_SH = "#f2cdc6"
SKIN_SH2 = "#e6b4ad"
HAIR = "#e3ddf6"
HAIR_SH = "#bdb3e6"
HAIR_SH2 = "#9c90d2"
HAIR_HI = "#fbfaff"
IRIS_TOP = "#4b3492"
IRIS_MID = "#8f72e6"
IRIS_BOT = "#c9b8ff"
GOLD = "#e7bf5f"
GOLD_SH = "#b88a2e"
GOLD_HI = "#fff0b8"


def svg(body: str, defs: str = "") -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
            f'viewBox="0 0 {W} {H}"><defs>{defs}</defs>{body}</svg>')


def mirror(group: str) -> str:
    """Mirror a group around the vertical centre line x=240."""
    return f'<g transform="translate({W},0) scale(-1,1)">{group}</g>'


# ----------------------------------------------------------------------------
# Hair
# ----------------------------------------------------------------------------
HAIR_DEFS = f"""
<linearGradient id="hairG" x1="0" y1="0" x2="0" y2="1">
  <stop offset="0" stop-color="{HAIR_HI}"/><stop offset=".35" stop-color="{HAIR}"/>
  <stop offset="1" stop-color="{HAIR_SH}"/></linearGradient>
<linearGradient id="hairBackG" x1="0" y1="0" x2="0" y2="1">
  <stop offset="0" stop-color="{HAIR_SH}"/><stop offset="1" stop-color="{HAIR_SH2}"/></linearGradient>
"""


def hair_back() -> str:
    p = ("M128,215 C112,120 178,64 240,64 C302,64 368,120 352,215 "
         "C358,250 362,290 356,330 L338,300 L334,352 L312,318 L300,360 L282,326 "
         "L240,340 L198,326 L180,360 L168,318 L146,352 L142,300 L124,330 "
         "C118,290 122,250 128,215 Z")
    body = f'<path d="{p}" fill="url(#hairBackG)" stroke="{OL}" stroke-width="3" stroke-linejoin="round"/>'
    # a few darker strands
    body += (f'<path d="M150,250 L146,330 M330,250 L334,330 M176,280 L170,340 M304,280 L310,340" '
             f'stroke="{HAIR_SH2}" stroke-width="3" stroke-linecap="round" opacity=".7"/>')
    return svg(body, HAIR_DEFS)


def _lock(root, tip, w, bend, fill="url(#hairLockG)") -> str:
    """A tapered, curved lock of hair from root to a pointed tip."""
    (rx, ry), (tx, ty) = root, tip
    dx, dy = tx - rx, ty - ry
    ln = math.hypot(dx, dy) or 1
    nx, ny = -dy / ln, dx / ln
    lx, ly = rx - nx * w / 2, ry - ny * w / 2
    gx, gy = rx + nx * w / 2, ry + ny * w / 2
    mx, my = rx + dx * 0.55 + nx * bend, ry + dy * 0.55 + ny * bend
    c1 = (mx - nx * w * 0.38, my - ny * w * 0.38)
    c2 = (mx + nx * w * 0.38, my + ny * w * 0.38)
    d = (f"M{lx:.1f},{ly:.1f} Q{c1[0]:.1f},{c1[1]:.1f} {tx:.1f},{ty:.1f} "
         f"Q{c2[0]:.1f},{c2[1]:.1f} {gx:.1f},{gy:.1f} Z")
    shade = (f"M{rx + dx * 0.35 + nx * bend * 0.5:.1f},{ry + dy * 0.35 + ny * bend * 0.5:.1f} "
             f"Q{mx:.1f},{my:.1f} {tx - dx * 0.08:.1f},{ty - dy * 0.08:.1f}")
    return d, shade


FRINGE = [  # (root, tip, width, bend)
    ((176, 120), (148, 266), 40, -12),
    ((196, 112), (178, 228), 38, -8),
    ((216, 108), (206, 218), 34, -4),
    ((234, 106), (238, 204), 30, 5),
    ((252, 106), (264, 222), 34, 8),
    ((272, 108), (292, 228), 38, 10),
    ((292, 114), (318, 238), 36, 10),
    ((306, 120), (336, 268), 40, 12),
]
CROSS_LOCK = ((246, 102), (212, 226), 26, -16)


def hair_front() -> str:
    defs = HAIR_DEFS + (f'<linearGradient id="hairLockG" gradientUnits="userSpaceOnUse" x1="0" y1="96" x2="0" y2="262">'
                        f'<stop offset="0" stop-color="{HAIR_HI}"/><stop offset=".3" stop-color="{HAIR}"/>'
                        f'<stop offset=".8" stop-color="{HAIR_SH}"/><stop offset="1" stop-color="{HAIR_SH2}"/></linearGradient>')
    dome = "M136,214 C124,120 184,82 240,82 C300,82 358,120 344,214 Q240,150 136,214 Z"
    shapes, shades = [dome], []
    # side locks framing the face (left, then mirrored)
    side = ("M150,186 C136,232 134,292 126,342 C144,320 152,302 157,290 C159,308 159,322 154,338 "
            "C170,310 175,272 171,236 C169,212 161,196 150,186 Z")
    for root, tip, w, bend in FRINGE + [CROSS_LOCK]:
        d, sh = _lock(root, tip, w, bend)
        shapes.append(d)
        shades.append(sh)
    clip = "".join(f'<path d="{d}"/>' for d in shapes)
    defs += f'<clipPath id="hairclip">{clip}</clipPath>'
    out = ""
    side_g = (f'<path d="{side}" fill="url(#hairLockG)" stroke="{OL}" stroke-width="3" stroke-linejoin="round"/>'
              f'<path d="M153,210 C148,250 145,292 137,326" stroke="{HAIR_SH2}" stroke-width="2.5" fill="none" '
              f'stroke-linecap="round" opacity=".6"/>'
              f'<path d="M160,226 C160,260 158,290 152,318" stroke="{HAIR_HI}" stroke-width="2" fill="none" '
              f'stroke-linecap="round" opacity=".8"/>')
    out += side_g + mirror(side_g)
    # fringe locks, left to right, then the swept lock on top
    for (root, tip, w, bend), d, sh in zip(FRINGE + [CROSS_LOCK], shapes[1:], shades):
        out += f'<path d="{d}" fill="url(#hairLockG)" stroke="{OL}" stroke-width="2.6" stroke-linejoin="round"/>'
        out += f'<path d="{sh}" stroke="{HAIR_SH2}" stroke-width="2" fill="none" stroke-linecap="round" opacity=".55"/>'
    # crown of the head drawn over the lock roots: filled, outlined only on the outside
    crown_fill = "M134,216 C122,120 184,80 240,80 C300,80 360,120 346,216 C330,176 300,150 240,146 C180,150 150,176 134,216 Z"
    out += f'<path d="{crown_fill}" fill="url(#hairLockG)"/>'
    out += (f'<path d="M136,214 C124,120 184,82 240,82 C300,82 358,120 344,214" fill="none" stroke="{OL}" '
            f'stroke-width="3" stroke-linecap="round"/>')
    # parting lines flowing from the crown into the locks
    for x1, y1, x2, y2 in [(200, 100, 182, 168), (222, 92, 214, 156), (258, 92, 266, 156), (284, 100, 300, 168),
                           (170, 120, 156, 186), (312, 120, 326, 186)]:
        out += (f'<path d="M{x1},{y1} Q{(x1 + x2) / 2 + 3},{(y1 + y2) / 2} {x2},{y2}" stroke="{HAIR_SH}" '
                f'stroke-width="2.4" fill="none" stroke-linecap="round" opacity=".75"/>')
    # anime shine: a broken highlight band clipped to the hair
    out += (f'<g clip-path="url(#hairclip)">'
            f'<path d="M152,146 Q240,100 328,146" stroke="#ffffff" stroke-width="8" fill="none" '
            f'stroke-dasharray="38 9 26 9" stroke-linecap="round" opacity=".75"/>'
            f'<path d="M140,236 Q240,200 340,236" stroke="{HAIR_SH2}" stroke-width="16" fill="none" opacity=".18"/>'
            f'</g>')
    # ahoge (cowlick)
    out += (f'<path d="M238,86 C236,64 250,48 272,46 C258,56 250,70 249,88 Z" fill="url(#hairLockG)" '
            f'stroke="{OL}" stroke-width="3" stroke-linejoin="round"/>')
    return svg(out, defs)


# ----------------------------------------------------------------------------
# Head (neck, ears, face skin)
# ----------------------------------------------------------------------------
def head() -> str:
    defs = f"""
<linearGradient id="skinG" x1="0" y1="0" x2="0" y2="1">
  <stop offset="0" stop-color="{SKIN_SH}"/><stop offset=".25" stop-color="{SKIN}"/>
  <stop offset="1" stop-color="{SKIN}"/></linearGradient>"""
    b = ""
    # neck
    b += (f'<path d="M222,300 L222,352 Q240,362 258,352 L258,300 Z" fill="{SKIN}" stroke="{OL}" '
          f'stroke-width="3"/>')
    b += f'<path d="M222,318 Q240,336 258,318 L258,300 L222,300 Z" fill="{SKIN_SH}"/>'
    # ears
    ear = (f'<path d="M152,232 C136,224 132,252 140,266 C146,276 154,276 158,270 Z" fill="{SKIN}" '
           f'stroke="{OL}" stroke-width="3" stroke-linejoin="round"/>'
           f'<path d="M148,244 C142,248 144,260 150,264" stroke="{SKIN_SH2}" stroke-width="2.5" fill="none"/>')
    b += ear + mirror(ear)
    # face
    face = "M150,188 C148,262 186,306 240,330 C294,306 332,262 330,188 C330,118 150,118 150,188 Z"
    b += f'<path d="{face}" fill="url(#skinG)" stroke="{OL}" stroke-width="3" stroke-linejoin="round"/>'
    # jaw shadow line hint + nose
    b += f'<path d="M238,276 L242,282" stroke="{SKIN_SH2}" stroke-width="2.5" stroke-linecap="round"/>'
    return svg(b, defs)


# ----------------------------------------------------------------------------
# Expressions (eyes, brows, mouth, blush)
# ----------------------------------------------------------------------------
EYE_L = (199, 248)
EYE_R = (281, 248)


def eye_open(openness=1.0, look=(0.0, 0.0), lid_flat=False, sparkle=1.0, uid="a") -> str:
    """Left eye drawn around (0,0); outer corner is at -x."""
    yt = -22 + (1 - openness) * 32
    if lid_flat:
        top = f"M-26,{yt+7:.1f} C-13,{yt:.1f} 12,{yt-1:.1f} 26,{yt+4:.1f}"
    else:
        top = f"M-26,{yt+12:.1f} C-17,{yt-4:.1f} 12,{yt-7:.1f} 26,{yt+5:.1f}"
    sclera = f"{top} L23,17 C11,27 -12,27 -22,14 Z"
    lx, ly = look
    cx, cy = 2 + lx, 4 + ly
    clip_id, grad_id, glow_id = f"eyeclip{uid}", f"irisG{uid}", f"irisGlow{uid}"
    defs = (f'<clipPath id="{clip_id}"><path d="{sclera}"/></clipPath>'
            f'<linearGradient id="{grad_id}" x1="0" y1="0" x2="0" y2="1">'
            f'<stop offset="0" stop-color="#32206e"/><stop offset=".45" stop-color="{IRIS_MID}"/>'
            f'<stop offset="1" stop-color="#d9ccff"/></linearGradient>'
            f'<radialGradient id="{glow_id}" cx=".5" cy=".85" r=".55">'
            f'<stop offset="0" stop-color="#f3edff" stop-opacity=".95"/><stop offset="1" stop-color="#f3edff" stop-opacity="0"/>'
            f'</radialGradient>')
    g = f'<path d="{sclera}" fill="#fbf9ff"/>'
    g += f'<g clip-path="url(#{clip_id})">'
    g += f'<path d="{sclera}" fill="#cfc4ee" opacity=".45" transform="translate(0,-6)"/>'  # soft lid shadow on the white
    g += f'<ellipse cx="{cx}" cy="{cy}" rx="18" ry="24" fill="url(#{grad_id})" stroke="#2a1b5a" stroke-width="2.4"/>'
    g += f'<ellipse cx="{cx}" cy="{cy + 9}" rx="14" ry="12" fill="url(#{glow_id})"/>'
    g += f'<ellipse cx="{cx}" cy="{cy}" rx="12.5" ry="17.5" fill="none" stroke="#6c55c4" stroke-width="1.4" opacity=".7"/>'
    for ang in range(0, 360, 30):  # fine iris fibres
        a = math.radians(ang)
        g += (f'<path d="M{cx + 9 * math.cos(a):.1f},{cy + 12 * math.sin(a):.1f} L{cx + 15 * math.cos(a):.1f},'
              f'{cy + 20 * math.sin(a):.1f}" stroke="#b9a6ff" stroke-width="1" opacity=".45"/>')
    g += f'<ellipse cx="{cx}" cy="{cy + 1}" rx="7.5" ry="11.5" fill="#1e1240"/>'
    g += f'<path d="{top} L26,{yt+17:.1f} C11,{yt+10:.1f} -12,{yt+12:.1f} -26,{yt+21:.1f} Z" fill="#3d2a78" opacity=".45"/>'
    if sparkle:
        sp = sparkle
        g += (f'<ellipse cx="{cx - 6}" cy="{cy - 8 + (1 - openness) * 12:.1f}" rx="{6 * sp:.1f}" ry="{8 * sp:.1f}" '
              f'fill="#ffffff" transform="rotate(-20 {cx - 6} {cy - 8})"/>')
        g += f'<circle cx="{cx + 8}" cy="{cy + 11}" r="{3 * sp:.1f}" fill="#ffffff"/>'
        g += f'<circle cx="{cx + 4}" cy="{cy - 12 + (1 - openness) * 12:.1f}" r="{1.8 * sp:.1f}" fill="#ffffff" opacity=".9"/>'
    g += '</g>'
    # upper lash line (tapered, heavier on the outer side) + lash flicks
    g += f'<path d="{top} L27,{yt+10:.1f} C12,{yt+1:.1f} -15,{yt+3:.1f} -24,{yt+18:.1f} Z" fill="{OL}"/>'
    g += (f'<path d="M-25,{yt+12:.1f} L-34,{yt+16:.1f} L-23,{yt+17:.1f} Z M-21,{yt+5:.1f} L-30,{yt+3:.1f} '
          f'L-18,{yt+9:.1f} Z M-12,{yt:.1f} L-17,{yt-6:.1f} L-8,{yt+1:.1f} Z" fill="{OL}"/>')
    # eyelid crease
    if openness > 0.6:
        g += (f'<path d="M-20,{yt-4:.1f} C-8,{yt-12:.1f} 10,{yt-13:.1f} 22,{yt-5:.1f}" stroke="#c7948f" '
              f'stroke-width="1.8" fill="none" stroke-linecap="round" opacity=".8"/>')
    # lower lash
    g += ('<path d="M-17,22 Q-2,27 14,20" stroke="#7a6896" stroke-width="2.2" fill="none" stroke-linecap="round"/>'
          '<path d="M-19,19 L-22,23" stroke="#7a6896" stroke-width="1.8" stroke-linecap="round"/>')
    return defs, g


def eye_closed(kind="down") -> str:
    if kind == "happy":  # ^  arc
        return "", (f'<path d="M-22,10 Q-2,-14 22,6" stroke="{OL}" stroke-width="5" fill="none" '
                    f'stroke-linecap="round"/>')
    # gentle closed lid ‿ with lashes
    return "", (f'<path d="M-24,4 Q0,16 24,2" stroke="{OL}" stroke-width="4.5" fill="none" stroke-linecap="round"/>'
                f'<path d="M-20,9 l-5,6 M-8,13 l-2,6" stroke="{OL}" stroke-width="2.5" stroke-linecap="round"/>')


def brow(shape: str) -> str:
    """Left brow in local eye coords."""
    shapes = {
        "neutral": "M-22,-40 Q-2,-48 20,-43",
        "raised": "M-22,-48 Q-2,-58 20,-52",
        "soft": "M-22,-42 Q-2,-48 20,-46",
        "focus": "M-22,-46 Q-2,-46 20,-37",
        "sleepy": "M-22,-38 Q-2,-44 20,-46",
        "smug_up": "M-22,-46 Q-2,-56 20,-50",
    }
    return (f'<path d="{shapes[shape]}" stroke="{HAIR_SH2}" stroke-width="4.5" fill="none" '
            f'stroke-linecap="round"/>')


def place(group: str, center, mirror_x=False) -> str:
    cx, cy = center
    if mirror_x:
        return f'<g transform="translate({cx},{cy}) scale(-1,1)">{group}</g>'
    return f'<g transform="translate({cx},{cy})">{group}</g>'


def blush(strength=0.4) -> str:
    out = ""
    for x in (180, 300):
        out += f'<ellipse cx="{x}" cy="284" rx="17" ry="8" fill="#f59ab8" opacity="{strength}"/>'
        out += (f'<path d="M{x-8},286 l4,-6 M{x-1},286 l4,-6 M{x+6},286 l4,-6" stroke="#ec7fa4" '
                f'stroke-width="1.8" stroke-linecap="round" opacity="{strength+0.2}"/>')
    return out


MOUTHS = {
    "smile": f'<path d="M228,298 Q240,307 252,298" stroke="{OL}" stroke-width="3" fill="none" stroke-linecap="round"/>',
    "smirk": f'<path d="M226,301 Q242,305 254,293" stroke="{OL}" stroke-width="3" fill="none" stroke-linecap="round"/>'
             f'<path d="M252,291 l4,4" stroke="{OL}" stroke-width="2.5" stroke-linecap="round"/>',
    "open": f'<path d="M224,294 Q240,298 256,294 Q252,316 240,317 Q228,316 224,294 Z" fill="#8c3354" stroke="{OL}" stroke-width="2.5" stroke-linejoin="round"/>'
            f'<path d="M230,309 Q240,303 250,309 Q246,316 240,316 Q234,316 230,309 Z" fill="#f08aa6"/>'
            f'<path d="M227,296 Q240,299 253,296 L252,300 Q240,302 228,300 Z" fill="#ffffff"/>',
    "o": f'<ellipse cx="240" cy="303" rx="5.5" ry="6.5" fill="#8c3354" stroke="{OL}" stroke-width="2.5"/>',
    "flat_side": f'<path d="M232,303 Q242,301 252,298" stroke="{OL}" stroke-width="3" fill="none" stroke-linecap="round"/>',
    "yawn": f'<ellipse cx="240" cy="304" rx="7" ry="8.5" fill="#8c3354" stroke="{OL}" stroke-width="2.5"/>'
            f'<ellipse cx="240" cy="308" rx="4" ry="3" fill="#f08aa6"/>',
    "firm": f'<path d="M230,301 Q240,299 250,301" stroke="{OL}" stroke-width="3" fill="none" stroke-linecap="round"/>',
    "grin": f'<path d="M224,295 Q240,300 256,293 Q250,310 240,311 Q229,310 224,295 Z" fill="#8c3354" stroke="{OL}" stroke-width="2.5" stroke-linejoin="round"/>'
            f'<path d="M227,297 Q240,301 253,295 L252,299 Q240,304 228,301 Z" fill="#ffffff"/>',
}

# name: (left eye spec, right eye spec, left brow, right brow, mouth, blush, extra)
# eye spec: ("open", openness, look, lid_flat, sparkle) | ("closed", kind)
EXPRESSIONS = {
    "idle":        (("open", 1.0, (0, 0), False, 1), ("open", 1.0, (0, 0), False, 1), "neutral", "neutral", "smile", 0.25, ""),
    "happy":       (("closed", "happy"), ("closed", "happy"), "raised", "raised", "open", 0.55, "sparkles"),
    "smug":        (("open", 0.55, (3, 2), True, 0.8), ("open", 0.55, (-1, 2), True, 0.8), "neutral", "smug_up", "smirk", 0.3, ""),
    "curious":     (("open", 1.05, (2, -2), False, 1.2), ("open", 1.05, (-2, -2), False, 1.2), "raised", "raised", "o", 0.2, "question"),
    "thinking":    (("open", 0.85, (-5, -7), False, 0.9), ("open", 0.85, (-7, -7), False, 0.9), "soft", "raised", "flat_side", 0.0, "dots"),
    "sleepy":      (("open", 0.35, (0, 4), True, 0.5), ("open", 0.35, (0, 4), True, 0.5), "sleepy", "sleepy", "yawn", 0.2, "zzz"),
    "focused":     (("open", 0.8, (0, 1), True, 1), ("open", 0.8, (0, 1), True, 1), "focus", "focus", "firm", 0.0, ""),
    "encouraging": (("open", 1.0, (0, 0), False, 1.1), ("closed", "happy"), "soft", "raised", "grin", 0.45, "star"),
}

EXTRAS = {
    "": "",
    "sparkles": (f'<path d="M352,150 l5,-14 l5,14 l14,5 l-14,5 l-5,14 l-5,-14 l-14,-5 z" fill="{GOLD}" stroke="{GOLD_SH}" stroke-width="1.5"/>'
                 f'<path d="M118,190 l3,-9 l3,9 l9,3 l-9,3 l-3,9 l-3,-9 l-9,-3 z" fill="#f7b6d6"/>'),
    "question": f'<text x="352" y="150" font-family="Georgia,serif" font-weight="bold" font-size="40" fill="#b9a2ff" stroke="{OL}" stroke-width="1.5">?</text>',
    "dots": (f'<circle cx="352" cy="170" r="6" fill="#ffffff" stroke="{OL}" stroke-width="2"/>'
             f'<circle cx="368" cy="148" r="8" fill="#ffffff" stroke="{OL}" stroke-width="2"/>'
             f'<circle cx="390" cy="122" r="11" fill="#ffffff" stroke="{OL}" stroke-width="2"/>'),
    "zzz": (f'<text x="350" y="160" font-family="Georgia,serif" font-weight="bold" font-size="26" fill="#9ed8ff" stroke="{OL}" stroke-width="1">z</text>'
            f'<text x="368" y="134" font-family="Georgia,serif" font-weight="bold" font-size="36" fill="#9ed8ff" stroke="{OL}" stroke-width="1.2">Z</text>'),
    "star": f'<path d="M352,198 l6,-15 l6,15 l15,6 l-15,6 l-6,15 l-6,-15 l-15,-6 z" fill="{GOLD}" stroke="{GOLD_SH}" stroke-width="1.5"/>',
}


def render_eye(spec, uid):
    if spec[0] == "open":
        _, o, look, flat, sp = spec
        return eye_open(o, look, flat, sp, uid)
    return eye_closed(spec[1])


def expression(name: str, blink=False) -> str:
    le, re_, lb, rb, mouth, bl, extra = EXPRESSIONS[name]
    if blink:
        le = le if le[0] == "closed" else ("closed", "down")
        re_ = re_ if re_[0] == "closed" else ("closed", "down")
    d1, g1 = render_eye(le, "L")
    # right eye: mirror. Look direction must be flipped back since mirroring inverts x.
    if re_[0] == "open":
        _, o, look, flat, sp = re_
        d2, g2 = eye_open(o, (-look[0], look[1]), flat, sp, "R")
    else:
        d2, g2 = render_eye(re_, "R")
    body = blush(bl) if bl else ""
    body += place(g1, EYE_L) + place(g2, EYE_R, mirror_x=True)
    body += place(brow(lb), EYE_L) + place(brow(rb), EYE_R, mirror_x=True)
    body += MOUTHS[mouth]
    body += EXTRAS[extra]
    return svg(body, d1 + d2)


# ----------------------------------------------------------------------------
# Body helpers
# ----------------------------------------------------------------------------
def legs(trouser, trouser_sh, shoe, shoe_hi="#5a4a7a", boots=False, cuff=None) -> str:
    out = ""
    for x0 in (194, 246):
        x1 = x0 + 40
        top = 488
        bottom = 598 if not boots else 560
        out += (f'<path d="M{x0},{top} L{x0+2},{bottom} L{x1-2},{bottom} L{x1},{top} Z" fill="{trouser}" '
                f'stroke="{OL}" stroke-width="3" stroke-linejoin="round"/>')
        out += f'<path d="M{x1-12},{top+6} L{x1-10},{bottom-4}" stroke="{trouser_sh}" stroke-width="7" opacity=".8"/>'
    for i, x0 in enumerate((190, 244)):
        toe = -10 if i == 0 else 10
        if boots:
            out += (f'<path d="M{x0+4},548 L{x0+44},548 L{x0+46},606 Q{x0+48+toe},622 {x0+24+toe},624 '
                    f'L{x0+6},624 Q{x0-2+min(toe,0)},620 {x0+2},606 Z" fill="{shoe}" stroke="{OL}" stroke-width="3" stroke-linejoin="round"/>')
            if cuff:
                out += f'<path d="M{x0+3},548 L{x0+45},548 L{x0+45},560 L{x0+3},560 Z" fill="{cuff}" stroke="{OL}" stroke-width="2.5"/>'
            out += f'<path d="M{x0+12},560 L{x0+12},604" stroke="{shoe_hi}" stroke-width="4" opacity=".6" stroke-linecap="round"/>'
        else:
            out += (f'<path d="M{x0+2},596 L{x0+46},596 Q{x0+50+toe},612 {x0+24+toe},622 L{x0+4},622 '
                    f'Q{x0-4+min(toe,0)},612 {x0+2},596 Z" fill="{shoe}" stroke="{OL}" stroke-width="3" stroke-linejoin="round"/>')
            out += f'<path d="M{x0+10},602 Q{x0+22},598 {x0+34},602" stroke="{shoe_hi}" stroke-width="3" fill="none" opacity=".8"/>'
    return out


def arm(sleeve, sleeve_sh, cuff=None, hand=SKIN, glove=False) -> str:
    """Left arm (viewer's left).  Mirror for the right one."""
    s = ("M166,358 C150,368 140,392 136,420 C132,446 130,462 130,478 L164,482 "
         "C166,462 170,440 176,420 C180,404 184,388 186,378 Z")
    out = f'<path d="{s}" fill="{sleeve}" stroke="{OL}" stroke-width="3" stroke-linejoin="round"/>'
    out += f'<path d="M150,392 C144,420 140,450 140,474" stroke="{sleeve_sh}" stroke-width="8" fill="none" opacity=".7"/>'
    hand_fill = "#ffffff" if glove else hand
    out += (f'<path d="M134,480 C128,494 132,512 146,514 C160,516 166,500 162,482 Z" fill="{hand_fill}" '
            f'stroke="{OL}" stroke-width="3" stroke-linejoin="round"/>')
    if cuff:
        out += f'<path d="M129,470 L165,474 L164,486 L128,482 Z" fill="{cuff}" stroke="{OL}" stroke-width="2.5" stroke-linejoin="round"/>'
    return out


def torso_path(hem_y=500, flare=0) -> str:
    return (f"M168,354 Q240,342 312,354 C318,380 314,420 304,452 L{306+flare},{hem_y} "
            f"Q240,{hem_y+10} {174-flare},{hem_y} L176,452 C166,420 162,380 168,354 Z")


def body_layer(parts: str) -> str:
    return svg(parts, GRADS)


GRADS = f"""
<linearGradient id="goldG" x1="0" y1="0" x2="0" y2="1">
  <stop offset="0" stop-color="{GOLD_HI}"/><stop offset=".5" stop-color="{GOLD}"/><stop offset="1" stop-color="{GOLD_SH}"/></linearGradient>
<linearGradient id="blackG" x1="0" y1="0" x2="1" y2="0">
  <stop offset="0" stop-color="#2c2944"/><stop offset=".5" stop-color="#1b1930"/><stop offset="1" stop-color="#121022"/></linearGradient>
<linearGradient id="navyG" x1="0" y1="0" x2="1" y2="0">
  <stop offset="0" stop-color="#3a3f80"/><stop offset=".6" stop-color="#2a2d62"/><stop offset="1" stop-color="#1f2150"/></linearGradient>
<linearGradient id="capeG" x1="0" y1="0" x2="0" y2="1">
  <stop offset="0" stop-color="#25213c"/><stop offset="1" stop-color="#141226"/></linearGradient>
<linearGradient id="liningG" x1="0" y1="0" x2="0" y2="1">
  <stop offset="0" stop-color="#7a52c8"/><stop offset="1" stop-color="#4b2f8c"/></linearGradient>
<linearGradient id="hoodieG" x1="0" y1="0" x2="1" y2="0">
  <stop offset="0" stop-color="#d9cdfa"/><stop offset=".6" stop-color="#bfaef0"/><stop offset="1" stop-color="#a593e0"/></linearGradient>
<linearGradient id="creamG" x1="0" y1="0" x2="1" y2="0">
  <stop offset="0" stop-color="#fbf1dc"/><stop offset=".6" stop-color="#efdfbf"/><stop offset="1" stop-color="#ddc9a2"/></linearGradient>
<linearGradient id="coatG" x1="0" y1="0" x2="1" y2="0">
  <stop offset="0" stop-color="#5a4b9a"/><stop offset=".6" stop-color="#443879"/><stop offset="1" stop-color="#352b63"/></linearGradient>
<linearGradient id="pjG" x1="0" y1="0" x2="1" y2="0">
  <stop offset="0" stop-color="#cfe6ff"/><stop offset=".6" stop-color="#b5d3f6"/><stop offset="1" stop-color="#9dbfe8"/></linearGradient>
"""


def both(g: str) -> str:
    return g + mirror(g)


def crown(cx=240, cy=96, scale=1.0, tilt=-12) -> str:
    pts = "-34,10 -38,-18 -20,-2 -8,-28 0,-6 8,-28 20,-2 38,-18 34,10"
    g = (f'<g transform="translate({cx},{cy}) rotate({tilt}) scale({scale})">'
         f'<polygon points="{pts}" fill="url(#goldG)" stroke="{OL}" stroke-width="3" stroke-linejoin="round"/>'
         f'<rect x="-35" y="6" width="70" height="12" rx="4" fill="url(#goldG)" stroke="{OL}" stroke-width="3"/>'
         f'<circle cx="0" cy="12" r="5" fill="#b07cff" stroke="{OL}" stroke-width="2"/>'
         f'<circle cx="-20" cy="12" r="3" fill="#f59ab8"/><circle cx="20" cy="12" r="3" fill="#f59ab8"/>'
         f'<circle cx="-38" cy="-18" r="4" fill="{GOLD_HI}" stroke="{OL}" stroke-width="2"/>'
         f'<circle cx="38" cy="-18" r="4" fill="{GOLD_HI}" stroke="{OL}" stroke-width="2"/>'
         f'<circle cx="-8" cy="-28" r="4" fill="{GOLD_HI}" stroke="{OL}" stroke-width="2"/>'
         f'<circle cx="8" cy="-28" r="4" fill="{GOLD_HI}" stroke="{OL}" stroke-width="2"/>'
         f'</g>')
    return g


def crown_pin(cx=312, cy=150) -> str:
    return crown(cx, cy, 0.42, 18)


# ----------------------------------------------------------------------------
# Outfits
# ----------------------------------------------------------------------------
def outfit_royal_black_gold():
    back = svg(
        f'<path d="M170,352 C140,420 116,520 100,616 Q240,640 380,616 C364,520 340,420 310,352 Z" '
        f'fill="url(#liningG)" stroke="{OL}" stroke-width="3" stroke-linejoin="round"/>'
        f'<path d="M176,356 C150,430 132,520 120,612 Q240,630 360,612 C348,520 330,430 304,356 Z" fill="url(#capeG)"/>',
        GRADS)
    b = legs("#f4f1fb", "#d4cde6", "#1b1930", boots=True, cuff="url(#goldG)")
    b += both(arm("url(#blackG)", "#0d0b1a", cuff="url(#goldG)", glove=True))
    b += f'<path d="{torso_path(512, 6)}" fill="url(#blackG)" stroke="{OL}" stroke-width="3" stroke-linejoin="round"/>'
    # gold trim down the front and along hem
    b += f'<path d="M240,356 L240,514" stroke="url(#goldG)" stroke-width="7"/>'
    b += f'<path d="M168,506 Q240,520 312,506" stroke="url(#goldG)" stroke-width="6" fill="none"/>'
    # double row of buttons
    for y in (392, 420, 448, 476):
        for x in (222, 258):
            b += f'<circle cx="{x}" cy="{y}" r="5" fill="url(#goldG)" stroke="{OL}" stroke-width="2"/>'
    # belt
    b += f'<path d="M176,462 Q240,472 304,462 L304,476 Q240,486 176,476 Z" fill="#3b2a66" stroke="{OL}" stroke-width="2.5"/>'
    b += f'<rect x="230" y="463" width="20" height="18" rx="3" fill="url(#goldG)" stroke="{OL}" stroke-width="2"/>'
    # cravat / jabot + brooch
    b += (f'<path d="M224,346 Q240,356 256,346 L262,372 Q250,392 240,398 Q230,392 218,372 Z" fill="#ffffff" '
          f'stroke="{OL}" stroke-width="2.5" stroke-linejoin="round"/>'
          f'<path d="M228,370 Q240,380 252,370" stroke="#d8d2ea" stroke-width="2.5" fill="none"/>'
          f'<circle cx="240" cy="360" r="7" fill="#b07cff" stroke="url(#goldG)" stroke-width="3"/>')
    # high collar
    collar = (f'<path d="M218,336 L222,358 L196,364 L190,344 Z" fill="url(#blackG)" stroke="{OL}" stroke-width="2.5" stroke-linejoin="round"/>'
              f'<path d="M191,346 L197,362" stroke="url(#goldG)" stroke-width="3"/>')
    b += both(collar)
    # epaulettes with fringe
    ep = (f'<path d="M160,352 Q176,340 196,350 L192,366 Q174,370 158,366 Z" fill="url(#goldG)" stroke="{OL}" stroke-width="2.5" stroke-linejoin="round"/>'
          + "".join(f'<path d="M{x},366 L{x-1},384" stroke="{GOLD}" stroke-width="3" stroke-linecap="round"/>' for x in range(160, 194, 6)))
    b += both(ep)
    # aiguillette cords from right shoulder
    b += (f'<path d="M300,362 Q284,400 262,410" stroke="url(#goldG)" stroke-width="4" fill="none" stroke-linecap="round"/>'
          f'<path d="M306,366 Q296,420 266,430" stroke="url(#goldG)" stroke-width="4" fill="none" stroke-linecap="round"/>')
    top = svg(crown(), GRADS)
    return back, body_layer(b), top


def outfit_royal_academy():
    b = legs("#3a3a5c", "#2a2a46", "#5a3b2a", shoe_hi="#8a6048")
    b += both(arm("url(#navyG)", "#171a40", cuff="#ffffff"))
    b += f'<path d="{torso_path(508)}" fill="url(#navyG)" stroke="{OL}" stroke-width="3" stroke-linejoin="round"/>'
    # shirt V and tie
    b += (f'<path d="M216,350 L240,420 L264,350 Q240,358 216,350 Z" fill="#ffffff" stroke="{OL}" stroke-width="2.5" stroke-linejoin="round"/>'
          f'<path d="M234,358 L246,358 L250,404 L240,416 L230,404 Z" fill="#b07cff" stroke="{OL}" stroke-width="2.5" stroke-linejoin="round"/>'
          f'<path d="M232,366 L248,374 M231,382 L249,390" stroke="#ffffff" stroke-width="3" opacity=".7"/>')
    # lapels with gold piping
    lap = (f'<path d="M216,350 L240,424 L222,440 L196,372 Z" fill="#33387a" stroke="{OL}" stroke-width="2.5" stroke-linejoin="round"/>'
           f'<path d="M198,374 L222,436" stroke="url(#goldG)" stroke-width="3"/>')
    b += both(lap)
    # crest on the breast pocket + buttons
    b += (f'<path d="M270,400 L290,400 L290,414 Q280,426 270,414 Z" fill="url(#goldG)" stroke="{OL}" stroke-width="2"/>'
          f'<path d="M276,406 l4,-4 l4,4 l-4,6 z" fill="#b07cff"/>')
    for y in (448, 476):
        b += f'<circle cx="240" cy="{y}" r="5" fill="url(#goldG)" stroke="{OL}" stroke-width="2"/>'
    b += f'<path d="M172,500 Q240,514 308,500" stroke="url(#goldG)" stroke-width="3" fill="none"/>'
    top = svg(crown_pin(), GRADS)
    return None, body_layer(b), top


def outfit_casual_hoodie():
    back = svg(f'<path d="M176,360 C160,320 186,292 240,292 C294,292 320,320 304,360 Z" fill="#a593e0" stroke="{OL}" stroke-width="3" stroke-linejoin="round"/>', GRADS)
    b = legs("#3b4a78", "#2c3860", "#f4f1fb", shoe_hi="#b07cff")
    b += both(arm("url(#hoodieG)", "#9a88d8", cuff="#a593e0"))
    b += f'<path d="{torso_path(508, 4)}" fill="url(#hoodieG)" stroke="{OL}" stroke-width="3" stroke-linejoin="round"/>'
    # hood rim around neck
    b += (f'<path d="M200,348 Q240,380 280,348 Q284,340 276,338 Q240,364 204,338 Q196,340 200,348 Z" fill="#d9cdfa" stroke="{OL}" stroke-width="2.5"/>')
    # drawstrings
    b += (f'<path d="M228,360 L224,410" stroke="#ffffff" stroke-width="3.5" stroke-linecap="round"/>'
          f'<path d="M252,360 L256,410" stroke="#ffffff" stroke-width="3.5" stroke-linecap="round"/>'
          f'<circle cx="224" cy="412" r="3.5" fill="{GOLD}"/><circle cx="256" cy="412" r="3.5" fill="{GOLD}"/>')
    # kangaroo pocket + little crown print
    b += f'<path d="M196,452 L284,452 L294,494 L186,494 Z" fill="#b6a5ec" stroke="{OL}" stroke-width="2.5" stroke-linejoin="round"/>'
    b += f'<path d="M226,428 l4,-12 l6,8 l4,-10 l4,10 l6,-8 l4,12 z" fill="url(#goldG)" stroke="{OL}" stroke-width="1.5"/>'
    b += f'<path d="M176,500 Q240,512 304,500 L304,508 Q240,520 176,508 Z" fill="#a593e0" stroke="{OL}" stroke-width="2"/>'
    top = svg(crown_pin(), GRADS)
    return back, body_layer(b), top


def outfit_study():
    b = legs("#4a4466", "#363050", "#5a3b2a", shoe_hi="#8a6048")
    b += both(arm("url(#creamG)", "#cdb68c", cuff="#ffffff"))
    b += f'<path d="{torso_path(506)}" fill="url(#creamG)" stroke="{OL}" stroke-width="3" stroke-linejoin="round"/>'
    # shirt collar + open cardigan front
    b += (f'<path d="M220,348 L240,400 L260,348 Q240,356 220,348 Z" fill="#ffffff" stroke="{OL}" stroke-width="2.5" stroke-linejoin="round"/>'
          f'<path d="M222,346 L214,362 L234,364 Z M258,346 L266,362 L246,364 Z" fill="#ffffff" stroke="{OL}" stroke-width="2"/>')
    b += f'<path d="M240,400 L240,506" stroke="#cdb68c" stroke-width="3"/>'
    for y in (420, 450, 480):
        b += f'<circle cx="232" cy="{y}" r="4" fill="#8a6048" stroke="{OL}" stroke-width="1.5"/>'
    # cable-knit hints
    for x in (200, 280):
        b += f'<path d="M{x},380 q6,10 0,20 q-6,10 0,20 q6,10 0,20 q-6,10 0,20" stroke="#d7c39c" stroke-width="3" fill="none"/>'
    # book held in front (over the right hand)
    b += (f'<g transform="rotate(-8 300 470)"><rect x="268" y="440" width="64" height="76" rx="4" fill="#5b3f9e" stroke="{OL}" stroke-width="3"/>'
          f'<rect x="272" y="444" width="8" height="68" fill="#4a3284"/>'
          f'<path d="M288,462 l8,-8 l8,8 l-8,10 z" fill="url(#goldG)"/>'
          f'<rect x="286" y="484" width="34" height="4" rx="2" fill="{GOLD}"/></g>')
    # glasses go in the top layer
    glasses = (f'<circle cx="199" cy="252" r="27" fill="#ffffff" fill-opacity=".08" stroke="{GOLD_SH}" stroke-width="3"/>'
               f'<circle cx="281" cy="252" r="27" fill="#ffffff" fill-opacity=".08" stroke="{GOLD_SH}" stroke-width="3"/>'
               f'<path d="M226,250 Q240,242 254,250" stroke="{GOLD_SH}" stroke-width="3" fill="none"/>'
               f'<path d="M172,248 L154,240 M308,248 L326,240" stroke="{GOLD_SH}" stroke-width="3"/>'
               f'<path d="M184,236 l10,-6 M266,236 l10,-6" stroke="#ffffff" stroke-width="3" opacity=".7" stroke-linecap="round"/>')
    top = svg(glasses + crown_pin(), GRADS)
    return None, body_layer(b), top


def outfit_winter():
    b = legs("#2f2c4a", "#221f38", "#6a4636", shoe_hi="#9a6c55", boots=True, cuff="#f5f2fb")
    b += both(arm("url(#coatG)", "#2a2150", cuff="#f5f2fb", hand="#f59ab8"))
    # long coat
    b += f'<path d="{torso_path(548, 12)}" fill="url(#coatG)" stroke="{OL}" stroke-width="3" stroke-linejoin="round"/>'
    b += f'<path d="M240,380 L240,552" stroke="#2a2150" stroke-width="3"/>'
    for y in (410, 450, 490, 530):
        b += f'<circle cx="252" cy="{y}" r="5" fill="url(#goldG)" stroke="{OL}" stroke-width="2"/>'
    # fur trim at hem
    b += f'<path d="M162,540 Q240,560 318,540 L320,556 Q240,576 160,556 Z" fill="#f5f2fb" stroke="{OL}" stroke-width="2.5"/>'
    # scarf
    b += (f'<path d="M206,340 Q240,362 274,340 L284,362 Q240,392 196,362 Z" fill="#f59ab8" stroke="{OL}" stroke-width="3" stroke-linejoin="round"/>'
          f'<path d="M256,366 L282,446 L262,452 L244,374 Z" fill="#f08aa6" stroke="{OL}" stroke-width="3" stroke-linejoin="round"/>'
          f'<path d="M262,446 l2,10 M270,444 l2,10 M278,442 l2,10" stroke="{OL}" stroke-width="2"/>'
          f'<path d="M214,352 Q240,370 266,352" stroke="#ffffff" stroke-width="3" fill="none" opacity=".6"/>')
    # beanie top layer
    beanie = (f'<path d="M146,176 C140,96 196,70 240,70 C290,70 346,96 336,176 Q240,150 146,176 Z" fill="#5b4fa0" stroke="{OL}" stroke-width="3" stroke-linejoin="round"/>'
              f'<path d="M140,170 Q240,140 342,170 L344,196 Q240,168 138,196 Z" fill="#f5f2fb" stroke="{OL}" stroke-width="3" stroke-linejoin="round"/>'
              + "".join(f'<path d="M{x},96 L{x+2},160" stroke="#4a3f8c" stroke-width="4" opacity=".7"/>' for x in range(178, 310, 22))
              + f'<circle cx="240" cy="64" r="18" fill="#f5f2fb" stroke="{OL}" stroke-width="3"/>'
              + crown(306, 156, 0.36, 14))
    top = svg(beanie, GRADS)
    return None, body_layer(b), top


def outfit_sleepwear():
    b = legs("url(#pjG)", "#8fb0dc", "#f4f1fb", shoe_hi="#cfe6ff")
    b += both(arm("url(#pjG)", "#8fb0dc", cuff="#ffffff"))
    b += f'<path d="{torso_path(506, 4)}" fill="url(#pjG)" stroke="{OL}" stroke-width="3" stroke-linejoin="round"/>'
    b += (f'<path d="M216,348 L240,380 L264,348 Q240,356 216,348 Z" fill="#ffffff" stroke="{OL}" stroke-width="2.5"/>'
          f'<path d="M240,380 L240,506" stroke="#8fb0dc" stroke-width="3"/>')
    for y in (404, 436, 468):
        b += f'<circle cx="246" cy="{y}" r="4" fill="#ffffff" stroke="{OL}" stroke-width="1.5"/>'
    # star & moon pattern
    for (x, y) in [(196, 400), (280, 420), (210, 470), (276, 480), (300, 386), (180, 440)]:
        b += f'<path d="M{x},{y-7} l2,5 l5,2 l-5,2 l-2,5 l-2,-5 l-5,-2 l5,-2 z" fill="{GOLD}"/>'
    b += f'<path d="M264,452 a9,9 0 1 0 8,-12 a7,7 0 1 1 -8,12 z" fill="#fff6c8"/>'
    # pillow hugged in front
    b += (f'<path d="M150,470 Q146,440 180,442 L300,442 Q334,440 330,470 L330,500 Q334,530 300,528 L180,528 Q146,530 150,500 Z" '
          f'fill="#ffffff" stroke="{OL}" stroke-width="3"/>'
          f'<path d="M170,458 Q240,470 310,458" stroke="#e6e0f5" stroke-width="3" fill="none"/>'
          f'<path d="M232,470 l8,-10 l8,10 l-8,14 z" fill="#d9cdfa"/>')
    nightcap = (f'<path d="M150,180 C138,104 190,72 246,74 C300,76 330,100 336,150 C352,124 370,124 388,150 C372,150 358,170 342,190 Q240,156 150,180 Z" '
                f'fill="url(#pjG)" stroke="{OL}" stroke-width="3" stroke-linejoin="round"/>'
                f'<path d="M144,176 Q240,150 340,178 L340,196 Q240,170 142,196 Z" fill="#ffffff" stroke="{OL}" stroke-width="3" stroke-linejoin="round"/>'
                f'<circle cx="392" cy="154" r="15" fill="#ffffff" stroke="{OL}" stroke-width="3"/>'
                f'<path d="M210,110 l2,5 l5,2 l-5,2 l-2,5 l-2,-5 l-5,-2 l5,-2 z" fill="{GOLD}"/>'
                f'<path d="M280,100 l2,5 l5,2 l-5,2 l-2,5 l-2,-5 l-5,-2 l5,-2 z" fill="{GOLD}"/>')
    top = svg(nightcap, GRADS)
    return None, body_layer(b), top


OUTFITS = {
    "royal_black_gold": ("Black & Gold Royal", outfit_royal_black_gold),
    "royal_academy": ("Royal Academy Uniform", outfit_royal_academy),
    "casual_hoodie": ("Casual Hoodie", outfit_casual_hoodie),
    "study": ("Study Prince", outfit_study),
    "winter": ("Winter Coat", outfit_winter),
    "sleepwear": ("Sleepwear", outfit_sleepwear),
}


# ----------------------------------------------------------------------------
# Icons (line icons, rendered white; the app tints nothing — keep them light)
# ----------------------------------------------------------------------------
ICON_STROKE = "#e9e2ff"
ICONS = {
    "chat": '<path d="M5 6h22v14H14l-6 5v-5H5z"/>',
    "home": '<path d="M4 15 16 5l12 10M8 13v13h16V13"/><path d="M13 26v-7h6v7"/>',
    "tasks": '<path d="M6 8l3 3 5-5M6 17l3 3 5-5M6 26l3 3 5-5" /><path d="M18 9h9M18 18h9M18 27h9"/>',
    "study": '<path d="M4 8c5-2 9-2 12 1 3-3 7-3 12-1v17c-5-2-9-2-12 1-3-3-7-3-12-1z"/><path d="M16 9v17"/>',
    "code": '<path d="M11 9 4 16l7 7M21 9l7 7-7 7M18 6l-4 20"/>',
    "focus": '<circle cx="16" cy="17" r="10"/><path d="M16 11v6l4 3M13 4h6"/>',
    "wardrobe": '<path d="M12 5c0 2 2 3 4 3s4-1 4-3l7 4-3 6-3-1v13H11V14l-3 1-3-6z"/>',
    "memory": '<path d="M11 6c-4 0-6 3-5 6-3 2-2 7 1 8 0 3 3 5 6 4 1 2 5 2 6 0 3 1 6-1 6-4 3-1 4-6 1-8 1-3-1-6-5-6-1-2-4-2-5 0-1-1-3-1-5 0z"/><path d="M16 6v20"/>',
    "reminders": '<path d="M8 22V14a8 8 0 0 1 16 0v8l2 3H6z"/><path d="M13 27a3 3 0 0 0 6 0"/>',
    "settings": '<circle cx="16" cy="16" r="4"/><path d="M16 3v4M16 25v4M3 16h4M25 16h4M6.8 6.8l2.8 2.8M22.4 22.4l2.8 2.8M6.8 25.2l2.8-2.8M22.4 9.6l2.8-2.8"/>',
    "send": '<path d="M5 16 27 6 20 27l-4-9z"/><path d="M16 18 27 6"/>',
    "copy": '<rect x="10" y="10" width="15" height="17" rx="2"/><path d="M7 21V6a1 1 0 0 1 1-1h12"/>',
    "plus": '<path d="M16 6v20M6 16h20"/>',
    "trash": '<path d="M6 9h20M13 9V6h6v3M9 9l1 18h12l1-18"/>',
    "play": '<path d="M10 6v20l16-10z"/>',
    "pause": '<path d="M10 6v20M22 6v20"/>',
    "stop": '<rect x="8" y="8" width="16" height="16" rx="2"/>',
    "close": '<path d="M8 8l16 16M24 8 8 24"/>',
    "minus": '<path d="M7 16h18"/>',
    "expand": '<path d="M6 13V6h7M26 19v7h-7M6 6l8 8M26 26l-8-8"/>',
}


def icon_svg(path: str, color=ICON_STROKE) -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 32 32" fill="none" '
            f'stroke="{color}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">{path}</svg>')


def app_icon_svg() -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256" viewBox="0 0 256 256"><defs>{GRADS}'
            f'<radialGradient id="bgR" cx=".5" cy=".4" r=".7"><stop offset="0" stop-color="#4a3a8c"/>'
            f'<stop offset="1" stop-color="#17152e"/></radialGradient></defs>'
            f'<rect x="8" y="8" width="240" height="240" rx="56" fill="url(#bgR)" stroke="{GOLD}" stroke-width="6"/>'
            f'<g transform="translate(128,140) scale(2.4)">'
            f'<polygon points="-34,10 -38,-18 -20,-2 -8,-28 0,-6 8,-28 20,-2 38,-18 34,10" fill="url(#goldG)" stroke="{OL}" stroke-width="3" stroke-linejoin="round"/>'
            f'<rect x="-35" y="6" width="70" height="12" rx="4" fill="url(#goldG)" stroke="{OL}" stroke-width="3"/>'
            f'<circle cx="0" cy="12" r="5" fill="#b07cff" stroke="{OL}" stroke-width="2"/></g>'
            f'<path d="M196,52 l5,-13 l5,13 l13,5 l-13,5 l-5,13 l-5,-13 l-13,-5 z" fill="#f7b6d6"/></svg>')


# ----------------------------------------------------------------------------
# Rendering
# ----------------------------------------------------------------------------
class Renderer:
    def __init__(self):
        self.mode = None
        try:
            import cairosvg  # noqa: F401
            self.mode = "cairo"
        except Exception:
            pass
        if self.mode is None:
            from playwright.sync_api import sync_playwright
            self._pw = sync_playwright().start()
            self._browser = self._pw.chromium.launch()
            self.mode = "playwright"

    def render(self, svg_text: str, out_path: str, w: int, h: int, scale: float):
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        if self.mode == "cairo":
            import cairosvg
            cairosvg.svg2png(bytestring=svg_text.encode(), write_to=out_path,
                             output_width=int(w * scale), output_height=int(h * scale))
            return
        page = self._browser.new_page(viewport={"width": w, "height": h}, device_scale_factor=scale)
        html = ("<html><head><style>html,body{margin:0;padding:0;background:transparent}"
                "svg{display:block}</style></head><body>" + svg_text + "</body></html>")
        page.set_content(html)
        page.locator("svg").first.screenshot(path=out_path, omit_background=True)
        page.close()

    def close(self):
        if self.mode == "playwright":
            self._browser.close()
            self._pw.stop()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--svg", action="store_true", help="also write SVG sources")
    args = ap.parse_args()
    r = Renderer()
    jobs = []
    char_dir = os.path.join(ASSETS, "characters", "aster")
    jobs.append((hair_back(), os.path.join(char_dir, "hair_back.png")))
    jobs.append((head(), os.path.join(char_dir, "head.png")))
    jobs.append((hair_front(), os.path.join(char_dir, "hair_front.png")))
    for name in EXPRESSIONS:
        jobs.append((expression(name), os.path.join(ASSETS, "expressions", f"{name}.png")))
        jobs.append((expression(name, blink=True), os.path.join(ASSETS, "expressions", f"{name}_blink.png")))
    outfit_meta = {}
    for oid, (label, fn) in OUTFITS.items():
        back, body, top = fn()
        d = os.path.join(ASSETS, "outfits", oid)
        if back:
            jobs.append((back, os.path.join(d, "back.png")))
        jobs.append((body, os.path.join(d, "body.png")))
        if top:
            jobs.append((top, os.path.join(d, "top.png")))
        outfit_meta[oid] = label
    for i, (svg_text, path) in enumerate(jobs):
        r.render(svg_text, path, W, H, SCALE)
        if args.svg:
            with open(path[:-4] + ".svg", "w", encoding="utf-8") as fh:
                fh.write(svg_text)
    icon_dir = os.path.join(ASSETS, "icons")
    for name, p in ICONS.items():
        r.render(icon_svg(p), os.path.join(icon_dir, f"{name}.png"), 32, 32, 2)
    r.render(app_icon_svg(), os.path.join(icon_dir, "aster.png"), 256, 256, 1)
    r.close()
    try:
        from PIL import Image
        img = Image.open(os.path.join(icon_dir, "aster.png"))
        img.save(os.path.join(icon_dir, "aster.ico"), sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    except Exception as exc:  # pragma: no cover
        print("ICO not written:", exc)
    print(f"Rendered {len(jobs)} character layers and {len(ICONS) + 1} icons with {r.mode}.")


if __name__ == "__main__":
    main()
