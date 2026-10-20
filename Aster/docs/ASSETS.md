# Artwork & asset pipeline

All character art is **original**, drawn as layered vector art by `tools/build_art.py` and shipped as
transparent PNGs (720 × 960 px, 8-bit RGBA, sRGB). You don't need to run anything to use it.

## What's included

* **Base character** (`assets/characters/aster/`): `hair_back.png`, `head.png`, `hair_front.png`
* **8 expressions** (`assets/expressions/`), each with a blink frame (`<name>_blink.png`):
  `idle`, `happy`, `smug`, `curious`, `thinking`, `sleepy`, `focused`, `encouraging`
* **6 outfits** (`assets/outfits/<id>/`: `body.png` required, `back.png` / `top.png` optional):
  `royal_black_gold` (cape + crown), `royal_academy`, `casual_hoodie`, `study` (glasses + book),
  `winter` (beanie + scarf), `sleepwear` (nightcap + pillow)
* **Icons** (`assets/icons/`): navigation icons (32 px drawn at 2×), `aster.png` and `aster.ico`
* Folders `assets/themes/` is reserved (themes are defined in code: `aster/ui/theme.py`).

## How layers are stacked (bottom → top)

```
characters/aster/hair_back.png
outfits/<outfit>/back.png        (optional)
characters/aster/head.png
outfits/<outfit>/body.png        (required)
characters/aster/hair_front.png
expressions/<expression>.png     (or <expression>_blink.png while blinking)
outfits/<outfit>/top.png         (optional: crown, glasses, hats)
```

All layers use the **same canvas** (720 × 960, character centred, feet near the bottom, head top around
y≈125). Animation (idle bob, blinking, expression changes) is done by the app by swapping and moving these
layers — there are no sprite sheets to maintain.

## Using your own hand-drawn sprites

Two options:

1. **Replace layers** with your own PNGs of the same size/canvas and file names.
2. **Full-frame sprites** (easiest for artists): put complete images here and they take priority over layers:
   ```
   assets/characters/aster/sprites/<outfit_id>/<expression>.png
   assets/characters/aster/sprites/<outfit_id>/<expression>_blink.png   (optional)
   ```
   Requirements: PNG with a **transparent background** (no white box), 3:4 aspect ratio (e.g. 720 × 960 or
   1080 × 1440), character standing centred with ~4 % margin, feet ~3 % above the bottom edge.
   An outfit counts as available if it has `outfits/<id>/body.png` **or** any sprite in its sprites folder.

If a required file is missing, the Wardrobe marks the outfit **Artwork missing** (it can't be selected) and the
prince falls back to a placeholder instead of crashing.

## Regenerating the shipped art (optional, developers only)

```
.\.venv\Scripts\python -m pip install cairosvg     # or: pip install playwright && playwright install chromium
.\.venv\Scripts\python tools\build_art.py --svg     # --svg also writes editable .svg sources next to the PNGs
```
Colours, shapes and expressions are defined at the top of `tools/build_art.py`.
(`cairosvg` needs the Cairo library on Windows; the Playwright route is usually easier.)
