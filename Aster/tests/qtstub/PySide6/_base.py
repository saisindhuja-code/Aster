"""Core of the fake Qt: permissive objects, real signals, simple stateful widgets."""
from __future__ import annotations

import inspect


class _Any:
    """Accepts any attribute access / call / arithmetic. Falsy, iterates as empty."""

    def __init__(self, *a, **k):
        pass

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        v = _Any()
        object.__setattr__(self, name, v)  # stable: Qt.X.Y is always the same object
        return v

    def __call__(self, *a, **k):
        return _Any()

    def __bool__(self):
        return False

    def __iter__(self):
        return iter(())

    def __len__(self):
        return 0

    def __int__(self):
        return 0

    def __index__(self):
        return 0

    def __float__(self):
        return 0.0

    def __str__(self):
        return ""

    def __format__(self, spec):
        return ""

    def __eq__(self, other):
        return self is other

    def __hash__(self):
        return id(self)

    def __lt__(self, o):
        return False

    __gt__ = __le__ = __ge__ = __lt__

    def _self(self, *a):
        return self

    __or__ = __ror__ = __and__ = __rand__ = __add__ = __radd__ = __sub__ = __rsub__ = _self
    __mul__ = __rmul__ = __truediv__ = __rtruediv__ = __floordiv__ = __neg__ = __xor__ = __invert__ = _self


class AnyMeta(type):
    def __getattr__(cls, name):
        if name.startswith("__"):
            raise AttributeError(name)
        v = _Any()
        type.__setattr__(cls, name, v)
        return v


def _call(fn, args):
    try:
        sig = inspect.signature(fn)
    except (TypeError, ValueError):
        return fn(*args)
    params = list(sig.parameters.values())
    if any(p.kind == p.VAR_POSITIONAL for p in params):
        return fn(*args)
    n = sum(1 for p in params if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD))
    return fn(*args[:n])


class BoundSignal:
    def __init__(self):
        self.slots = []

    def connect(self, fn, *a):
        if isinstance(fn, BoundSignal):
            self.slots.append(fn.emit)
        else:
            self.slots.append(fn)

    def disconnect(self, fn=None):
        if fn is None:
            self.slots.clear()
        elif fn in self.slots:
            self.slots.remove(fn)

    def emit(self, *args):
        for fn in list(self.slots):
            _call(fn, args)


class Signal:
    def __init__(self, *types, **kw):
        self.name = None

    def __set_name__(self, owner, name):
        self.name = name

    def __get__(self, obj, owner):
        if obj is None:
            return self
        key = "_sig_" + self.name
        d = obj.__dict__
        if key not in d:
            d[key] = BoundSignal()
        return d[key]


def Slot(*a, **k):
    return lambda f: f


class QObject(metaclass=AnyMeta):
    destroyed = Signal()

    def __init__(self, *args, **kw):
        for k, v in kw.items():
            attr = getattr(type(self), k, None)
            if isinstance(attr, Signal):
                getattr(self, k).connect(v)
            else:
                self.__dict__["_prop_" + k] = v

    def __getattr__(self, name):
        if name.startswith("__") or name.startswith("_sig_") or name.startswith("_prop_"):
            raise AttributeError(name)
        return _Any()

    def deleteLater(self):
        pass

    def setObjectName(self, n):
        self.__dict__["_objname"] = n

    def objectName(self):
        return self.__dict__.get("_objname", "")
