# ─────────────────────────────────────────────────────────────
#  PyWeb  –  core/engine/dom_api.py
#  JS'in HTML'e müdahale etmesini sağlayan Python-taraflı API.
#  V8Bridge aracılığıyla sayfaya komut gönderir,
#  Python kodundan DOM manipülasyonu yapmayı kolaylaştırır.
# ─────────────────────────────────────────────────────────────
from __future__ import annotations
from typing import Callable, Optional, Any
from core.engine.v8_bridge import V8Bridge


class DOMQuery:
    """
    Zincirleme DOM sorgu arayüzü.
    Örnek:
        dom.query("#main p").set_style("color","red").run()
    """

    def __init__(self, bridge: V8Bridge, selector: str):
        self._b   = bridge
        self._sel = selector
        self._ops: list[str] = []

    def set_style(self, prop: str, value: str) -> "DOMQuery":
        safe_sel = self._sel.replace("'", "\\'")
        op = (
            f"document.querySelectorAll('{safe_sel}')"
            f".forEach(function(el){{el.style['{prop}']='{value}';}});"
        )
        self._ops.append(op)
        return self

    def set_text(self, text: str) -> "DOMQuery":
        safe_sel  = self._sel.replace("'", "\\'")
        safe_text = text.replace("'", "\\'")
        op = (
            f"document.querySelectorAll('{safe_sel}')"
            f".forEach(function(el){{el.innerText='{safe_text}';}});"
        )
        self._ops.append(op)
        return self

    def set_attr(self, attr: str, value: str) -> "DOMQuery":
        safe_sel = self._sel.replace("'", "\\'")
        op = (
            f"document.querySelectorAll('{safe_sel}')"
            f".forEach(function(el){{el.setAttribute('{attr}','{value}');}});"
        )
        self._ops.append(op)
        return self

    def hide(self) -> "DOMQuery":
        return self.set_style("display", "none")

    def show(self, display: str = "block") -> "DOMQuery":
        return self.set_style("display", display)

    def remove(self) -> "DOMQuery":
        safe_sel = self._sel.replace("'", "\\'")
        op = (
            f"document.querySelectorAll('{safe_sel}')"
            f".forEach(function(el){{el.remove();}});"
        )
        self._ops.append(op)
        return self

    def add_class(self, cls: str) -> "DOMQuery":
        safe_sel = self._sel.replace("'", "\\'")
        op = (
            f"document.querySelectorAll('{safe_sel}')"
            f".forEach(function(el){{el.classList.add('{cls}');}});"
        )
        self._ops.append(op)
        return self

    def remove_class(self, cls: str) -> "DOMQuery":
        safe_sel = self._sel.replace("'", "\\'")
        op = (
            f"document.querySelectorAll('{safe_sel}')"
            f".forEach(function(el){{el.classList.remove('{cls}');}});"
        )
        self._ops.append(op)
        return self

    def run(self) -> None:
        if self._ops:
            self._b.run_sync_result("\n".join(self._ops))
        return None


class DOMAPI:
    """
    Python'dan DOM manipülasyonu için üst düzey API.
    V8Bridge üzerinden sayfaya komutlar iletir.
    """

    def __init__(self, bridge: V8Bridge):
        self._b = bridge

    def query(self, selector: str) -> DOMQuery:
        return DOMQuery(self._b, selector)

    # ── Element oluşturma / ekleme ────────────
    def append_html(self, selector: str, html: str) -> None:
        safe_sel = selector.replace("'", "\\'")
        safe_html = html.replace("`", "\\`")
        self._b.run(
            f"(function(){{"
            f"var el=document.querySelector('{safe_sel}');"
            f"if(el)el.insertAdjacentHTML('beforeend',`{safe_html}`);"
            f"}})()"
        )

    def prepend_html(self, selector: str, html: str) -> None:
        safe_sel  = selector.replace("'", "\\'")
        safe_html = html.replace("`", "\\`")
        self._b.run(
            f"(function(){{"
            f"var el=document.querySelector('{safe_sel}');"
            f"if(el)el.insertAdjacentHTML('afterbegin',`{safe_html}`);"
            f"}})()"
        )

    # ── Değer okuma ───────────────────────────
    def get_inner_text(self, selector: str,
                       callback: Callable[[str], None]) -> None:
        safe_sel = selector.replace("'", "\\'")
        self._b.run(
            f"(function(){{"
            f"var el=document.querySelector('{safe_sel}');"
            f"return el?el.innerText:'';"
            f"}})()",
            callback
        )

    def get_attr(self, selector: str, attr: str,
                 callback: Callable[[str], None]) -> None:
        safe_sel = selector.replace("'", "\\'")
        self._b.run(
            f"(function(){{"
            f"var el=document.querySelector('{safe_sel}');"
            f"return el?el.getAttribute('{attr}'):null;"
            f"}})()",
            callback
        )

    def count(self, selector: str, callback: Callable[[int], None]) -> None:
        safe_sel = selector.replace("'", "\\'")
        self._b.run(
            f"document.querySelectorAll('{safe_sel}').length",
            callback
        )

    def exists(self, selector: str, callback: Callable[[bool], None]) -> None:
        safe_sel = selector.replace("'", "\\'")
        self._b.run(
            f"!!document.querySelector('{safe_sel}')",
            callback
        )

    # ── Form işlemleri ────────────────────────
    def fill_input(self, selector: str, value: str) -> None:
        safe_sel = selector.replace("'", "\\'")
        safe_val = value.replace("'", "\\'")
        self._b.run(
            f"(function(){{"
            f"var el=document.querySelector('{safe_sel}');"
            f"if(el){{"
            f"  var nativeInputValueSetter=Object.getOwnPropertyDescriptor("
            f"    window.HTMLInputElement.prototype,'value').set;"
            f"  nativeInputValueSetter.call(el,'{safe_val}');"
            f"  el.dispatchEvent(new Event('input',{{bubbles:true}}));"
            f"  el.dispatchEvent(new Event('change',{{bubbles:true}}));"
            f"}}"
            f"}})()"
        )

    def click(self, selector: str) -> None:
        safe_sel = selector.replace("'", "\\'")
        self._b.run(
            f"(function(){{"
            f"var el=document.querySelector('{safe_sel}');"
            f"if(el)el.click();"
            f"}})()"
        )

    # ── Sayfa düzey işlemler ─────────────────
    def get_title(self, callback: Callable[[str], None]) -> None:
        self._b.get_title(callback)

    def get_html(self, callback: Callable[[str], None]) -> None:
        self._b.get_html(callback)

    def get_text(self, callback: Callable[[str], None]) -> None:
        self._b.get_text(callback)

    def get_meta(self, callback: Callable[[dict], None]) -> None:
        self._b.get_meta(callback)

    def get_links(self, callback: Callable[[list], None]) -> None:
        self._b.get_links(callback)

    def scroll_top(self)    -> None: self._b.scroll_top()
    def scroll_bottom(self) -> None: self._b.scroll_bottom()

    def set_body_style(self, prop: str, value: str) -> None:
        self._b.run(f"document.body.style['{prop}']='{value}'")

    def restore_body_style(self, prop: str) -> None:
        self._b.run(f"document.body.style['{prop}']=''")

    # ── Reklam / izleyici temizleme ───────────
    def remove_ads(self) -> None:
        """Yaygın reklam sınıf/id kalıplarını gizler."""
        self._b.run(
            "(function(){"
            "var sel=['[class*=\"ad-\"]','[class*=\"ads-\"]','[id*=\"ad-\"]',"
            "'[id*=\"ads\"]','[class*=\"banner\"]','[class*=\"popup\"]',"
            "'[class*=\"overlay\"]','[class*=\"cookie-\"]','[class*=\"consent\"]',"
            "'[class*=\"newsletter\"]','iframe[src*=\"doubleclick\"]',"
            "'iframe[src*=\"googlesyndication\"]'];"
            "sel.forEach(function(s){"
            "  document.querySelectorAll(s).forEach(function(el){"
            "    el.style.setProperty('display','none','important');"
            "  });"
            "});"
            "})()"
        )

    def print_reader_content(self) -> None:
        self._b.run("window.print()")
