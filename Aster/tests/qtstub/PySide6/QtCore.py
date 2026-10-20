from __future__ import annotations

import datetime as _dt

from ._base import AnyMeta, QObject, Signal, Slot, _Any  # noqa: F401


class Qt(metaclass=AnyMeta):
    pass


class QTimer(QObject):
    timeout = Signal()

    def __init__(self, *a, **kw):
        super().__init__(**kw)
        self._active = False
        self.interval = 0

    def start(self, ms=None):
        self._active = True
        if ms is not None:
            self.interval = ms

    def stop(self):
        self._active = False

    def isActive(self):
        return self._active

    @staticmethod
    def singleShot(ms, fn, *a):
        fn()


class QThread(QObject):
    started = Signal()
    finished = Signal()

    def __init__(self, *a, **kw):
        super().__init__()

    def start(self):
        self.started.emit()
        self.run()
        self.finished.emit()

    def run(self):
        pass

    def wait(self, *a):
        return True

    def isRunning(self):
        return False


class QAbstractNativeEventFilter:
    pass


class QPoint:
    def __init__(self, x=0, y=0):
        self._x, self._y = x, y

    def x(self):
        return self._x

    def y(self):
        return self._y

    def __add__(self, o):
        return QPoint(self._x + o._x, self._y + o._y)

    def __sub__(self, o):
        return QPoint(self._x - o._x, self._y - o._y)

    def manhattanLength(self):
        return abs(self._x) + abs(self._y)


class QPointF(QPoint):
    def toPoint(self):
        return QPoint(int(self._x), int(self._y))


class QRect(_Any):
    pass


class QRectF(_Any):
    pass


class QSize(_Any):
    pass


class QUrl:
    def __init__(self, s=""):
        self.s = s

    def toString(self):
        return self.s

    @staticmethod
    def fromLocalFile(p):
        return QUrl("file:///" + p)


class QDate:
    def __init__(self, d=None):
        self.d = d or _dt.date.today()

    @staticmethod
    def currentDate():
        return QDate()

    def addDays(self, n):
        return QDate(self.d + _dt.timedelta(days=n))

    def toString(self, fmt="yyyy-MM-dd"):
        return self.d.isoformat()

    @staticmethod
    def fromString(s, fmt="yyyy-MM-dd"):
        try:
            return QDate(_dt.date.fromisoformat(s))
        except (TypeError, ValueError):
            return QDate()


class QTime:
    def __init__(self, h=0, m=0):
        self.h, self.m = h, m

    @staticmethod
    def fromString(s, fmt="HH:mm"):
        h, m = s.split(":")
        return QTime(int(h), int(m))

    def toString(self, fmt="HH:mm"):
        return f"{self.h:02d}:{self.m:02d}"


class QRegularExpression(_Any):
    PatternOption = _Any()


class QLockFile:
    def __init__(self, path):
        self.path = path

    def setStaleLockTime(self, t):
        pass

    def tryLock(self, t=0):
        return True

    def unlock(self):
        pass


class QByteArray(_Any):
    pass
