"""UI themes → Qt style sheets."""
from __future__ import annotations

THEMES = {
    "royal_purple": {
        "label": "Royal Purple",
        "bg": "#14122a", "bg2": "#1c1838", "card": "#242046", "card2": "#2e2856", "border": "#3d3570",
        "text": "#f4efff", "muted": "#b3a8d8", "accent": "#a98bff", "accent2": "#f3a6d0", "gold": "#e7bf5f",
        "good": "#7fd6a8", "bad": "#ff8fa3", "input": "#120f26", "sel": "#4a3d8f",
        "user_bubble": "#3b2f74", "ai_bubble": "#262049",
    },
    "midnight_blue": {
        "label": "Midnight Blue",
        "bg": "#0d1426", "bg2": "#121c34", "card": "#18233f", "card2": "#1f2c50", "border": "#2c3d68",
        "text": "#eef3ff", "muted": "#9fb0d6", "accent": "#7fb2ff", "accent2": "#b9a2ff", "gold": "#e7bf5f",
        "good": "#7fd6a8", "bad": "#ff8fa3", "input": "#0a1020", "sel": "#2f4a86",
        "user_bubble": "#24396b", "ai_bubble": "#172342",
    },
    "soft_lavender": {
        "label": "Soft Lavender",
        "bg": "#f3effc", "bg2": "#ebe4fa", "card": "#ffffff", "card2": "#f6f2ff", "border": "#d8ccf3",
        "text": "#2b2342", "muted": "#6e6290", "accent": "#7d5fd6", "accent2": "#d4589b", "gold": "#b88a2e",
        "good": "#2f8f63", "bad": "#c4405c", "input": "#ffffff", "sel": "#d9ccff",
        "user_bubble": "#e3d9ff", "ai_bubble": "#ffffff",
    },
    "warm_starlight": {
        "label": "Warm Starlight",
        "bg": "#1d1420", "bg2": "#271a2a", "card": "#312133", "card2": "#3b293d", "border": "#563a55",
        "text": "#fff4ea", "muted": "#d6b9b4", "accent": "#f0a86b", "accent2": "#f3a6d0", "gold": "#f2cf72",
        "good": "#9ad6a0", "bad": "#ff8f8f", "input": "#170f19", "sel": "#6b4560",
        "user_bubble": "#55354d", "ai_bubble": "#2c1e2e",
    },
}


def palette(name: str) -> dict:
    return THEMES.get(name, THEMES["royal_purple"])


def stylesheet(name: str, compact: bool = False) -> str:
    p = palette(name)
    pad = 4 if compact else 7
    fs = 12 if compact else 13
    return f"""
* {{ font-family: "Segoe UI", "Segoe UI Variable", Arial, sans-serif; font-size: {fs}px; color: {p['text']}; }}
QMainWindow, QDialog, #Page, #MiniChat, #Root {{ background: {p['bg']}; }}
QWidget#Sidebar {{ background: {p['bg2']}; border-right: 1px solid {p['border']}; }}
QFrame#Card {{ background: {p['card']}; border: 1px solid {p['border']}; border-radius: 14px; }}
QFrame#CardAlt {{ background: {p['card2']}; border: 1px solid {p['border']}; border-radius: 12px; }}
QLabel {{ background: transparent; }}
QLabel#H1 {{ font-size: {fs + 11}px; font-weight: 700; color: {p['text']}; }}
QLabel#H2 {{ font-size: {fs + 3}px; font-weight: 700; color: {p['accent2']}; }}
QLabel#Muted {{ color: {p['muted']}; }}
QLabel#Gold {{ color: {p['gold']}; font-weight: 700; }}
QLabel#Badge {{ background: {p['card2']}; border: 1px solid {p['border']}; border-radius: 9px; padding: 2px 8px; color: {p['muted']}; }}
QLabel#Warn {{ color: {p['bad']}; }}
QLabel#Good {{ color: {p['good']}; }}
QLabel#Timer {{ font-size: 56px; font-weight: 300; color: {p['text']}; }}
QPushButton {{ background: {p['card2']}; border: 1px solid {p['border']}; border-radius: 10px; padding: {pad}px 14px; }}
QPushButton:hover {{ border-color: {p['accent']}; }}
QPushButton:pressed {{ background: {p['sel']}; }}
QPushButton:disabled {{ color: {p['muted']}; background: {p['card']}; }}
QPushButton#Primary {{ background: {p['accent']}; color: #ffffff; border: none; font-weight: 600; }}
QPushButton#Primary:hover {{ background: {p['accent2']}; }}
QPushButton#Danger {{ color: {p['bad']}; }}
QPushButton#Nav {{ text-align: left; padding: 9px 14px; border: none; border-radius: 10px; background: transparent; font-size: {fs + 1}px; }}
QPushButton#Nav:hover {{ background: {p['card']}; }}
QPushButton#Nav:checked {{ background: {p['sel']}; color: #ffffff; font-weight: 600; }}
QPushButton#Flat {{ background: transparent; border: none; padding: 4px; }}
QPushButton#Flat:hover {{ background: {p['card2']}; }}
QLineEdit, QPlainTextEdit, QTextEdit, QSpinBox, QDoubleSpinBox, QComboBox, QDateEdit, QTimeEdit {{
    background: {p['input']}; border: 1px solid {p['border']}; border-radius: 9px; padding: {pad - 1}px 8px;
    selection-background-color: {p['sel']}; }}
QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus {{ border-color: {p['accent']}; }}
QComboBox QAbstractItemView {{ background: {p['card']}; selection-background-color: {p['sel']}; border: 1px solid {p['border']}; }}
QTextBrowser {{ background: {p['input']}; border: 1px solid {p['border']}; border-radius: 12px; padding: 6px; }}
QListWidget, QTreeWidget, QTableWidget {{ background: {p['input']}; border: 1px solid {p['border']}; border-radius: 10px;
    alternate-background-color: {p['card']}; outline: 0; }}
QListWidget::item, QTreeWidget::item {{ padding: 5px; border-radius: 6px; }}
QListWidget::item:selected, QTreeWidget::item:selected, QTableWidget::item:selected {{ background: {p['sel']}; color: #ffffff; }}
QHeaderView::section {{ background: {p['card2']}; border: none; padding: 6px; color: {p['muted']}; font-weight: 600; }}
QTabWidget::pane {{ border: 1px solid {p['border']}; border-radius: 12px; top: -1px; background: {p['card']}; }}
QTabBar::tab {{ background: transparent; padding: 8px 16px; color: {p['muted']}; border-bottom: 2px solid transparent; }}
QTabBar::tab:selected {{ color: {p['text']}; border-bottom: 2px solid {p['accent2']}; }}
QCheckBox, QRadioButton {{ spacing: 8px; background: transparent; }}
QCheckBox::indicator {{ width: 16px; height: 16px; border-radius: 5px; border: 1px solid {p['border']}; background: {p['input']}; }}
QCheckBox::indicator:checked {{ background: {p['accent']}; border-color: {p['accent']}; }}
QProgressBar {{ background: {p['input']}; border: 1px solid {p['border']}; border-radius: 7px; height: 12px; text-align: center; color: {p['text']}; }}
QProgressBar::chunk {{ border-radius: 6px; background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 {p['accent']}, stop:1 {p['accent2']}); }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {p['border']}; border-radius: 4px; min-height: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: {p['border']}; border-radius: 4px; min-width: 30px; }}
QScrollArea {{ background: transparent; border: none; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QMenu {{ background: {p['card']}; border: 1px solid {p['border']}; border-radius: 10px; padding: 6px; }}
QMenu::item {{ padding: 6px 22px; border-radius: 6px; }}
QMenu::item:selected {{ background: {p['sel']}; color: #ffffff; }}
QMenu::separator {{ height: 1px; background: {p['border']}; margin: 4px 8px; }}
QToolTip {{ background: {p['card']}; color: {p['text']}; border: 1px solid {p['border']}; padding: 4px; }}
QSplitter::handle {{ background: {p['border']}; }}
QGroupBox {{ border: 1px solid {p['border']}; border-radius: 12px; margin-top: 14px; padding: 10px; background: {p['card']}; }}
QGroupBox::title {{ subcontrol-origin: margin; left: 12px; padding: 0 6px; color: {p['accent2']}; font-weight: 700; }}
"""


def chat_css(name: str) -> str:
    """CSS for the QTextBrowser chat transcript (Qt's rich-text subset)."""
    p = palette(name)
    return f"""
body {{ color: {p['text']}; }}
p {{ margin: 0 0 6px 0; }}
h3, h4, h5, h6 {{ margin: 6px 0 4px 0; color: {p['accent2']}; }}
ul, ol {{ margin: 2px 0 6px 0; }}
a {{ color: {p['accent']}; }}
a.copy {{ color: {p['gold']}; text-decoration: none; }}
code.ic {{ font-family: Consolas, 'Cascadia Mono', monospace; background: {p['card2']}; color: {p['accent2']}; }}
table.code {{ background: {p['input']}; border: 1px solid {p['border']}; margin: 6px 0; }}
td.codehead {{ background: {p['card2']}; color: {p['muted']}; font-size: 11px; }}
td.codebody pre {{ font-family: Consolas, 'Cascadia Mono', monospace; font-size: 12px; color: {p['text']}; margin: 0; }}
span.lang {{ color: {p['muted']}; }}
blockquote {{ color: {p['muted']}; margin-left: 10px; }}
td.user {{ background: {p['user_bubble']}; }}
td.ai {{ background: {p['ai_bubble']}; border: 1px solid {p['border']}; }}
td.sys {{ color: {p['muted']}; font-style: italic; }}
span.who {{ color: {p['accent2']}; font-weight: 700; }}
span.whou {{ color: {p['accent']}; font-weight: 700; }}
span.time {{ color: {p['muted']}; font-size: 10px; }}
"""
