"""Wardrobe (outfits) and UI themes."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QCheckBox, QComboBox, QFormLayout, QGridLayout, QLabel, QVBoxLayout, QWidget

from ...core.wardrobe import EXPRESSIONS, MODES, OUTFITS, outfit_status
from ..theme import THEMES
from ..widgets import Card, button, clear_layout, hrow, label, page_header


class WardrobePage(QWidget):
    scrollable = True

    def __init__(self, ctx):
        super().__init__()
        self.ctx = ctx
        self.setObjectName("Page")
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 18)
        root.setSpacing(14)
        root.addWidget(page_header("Wardrobe", "Dress your prince and choose the look of the app."))
        self.grid = QGridLayout()
        self.grid.setSpacing(14)
        root.addLayout(self.grid)

        auto = Card("Automatic outfits")
        self.auto = QCheckBox("Change outfit automatically when the mode changes")
        self.auto.toggled.connect(self._auto)
        auto.add(self.auto)
        form = QFormLayout()
        self.mode_combos = {}
        for m in MODES:
            cb = QComboBox()
            for oid, lbl in OUTFITS.items():
                cb.addItem(lbl, oid)
            cb.currentIndexChanged.connect(lambda _i, mode=m, c=cb: self._map(mode, c.currentData()))
            self.mode_combos[m] = cb
            form.addRow(f"{m} mode", cb)
        auto.add(form)
        root.addWidget(auto)

        expr = Card("Expressions")
        self.expr_row = QGridLayout()
        expr.add(self.expr_row)
        expr.add(label("Aster switches expressions on his own: thinking while the AI works, focused during focus "
                       "sessions, sleepy in Rest mode or late at night, happy when you finish tasks.", "Muted", True))
        root.addWidget(expr)

        themes = Card("App theme")
        trow = []
        for tid, t in THEMES.items():
            b = button(t["label"], lambda _=False, x=tid: self._theme(x))
            b.setStyleSheet(f"QPushButton{{background:{t['bg']};color:{t['text']};border:2px solid {t['accent']};"
                            f"border-radius:12px;padding:16px 18px;font-weight:600;}}"
                            f"QPushButton:hover{{border-color:{t['accent2']};}}")
            trow.append(b)
        themes.add(hrow(*trow, None))
        root.addWidget(themes)
        root.addStretch(1)
        ctx.outfit_changed.connect(lambda _o: self.isVisible() and self.refresh())

    def refresh(self):
        core = self.ctx.core
        dpr = self.devicePixelRatioF()
        clear_layout(self.grid)
        for i, (oid, lbl) in enumerate(OUTFITS.items()):
            st = outfit_status(oid)
            card = Card(alt=(oid != core.outfit))
            pic = QLabel()
            pic.setAlignment(Qt.AlignmentFlag.AlignCenter)
            pic.setPixmap(self.ctx.sprites.frame(oid, "idle", False, 230, dpr))
            card.add(pic)
            name = label(lbl, "H2")
            name.setAlignment(Qt.AlignmentFlag.AlignCenter)
            card.add(name)
            if not st["available"]:
                warn = label("Artwork missing:\n" + "\n".join(st["missing"]), "Warn", True)
                card.add(warn)
            elif oid == core.outfit:
                cur = label("✓ Wearing now", "Gold")
                cur.setAlignment(Qt.AlignmentFlag.AlignCenter)
                card.add(cur)
            else:
                b = button("Wear this", lambda _=False, o=oid: self._wear(o), "Primary")
                card.add(b)
            self.grid.addWidget(card, i // 3, i % 3)
        clear_layout(self.expr_row)
        for i, e in enumerate(EXPRESSIONS):
            box = QVBoxLayout()
            pic = QLabel()
            pic.setAlignment(Qt.AlignmentFlag.AlignCenter)
            pic.setPixmap(self.ctx.sprites.portrait(core.outfit, e, 88, dpr))
            box.addWidget(pic)
            t = label(e.title(), "Muted")
            t.setAlignment(Qt.AlignmentFlag.AlignCenter)
            box.addWidget(t)
            self.expr_row.addLayout(box, 0, i)
        self.auto.blockSignals(True)
        self.auto.setChecked(core.auto_outfit)
        self.auto.blockSignals(False)
        mapping = self.ctx.cfg.get("wardrobe.mode_outfits", {})
        for m, cb in self.mode_combos.items():
            cb.blockSignals(True)
            cb.setCurrentIndex(max(0, cb.findData(mapping.get(m))))
            cb.blockSignals(False)

    def _wear(self, oid):
        if self.ctx.core.auto_outfit:
            self.ctx.core.set_auto_outfit(False)  # a manual choice shouldn't be overridden by the next mode change
        self.ctx.set_outfit(oid)
        self.ctx.expression.emit("smug", 3000)
        self.ctx.bubble(f"{OUTFITS[oid]}. Excellent taste. Naturally.", 4)
        self.refresh()

    def _auto(self, on):
        self.ctx.core.set_auto_outfit(on)
        if on:
            self.ctx.set_mode(self.ctx.core.mode)
        self.refresh()

    def _map(self, mode, oid):
        m = dict(self.ctx.cfg.get("wardrobe.mode_outfits", {}))
        m[mode] = oid
        self.ctx.cfg.set("wardrobe.mode_outfits", m)

    def _theme(self, tid):
        self.ctx.cfg.set("theme", tid)
        self.ctx.theme_changed.emit()
