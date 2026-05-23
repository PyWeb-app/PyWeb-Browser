# ─────────────────────────────────────────────────────────────
#  PyWeb  –  core/engine/page_context.py
#  Her sekmenin kendi izole hafızasını ve durumunu tutan sınıf.
# ─────────────────────────────────────────────────────────────
from __future__ import annotations
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional, Any


@dataclass
class NavigationEntry:
    """Geri/ileri geçmişindeki tek bir kayıt."""
    url:       str
    title:     str   = ""
    timestamp: float = field(default_factory=time.time)
    scroll_y:  int   = 0


class PageContext:
    """
    Tek bir sekmenin tam durumunu tutar.
    Navigasyon geçmişi, form verileri, JS durumu,
    kaydırma pozisyonu, zoom ve izolasyon bilgisi.
    """

    def __init__(self, tab_id: Optional[str] = None):
        self.tab_id:     str   = tab_id or str(uuid.uuid4())[:8]
        self.url:        str   = ""
        self.title:      str   = "New Tab"
        self.is_loading: bool  = False
        self.progress:   int   = 0
        self.zoom:       float = 1.0
        self.muted:      bool  = False
        self.pinned:     bool  = False
        self.sleeping:   bool  = False
        self.incognito:  bool  = False
        self.container:  str   = ""
        self.created_at: float = time.time()

        # Navigasyon geçmişi
        self._history:   list[NavigationEntry] = []
        self._hist_idx:  int                   = -1

        # Sayfa içi durum
        self.scroll_x:   int   = 0
        self.scroll_y:   int   = 0
        self.find_query: str   = ""

        # JS durumu (key-value)
        self._js_state:  dict[str, Any] = {}

        # Okuma süresi
        self.reading_start: float = time.time()
        self.total_read_sec: int  = 0

    # ── Navigasyon ────────────────────────────
    def navigate(self, url: str, title: str = "") -> None:
        entry = NavigationEntry(url=url, title=title or url)
        # İleriye gidilen geçmişi sil
        self._history = self._history[:self._hist_idx + 1]
        self._history.append(entry)
        self._hist_idx = len(self._history) - 1
        self.url   = url
        self.title = title or url

    def can_go_back(self) -> bool:
        return self._hist_idx > 0

    def can_go_forward(self) -> bool:
        return self._hist_idx < len(self._history) - 1

    def go_back(self) -> Optional[str]:
        if self.can_go_back():
            self._hist_idx -= 1
            entry = self._history[self._hist_idx]
            self.url   = entry.url
            self.title = entry.title
            return entry.url
        return None

    def go_forward(self) -> Optional[str]:
        if self.can_go_forward():
            self._hist_idx += 1
            entry = self._history[self._hist_idx]
            self.url   = entry.url
            self.title = entry.title
            return entry.url
        return None

    @property
    def history(self) -> list[NavigationEntry]:
        return list(self._history)

    # ── JS Durumu ─────────────────────────────
    def set_js_state(self, key: str, value: Any) -> None:
        self._js_state[key] = value

    def get_js_state(self, key: str, default: Any = None) -> Any:
        return self._js_state.get(key, default)

    # ── Okuma Süresi ─────────────────────────
    def update_reading_time(self) -> int:
        if not self.sleeping and self.url:
            elapsed = int(time.time() - self.reading_start)
            self.total_read_sec += elapsed
        self.reading_start = time.time()
        return self.total_read_sec

    # ── Seri hale getirme (Oturum kayıt) ─────
    def to_dict(self) -> dict:
        return {
            "tab_id":   self.tab_id,
            "url":      self.url,
            "title":    self.title,
            "zoom":     self.zoom,
            "pinned":   self.pinned,
            "container":self.container,
            "incognito":self.incognito,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "PageContext":
        ctx = cls(tab_id=d.get("tab_id"))
        ctx.url       = d.get("url","")
        ctx.title     = d.get("title","")
        ctx.zoom      = d.get("zoom",1.0)
        ctx.pinned    = d.get("pinned",False)
        ctx.container = d.get("container","")
        ctx.incognito = d.get("incognito",False)
        return ctx

    def __repr__(self) -> str:
        return f"PageContext(id={self.tab_id}, url={self.url[:40]!r})"
