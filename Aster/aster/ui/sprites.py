"""Composes character layers into pixmaps and caches them."""
from __future__ import annotations

import os
from collections import OrderedDict

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QPixmap

from ..core.wardrobe import EXPRESSIONS, layers_for

CANVAS_RATIO = 960 / 720  # height / width of the shipped layers


class SpriteManager:
    def __init__(self):
        # Full-size layers are big (720x960); keep only a few to stay light on 8 GB machines.
        self._layer_cache: OrderedDict[str, QPixmap] = OrderedDict()
        self.max_layers = 10
        self._frame_cache: dict[tuple, QPixmap] = {}
        self.last_missing: list[str] = []

    def clear(self):
        self._layer_cache.clear()
        self._frame_cache.clear()

    def _layer(self, path: str) -> QPixmap | None:
        pm = self._layer_cache.get(path)
        if pm is not None:
            self._layer_cache.move_to_end(path)
            return pm
        pm = QPixmap(path)
        if pm.isNull():
            return None
        self._layer_cache[path] = pm
        while len(self._layer_cache) > self.max_layers:
            self._layer_cache.popitem(last=False)
        return pm

    def frame(self, outfit: str, expression: str, blink: bool, height: int, dpr: float = 1.0) -> QPixmap:
        key = (outfit, expression, blink, height, round(dpr, 2))
        pm = self._frame_cache.get(key)
        if pm is not None:
            return pm
        width = int(round(height / CANVAS_RATIO))
        layers, missing = layers_for(outfit, expression, blink)
        self.last_missing = missing
        pw, ph = max(1, int(width * dpr)), max(1, int(height * dpr))
        pm = QPixmap(pw, ph)
        pm.fill(Qt.GlobalColor.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        drawn = 0
        for path in layers:
            layer = self._layer(path)
            if layer is not None:
                # area-averaged downscale looks much cleaner than bilinear drawPixmap scaling
                scaled = layer.scaled(pw, ph, Qt.AspectRatioMode.IgnoreAspectRatio,
                                      Qt.TransformationMode.SmoothTransformation)
                p.drawPixmap(0, 0, scaled)
                drawn += 1
        if drawn == 0 or (missing and len(layers) < 3):
            self._placeholder(p, pw, ph, missing)
        p.end()
        pm.setDevicePixelRatio(dpr)
        if len(self._frame_cache) > 64:
            self._frame_cache.clear()
        self._frame_cache[key] = pm
        return pm

    @staticmethod
    def _placeholder(p: QPainter, w: int, h: int, missing: list[str]) -> None:
        """Graceful stand-in when artwork files are missing."""
        p.setPen(QPen(QColor("#e7bf5f"), max(2, w // 80)))
        p.setBrush(QColor(40, 34, 80, 220))
        r = QRectF(w * 0.18, h * 0.12, w * 0.64, w * 0.64)
        p.drawEllipse(r)
        body = QPainterPath()
        body.addRoundedRect(QRectF(w * 0.22, h * 0.55, w * 0.56, h * 0.38), w * 0.1, w * 0.1)
        p.drawPath(body)
        p.setPen(QColor("#f4efff"))
        f = QFont("Segoe UI", max(8, w // 12), QFont.Weight.Bold)
        p.setFont(f)
        p.drawText(r, Qt.AlignmentFlag.AlignCenter, "♛ ?")
        f.setPointSize(max(7, w // 26))
        f.setBold(False)
        p.setFont(f)
        p.drawText(QRectF(w * 0.05, h * 0.6, w * 0.9, h * 0.3), Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
                   "Artwork missing\nsee docs/ASSETS.md")

    def portrait(self, outfit: str, expression: str, size: int, dpr: float = 1.0) -> QPixmap:
        """Head-and-shoulders crop for avatars."""
        full = self.frame(outfit, expression, False, int(size * 2.1), dpr)
        w = full.width()
        crop_w = int(w * 0.72)
        x = (w - crop_w) // 2
        y = int(full.height() * 0.06)
        pm = full.copy(x, y, crop_w, crop_w)
        pm.setDevicePixelRatio(dpr)
        return pm


def icon_path(name: str) -> str:
    from .. import paths
    return paths.asset("icons", f"{name}.png")


def has_icon(name: str) -> bool:
    return os.path.exists(icon_path(name))


__all__ = ["SpriteManager", "EXPRESSIONS", "icon_path", "has_icon"]
