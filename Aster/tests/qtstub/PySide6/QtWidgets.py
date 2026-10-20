from __future__ import annotations

from ._base import AnyMeta, QObject, Signal, _Any
from .QtCore import QDate, QTime
from .QtGui import QGuiApplication


class QWidget(QObject):
    def __init__(self, *a, **kw):
        super().__init__(**{k: v for k, v in kw.items()})
        self._visible = False
        self._blocked = False
        self._enabled = True
        self._w, self._h = 300, 400

    # visibility
    def show(self):
        self._visible = True

    def hide(self):
        self._visible = False

    def setVisible(self, v):
        self._visible = bool(v)

    def isVisible(self):
        return self._visible

    def close(self):
        self._visible = False
        return True

    def setEnabled(self, v):
        self._enabled = bool(v)

    def isEnabled(self):
        return self._enabled

    def blockSignals(self, b):
        old = self._blocked
        self._blocked = bool(b)
        return old

    def _emit(self, sig, *args):
        if not self._blocked:
            sig.emit(*args)

    def devicePixelRatioF(self):
        return 1.0

    def setFixedSize(self, w, h=None):
        if h is not None:
            self._w, self._h = w, h

    def width(self):
        return self._w

    def height(self):
        return self._h

    def update(self, *a):
        pass

    def isMinimized(self):
        return False


class QMainWindow(QWidget):
    pass


class QDialog(QWidget):
    def exec(self):
        return 0


class QFrame(QWidget):
    Shape = _Any()


class QLabel(QWidget):
    def __init__(self, text="", *a, **k):
        super().__init__()
        self._text = text

    def setText(self, t):
        self._text = t

    def text(self):
        return self._text


class QAbstractButton(QWidget):
    clicked = Signal(bool)
    toggled = Signal(bool)

    def __init__(self, text="", *a, **k):
        super().__init__()
        self._text = text
        self._checked = False
        self._checkable = False

    def setText(self, t):
        self._text = t

    def text(self):
        return self._text

    def setCheckable(self, v):
        self._checkable = v

    def setChecked(self, v):
        v = bool(v)
        if v != self._checked:
            self._checked = v
            self._emit(self.toggled, v)

    def isChecked(self):
        return self._checked

    def click(self):
        if self._checkable:
            self.setChecked(not self._checked)
        self.clicked.emit(self._checked)


class QPushButton(QAbstractButton):
    pass


class QCheckBox(QAbstractButton):
    def __init__(self, text="", *a, **k):
        super().__init__(text)
        self._checkable = True


class QRadioButton(QCheckBox):
    pass


class QLineEdit(QWidget):
    textChanged = Signal(str)
    returnPressed = Signal()
    editingFinished = Signal()

    def __init__(self, text="", *a, **k):
        super().__init__()
        self._text = text

    def setText(self, t):
        self._text = t
        self._emit(self.textChanged, t)

    def text(self):
        return self._text

    def clear(self):
        self.setText("")


class QPlainTextEdit(QWidget):
    textChanged = Signal()
    LineWrapMode = _Any()

    def __init__(self, text="", *a, **k):
        super().__init__()
        self._text = text

    def setPlainText(self, t):
        self._text = t

    def toPlainText(self):
        return self._text

    def insertPlainText(self, t):
        self._text += t

    def clear(self):
        self._text = ""

    def appendPlainText(self, t):
        self._text += "\n" + t

    def document(self):
        return _Any()


class QTextEdit(QPlainTextEdit):
    pass


class QTextBrowser(QPlainTextEdit):
    anchorClicked = Signal(object)

    def setHtml(self, h):
        self._html = h

    def toHtml(self):
        return getattr(self, "_html", "")

    def append(self, t):
        self._text += t

    def verticalScrollBar(self):
        return _Any()


class QComboBox(QWidget):
    currentIndexChanged = Signal(int)
    currentTextChanged = Signal(str)
    activated = Signal(int)

    def __init__(self, *a, **k):
        super().__init__()
        self._items = []  # (text, data)
        self._idx = -1
        self._edit_text = None

    def addItem(self, text, data=None):
        self._items.append((text, data))
        if self._idx < 0:
            self._idx = 0
            self._emit(self.currentIndexChanged, 0)

    def addItems(self, texts):
        for t in texts:
            self.addItem(t)

    def clear(self):
        self._items = []
        self._idx = -1

    def count(self):
        return len(self._items)

    def setCurrentIndex(self, i):
        if i != self._idx and 0 <= i < len(self._items):
            self._idx = i
            self._edit_text = None
            self._emit(self.currentIndexChanged, i)
            self._emit(self.currentTextChanged, self._items[i][0])

    def currentIndex(self):
        return self._idx

    def currentData(self):
        return self._items[self._idx][1] if 0 <= self._idx < len(self._items) else None

    def currentText(self):
        if self._edit_text is not None:
            return self._edit_text
        return self._items[self._idx][0] if 0 <= self._idx < len(self._items) else ""

    def setCurrentText(self, t):
        i = self.findText(t)
        if i >= 0:
            self.setCurrentIndex(i)
        else:
            self._edit_text = t

    def findData(self, d):
        for i, (_, dd) in enumerate(self._items):
            if dd == d:
                return i
        return -1

    def findText(self, t):
        for i, (tt, _) in enumerate(self._items):
            if tt == t:
                return i
        return -1

    def itemText(self, i):
        return self._items[i][0]

    def lineEdit(self):
        return _Any()


class _Spin(QWidget):
    valueChanged = Signal(object)

    def __init__(self, *a, **k):
        super().__init__()
        self._v = 0
        self._min, self._max = 0, 99

    def setRange(self, a, b):
        self._min, self._max = a, b
        self._v = min(max(self._v, a), b)

    def setValue(self, v):
        v = min(max(v, self._min), self._max)
        if v != self._v:
            self._v = v
            self._emit(self.valueChanged, v)

    def value(self):
        return self._v


class QSpinBox(_Spin):
    pass


class QDoubleSpinBox(_Spin):
    pass


class QDateEdit(QWidget):
    dateChanged = Signal(object)

    def __init__(self, d=None, *a, **k):
        super().__init__()
        self._d = d or QDate.currentDate()

    def setDate(self, d):
        self._d = d

    def date(self):
        return self._d


class QTimeEdit(QWidget):
    timeChanged = Signal(object)

    def __init__(self, *a, **k):
        super().__init__()
        self._t = QTime(0, 0)

    def setTime(self, t):
        self._t = t
        self._emit(self.timeChanged, t)

    def time(self):
        return self._t


class _Item:
    def __init__(self, text=""):
        self._text = text
        self._data = {}
        self._check = None

    def text(self, *col):
        return self._text

    def setText(self, *a):
        self._text = a[-1]

    def setData(self, *a):
        self._data[a[-2]] = a[-1]

    def data(self, *a):
        return self._data.get(a[-1])

    def setCheckState(self, *a):
        self._check = a[-1]

    def checkState(self, *a):
        return self._check

    def __getattr__(self, n):
        if n.startswith("__"):
            raise AttributeError(n)
        return _Any()


class QListWidgetItem(_Item):
    pass


class QListWidget(QWidget):
    itemClicked = Signal(object)
    currentRowChanged = Signal(int)
    currentItemChanged = Signal(object, object)

    def __init__(self, *a, **k):
        super().__init__()
        self._items = []
        self._row = -1

    def addItem(self, it):
        if isinstance(it, str):
            it = QListWidgetItem(it)
        self._items.append(it)

    def clear(self):
        self._items = []
        self._row = -1

    def count(self):
        return len(self._items)

    def item(self, i):
        return self._items[i]

    def currentItem(self):
        return self._items[self._row] if 0 <= self._row < len(self._items) else None

    def currentRow(self):
        return self._row

    def setCurrentRow(self, r):
        self._row = r
        self._emit(self.currentRowChanged, r)
        self._emit(self.currentItemChanged, self.currentItem(), None)

    def setCurrentItem(self, it):
        self.setCurrentRow(self._items.index(it))


class QTableWidgetItem(_Item):
    def __init__(self, text=""):
        super().__init__(text)
        self._row = self._col = 0

    def row(self):
        return self._row

    def column(self):
        return self._col


class QTableWidget(QWidget):
    itemChanged = Signal(object)
    cellDoubleClicked = Signal(int, int)
    SelectionBehavior = _Any()
    EditTrigger = _Any()

    def __init__(self, rows=0, cols=0, *a, **k):
        super().__init__()
        self._cells = {}
        self._rows, self._cols = rows, cols
        self._cur = -1

    def setRowCount(self, n):
        self._rows = n
        self._cells = {k: v for k, v in self._cells.items() if k[0] < n}

    def rowCount(self):
        return self._rows

    def setItem(self, r, c, it):
        it._row, it._col = r, c
        self._cells[(r, c)] = it

    def item(self, r, c):
        return self._cells.get((r, c))

    def currentRow(self):
        return self._cur

    def setCurrentCell(self, r, c):
        self._cur = r

    def insertRow(self, r):
        self._rows += 1

    def removeRow(self, r):
        self._cells = {(rr - (1 if rr > r else 0), c): v for (rr, c), v in self._cells.items() if rr != r}
        self._rows -= 1


class QTreeWidgetItem(_Item):
    def __init__(self, cols=None):
        super().__init__((cols or [""])[0])
        self.children = []

    def addChild(self, c):
        self.children.append(c)


class QTreeWidget(QWidget):
    itemChanged = Signal(object, int)
    itemDoubleClicked = Signal(object, int)

    def __init__(self, *a, **k):
        super().__init__()
        self.top = []

    def addTopLevelItem(self, it):
        self.top.append(it)

    def clear(self):
        self.top = []

    def currentItem(self):
        return None


class QTabWidget(QWidget):
    currentChanged = Signal(int)

    def __init__(self, *a, **k):
        super().__init__()
        self._tabs = []
        self._i = 0

    def addTab(self, w, name):
        self._tabs.append(w)

    def currentWidget(self):
        return self._tabs[self._i] if self._tabs else None

    def setCurrentIndex(self, i):
        self._i = i
        self._emit(self.currentChanged, i)

    def count(self):
        return len(self._tabs)


class QStackedWidget(QWidget):
    def __init__(self, *a, **k):
        super().__init__()
        self._w = []
        self.current = None

    def addWidget(self, w):
        self._w.append(w)

    def setCurrentWidget(self, w):
        self.current = w


class _LayoutItem:
    def __init__(self, w=None, l=None):
        self._w, self._l = w, l

    def widget(self):
        return self._w

    def layout(self):
        return self._l


class _Layout(QObject):
    def __init__(self, parent=None, *a, **k):
        super().__init__()
        self.items = []

    def addWidget(self, w, *a, **k):
        self.items.append(_LayoutItem(w=w))

    def addLayout(self, l, *a, **k):
        self.items.append(_LayoutItem(l=l))

    def addRow(self, *a):
        for x in a:
            if isinstance(x, QWidget):
                self.addWidget(x)
            elif isinstance(x, _Layout):
                self.addLayout(x)

    def addStretch(self, *a):
        self.items.append(_LayoutItem())

    def count(self):
        return len(self.items)

    def takeAt(self, i):
        return self.items.pop(i)


class QHBoxLayout(_Layout):
    pass


class QVBoxLayout(_Layout):
    pass


class QGridLayout(_Layout):
    pass


class QFormLayout(_Layout):
    pass


class QScrollArea(QWidget):
    Shape = _Any()


class QSplitter(QWidget):
    pass


class QSizeGrip(QWidget):
    pass


class QProgressBar(QWidget):
    pass


class QGroupBox(QWidget):
    pass


class QMenu(QWidget):
    aboutToShow = Signal()

    def addAction(self, *a):
        return _Any()

    def addMenu(self, *a):
        return QMenu()

    def exec(self, *a):
        return None


class QButtonGroup(QObject):
    def addButton(self, b, *a):
        pass


class QHeaderView(metaclass=AnyMeta):
    pass


class QDialogButtonBox(QWidget):
    accepted = Signal()
    rejected = Signal()
    StandardButton = _Any()
    ButtonRole = _Any()


class QSizePolicy(metaclass=AnyMeta):
    pass


class QAbstractItemView(metaclass=AnyMeta):
    pass


class QMessageBox(QWidget):
    Icon = _Any()
    StandardButton = _Any()
    ButtonRole = _Any()
    shown = []

    def exec(self):
        return 0

    @staticmethod
    def information(*a):
        QMessageBox.shown.append(("information", a[1:]))

    @staticmethod
    def warning(*a):
        QMessageBox.shown.append(("warning", a[1:]))

    @staticmethod
    def critical(*a):
        QMessageBox.shown.append(("critical", a[1:]))


class QInputDialog(metaclass=AnyMeta):
    answers = []  # queue of return values for tests

    @staticmethod
    def _next(default):
        return QInputDialog.answers.pop(0) if QInputDialog.answers else default

    @staticmethod
    def getText(*a, **k):
        return QInputDialog._next(("", False))

    @staticmethod
    def getMultiLineText(*a, **k):
        return QInputDialog._next(("", False))

    @staticmethod
    def getItem(*a, **k):
        return QInputDialog._next(("", False))


class QFileDialog(metaclass=AnyMeta):
    @staticmethod
    def getOpenFileName(*a, **k):
        return ("", "")

    @staticmethod
    def getSaveFileName(*a, **k):
        return ("", "")


class QSystemTrayIcon(QObject):
    activated = Signal(object)
    ActivationReason = _Any()

    @staticmethod
    def isSystemTrayAvailable():
        return False


class QApplication(QGuiApplication):
    aboutToQuit = Signal()

    def __init__(self, *a):
        super().__init__()

    def setStyleSheet(self, s):
        self.style = s

    @staticmethod
    def beep():
        pass

    def exec(self):
        return 0

    def quit(self):
        self.aboutToQuit.emit()
