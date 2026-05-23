# PyWeb – ui/window.py  (tam sürüm)
from __future__ import annotations
import os, sys, json, time, re, urllib.parse
from typing import Optional

from PyQt6.QtCore import (Qt, QUrl, QPoint, QTimer, QPropertyAnimation,
                           QEasingCurve, QSize, pyqtSignal, QRect)
from PyQt6.QtWidgets import (QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QLineEdit, QPushButton, QLabel, QStackedWidget, QListWidget, QListWidgetItem,
    QFileDialog, QProgressBar, QApplication, QMenu, QMessageBox, QDialog,
    QPlainTextEdit, QComboBox, QCheckBox, QTextEdit, QScrollArea, QSplitter,
    QInputDialog, QSpinBox, QRadioButton)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import (QWebEngineProfile, QWebEngineScript,
    QWebEngineDownloadRequest, QWebEnginePage, QWebEngineSettings,
    QWebEngineUrlRequestInterceptor, QWebEngineUrlRequestInfo)
from PyQt6.QtGui import (QIcon, QShortcut, QKeySequence, QColor, QPixmap,
                          QPainter, QPen, QBrush, QPolygonF)
from PyQt6.QtCore import QPointF
from PyQt6.QtPrintSupport import QPrinter, QPrintDialog

from ui.tabs import TabBarWidget
from storage.history_db import HistoryDB
from storage.bookmark import BookmarkManager
from storage.download_manager import DownloadManager
from core.engine.page_context import PageContext
from core.scheduler.thread_pool import ThreadPool
from core.scheduler.event_loop import EventLoop

# ── Dizinler ──────────────────────────────────────────────────
BASE_DIR  = os.path.dirname(os.path.dirname(__file__))
DATA_DIR  = os.path.join(os.path.expanduser("~"), ".pyweb")
PAGES_DIR = os.path.join(BASE_DIR, "pages")
os.makedirs(DATA_DIR, exist_ok=True)

SETTINGS_FILE = os.path.join(DATA_DIR, "settings.json")
SESSIONS_FILE = os.path.join(DATA_DIR, "sessions.json")
NEWTAB_FILE   = os.path.join(PAGES_DIR, "newtab.html")
HISTORY_FILE  = os.path.join(PAGES_DIR, "history.html")
ERROR_FILE    = os.path.join(PAGES_DIR, "error404.html")
CUSTOM_CSS    = os.path.join(DATA_DIR, "custom.css")
CUSTOM_JS     = os.path.join(DATA_DIR, "custom.js")

def _newtab_url():
    if os.path.exists(NEWTAB_FILE):
        return QUrl.fromLocalFile(NEWTAB_FILE).toString()
    return "https://duckduckgo.com"

def _error_url():
    if os.path.exists(ERROR_FILE):
        return QUrl.fromLocalFile(ERROR_FILE).toString()
    return ""

# ── Renk paleti (mat, neon yok) ───────────────────────────────
C = {
    "bg":      "#0f0f18", "mantle":  "#0c0c14",
    "surface": "#161620", "surface2":"#1e1e2c",
    "border":  "#252535", "text":    "#c8c8e0",
    "subtext": "#686880", "accent":  "#5a54c8",
    "accent2": "#3d7acc", "success": "#4aab6d",
    "warn":    "#b89040", "danger":  "#b04040",
}

# ── Arama motorları (Google telemetri parametresiz) ────────────
SEARCH_ENGINES = {
    "DuckDuckGo": "https://duckduckgo.com/?q={}",
    "Google":     "https://www.google.com/search?q={}&pws=0&nfpr=1",
    "Bing":       "https://www.bing.com/search?q={}",
    "Brave":      "https://search.brave.com/search?q={}",
    "Ecosia":     "https://www.ecosia.org/search?q={}",
    "SearXNG":    "https://searx.be/search?q={}",
}

CONTAINERS = {
    "Kişisel":   "#4aab6d", "İş":     "#3d7acc",
    "Alışveriş": "#b89040", "Sosyal": "#5a54c8",
    "Araştırma": "#3a8a8a", "Genel":  "#686880",
}

UA_MAP = {
    "default": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"),
    "mobile":  ("Mozilla/5.0 (Linux; Android 13; Pixel 7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Mobile Safari/537.36"),
}

# ── Google/Meta telemetri engel listesi ───────────────────────
TELEMETRY_HOSTS = {
    "ssl.google-analytics.com","www.google-analytics.com",
    "google-analytics.com","analytics.google.com",
    "googletagmanager.com","googletagservices.com",
    "doubleclick.net","adservice.google.com","adservice.google.com.tr",
    "pagead2.googlesyndication.com","tpc.googlesyndication.com",
    "connect.facebook.net","graph.facebook.com","pixel.facebook.com",
    "bat.bing.com","c.clarity.ms","hotjar.com","mouseflow.com",
    "fullstory.com","segment.com","mixpanel.com","amplitude.com",
    "heap.io","stats.g.doubleclick.net","cm.g.doubleclick.net",
    "scorecardresearch.com","quantserve.com","taboola.com","outbrain.com",
    "criteo.com","adnxs.com","rubiconproject.com","openx.net",
}

TRACKER_JS = (
    "(function(){var B=" + json.dumps(sorted(TELEMETRY_HOSTS)) + ";"
    "function bl(u){if(typeof u!=='string')return false;"
    "for(var i=0;i<B.length;i++)if(u.indexOf(B[i])>-1)return true;return false;}"
    "var ox=XMLHttpRequest.prototype.open;"
    "XMLHttpRequest.prototype.open=function(m,u){if(bl(u))return;return ox.apply(this,arguments);};"
    "var of=window.fetch;"
    "if(of)window.fetch=function(u,o){if(bl(u+''))return Promise.reject(new Error('blocked'));"
    "return of.apply(this,arguments);};"
    "var oc=document.createElement.bind(document);"
    "document.createElement=function(t){"
    "var el=oc(t);if(t.toLowerCase()==='script'){"
    "var d=Object.getOwnPropertyDescriptor(HTMLElement.prototype,'src');"
    "Object.defineProperty(el,'src',{set:function(v){if(bl(v))return;d.set.call(this,v);},"
    "get:function(){return d.get.call(this);}});}return el;};"
    "})()"
)

DARK_ON  = ("(function(){if(document.getElementById('__pw_dk'))return;"
            "var s=document.createElement('style');s.id='__pw_dk';"
            "s.textContent='html{filter:invert(1) hue-rotate(180deg)!important;}"
            "img,video,canvas,iframe{filter:invert(1) hue-rotate(180deg)!important;}';"
            "document.head.appendChild(s);})()")
DARK_OFF = ("(function(){var s=document.getElementById('__pw_dk');"
            "if(s)s.remove();})()")
FOCUS_ON = ("(function(){if(document.getElementById('__pw_foc'))return;"
            "var s=document.createElement('style');s.id='__pw_foc';"
            "s.textContent='*{animation:none!important;transition:none!important;}"
            "[class*=\"ad\"],[id*=\"ad\"],[class*=\"banner\"],[class*=\"popup\"],"
            "[class*=\"cookie\"],[class*=\"consent\"],[class*=\"overlay\"]"
            "{display:none!important;}';"
            "document.head.appendChild(s);})()")

# ── İkon motoru ───────────────────────────────────────────────
def _ic(name: str, color: str = "#c8c8e0", size: int = 20) -> QIcon:
    px = QPixmap(size, size); px.fill(Qt.GlobalColor.transparent)
    p  = QPainter(px); p.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen= QPen(QColor(color), 1.7, Qt.PenStyle.SolidLine,
               Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen); s = size / 20

    def L(x1,y1,x2,y2): p.drawLine(int(x1*s),int(y1*s),int(x2*s),int(y2*s))
    def R(x,y,w,h): p.drawRect(int(x*s),int(y*s),int(w*s),int(h*s))
    def E(x,y,w,h): p.drawEllipse(int(x*s),int(y*s),int(w*s),int(h*s))
    def A(x,y,w,h,a,sp): p.drawArc(int(x*s),int(y*s),int(w*s),int(h*s),a,sp)
    def poly(pts, fill=False):
        if fill: p.setBrush(QBrush(QColor(color)))
        p.drawPolygon(QPolygonF([QPointF(x*s,y*s) for x,y in pts]))
        p.setBrush(Qt.BrushStyle.NoBrush)

    d = {
        "back":    lambda: (L(14,10,6,10),L(9,6,6,10),L(9,14,6,10)),
        "forward": lambda: (L(6,10,14,10),L(11,6,14,10),L(11,14,14,10)),
        "refresh": lambda: (A(5,5,10,10,45*16,270*16),L(13,8,13,4),L(13,8,9,8)),
        "stop":    lambda: (L(6,6,14,14),L(14,6,6,14)),
        "home":    lambda: (L(5,11,10,4),L(10,4,15,11),L(7,11,7,17),L(13,11,13,17),L(7,17,13,17)),
        "lock":    lambda: (R(5,9,10,7), A(7,4,6,9,0,180*16)),
        "lock_open":lambda:(R(5,9,10,7), A(7,2,6,8,0,180*16), L(7,2,4,2)),
        "star":    lambda: poly([(10,3),(11.8,7.5),(16.5,7.5),(12.8,10.5),(14.2,15),(10,12.2),(5.8,15),(7.2,10.5),(3.5,7.5),(8.2,7.5)]),
        "star_on": lambda: poly([(10,3),(11.8,7.5),(16.5,7.5),(12.8,10.5),(14.2,15),(10,12.2),(5.8,15),(7.2,10.5),(3.5,7.5),(8.2,7.5)], fill=True),
        "menu":    lambda: (L(4,6,16,6),L(4,10,16,10),L(4,14,16,14)),
        "find":    lambda: (E(4,4,9,9),L(12,12,17,17)),
        "reader":  lambda: (L(4,5,16,5),L(4,8,16,8),L(4,11,13,11),L(4,14,14,14),L(4,17,11,17)),
        "pip":     lambda: (R(3,4,14,9), [p.setBrush(QBrush(QColor(color))),R(11,10,7,5),p.setBrush(Qt.BrushStyle.NoBrush)]),
        "shot":    lambda: (R(4,5,12,10),E(8,8,4,4),L(4,5,6,3),L(6,3,9,3)),
        "translate":lambda:(L(4,6,16,6),L(10,4,10,8),L(6,6,5,14),L(14,6,15,14),L(6,14,14,14)),
        "share":   lambda: (E(13,3,4,4),E(3,8,4,4),E(13,13,4,4),L(5,10,13,5),L(5,11,13,15)),
        "print":   lambda: (R(5,7,10,6),R(6,4,8,3),R(5,13,10,5),L(6,15,6,17),L(14,15,14,17),L(6,17,14,17)),
        "dl":      lambda: (L(10,4,10,14),L(6,10,10,14),L(14,10,10,14),L(4,17,16,17)),
        "settings":None,
        "shield_ok":None,
        "dns":     lambda: (E(4,4,12,12),L(10,4,10,16),L(4,10,16,10)),
        "history": lambda: (E(4,4,12,12),L(10,6,10,10),L(10,10,13,12)),
        "note":    lambda: (R(4,3,12,14),L(7,7,13,7),L(7,10,13,10),L(7,13,11,13)),
        "task":    lambda: (R(4,3,12,14),L(7,8,9,11),L(9,11,14,6),L(7,14,13,14)),
        "pw":      lambda: (E(6,4,8,8),R(4,10,12,7),L(10,13,10,15)),
        "code":    lambda: (L(7,6,3,10),L(3,10,7,14),L(13,6,17,10),L(17,10,13,14),L(11,4,9,16)),
        "zi":      lambda: (E(4,4,9,9),L(12,12,17,17),L(8,8,8,12),L(6,10,10,10)),
        "zo":      lambda: (E(4,4,9,9),L(12,12,17,17),L(6,10,10,10)),
        "gemini":  lambda: poly([(10,2),(12,8),(18,10),(12,12),(10,18),(8,12),(2,10),(8,8)],fill=True),
        "split":   lambda: (R(3,4,6,12),R(11,4,6,12),L(10,4,10,16)),
        "container":lambda:(R(3,3,6,6),R(11,3,6,6),R(3,11,6,6)),
        "close_x": lambda: (L(5,5,15,15),L(15,5,5,15)),
        "max_sq":  lambda: R(4,4,12,12),
        "min_ln":  lambda: L(4,16,16,16),
        "incognito":lambda:(E(6,5,8,7),L(4,14,16,14),L(4,14,7,18),L(16,14,13,18)),
        "source":  lambda: (L(7,6,3,10),L(3,10,7,14),L(13,6,17,10),L(17,10,13,14)),
        "save":    lambda: (R(4,4,12,12),L(7,4,7,9),L(13,4,13,9),L(10,11,10,16),L(6,12,10,16),L(14,12,10,16)),
        "fullscreen": lambda:(L(3,3,7,3),L(3,3,3,7),L(17,3,13,3),L(17,3,17,7),L(3,17,7,17),L(3,17,3,13),L(17,17,13,17),L(17,17,17,13)),
        "exit_full":  lambda:(L(3,7,7,7),L(7,3,7,7),L(13,3,13,7),L(17,7,13,7),L(3,13,7,13),L(7,17,7,13),L(13,17,13,13),L(17,13,13,13)),
        "timer":   lambda: (E(4,5,12,12),L(10,8,10,11),L(10,11,13,12),L(8,3,12,3)),
    }

    if name == "settings":
        E(7,7,6,6)
        for _ in range(4): L(10,2,10,6); L(10,14,10,18); p.translate(int(10*s),int(10*s)); p.rotate(45); p.translate(-int(10*s),-int(10*s))
    elif name == "shield_ok":
        from PyQt6.QtGui import QPainterPath
        pp=QPainterPath(); pp.moveTo(10*s,3*s); pp.lineTo(16*s,6*s); pp.lineTo(16*s,12*s)
        pp.quadTo(16*s,17*s,10*s,18*s); pp.quadTo(4*s,17*s,4*s,12*s); pp.lineTo(4*s,6*s); pp.closeSubpath()
        p.drawPath(pp); L(6,10,9,14); L(9,14,14,8)
    elif name in d and d[name]:
        try: d[name]()
        except Exception: pass

    p.end()
    return QIcon(px)


def _btn(icon="", tip="", color=None, size=32) -> QPushButton:
    b = QPushButton()
    c = color or C["subtext"]
    if icon: b.setIcon(_ic(icon, c)); b.setIconSize(QSize(18,18))
    b.setToolTip(tip); b.setFixedSize(size,size)
    b.setStyleSheet(
        f"QPushButton{{background:transparent;border:none;border-radius:5px;}}"
        f"QPushButton:hover{{background:{C['surface2']};}}"
        f"QPushButton:pressed{{background:{C['border']};}}")
    return b


# ── İstek Yakalayıcı (telemetri + reklam engel) ───────────────
class _Interceptor(QWebEngineUrlRequestInterceptor):
    def __init__(self, blocked_sites=None, ad_block=True):
        super().__init__()
        self.blocked_sites = blocked_sites or []
        self.ad_block      = ad_block
        self.count         = 0
        self._patterns     = [re.compile(p, re.I) for p in [
            r"doubleclick\.net", r"googlesyndication\.com",
            r"adservice\.google\.", r"facebook\.net.*sdk",
            r"hotjar\.com", r"fullstory\.com", r"\.ads\.",
            r"/adserver/", r"tracking\.", r"analytics\.",
        ]]

    def interceptRequest(self, info: QWebEngineUrlRequestInfo):
        url  = info.requestUrl().toString()
        host = info.requestUrl().host().lower()

        # Telemetri engeli
        if host in TELEMETRY_HOSTS:
            info.block(True); self.count += 1; return

        # Kullanıcı listesi
        for s in self.blocked_sites:
            if s.lower() in host:
                info.block(True); self.count += 1; return

        # Reklam pattern
        if self.ad_block:
            for pat in self._patterns:
                if pat.search(url):
                    info.block(True); self.count += 1; return

        # Güvenlik başlıkları
        info.setHttpHeader(b"X-Content-Type-Options", b"nosniff")
        info.setHttpHeader(b"X-Frame-Options", b"SAMEORIGIN")

        # Google izleme parametrelerini temizle
        if "google.com" in host:
            url2 = re.sub(r"[&?](gclid|utm_[^&]+|fbclid|msclkid)=[^&]*","",url)
            if url2 != url:
                info.redirect(QUrl(url2))


# ═════════════════════════════════════════════════════════════
# ANA PENCERE
# ═════════════════════════════════════════════════════════════
class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("PyWeb")
        self.resize(1440, 900)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setStyleSheet(
            f"background:{C['bg']};color:{C['text']};"
            f"font-family:'Segoe UI',sans-serif;")

        # Servisler
        self._settings    = self._load_settings()
        self._history_db  = HistoryDB()
        self._bookmarks   = BookmarkManager()
        self._dl_manager  = DownloadManager()
        self._thread_pool = ThreadPool(max_workers=4)
        self._event_loop  = EventLoop()
        self._thread_pool.start(); self._event_loop.start()

        # Durum
        self._contexts:    dict[int, PageContext] = {}
        self._dark_tabs:   set[int] = set()
        self._focus_tabs:  set[int] = set()
        self._reader_tabs: set[int] = set()
        self._pip_windows: list     = []
        self._last_closed: Optional[str] = None
        self._side_mode:   Optional[str] = None
        self._find_open:   bool          = False
        self._fullscreen:  bool          = False
        self._old_pos      = QPoint()
        self._pre_fs_geom  = None  # tam ekran öncesi geometri

        # Profil & UA
        ua = UA_MAP.get(self._settings.get("user_agent","default"), UA_MAP["default"])
        self._ua = ua
        self._interceptor = _Interceptor(
            blocked_sites=self._settings.get("blocked_sites",[]),
            ad_block=self._settings.get("ad_block", True),
        )
        profile = QWebEngineProfile.defaultProfile()
        profile.setHttpUserAgent(ua)
        profile.setUrlRequestInterceptor(self._interceptor)
        # Google telemetri scriptlerini baştan engelle
        self._inject_tracker(profile)
        # Spellcheck kapat (gizlilik)
        profile.setSpellCheckEnabled(False)

        self._build_ui()
        self._connect_signals()
        self._setup_shortcuts()
        self._setup_tray()

        # Zamanlayıcılar
        QTimer.singleShot(800, self._check_doh)
        self._auto_save_tmr = QTimer(self); self._auto_save_tmr.timeout.connect(self._auto_save); self._auto_save_tmr.start(30_000)
        self._read_tmr = QTimer(self); self._read_tmr.timeout.connect(self._tick_reading); self._read_tmr.start(1_000)

        # İlk sekme
        if self._settings.get("restore_session", True):
            self._restore_session()
        else:
            self._open_newtab()

    # ── Arayüz ──────────────────────────────────────────────────
    def _build_ui(self):
        root = QWidget(); root.setStyleSheet(f"background:{C['bg']};")
        v = QVBoxLayout(root); v.setContentsMargins(0,0,0,0); v.setSpacing(0)
        self.setCentralWidget(root)

        self._tab_bar = TabBarWidget(self)
        v.addWidget(self._tab_bar)
        v.addWidget(self._build_navbar())
        self._find_bar = self._build_find_bar(); v.addWidget(self._find_bar)

        body = QHBoxLayout(); body.setContentsMargins(0,0,0,0); body.setSpacing(0)
        body.addWidget(self._build_left_bar())
        self._side_panel = self._build_side_panel()
        body.addWidget(self._side_panel)
        self._content = QStackedWidget(); body.addWidget(self._content)
        bw = QWidget(); bw.setLayout(body); v.addWidget(bw, 1)

        self._dl_bar = self._build_dl_bar(); v.addWidget(self._dl_bar)
        v.addWidget(self._build_status_bar())

    def _build_navbar(self):
        bar = QWidget(); bar.setFixedHeight(46)
        bar.setStyleSheet(f"background:{C['bg']};border-bottom:1px solid {C['border']};")
        lay = QHBoxLayout(bar); lay.setContentsMargins(8,0,8,0); lay.setSpacing(4)

        self._btn_back    = _btn("back",    "Geri  Alt+Sol")
        self._btn_fwd     = _btn("forward", "İleri  Alt+Sağ")
        self._btn_reload  = _btn("refresh", "Yenile  F5")
        self._btn_home    = _btn("home",    "Ana Sayfa")
        for b in [self._btn_back, self._btn_fwd, self._btn_reload, self._btn_home]:
            lay.addWidget(b)

        # Adres kutusu
        aw = QWidget()
        aw.setStyleSheet(f"background:{C['surface']};border:1px solid {C['border']};border-radius:14px;max-height:30px;")
        al = QHBoxLayout(aw); al.setContentsMargins(10,0,6,0); al.setSpacing(4)
        self._btn_sec = _btn("lock","HTTPS Güvenli", C["success"], 22); self._btn_sec.setFixedSize(22,22)
        self._addr = QLineEdit(); self._addr.setPlaceholderText("Arama yapın veya URL girin…")
        self._addr.setStyleSheet(f"background:transparent;border:none;color:{C['text']};font-size:13px;font-family:Consolas;")
        self._btn_shield = _btn("shield_ok","Tracker koruması aktif", C["success"], 22); self._btn_shield.setFixedSize(22,22)
        self._btn_star   = _btn("star","Favorilere ekle  Ctrl+D", C["subtext"], 24); self._btn_star.setFixedSize(24,24)
        al.addWidget(self._btn_sec); al.addWidget(self._addr,1); al.addWidget(self._btn_shield); al.addWidget(self._btn_star)
        lay.addWidget(aw,1)

        # Sağ butonlar
        nb = [
            ("_btn_reader",  "reader",    "Okuma Modu  Ctrl+R"),
            ("_btn_find_btn","find",      "Ara  Ctrl+F"),
            ("_btn_pip",     "pip",       "Resim İçinde Resim"),
            ("_btn_shot",    "shot",      "Ekran Görüntüsü  Ctrl+Shift+S"),
            ("_btn_trans",   "translate", "Çevir"),
            ("_btn_share",   "share",     "Paylaş"),
            ("_btn_print",   "print",     "Yazdır  Ctrl+P"),
            ("_btn_zo",      "zo",        "Uzaklaştır"),
            ("_btn_zi",      "zi",        "Yaklaştır"),
            ("_btn_menu",    "menu",      "Menü"),
        ]
        for attr, icon, tip in nb:
            b = _btn(icon, tip); setattr(self, attr, b); lay.addWidget(b)
        return bar

    def _build_find_bar(self):
        bar = QWidget(); bar.setFixedHeight(0)
        bar.setStyleSheet(f"background:{C['surface']};border-bottom:1px solid {C['border']};")
        lay = QHBoxLayout(bar); lay.setContentsMargins(12,4,12,4); lay.setSpacing(6)
        lbl = QLabel("Bul:"); lbl.setStyleSheet(f"color:{C['subtext']};font-size:12px;")
        self._find_inp = QLineEdit(); self._find_inp.setPlaceholderText("Sayfada ara…"); self._find_inp.setFixedWidth(240)
        self._find_inp.setStyleSheet(f"background:{C['surface2']};border:1px solid {C['border']};border-radius:5px;padding:4px 8px;color:{C['text']};font-size:12px;")
        self._find_res = QLabel(""); self._find_res.setStyleSheet(f"color:{C['subtext']};font-size:11px;")
        bp = _btn("back","Önceki",size=26); bn = _btn("forward","Sonraki",size=26); bx = _btn("close_x","Kapat",size=26)
        bp.clicked.connect(lambda: self._do_find(True)); bn.clicked.connect(lambda: self._do_find())
        bx.clicked.connect(self._hide_find); self._find_inp.returnPressed.connect(lambda: self._do_find())
        self._find_inp.textChanged.connect(lambda: self._do_find())
        lay.addWidget(lbl); lay.addWidget(self._find_inp); lay.addWidget(self._find_res)
        lay.addWidget(bp); lay.addWidget(bn); lay.addStretch(); lay.addWidget(bx)
        return bar

    def _build_left_bar(self):
        bar = QWidget(); bar.setFixedWidth(48)
        bar.setStyleSheet(f"background:{C['mantle']};border-right:1px solid {C['border']};")
        lay = QVBoxLayout(bar); lay.setContentsMargins(4,10,4,10); lay.setSpacing(4)
        lay.setAlignment(Qt.AlignmentFlag.AlignTop|Qt.AlignmentFlag.AlignHCenter)

        def lb(i,t,c=None):
            b=_btn(i,t,c,38); b.setFixedSize(38,38); return b

        self._lb = {
            "gemini":   lb("gemini",   "Gemini AI",          C["accent"]),
            "history":  lb("history",  "Geçmiş  Ctrl+H"),
            "bookmarks":lb("star",     "Favoriler  Ctrl+B",  C["warn"]),
            "notes":    lb("note",     "Not Defteri"),
            "tasks":    lb("task",     "Görevler",           C["success"]),
            "container":lb("container","Konteyner",          C["accent2"]),
            "dns":      lb("dns",      "DoH Durumu",         C["success"]),
            "passwords":lb("pw",       "Şifreler",           C["warn"]),
            "downloads":lb("dl",       "İndirmeler"),
            "code":     lb("code",     "Kod Enjektörü  Ctrl+Shift+J"),
        }
        for b in self._lb.values(): lay.addWidget(b)
        lay.addStretch()
        self._lb_settings = lb("settings","Ayarlar"); lay.addWidget(self._lb_settings)
        return bar

    def _build_side_panel(self):
        p = QWidget(); p.setFixedWidth(0)
        p.setStyleSheet(f"background:{C['surface']};border-right:1px solid {C['border']};")
        lay = QVBoxLayout(p); lay.setContentsMargins(8,12,8,8); lay.setSpacing(6)
        self._side_title = QLabel(); self._side_title.setStyleSheet(f"font-size:13px;font-weight:700;color:{C['accent']};")
        self._side_search = QLineEdit(); self._side_search.setPlaceholderText("Ara…")
        self._side_search.setStyleSheet(f"background:{C['surface2']};border:1px solid {C['border']};border-radius:5px;padding:5px 8px;color:{C['text']};font-size:12px;")
        self._side_list = QListWidget()
        self._side_list.setStyleSheet(
            f"QListWidget{{background:{C['mantle']};border:1px solid {C['border']};border-radius:5px;color:{C['text']};}}"
            f"QListWidget::item{{padding:6px 8px;font-size:11px;border-radius:3px;}}"
            f"QListWidget::item:hover{{background:{C['surface2']};}}"
            f"QListWidget::item:selected{{background:{C['accent']};color:{C['mantle']};}}")
        bc = QPushButton("Temizle")
        bc.setStyleSheet(f"background:{C['surface2']};color:{C['danger']};border:none;border-radius:4px;padding:5px;font-size:11px;")
        bc.clicked.connect(self._clear_side)
        lay.addWidget(self._side_title); lay.addWidget(self._side_search)
        lay.addWidget(self._side_list); lay.addWidget(bc)
        self._side_search.textChanged.connect(self._filter_side)
        self._side_list.itemDoubleClicked.connect(lambda it: self._open_tab(it.text()))
        return p

    def _build_dl_bar(self):
        b = QWidget(); b.setFixedHeight(0)
        b.setStyleSheet(f"background:{C['mantle']};border-top:1px solid {C['success']};")
        lay = QHBoxLayout(b); lay.setContentsMargins(12,0,12,0); lay.setSpacing(8)
        self._dl_lbl = QLabel("İndiriliyor…"); self._dl_lbl.setStyleSheet(f"color:{C['text']};font-size:12px;")
        self._dl_prog = QProgressBar()
        self._dl_prog.setStyleSheet(
            f"QProgressBar{{background:{C['surface2']};border-radius:3px;height:10px;text-align:center;color:{C['text']};font-size:10px;}}"
            f"QProgressBar::chunk{{background:{C['success']};border-radius:3px;}}")
        bx = QPushButton("×"); bx.setFixedSize(22,22)
        bx.setStyleSheet(f"background:transparent;color:{C['danger']};border:none;font-size:16px;")
        bx.clicked.connect(lambda: b.setFixedHeight(0))
        lay.addWidget(self._dl_lbl); lay.addWidget(self._dl_prog,1); lay.addWidget(bx)
        return b

    def _build_status_bar(self):
        bar = QWidget(); bar.setFixedHeight(20)
        bar.setStyleSheet(f"background:{C['mantle']};border-top:1px solid {C['border']};")
        lay = QHBoxLayout(bar); lay.setContentsMargins(12,0,12,0); lay.setSpacing(16)
        def sl(t=""): l=QLabel(t); l.setStyleSheet(f"color:{C['subtext']};font-size:10px;"); return l
        self._st_tracker = sl("Koruma: Aktif")
        self._st_doh     = sl("DoH: …")
        self._st_tabs    = sl("Sekmeler: 1")
        self._st_zoom    = sl("Zoom: %100")
        self._st_reading = sl("")
        for l in [self._st_tracker,self._st_doh,self._st_tabs,self._st_zoom]: lay.addWidget(l)
        lay.addStretch(); lay.addWidget(self._st_reading)
        return bar

    # ── Sinyaller ────────────────────────────────────────────────
    def _connect_signals(self):
        tb = self._tab_bar
        tb.btn_win_close.clicked.connect(self.close)
        tb.btn_win_min.clicked.connect(self.showMinimized)
        tb.btn_win_max.clicked.connect(self._toggle_maximize)
        tb.btn_new.clicked.connect(self._open_newtab)
        tb.btn_incognito.clicked.connect(self._open_incognito)
        tb.tabs.currentChanged.connect(self._on_tab_changed)
        tb.tabs.tabCloseRequested.connect(self._close_tab)
        tb.context_menu_requested.connect(self._tab_ctx_menu)

        self._addr.returnPressed.connect(self._navigate)
        self._btn_back.clicked.connect(lambda: (v:=self._cview()) and v.back())
        self._btn_fwd.clicked.connect(lambda: (v:=self._cview()) and v.forward())
        self._btn_reload.clicked.connect(self._reload)
        self._btn_home.clicked.connect(self._go_home)
        self._btn_star.clicked.connect(self._toggle_bookmark)
        self._btn_reader.clicked.connect(self._toggle_reader)
        self._btn_find_btn.clicked.connect(self._toggle_find)
        self._btn_pip.clicked.connect(self._open_pip)
        self._btn_shot.clicked.connect(self._take_shot)
        self._btn_trans.clicked.connect(self._translate)
        self._btn_share.clicked.connect(self._share_menu)
        self._btn_print.clicked.connect(self._print_page)
        self._btn_zo.clicked.connect(self._zoom_out)
        self._btn_zi.clicked.connect(self._zoom_in)
        self._btn_menu.clicked.connect(self._main_menu)

        self._lb["gemini"].clicked.connect(lambda: self._open_tab("https://gemini.google.com","Gemini"))
        self._lb["history"].clicked.connect(lambda: self._toggle_side("history"))
        self._lb["bookmarks"].clicked.connect(lambda: self._toggle_side("bookmarks"))
        self._lb["notes"].clicked.connect(self._open_notes)
        self._lb["tasks"].clicked.connect(self._open_tasks)
        self._lb["container"].clicked.connect(self._container_menu)
        self._lb["dns"].clicked.connect(self._check_doh)
        self._lb["passwords"].clicked.connect(self._open_passwords)
        self._lb["downloads"].clicked.connect(lambda: self._toggle_side("downloads"))
        self._lb["code"].clicked.connect(self._open_injector)
        self._lb_settings.clicked.connect(self._open_settings)

        self._dl_manager.download_progress.connect(self._on_dl_progress)
        self._dl_manager.download_finished.connect(self._on_dl_done)

    # ── Kısayollar ───────────────────────────────────────────────
    def _setup_shortcuts(self):
        for key, fn in [
            ("Ctrl+T",         self._open_newtab),
            ("Ctrl+W",         lambda: self._close_tab(self._tab_bar.tabs.currentIndex())),
            ("Ctrl+Shift+T",   self._reopen_last),
            ("Ctrl+Shift+N",   self._open_incognito),
            ("Ctrl+L",         lambda: (self._addr.selectAll(), self._addr.setFocus())),
            ("Ctrl+D",         self._toggle_bookmark),
            ("Ctrl+H",         lambda: self._toggle_side("history")),
            ("Ctrl+B",         lambda: self._toggle_side("bookmarks")),
            ("Ctrl+F",         self._toggle_find),
            ("Ctrl+R",         self._toggle_reader),
            ("Ctrl+P",         self._print_page),
            ("Ctrl+S",         self._save_page),
            ("Ctrl+U",         self._view_source),
            ("Ctrl++",         self._zoom_in),
            ("Ctrl+Equal",     self._zoom_in),
            ("Ctrl+-",         self._zoom_out),
            ("Ctrl+0",         self._zoom_reset),
            ("Ctrl+Shift+S",   self._take_shot),
            ("Ctrl+Shift+J",   self._open_injector),
            ("Ctrl+Shift+I",   self._devtools),
            ("Ctrl+Shift+D",   self._toggle_dark),
            ("Ctrl+Shift+F",   self._toggle_focus),
            ("Ctrl+Shift+M",   self._toggle_mute),
            ("Ctrl+K",         self._spotlight),
            ("Ctrl+Tab",       self._next_tab),
            ("Ctrl+Shift+Tab", self._prev_tab),
            ("F5",             self._reload),
            ("F11",            self._toggle_fullscreen),
            ("F12",            self._devtools),
            ("Alt+Left",       lambda: (v:=self._cview()) and v.back()),
            ("Alt+Right",      lambda: (v:=self._cview()) and v.forward()),
            ("Alt+Home",       self._go_home),
            ("Escape",         self._escape),
        ] + [(f"Ctrl+{i+1}", (lambda idx=i: self._tab_bar.tabs.setCurrentIndex(idx))) for i in range(9)]:
            try:
                sc = QShortcut(QKeySequence(key), self)
                sc.activated.connect(fn)
            except Exception:
                pass

    # ── Tam ekran ────────────────────────────────────────────────
    def _toggle_fullscreen(self):
        if not self._fullscreen:
            self._pre_fs_geom = self.geometry()
            self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
            self.showFullScreen()
            self._fullscreen = True
            # Başlık/sekme çubuğunu gizle
            self._tab_bar.setVisible(False)
        else:
            self._fullscreen = False
            self._tab_bar.setVisible(True)
            self.showNormal()
            if self._pre_fs_geom:
                self.setGeometry(self._pre_fs_geom)

    # ── Sekme oluşturma ──────────────────────────────────────────
    def _open_newtab(self, url="", title="Yeni Sekme"):
        if not url:
            url = _newtab_url()
        view = self._make_view()
        si   = self._content.addWidget(view)
        ti   = self._tab_bar.tabs.addTab(title[:18])
        self._tab_bar.tabs.setTabData(ti, si)
        self._tab_bar.tabs.setCurrentIndex(ti)
        self._content.setCurrentIndex(si)
        self._contexts[si] = PageContext()
        # Animasyonlu sekme açılışı — opaklık efekti
        if self._settings.get("animations", True):
            eff = self._content.currentWidget()
            if eff:
                anim = QPropertyAnimation(view, b"windowOpacity")
                anim.setDuration(200)
                anim.setStartValue(0.0)
                anim.setEndValue(1.0)
                anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
                anim.start(); self._last_anim = anim
        view.setUrl(QUrl(url))
        self._update_status()

    def _open_incognito(self):
        view = self._make_view(incognito=True)
        si   = self._content.addWidget(view)
        ti   = self._tab_bar.tabs.addTab("Gizli")
        self._tab_bar.tabs.setTabData(ti, si)
        self._tab_bar.tabs.setCurrentIndex(ti)
        self._content.setCurrentIndex(si)
        self._contexts[si] = PageContext(); self._contexts[si].incognito = True
        self._tab_bar.tabs.setTabToolTip(ti, "Gizli Sekme")
        view.setUrl(QUrl("https://duckduckgo.com"))
        self._update_status()

    def _open_tab(self, url, title="Yükleniyor…"):
        self._open_newtab(url, title)

    def _make_view(self, incognito=False) -> QWebEngineView:
        view = QWebEngineView()
        profile = view.page().profile()
        profile.setHttpUserAgent(self._ua)
        profile.setSpellCheckEnabled(False)
        if incognito:
            profile.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.NoPersistentCookies)
            profile.setHttpCacheType(QWebEngineProfile.HttpCacheType.MemoryHttpCache)
        else:
            # Google Push bildirimleri, izleme çerezleri engeli
            s = profile.settings()
            s.setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanOpenWindows, False)
            s.setAttribute(QWebEngineSettings.WebAttribute.PluginsEnabled, False)
        profile.downloadRequested.connect(self._handle_dl)
        view.urlChanged.connect(self._on_url_changed)
        view.titleChanged.connect(lambda t, v=view: self._on_title_changed(v, t))
        view.loadStarted.connect(lambda v=view: self._btn_reload.setIcon(_ic("stop", C["subtext"])))
        view.loadFinished.connect(lambda ok, v=view: self._on_load_done(v, ok))
        return view

    def _close_tab(self, idx):
        if self._tab_bar.tabs.count() <= 1: return
        si = self._tab_bar.tabs.tabData(idx)
        if isinstance(si, int):
            w = self._content.widget(si)
            if isinstance(w, QWebEngineView):
                self._last_closed = w.url().toString()
            self._content.removeWidget(w)
            if w: w.deleteLater()
            self._contexts.pop(si, None)
            self._dark_tabs.discard(idx); self._focus_tabs.discard(idx); self._reader_tabs.discard(idx)
        self._tab_bar.tabs.removeTab(idx)
        self._update_status()

    # ── Sekme olayları ────────────────────────────────────────────
    def _on_tab_changed(self, idx):
        if idx < 0: return
        si = self._tab_bar.tabs.tabData(idx)
        if not isinstance(si, int): return
        self._content.setCurrentIndex(si)
        w = self._content.widget(si)
        if isinstance(w, QWebEngineView):
            url = w.url().toString()
            self._addr.setText(url)
            self._update_sec_icon(url)
            self._update_star_icon(url)
            z = self._contexts.get(si, PageContext()).zoom
            self._st_zoom.setText(f"Zoom: %{int(z*100)}")
        else:
            self._addr.setText("pyweb://newtab")

    def _on_title_changed(self, view, title):
        for i in range(self._tab_bar.tabs.count()):
            si = self._tab_bar.tabs.tabData(i)
            if isinstance(si, int) and self._content.widget(si) is view:
                s = (title[:15]+"…") if len(title) > 15 else title
                self._tab_bar.tabs.setTabText(i, s); break

    def _on_url_changed(self, qurl):
        v = self._cview()
        if not (v and self.sender() is v): return
        url = qurl.toString()
        self._addr.setText(url)
        self._update_sec_icon(url)
        self._update_star_icon(url)
        if url and url != "about:blank" and not url.startswith("file://"):
            self._history_db.add(url, v.title())

    def _on_load_done(self, view, ok):
        self._btn_reload.setIcon(_ic("refresh", C["subtext"]))
        si = self._content.indexOf(view)
        idx = self._si_to_idx(si)
        if idx in self._dark_tabs:   view.page().runJavaScript(DARK_ON)
        if idx in self._focus_tabs:  view.page().runJavaScript(FOCUS_ON)
        # Özel CSS
        if self._settings.get("custom_css") and os.path.exists(CUSTOM_CSS):
            with open(CUSTOM_CSS, "r", encoding="utf-8") as f:
                css = f.read().replace("`","\\`")
            view.page().runJavaScript(
                f"(function(){{var s=document.createElement('style');s.textContent=`{css}`;document.head.appendChild(s);}})()")
        # Newtab istatistikleri
        url = view.url().toString()
        if "newtab.html" in url:
            tabs = self._tab_bar.tabs.count()
            hist = self._history_db.count
            book = self._bookmarks.count
            blck = self._interceptor.count
            view.page().runJavaScript(
                f"if(typeof pwSetStats==='function')pwSetStats({tabs},{hist},{book},{blck})")
        # Hata sayfası
        if not ok and url and url != "about:blank" and "error404.html" not in url:
            eu = _error_url()
            if eu:
                info = json.dumps({"code":"Bağlantı Hatası","title":"Sayfa Yüklenemedi",
                    "sub":f"{url} adresine ulaşılamadı.","url":url,
                    "dns":"Çözümlenemedi","protocol":"HTTPS" if url.startswith("https") else "HTTP",
                    "errCode":"ERR_CONNECTION_FAILED"})
                view.setUrl(QUrl(eu))
                QTimer.singleShot(600, lambda: view.page().runJavaScript(
                    f"if(typeof pwSetError==='function')pwSetError({info})"))

    # ── Navigasyon ────────────────────────────────────────────────
    def _navigate(self):
        t = self._addr.text().strip()
        if not t: return
        v = self._cview()
        if not v: return
        if re.match(r"^[a-zA-Z][\w\-.]*://", t): url = QUrl(t)
        elif re.match(r"^[\w\-]+\.[a-zA-Z]{2,}", t) and " " not in t: url = QUrl("https://"+t)
        else:
            e = self._settings.get("search_engine","DuckDuckGo")
            t2 = SEARCH_ENGINES.get(e, SEARCH_ENGINES["DuckDuckGo"])
            url = QUrl(t2.format(urllib.parse.quote(t)))
        v.setUrl(url)

    def _reload(self):
        v = self._cview()
        if v: v.reload()

    def _go_home(self):
        v = self._cview()
        if not v: return
        hp = self._settings.get("homepage","")
        if not hp: hp = _newtab_url()
        v.setUrl(QUrl(hp))

    # ── Güvenlik ikonları ─────────────────────────────────────────
    def _update_sec_icon(self, url):
        if url.startswith("https://"):
            self._btn_sec.setIcon(_ic("lock", C["success"]))
            self._btn_sec.setToolTip("Güvenli (HTTPS)")
        elif url.startswith("http://"):
            self._btn_sec.setIcon(_ic("lock_open", C["danger"]))
            self._btn_sec.setToolTip("Güvensiz (HTTP)")
        else:
            self._btn_sec.setIcon(_ic("lock", C["subtext"]))

    def _update_star_icon(self, url):
        if self._bookmarks.contains(url):
            self._btn_star.setIcon(_ic("star_on", C["warn"]))
        else:
            self._btn_star.setIcon(_ic("star", C["subtext"]))

    # ── Favori ────────────────────────────────────────────────────
    def _toggle_bookmark(self):
        url = self._addr.text().strip()
        if not url or url == "about:blank": return
        if self._bookmarks.contains(url): self._bookmarks.remove(url)
        else:
            v = self._cview()
            self._bookmarks.add(url, v.title() if v else "")
        self._update_star_icon(url)

    # ── Yan panel ────────────────────────────────────────────────
    def _toggle_side(self, mode):
        same = (self._side_mode == mode and self._side_panel.width() > 0)
        tw = 0 if same else self._settings.get("sidebar_width", 250)
        self._side_mode = None if same else mode
        if mode == "history":
            self._side_title.setText("Geçmiş")
            self._side_list.clear()
            for e in self._history_db.recent(200): self._side_list.addItem(e.url)
        elif mode == "bookmarks":
            self._side_title.setText("Favoriler")
            self._side_list.clear()
            for bm in self._bookmarks.all(): self._side_list.addItem(bm.url)
        elif mode == "downloads":
            self._side_title.setText("İndirmeler")
            self._side_list.clear()
            for it in self._dl_manager.history[:50]: self._side_list.addItem(f"{it.filename}  {it.status.name}")
        self._side_search.clear()
        anim = QPropertyAnimation(self._side_panel, b"minimumWidth")
        anim.setDuration(220); anim.setStartValue(self._side_panel.width())
        anim.setEndValue(tw); anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
        anim.start(); self._sp_anim = anim

    def _filter_side(self, text):
        for i in range(self._side_list.count()):
            it = self._side_list.item(i); it.setHidden(text.lower() not in it.text().lower())

    def _clear_side(self):
        self._side_list.clear()
        if self._side_mode == "history": self._history_db.clear()
        elif self._side_mode == "bookmarks": self._bookmarks.clear()

    # ── Sayfada arama ─────────────────────────────────────────────
    def _toggle_find(self):
        self._find_open = not self._find_open
        self._find_bar.setFixedHeight(36 if self._find_open else 0)
        if self._find_open: self._find_inp.setFocus(); self._find_inp.selectAll()

    def _hide_find(self):
        self._find_open = False; self._find_bar.setFixedHeight(0)
        v = self._cview()
        if v: v.findText("")

    def _do_find(self, back=False):
        v = self._cview()
        if not v: return
        t = self._find_inp.text()
        fl= QWebEnginePage.FindFlag.FindBackward if back else QWebEnginePage.FindFlag(0)
        v.findText(t, fl, lambda ok: self._find_res.setText("" if not t else ("Bulundu" if ok else "Bulunamadı")))

    # ── Zoom ──────────────────────────────────────────────────────
    def _zoom_in(self):   self._set_zoom(0.1)
    def _zoom_out(self):  self._set_zoom(-0.1)
    def _zoom_reset(self):self._set_zoom(0, reset=True)

    def _set_zoom(self, d, reset=False):
        v = self._cview()
        if not v: return
        si  = self._content.currentIndex()
        ctx = self._contexts.get(si, PageContext())
        ctx.zoom = 1.0 if reset else max(0.25, min(5.0, ctx.zoom + d))
        v.setZoomFactor(ctx.zoom)
        self._st_zoom.setText(f"Zoom: %{int(ctx.zoom*100)}")

    # ── Okuma modu ────────────────────────────────────────────────
    def _toggle_reader(self):
        v = self._cview()
        if not v: return
        idx = self._tab_bar.tabs.currentIndex()
        if idx in self._reader_tabs:
            v.back(); self._reader_tabs.discard(idx)
            self._btn_reader.setIcon(_ic("reader", C["subtext"]))
        else:
            title = v.title(); url = v.url().toString()
            dark  = idx in self._dark_tabs
            fs    = self._settings.get("reading_font_size", 18)
            v.page().runJavaScript(
                "document.body ? document.body.innerHTML : ''",
                lambda html: self._render_reader(v, idx, title, url, html or "", dark, fs))

    def _render_reader(self, view, idx, title, url, html, dark, fs):
        import re as _re
        clean = _re.sub(r"<script[^>]*>.*?</script>","",html,flags=_re.DOTALL|_re.IGNORECASE)
        clean = _re.sub(r"<style[^>]*>.*?</style>","",clean,flags=_re.DOTALL|_re.IGNORECASE)
        bg  = "#1a1814" if dark else "#f4f0ea"
        fg  = "#d4cfc8" if dark else "#2c2820"
        sur = "#252018" if dark else "#e8e4dc"
        brd = "#383028" if dark else "#d4cec4"
        lnk = "#8898c0" if dark else "#3a5080"
        css = f"""
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:{bg};color:{fg};font-family:Georgia,serif;
      font-size:{fs}px;line-height:1.85;
      animation:fadeIn .35s ease}}
@keyframes fadeIn{{from{{opacity:0;transform:translateY(5px)}}to{{opacity:1;transform:none}}}}
.wrap{{max-width:700px;margin:0 auto;padding:56px 32px 100px}}
.meta{{font-size:.78em;color:{brd};margin-bottom:2em;padding-bottom:1em;border-bottom:1px solid {brd};font-family:'Segoe UI',sans-serif}}
h1{{font-size:1.75em;line-height:1.3;margin-bottom:.8em}}
h2,h3{{margin:1.4em 0 .5em}}
p{{margin-bottom:1.2em;text-align:justify}}
a{{color:{lnk};text-decoration:none;border-bottom:1px solid {brd}}}
img{{max-width:100%;border-radius:4px;margin:1em 0}}
blockquote{{border-left:3px solid {brd};padding:10px 20px;background:{sur};margin:1em 0;font-style:italic}}
code{{background:{sur};padding:2px 6px;border-radius:3px;font-family:Consolas,monospace;font-size:.88em}}
pre{{background:{sur};padding:16px;border-radius:6px;overflow-x:auto;margin:1em 0}}"""
        tesc = title.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
        rendered = f"<!DOCTYPE html><html><head><meta charset='utf-8'><style>{css}</style></head><body><div class='wrap'><h1>{tesc}</h1><div class='meta'>PyWeb Okuma Modu &middot; {url}</div>{clean}</div></body></html>"
        view.setHtml(rendered, QUrl(url))
        self._reader_tabs.add(idx)
        self._btn_reader.setIcon(_ic("reader", C["accent"]))

    # ── Karanlık / Odak mod ───────────────────────────────────────
    def _toggle_dark(self):
        idx = self._tab_bar.tabs.currentIndex(); v = self._cview()
        if not v: return
        if idx in self._dark_tabs: self._dark_tabs.discard(idx); v.page().runJavaScript(DARK_OFF)
        else: self._dark_tabs.add(idx); v.page().runJavaScript(DARK_ON)

    def _toggle_focus(self):
        idx = self._tab_bar.tabs.currentIndex(); v = self._cview()
        if not v: return
        if idx in self._focus_tabs:
            self._focus_tabs.discard(idx)
            v.page().runJavaScript("(function(){var s=document.getElementById('__pw_foc');if(s)s.remove();})()")
        else: self._focus_tabs.add(idx); v.page().runJavaScript(FOCUS_ON)

    # ── Ses kapat ─────────────────────────────────────────────────
    def _toggle_mute(self):
        idx = self._tab_bar.tabs.currentIndex(); si = self._tab_bar.tabs.tabData(idx)
        if isinstance(si, int):
            w = self._content.widget(si)
            if isinstance(w, QWebEngineView):
                muted = not w.page().isAudioMuted(); w.page().setAudioMuted(muted)
                t = self._tab_bar.tabs.tabText(idx).replace("🔇 ","")
                self._tab_bar.tabs.setTabText(idx, ("🔇 " if muted else "") + t)

    # ── Ekran görüntüsü ───────────────────────────────────────────
    def _take_shot(self):
        v = self._cview()
        if not v: return
        px = v.grab()
        dlg = QDialog(self); dlg.setWindowTitle("Ekran Görüntüsü")
        dlg.setStyleSheet(f"background:{C['bg']};color:{C['text']};"); dlg.resize(800,540)
        lay = QVBoxLayout(dlg); lay.setContentsMargins(16,16,16,16)
        lbl = QLabel(); lbl.setPixmap(px.scaled(768,440,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation))
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet(f"background:{C['surface']};border:1px solid {C['border']};border-radius:6px;padding:8px;")
        lay.addWidget(lbl)
        def save(fmt):
            path,_ = QFileDialog.getSaveFileName(dlg,f"Kaydet",f"screenshot.{fmt}",f"{fmt.upper()} (*.{fmt})")
            if path: px.save(path)
        row = QHBoxLayout()
        for t,fn in [("PNG Kaydet",lambda:save("png")),("JPEG Kaydet",lambda:save("jpg")),("Kopyala",lambda:QApplication.clipboard().setPixmap(px)),("Kapat",dlg.close)]:
            b=QPushButton(t); b.setStyleSheet(f"background:{C['surface2']};color:{C['text']};border:1px solid {C['border']};border-radius:5px;padding:8px 14px;"); b.clicked.connect(fn); row.addWidget(b)
        row.addStretch(); lay.addLayout(row); dlg.exec()

    # ── PiP ───────────────────────────────────────────────────────
    def _open_pip(self):
        v = self._cview()
        if v: self._pip_url(v.url().toString())

    def _pip_url(self, url):
        pip = _PiP(url, self._ua, self); pip.show()
        scr = QApplication.primaryScreen().availableGeometry()
        pip.move(scr.width()-520, scr.height()-320)
        self._pip_windows.append(pip)

    # ── Çeviri / Paylaş / Yazdır ──────────────────────────────────
    def _translate(self):
        v = self._cview()
        if v: self._open_tab(f"https://translate.google.com/translate?sl=auto&tl=tr&u={urllib.parse.quote(v.url().toString())}","Çeviri")

    def _share_menu(self):
        url  = self._addr.text()
        menu = QMenu(self); menu.setStyleSheet(self._menu_style())
        menu.addAction("URL Kopyala", lambda: QApplication.clipboard().setText(url))
        menu.addAction("QR Kod", lambda: self._open_tab(f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={urllib.parse.quote(url)}","QR"))
        menu.addAction("E-posta", lambda: self._open_tab(f"mailto:?body={urllib.parse.quote(url)}","Mail"))
        menu.exec(self._btn_share.mapToGlobal(QPoint(0,32)))

    def _print_page(self):
        v = self._cview()
        if not v: return
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        dlg = QPrintDialog(printer, self)
        if dlg.exec() == QPrintDialog.DialogCode.Accepted:
            try: v.page().print(printer, lambda ok: None)
            except Exception as e: QMessageBox.warning(self,"Hata",str(e))

    def _save_page(self):
        v = self._cview()
        if not v: return
        path,_ = QFileDialog.getSaveFileName(self,"Kaydet","sayfa.html","HTML (*.html)")
        if path:
            v.page().toHtml(lambda html: open(path,"w",encoding="utf-8").write(html))

    def _view_source(self):
        v = self._cview()
        if v: v.setUrl(QUrl("view-source:"+v.url().toString()))

    # ── DevTools ──────────────────────────────────────────────────
    def _devtools(self):
        v = self._cview()
        if not v: return
        dev = QWebEngineView(); v.page().setDevToolsPage(dev.page())
        dlg = QDialog(self); dlg.setWindowTitle("DevTools"); dlg.resize(1000,600)
        dlg.setStyleSheet(f"background:{C['mantle']};")
        lay = QVBoxLayout(dlg); lay.setContentsMargins(0,0,0,0); lay.addWidget(dev); dlg.show()

    # ── Kod enjektörü ─────────────────────────────────────────────
    def _open_injector(self):
        dlg = QDialog(self); dlg.setWindowTitle("Kod Enjektörü")
        dlg.setStyleSheet(f"background:{C['bg']};color:{C['text']};"); dlg.resize(720,500)
        lay = QVBoxLayout(dlg); lay.setContentsMargins(16,16,16,16); lay.setSpacing(10)
        hdr = QHBoxLayout()
        combo = QComboBox(); combo.addItems(["JavaScript","CSS"])
        combo.setStyleSheet(f"background:{C['surface2']};color:{C['text']};border:1px solid {C['border']};border-radius:5px;padding:5px 10px;")
        hdr.addWidget(QLabel("Kod Enjektörü").setParent(None) or (lambda l: (l.setStyleSheet(f"font-size:15px;font-weight:700;color:{C['accent']};"),l)[1])(QLabel("Kod Enjektörü")))
        hdr.addStretch(); hdr.addWidget(combo); lay.addLayout(hdr)
        ed = QPlainTextEdit()
        ed.setStyleSheet(f"background:{C['surface']};color:{C['text']};border:1px solid {C['border']};border-radius:6px;padding:8px;font-family:Consolas;font-size:13px;")
        ed.setPlaceholderText("// JavaScript veya CSS kodunuzu buraya yazın…"); lay.addWidget(ed,1)
        row = QHBoxLayout(); row.setSpacing(8)
        for t,fn,c in [("Çalıştır",lambda:self._run_code(ed.toPlainText(),combo.currentText()),C["success"]),("Temizle",ed.clear,C["danger"]),("Kapat",dlg.close,C["subtext"])]:
            b=QPushButton(t); b.setStyleSheet(f"background:{C['surface2']};color:{c};border:1px solid {C['border']};border-radius:5px;padding:9px 18px;font-weight:600;"); b.clicked.connect(fn); row.addWidget(b)
        row.addStretch(); lay.addLayout(row); dlg.exec()

    def _run_code(self, code, mode):
        v = self._cview()
        if not v or not code: return
        if mode == "CSS":
            code = f"(function(){{var s=document.createElement('style');s.textContent=`{code}`;document.head.appendChild(s);}})()"
        v.page().runJavaScript(code)

    # ── Spotlight ─────────────────────────────────────────────────
    def _spotlight(self):
        dlg = QDialog(self)
        dlg.setWindowFlags(Qt.WindowType.FramelessWindowHint|Qt.WindowType.Dialog)
        dlg.setStyleSheet(f"QDialog{{background:{C['surface']};border:1px solid {C['accent']};border-radius:10px;}}")
        dlg.resize(600,380)
        scr = QApplication.primaryScreen().availableGeometry()
        dlg.move(scr.center().x()-300, scr.center().y()-190)
        lay = QVBoxLayout(dlg); lay.setContentsMargins(14,14,14,14); lay.setSpacing(8)
        inp = QLineEdit(); inp.setPlaceholderText("Arama veya URL…")
        inp.setStyleSheet(f"background:{C['surface2']};border:1px solid {C['border']};border-radius:7px;padding:11px 14px;color:{C['text']};font-size:15px;")
        lst = QListWidget()
        lst.setStyleSheet(f"QListWidget{{background:{C['surface2']};border:1px solid {C['border']};border-radius:7px;color:{C['text']};}}QListWidget::item{{padding:9px 12px;font-size:12px;border-radius:4px;}}QListWidget::item:hover{{background:{C['bg']};}}QListWidget::item:selected{{background:{C['accent']};color:{C['mantle']};}}")
        hint = QLabel("Enter: Aç  ·  Esc: Kapat"); hint.setStyleSheet(f"color:{C['subtext']};font-size:10px;"); hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(inp); lay.addWidget(lst,1); lay.addWidget(hint)

        def flt(t):
            lst.clear()
            pool = list(dict.fromkeys([bm.url for bm in self._bookmarks.all()]+[e.url for e in self._history_db.recent(100)]))
            for u in ([u for u in pool if t.lower() in u.lower()] if t else pool[:40])[:50]: lst.addItem(u)

        def go():
            t = inp.text().strip(); it = lst.currentItem()
            url = (it.text() if it else None) or t
            if not url: return
            if not re.match(r"^https?://|^file://", url):
                if "." in url and " " not in url: url = "https://"+url
                else:
                    e = self._settings.get("search_engine","DuckDuckGo")
                    url = SEARCH_ENGINES.get(e,SEARCH_ENGINES["DuckDuckGo"]).format(urllib.parse.quote(url))
            self._open_tab(url); dlg.close()

        inp.textChanged.connect(flt); inp.returnPressed.connect(go)
        lst.itemDoubleClicked.connect(lambda i: (self._open_tab(i.text()), dlg.close()))
        def kp(e):
            if e.key()==Qt.Key.Key_Escape: dlg.close()
            elif e.key()==Qt.Key.Key_Down: lst.setFocus()
            else: QDialog.keyPressEvent(dlg,e)
        dlg.keyPressEvent = kp; flt(""); dlg.exec()

    # ── Not / Görev / Şifre / Ayarlar ────────────────────────────
    def _open_notes(self):
        self._generic_list_dialog("Not Defteri", os.path.join(DATA_DIR,"notes.json"))

    def _open_tasks(self):
        self._generic_list_dialog("Görevler", os.path.join(DATA_DIR,"tasks.json"))

    def _open_passwords(self):
        self._generic_list_dialog("Şifreler", os.path.join(DATA_DIR,"passwords.json"))

    def _generic_list_dialog(self, title, jfile):
        dlg = QDialog(self); dlg.setWindowTitle(title)
        dlg.setStyleSheet(f"background:{C['bg']};color:{C['text']};"); dlg.resize(560,440)
        lay = QVBoxLayout(dlg); lay.setContentsMargins(16,16,16,16); lay.setSpacing(10)
        lbl = QLabel(title); lbl.setStyleSheet(f"font-size:16px;font-weight:700;color:{C['accent']};"); lay.addWidget(lbl)
        lst = QListWidget(); lst.setStyleSheet(f"QListWidget{{background:{C['surface']};border:1px solid {C['border']};border-radius:5px;color:{C['text']};}}QListWidget::item{{padding:8px;}}"); lay.addWidget(lst,1)
        try:
            if os.path.exists(jfile):
                data = json.load(open(jfile,encoding="utf-8"))
                for item in data:
                    lst.addItem(str(item.get("text") or item.get("title") or item.get("site") or str(item))[:80])
        except Exception: pass
        inp = QLineEdit(); inp.setPlaceholderText("Yeni ekle…"); inp.setStyleSheet(f"background:{C['surface2']};border:1px solid {C['border']};border-radius:5px;padding:8px;color:{C['text']};")
        lay.addWidget(inp)
        row = QHBoxLayout()
        def add():
            t = inp.text().strip()
            if not t: return
            lst.addItem(t); inp.clear()
            data = json.load(open(jfile,encoding="utf-8")) if os.path.exists(jfile) else []
            data.append({"text":t}); json.dump(data,open(jfile,"w",encoding="utf-8"),ensure_ascii=False)
        def rem():
            r = lst.currentRow()
            if r >= 0:
                lst.takeItem(r)
                try:
                    data = json.load(open(jfile,encoding="utf-8"))
                    if 0<=r<len(data): data.pop(r); json.dump(data,open(jfile,"w",encoding="utf-8"),ensure_ascii=False)
                except Exception: pass
        for t,fn,c in [("Ekle",add,C["success"]),("Sil",rem,C["danger"]),("Kapat",dlg.close,C["subtext"])]:
            b=QPushButton(t); b.setStyleSheet(f"background:{C['surface2']};color:{c};border:none;border-radius:5px;padding:9px 16px;"); b.clicked.connect(fn); row.addWidget(b)
        row.addStretch(); lay.addLayout(row); dlg.exec()

    def _open_settings(self):
        dlg = QDialog(self); dlg.setWindowTitle("Ayarlar")
        dlg.setStyleSheet(f"background:{C['bg']};color:{C['text']};"); dlg.resize(560,500)
        lay = QVBoxLayout(dlg); lay.setContentsMargins(20,20,20,20); lay.setSpacing(14)
        lbl = QLabel("Ayarlar"); lbl.setStyleSheet(f"font-size:18px;font-weight:700;color:{C['accent']};"); lay.addWidget(lbl)

        def row_combo(label, key, items):
            r = QHBoxLayout(); l = QLabel(label); l.setFixedWidth(200); l.setStyleSheet(f"color:{C['subtext']};font-size:13px;")
            combo = QComboBox(); combo.addItems(items); combo.setStyleSheet(f"background:{C['surface2']};color:{C['text']};border:1px solid {C['border']};border-radius:5px;padding:5px;")
            val = self._settings.get(key, items[0])
            if val in items: combo.setCurrentText(val)
            combo.currentTextChanged.connect(lambda v,k=key: self._settings.update({k:v}))
            r.addWidget(l); r.addWidget(combo); r.addStretch(); return r

        def row_cb(label, key):
            cb = QCheckBox(label); cb.setChecked(bool(self._settings.get(key,False)))
            cb.setStyleSheet(f"QCheckBox{{color:{C['text']};font-size:13px;padding:4px;}}QCheckBox::indicator{{width:16px;height:16px;border:1px solid {C['border']};border-radius:3px;background:{C['mantle']};}}QCheckBox::indicator:checked{{background:{C['accent']};border-color:{C['accent']};}}")
            cb.toggled.connect(lambda v,k=key: self._settings.update({k:v})); return cb

        def row_edit(label, key):
            r = QHBoxLayout(); l = QLabel(label); l.setFixedWidth(200); l.setStyleSheet(f"color:{C['subtext']};font-size:13px;")
            edit = QLineEdit(str(self._settings.get(key,""))); edit.setStyleSheet(f"background:{C['surface2']};border:1px solid {C['border']};border-radius:5px;padding:6px;color:{C['text']};")
            edit.textChanged.connect(lambda v,k=key: self._settings.update({k:v}))
            r.addWidget(l); r.addWidget(edit,1); return r

        lay.addLayout(row_combo("Varsayılan Arama Motoru","search_engine",list(SEARCH_ENGINES.keys())))
        lay.addLayout(row_edit("Ana Sayfa","homepage"))
        lay.addLayout(row_combo("User Agent","user_agent",["default","mobile"]))
        lay.addWidget(row_cb("Tracker koruması","tracking"))
        lay.addWidget(row_cb("Reklam engelleme","ad_block"))
        lay.addWidget(row_cb("Kapatınca geçmişi temizle","clear_on_exit"))
        lay.addWidget(row_cb("Oturumu geri yükle","restore_session"))
        lay.addWidget(row_cb("Animasyonlar","animations"))
        lay.addWidget(row_cb("Özel CSS (custom.css)","custom_css"))

        row = QHBoxLayout()
        def save():
            json.dump(self._settings, open(SETTINGS_FILE,"w",encoding="utf-8"), ensure_ascii=False, indent=2)
            dlg.close()
        b_save = QPushButton("Kaydet"); b_save.setStyleSheet(f"background:{C['accent']};color:{C['mantle']};font-weight:700;border:none;border-radius:6px;padding:10px 24px;"); b_save.clicked.connect(save)
        b_can  = QPushButton("İptal");  b_can.setStyleSheet(f"background:{C['surface2']};color:{C['text']};border:none;border-radius:6px;padding:10px 24px;"); b_can.clicked.connect(dlg.close)
        row.addStretch(); row.addWidget(b_can); row.addWidget(b_save); lay.addLayout(row)
        dlg.exec()

    # ── Konteyner menü ────────────────────────────────────────────
    def _container_menu(self):
        menu = QMenu(self); menu.setStyleSheet(self._menu_style())
        for name, color in CONTAINERS.items():
            menu.addAction(name).triggered.connect(lambda _,n=name: self._open_tab("https://www.google.com",f"[{n}]"))
        menu.exec(self._lb["container"].mapToGlobal(QPoint(48,0)))

    # ── DoH kontrolü ─────────────────────────────────────────────
    def _check_doh(self):
        from PyQt6.QtCore import QThread, pyqtSignal as pS
        class _T(QThread):
            res = pS(bool)
            def run(self):
                import socket
                try: socket.setdefaulttimeout(3); socket.gethostbyname("cloudflare.com"); self.res.emit(True)
                except: self.res.emit(False)
        self._doh_t = _T()
        def done(ok):
            c = C["success"] if ok else C["danger"]
            self._st_doh.setText("DoH: Aktif" if ok else "DoH: Kapalı")
            self._st_doh.setStyleSheet(f"color:{c};font-size:10px;")
            self._lb["dns"].setIcon(_ic("dns", c))
        self._doh_t.res.connect(done); self._doh_t.start()

    # ── İndirme ───────────────────────────────────────────────────
    def _handle_dl(self, item: QWebEngineDownloadRequest):
        path,_ = QFileDialog.getSaveFileName(self,"İndir",item.suggestedFileName())
        if path:
            self._dl_manager.handle(item, path)
            self._dl_bar.setFixedHeight(40)

    def _on_dl_progress(self, fname, pct, size_str, speed_str):
        self._dl_lbl.setText(f"{fname}  {size_str}  {speed_str}")
        self._dl_prog.setValue(pct)

    def _on_dl_done(self, fname):
        self._dl_lbl.setText(f"Tamamlandı: {fname}")
        QTimer.singleShot(4000, lambda: self._dl_bar.setFixedHeight(0))

    # ── Oturum ────────────────────────────────────────────────────
    def _save_session(self):
        s = []
        for i in range(self._tab_bar.tabs.count()):
            si = self._tab_bar.tabs.tabData(i)
            if isinstance(si, int):
                w = self._content.widget(si)
                if isinstance(w, QWebEngineView):
                    url = w.url().toString()
                    if url and url != "about:blank":
                        s.append({"url":url,"title":self._tab_bar.tabs.tabText(i)})
        try: json.dump(s, open(SESSIONS_FILE,"w",encoding="utf-8"), ensure_ascii=False)
        except: pass

    def _restore_session(self):
        try:
            if os.path.exists(SESSIONS_FILE):
                data = json.load(open(SESSIONS_FILE,encoding="utf-8"))
                if data:
                    for e in data: self._open_newtab(e.get("url",""), e.get("title","Sekme"))
                    return
        except: pass
        self._open_newtab()

    def _auto_save(self):
        self._save_session()
        try: json.dump(self._settings, open(SETTINGS_FILE,"w",encoding="utf-8"), ensure_ascii=False, indent=2)
        except: pass

    def _tick_reading(self):
        idx = self._tab_bar.tabs.currentIndex()
        si  = self._tab_bar.tabs.tabData(idx)
        if isinstance(si, int):
            ctx = self._contexts.get(si)
            if ctx:
                elapsed = int(time.time() - ctx.reading_start)
                if elapsed > 3:
                    m,s = divmod(elapsed,60); self._st_reading.setText(f"{m:02d}:{s:02d}"); return
        self._st_reading.setText("")

    # ── Tracker enjeksiyonu ───────────────────────────────────────
    def _inject_tracker(self, profile):
        sc = QWebEngineScript(); sc.setName("PyWebTracker")
        sc.setSourceCode(TRACKER_JS)
        sc.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentCreation)
        sc.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
        profile.scripts().insert(sc)

    # ── Ana menü ─────────────────────────────────────────────────
    def _main_menu(self):
        menu = QMenu(self); menu.setStyleSheet(self._menu_style())
        for item in [
            ("Yeni Sekme", self._open_newtab), ("Gizli Sekme", self._open_incognito),
            None,
            ("Okuma Modu", self._toggle_reader), ("Karanlık Mod", self._toggle_dark),
            ("Odak Modu", self._toggle_focus), ("Tam Ekran  F11", self._toggle_fullscreen),
            None,
            ("Sayfayı Kaydet", self._save_page), ("Yazdır", self._print_page),
            ("Kaynağı Görüntüle", self._view_source), ("Çevir", self._translate),
            None,
            ("Geliştirici Araçları", self._devtools), ("Kod Enjektörü", self._open_injector),
            None,
            ("Ayarlar", self._open_settings), ("Hakkında", self._about),
        ]:
            if item is None: menu.addSeparator()
            else: menu.addAction(item[0]).triggered.connect(item[1])
        menu.exec(self._btn_menu.mapToGlobal(QPoint(0,32)))

    def _about(self):
        QMessageBox.about(self,"PyWeb Hakkında",
            "<b>PyWeb Browser</b><br>Sürüm 1.0.0<br><br>"
            "PyQt6 + QtWebEngine tabanlı modern masaüstü tarayıcı.<br>"
            "GPL-3.0 Lisansı")

    # ── Sekme bağlam menüsü ───────────────────────────────────────
    def _tab_ctx_menu(self, idx, gpos):
        menu = QMenu(self); menu.setStyleSheet(self._menu_style())
        for item in [
            ("Yeni Sekme",      self._open_newtab),
            ("Sekmeyi Çoğalt",  lambda: self._dup_tab(idx)),
            ("URL Kopyala",     lambda: self._copy_url(idx)),
            ("Uyut / Uyandır",  lambda: self._sleep_tab(idx)),
            ("Sesi Kapat / Aç", self._toggle_mute),
            ("Resim İçinde Resim", lambda: self._pip_from_tab(idx)),
            None,
            ("Diğerlerini Kapat", lambda: self._close_others(idx)),
            ("Sağdakileri Kapat", lambda: self._close_right(idx)),
            ("Bu Sekmeyi Kapat", lambda: self._close_tab(idx)),
        ]:
            if item is None: menu.addSeparator()
            else: menu.addAction(item[0]).triggered.connect(item[1])
        menu.exec(gpos)

    def _dup_tab(self, idx):
        si = self._tab_bar.tabs.tabData(idx)
        if isinstance(si, int):
            w = self._content.widget(si)
            if isinstance(w, QWebEngineView):
                self._open_newtab(w.url().toString(), self._tab_bar.tabs.tabText(idx))

    def _copy_url(self, idx):
        si = self._tab_bar.tabs.tabData(idx)
        if isinstance(si, int):
            w = self._content.widget(si)
            if isinstance(w, QWebEngineView):
                QApplication.clipboard().setText(w.url().toString())

    def _pip_from_tab(self, idx):
        si = self._tab_bar.tabs.tabData(idx)
        if isinstance(si, int):
            w = self._content.widget(si)
            if isinstance(w, QWebEngineView): self._pip_url(w.url().toString())

    def _sleep_tab(self, idx):
        si = self._tab_bar.tabs.tabData(idx)
        if isinstance(si, int):
            w = self._content.widget(si)
            if isinstance(w, QWebEngineView):
                t = self._tab_bar.tabs.tabText(idx)
                if t.startswith("💤 "):
                    ctx = self._contexts.get(si)
                    if ctx: w.setUrl(QUrl(ctx.url))
                    self._tab_bar.tabs.setTabText(idx, t[3:])
                else:
                    ctx = self._contexts.get(si, PageContext()); ctx.url = w.url().toString()
                    w.setUrl(QUrl("about:blank"))
                    self._tab_bar.tabs.setTabText(idx, "💤 "+t)

    def _close_others(self, keep):
        for i in reversed(range(self._tab_bar.tabs.count())):
            if i != keep: self._close_tab(i)

    def _close_right(self, fi):
        for i in reversed(range(fi+1, self._tab_bar.tabs.count())):
            self._close_tab(i)

    def _reopen_last(self):
        if self._last_closed: self._open_newtab(self._last_closed)

    def _next_tab(self):
        n=self._tab_bar.tabs.count(); self._tab_bar.tabs.setCurrentIndex((self._tab_bar.tabs.currentIndex()+1)%n)

    def _prev_tab(self):
        n=self._tab_bar.tabs.count(); self._tab_bar.tabs.setCurrentIndex((self._tab_bar.tabs.currentIndex()-1)%n)

    def _escape(self):
        if self._fullscreen: self._toggle_fullscreen()
        elif self._find_open: self._hide_find()
        else:
            v = self._cview()
            if v: v.stop()

    def _update_status(self):
        n = self._tab_bar.tabs.count(); self._st_tabs.setText(f"Sekmeler: {n}")

    # ── Pencere ───────────────────────────────────────────────────
    def _toggle_maximize(self):
        self.showNormal() if self.isMaximized() else self.showMaximized()

    def mousePressEvent(self, e):
        if e.button()==Qt.MouseButton.LeftButton and e.position().y()<=self._tab_bar.height():
            self._old_pos = e.globalPosition().toPoint()

    def mouseMoveEvent(self, e):
        if not self._old_pos.isNull():
            d = e.globalPosition().toPoint()-self._old_pos
            self.move(self.x()+d.x(), self.y()+d.y())
            self._old_pos = e.globalPosition().toPoint()

    def mouseReleaseEvent(self, e): self._old_pos = QPoint()

    def mouseDoubleClickEvent(self, e):
        if e.position().y() <= self._tab_bar.height():
            self._toggle_maximize()

    def closeEvent(self, e):
        self._save_session()
        if self._settings.get("clear_on_exit", False):
            self._history_db.clear()
        for pip in self._pip_windows:
            try: pip.close()
            except: pass
        self._thread_pool.stop(wait=False)
        self._event_loop.stop()
        e.accept()

    # ── Yardımcılar ───────────────────────────────────────────────
    def _cview(self) -> Optional[QWebEngineView]:
        w = self._content.currentWidget()
        return w if isinstance(w, QWebEngineView) else None

    def _si_to_idx(self, si):
        for i in range(self._tab_bar.tabs.count()):
            if self._tab_bar.tabs.tabData(i) == si: return i
        return -1

    def _menu_style(self):
        return (f"QMenu{{background:{C['surface']};color:{C['text']};border:1px solid {C['border']};padding:4px;}}"
                f"QMenu::item{{padding:9px 20px;border-radius:3px;font-size:13px;}}"
                f"QMenu::item:selected{{background:{C['surface2']};}}")

    def _load_settings(self):
        defaults = {"search_engine":"DuckDuckGo","homepage":"","user_agent":"default",
                    "tracking":True,"ad_block":True,"doh":True,"clear_on_exit":False,
                    "custom_css":False,"restore_session":True,"zoom":1.0,
                    "reading_font_size":18,"blocked_sites":[],"sidebar_width":250,"animations":True}
        try:
            if os.path.exists(SETTINGS_FILE):
                defaults.update(json.load(open(SETTINGS_FILE,encoding="utf-8")))
        except: pass
        return defaults

    def _setup_tray(self):
        try:
            from PyQt6.QtWidgets import QSystemTrayIcon
            px = QPixmap(24,24); px.fill(QColor(C["accent"]))
            self._tray = QSystemTrayIcon(QIcon(px), self)
            m = QMenu(); m.setStyleSheet(self._menu_style())
            m.addAction("Göster", self.showNormal)
            m.addAction("Yeni Sekme", self._open_newtab)
            m.addSeparator(); m.addAction("Çıkış", self.close)
            self._tray.setContextMenu(m); self._tray.setToolTip("PyWeb"); self._tray.show()
        except: pass


# ── PiP yardımcı penceresi ────────────────────────────────────
class _PiP(QMainWindow):
    def __init__(self, url, ua, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint|Qt.WindowType.FramelessWindowHint)
        self.resize(480,280); self._op = QPoint()
        cw = QWidget(); cw.setStyleSheet(f"background:{C['mantle']};border:1px solid {C['accent']};border-radius:7px;")
        v  = QVBoxLayout(cw); v.setContentsMargins(0,0,0,0); v.setSpacing(0)
        bar= QWidget(); bar.setFixedHeight(26); bar.setStyleSheet(f"background:{C['surface']};border-bottom:1px solid {C['border']};")
        bl = QHBoxLayout(bar); bl.setContentsMargins(10,0,6,0)
        bl.addWidget((lambda l:(l.setStyleSheet(f"color:{C['subtext']};font-size:11px;"),l)[1])(QLabel("Resim İçinde Resim")))
        bl.addStretch()
        bx = QPushButton("×"); bx.setFixedSize(20,20); bx.setStyleSheet(f"background:transparent;color:{C['subtext']};border:none;font-size:14px;"); bx.clicked.connect(self.close); bl.addWidget(bx)
        wv = QWebEngineView(); wv.setUrl(QUrl(url)); wv.page().profile().setHttpUserAgent(ua)
        v.addWidget(bar); v.addWidget(wv); self.setCentralWidget(cw)
        bar.mousePressEvent  = lambda e: setattr(self,"_op",e.globalPosition().toPoint()) if e.button()==Qt.MouseButton.LeftButton else None
        bar.mouseMoveEvent   = lambda e: (self.move(self.x()+(e.globalPosition().toPoint()-self._op).x(),self.y()+(e.globalPosition().toPoint()-self._op).y()),setattr(self,"_op",e.globalPosition().toPoint())) if not self._op.isNull() else None
