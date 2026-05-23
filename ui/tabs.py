# PyWeb – ui/tabs.py
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QPushButton, QTabBar
from PyQt6.QtCore import Qt, QPoint, pyqtSignal
from PyQt6.QtGui import QColor

C = {
    "bg":          "#0f0f18",
    "surface":     "#161620",
    "active":      "#1e1e2c",
    "border":      "#252535",
    "text":        "#c8c8e0",
    "subtext":     "#686880",
    "accent":      "#5a54c8",
    "close_hover": "#803030",
}

TAB_STYLE = f"""
QTabBar::tab {{
    background:{C['surface']};color:{C['subtext']};
    padding:7px 28px 7px 12px;border-radius:6px 6px 0 0;
    margin-right:2px;min-width:120px;max-width:210px;
    font-size:12px;border:1px solid {C['border']};border-bottom:none;
}}
QTabBar::tab:hover {{ background:{C['active']};color:{C['text']}; }}
QTabBar::tab:selected {{
    background:{C['active']};color:{C['text']};
    border-bottom:2px solid {C['accent']};font-weight:600;
}}
QTabBar::close-button {{ subcontrol-position:right;margin-right:4px;width:14px;height:14px; }}
"""

class TabBarWidget(QWidget):
    tab_close_requested    = pyqtSignal(int)
    new_tab_requested      = pyqtSignal()
    incognito_requested    = pyqtSignal()
    context_menu_requested = pyqtSignal(int, QPoint)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(40)
        self.setStyleSheet(f"background:{C['bg']};border-bottom:1px solid {C['border']};")

        lay = QHBoxLayout(self)
        lay.setContentsMargins(8,0,0,0)
        lay.setSpacing(0)

        self.tabs = QTabBar()
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        self.tabs.setExpanding(False)
        self.tabs.setStyleSheet(TAB_STYLE)
        self.tabs.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tabs.customContextMenuRequested.connect(self._on_context)
        self.tabs.tabCloseRequested.connect(self.tab_close_requested)
        lay.addWidget(self.tabs)

        self.btn_new = _Btn("+", "Yeni Sekme  Ctrl+T", 30)
        self.btn_new.clicked.connect(self.new_tab_requested)
        lay.addWidget(self.btn_new)

        self.btn_incognito = _Btn("⊘", "Gizli Sekme  Ctrl+Shift+N", 30)
        self.btn_incognito.clicked.connect(self.incognito_requested)
        lay.addWidget(self.btn_incognito)

        lay.addStretch()

        self.btn_win_min   = _WinBtn("–",  C["surface"])
        self.btn_win_max   = _WinBtn("□",  C["surface"])
        self.btn_win_close = _WinBtn("×",  C["close_hover"])
        for b in [self.btn_win_min, self.btn_win_max, self.btn_win_close]:
            b.setFixedSize(44, 40)
            lay.addWidget(b)

    def _on_context(self, pos):
        idx = self.tabs.tabAt(pos)
        if idx >= 0:
            self.context_menu_requested.emit(idx, self.tabs.mapToGlobal(pos))

    def stack_index(self, tab_idx):
        d = self.tabs.tabData(tab_idx)
        return d.get("stack") if isinstance(d, dict) else d

    @property
    def count(self): return self.tabs.count()

    @property
    def current_index(self): return self.tabs.currentIndex()


class _Btn(QPushButton):
    def __init__(self, text, tip, size=30, parent=None):
        super().__init__(text, parent)
        self.setToolTip(tip)
        self.setFixedSize(size, size)
        self.setStyleSheet(f"""
            QPushButton{{background:transparent;color:{C['subtext']};
                border:none;border-radius:5px;font-size:15px;font-weight:300;}}
            QPushButton:hover{{background:{C['surface']};color:{C['text']};}}
        """)

class _WinBtn(QPushButton):
    def __init__(self, text, hover_bg, parent=None):
        super().__init__(text, parent)
        self.setStyleSheet(f"""
            QPushButton{{background:transparent;color:{C['subtext']};
                border:none;font-size:14px;}}
            QPushButton:hover{{background:{hover_bg};color:{C['text']};}}
        """)
