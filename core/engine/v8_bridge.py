# ─────────────────────────────────────────────────────────────
#  PyWeb  –  core/engine/v8_bridge.py
#  JavaScript motoruna köprü görevi görür.
#  QtWebEngine'in V8 entegrasyonu üzerinden JS çalıştırır,
#  sonuçları Python tarafına geri iletir.
# ─────────────────────────────────────────────────────────────
from __future__ import annotations
import json
from typing import Callable, Optional, Any
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEnginePage
from PyQt6.QtCore import QObject, pyqtSignal, QTimer


class JSCallback(QObject):
    """
    Tek kullanımlık JavaScript sonuç dinleyici.
    runJavaScript tamamlanınca result sinyali tetiklenir.
    """
    result = pyqtSignal(object)

    def __call__(self, value):
        self.result.emit(value)


class V8Bridge(QObject):
    """
    Python ↔ JavaScript köprüsü.

    - Sayfalara JS komutu gönderir
    - Sonuçları Python callback'ine iletir
    - JS event dinleyicileri kaydeder
    - Hata yakalama ve zaman aşımı yönetir
    """

    js_error   = pyqtSignal(str)          # JS hata mesajı
    js_console = pyqtSignal(str, int)     # konsol mesajı, satır no

    def __init__(self, page: QWebEnginePage, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._page    = page
        self._pending: dict[int, JSCallback] = {}
        self._counter = 0

    # ── Temel çalıştırma ─────────────────────
    def run(self, code: str,
            callback: Optional[Callable[[Any], None]] = None,
            timeout_ms: int = 5000) -> None:
        """
        JavaScript kodunu sayfada çalıştırır.
        callback: sonuç gelince çağrılacak fonksiyon
        timeout_ms: zaman aşımı (ms)
        """
        if callback:
            cb = JSCallback()
            cb.result.connect(callback)
            self._counter += 1
            cid = self._counter
            self._pending[cid] = cb

            # Zaman aşımı temizleyici
            def _on_timeout():
                if cid in self._pending:
                    del self._pending[cid]
            timer = QTimer(self)
            timer.setSingleShot(True)
            timer.timeout.connect(_on_timeout)
            timer.start(timeout_ms)

            self._page.runJavaScript(code, cb)
        else:
            self._page.runJavaScript(code)

    def run_sync_result(self, code: str) -> None:
        """
        Sonucu önemsemeksizin kodu çalıştırır.
        Sayfa animasyonları, DOM değişiklikleri için.
        """
        self._page.runJavaScript(code)

    # ── Özel yardımcı metodlar ────────────────
    def get_title(self, callback: Callable[[str], None]) -> None:
        self.run("document.title", callback)

    def get_url(self, callback: Callable[[str], None]) -> None:
        self.run("window.location.href", callback)

    def get_html(self, callback: Callable[[str], None]) -> None:
        self.run("document.documentElement.outerHTML", callback)

    def get_text(self, callback: Callable[[str], None]) -> None:
        self.run("document.body ? document.body.innerText : ''", callback)

    def get_scroll_y(self, callback: Callable[[int], None]) -> None:
        self.run("window.scrollY", callback)

    def get_meta(self, callback: Callable[[dict], None]) -> None:
        code = (
            "(function(){"
            "var m={};"
            "m.title=document.title;"
            "var desc=document.querySelector('meta[name=\"description\"]');"
            "m.desc=desc?desc.content:'';"
            "m.words=document.body?document.body.innerText.trim().split(/[ \\t\\n]+/).length:0;"
            "return JSON.stringify(m);"
            "})()"
        )
        def _parse(raw):
            try:
                callback(json.loads(raw) if raw else {})
            except (json.JSONDecodeError, TypeError):
                callback({})
        self.run(code, _parse)

    def get_links(self, callback: Callable[[list], None]) -> None:
        code = (
            "JSON.stringify(Array.from(document.querySelectorAll('a[href]'))"
            ".map(a=>({text:a.innerText.trim().slice(0,80),href:a.href}))"
            ".filter(l=>l.href.startsWith('http')).slice(0,200))"
        )
        def _parse(raw):
            try:
                callback(json.loads(raw) if raw else [])
            except (json.JSONDecodeError, TypeError):
                callback([])
        self.run(code, _parse)

    # ── Sayfa manipülasyonu ───────────────────
    def scroll_to(self, x: int = 0, y: int = 0, smooth: bool = True) -> None:
        behavior = "smooth" if smooth else "instant"
        self.run(f"window.scrollTo({{top:{y},left:{x},behavior:'{behavior}'}})")

    def scroll_top(self)    -> None: self.scroll_to(0, 0)
    def scroll_bottom(self) -> None:
        self.run("window.scrollTo({top:document.body.scrollHeight,behavior:'smooth'})")

    def set_zoom(self, factor: float) -> None:
        self.run(f"document.body.style.zoom='{factor}'")

    def reset_zoom(self) -> None:
        self.run("document.body.style.zoom='1'")

    def inject_css(self, css: str) -> None:
        safe = css.replace("`", "\\`").replace("\\", "\\\\")
        self.run(
            f"(function(){{"
            f"var s=document.createElement('style');"
            f"s.id='__pyweb_custom_css__';"
            f"s.textContent=`{safe}`;"
            f"var old=document.getElementById('__pyweb_custom_css__');"
            f"if(old)old.remove();"
            f"document.head.appendChild(s);"
            f"}})()"
        )

    def remove_css(self) -> None:
        self.run(
            "(function(){"
            "var s=document.getElementById('__pyweb_custom_css__');"
            "if(s)s.remove();"
            "})()"
        )

    def highlight_text(self, query: str) -> None:
        safe = query.replace("'", "\\'")
        code = (
            f"(function(q){{"
            f"if(!q)return;"
            f"document.querySelectorAll('mark.__pw').forEach(m=>"
            f"m.replaceWith(document.createTextNode(m.textContent)));"
            f"var re=new RegExp(q.replace(/[.*+?^${{}}()|[\\]\\\\]/g,'\\\\$&'),'gi');"
            f"document.querySelectorAll('p,li,h1,h2,h3,h4,h5,h6,td,span')."
            f"forEach(function(el){{"
            f"if(el.children.length)return;"
            f"el.innerHTML=el.innerHTML.replace(re,"
            f"'<mark class=\"__pw\" style=\""
            f"background:#d4b896;color:#1a1a1a;"
            f"border-radius:2px;padding:0 2px\">"
            f"$&</mark>');"
            f"}});"
            f"}})(\'{safe}')"
        )
        self.run(code)

    def clear_highlights(self) -> None:
        self.run(
            "(function(){"
            "document.querySelectorAll('mark.__pw').forEach(m=>"
            "m.replaceWith(document.createTextNode(m.textContent)));"
            "})()"
        )

    def set_newtab_stats(self, tabs: int, history: int,
                         bookmarks: int, blocked: int) -> None:
        self.run(
            f"if(typeof pwSetStats==='function')"
            f"pwSetStats({tabs},{history},{bookmarks},{blocked})"
        )

    def set_history_data(self, entries: list[dict]) -> None:
        data = json.dumps(entries, ensure_ascii=False)
        self.run(
            f"if(typeof pwSetHistory==='function')"
            f"pwSetHistory({data})"
        )

    def set_error_info(self, info: dict) -> None:
        data = json.dumps(info, ensure_ascii=False)
        self.run(
            f"if(typeof pwSetError==='function')"
            f"pwSetError({data})"
        )

    # ── Konsol mesajlarını yakala ─────────────
    def attach_console_handler(self) -> None:
        """
        JS console.log mesajlarını Python sinyaline yönlendirir.
        QWebEnginePage.javaScriptConsoleMessage override eder.
        """
        page = self._page
        original = page.javaScriptConsoleMessage

        def _handler(level, message, lineNumber, sourceID):
            self.js_console.emit(f"[{sourceID}:{lineNumber}] {message}", lineNumber)

        page.javaScriptConsoleMessage = _handler
