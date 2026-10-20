from __future__ import annotations

from ._base import AnyMeta, QObject, Signal, _Any


class QAction(QObject):
    triggered = Signal(bool)
    toggled = Signal(bool)

    def __init__(self, text="", parent=None, checkable=False, checked=False, **kw):
        super().__init__()
        self._text, self._checked, self._enabled = text, checked, True

    def setChecked(self, v):
        self._checked = bool(v)

    def isChecked(self):
        return self._checked

    def setEnabled(self, v):
        self._enabled = v


class QActionGroup(QObject):
    def addAction(self, a):
        return a


class QIcon(_Any):
    pass


class QPixmap:
    def __init__(self, *a):
        if len(a) == 2:
            self._w, self._h = a
        elif a and isinstance(a[0], str):
            import os
            self._w, self._h = (720, 960) if os.path.exists(a[0]) else (0, 0)
        else:
            self._w, self._h = 0, 0
        self.dpr = 1.0

    def isNull(self):
        return self._w == 0

    def width(self):
        return self._w

    def height(self):
        return self._h

    def rect(self):
        return _Any()

    def fill(self, *a):
        pass

    def setDevicePixelRatio(self, r):
        self.dpr = r

    def scaled(self, w, h, *a):
        return QPixmap(w, h)

    def copy(self, x, y, w, h):
        return QPixmap(w, h)


class QPainter(_Any):
    RenderHint = _Any()


class QColor(_Any):
    pass


class QFont(_Any):
    Weight = _Any()
    StyleHint = _Any()


class QPen(_Any):
    pass


class QBrush(_Any):
    pass


class QPainterPath(_Any):
    pass


class QCursor(_Any):
    pass


class QTextCharFormat(_Any):
    pass


class _Clipboard:
    def __init__(self):
        self._t = ""

    def setText(self, t):
        self._t = t

    def text(self):
        return self._t


class QGuiApplication(QObject):
    _clip = _Clipboard()

    @staticmethod
    def clipboard():
        return QGuiApplication._clip

    @staticmethod
    def screenAt(p):
        return None

    @staticmethod
    def primaryScreen():
        return _Any()


class QDesktopServices(metaclass=AnyMeta):
    opened = []

    @staticmethod
    def openUrl(u):
        QDesktopServices.opened.append(u)


class QSyntaxHighlighter:
    def __init__(self, doc=None):
        pass

    def setFormat(self, *a):
        pass
