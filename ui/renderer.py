# ─────────────────────────────────────────────────────────────
#  PyWeb  –  ui/renderer.py
#  Sayfa render yardımcıları.
#  Okuma modu, yazdırma, ekran görüntüsü, PDF dışa aktarma.
# ─────────────────────────────────────────────────────────────
from __future__ import annotations
import re
import os
from typing import Callable, Optional
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEnginePage
from PyQt6.QtPrintSupport import QPrinter, QPrintDialog
from PyQt6.QtWidgets import QFileDialog, QMessageBox, QApplication
from PyQt6.QtCore import QUrl, QSizeF
from PyQt6.QtGui import QPageSize, QPageLayout

DATA_DIR = os.path.join(os.path.expanduser("~"), ".pyweb")


# ─────────────────────────────────────────────
# Okuma Modu Şablonu  (mat, göz yormayan renkler)
# ─────────────────────────────────────────────
READER_CSS = """
  * { box-sizing: border-box; margin: 0; padding: 0; }
  :root {
    --bg: #f4f1ec;   /* Krem — göz yormayan arka plan */
    --fg: #2a2520;
    --sub: #7a7060;
    --accent: #4a5090;
    --surface: #ece9e2;
    --border: #d8d4ca;
    --link: #3a5080;
    --code-bg: #e8e4da;
  }
  body {
    background: var(--bg);
    color: var(--fg);
    font-family: Georgia, 'Times New Roman', serif;
    font-size: {fs}px;
    line-height: 1.85;
    animation: fadeIn .35s ease;
  }
  @keyframes fadeIn { from { opacity:0; transform:translateY(6px) } to { opacity:1; transform:none } }
  .wrap { max-width: 700px; margin: 0 auto; padding: 56px 32px 100px; }
  .meta { font-size: .78em; color: var(--sub); margin-bottom: 2.5em;
          padding-bottom: 1em; border-bottom: 1px solid var(--border);
          font-family: 'Segoe UI', sans-serif; }
  h1 { font-size: 1.75em; color: var(--fg); line-height: 1.3;
       margin-bottom: .8em; }
  h2, h3 { color: var(--fg); margin: 1.4em 0 .5em; }
  p { margin-bottom: 1.25em; text-align: justify; }
  a { color: var(--link); text-decoration: none;
      border-bottom: 1px solid var(--border); }
  a:hover { border-color: var(--link); }
  img { max-width: 100%; border-radius: 4px; margin: 1em 0;
        box-shadow: 0 2px 12px rgba(0,0,0,.12); }
  blockquote { border-left: 3px solid var(--border);
               padding: 10px 20px; background: var(--surface);
               margin: 1em 0; color: var(--sub);
               border-radius: 0 4px 4px 0; font-style: italic; }
  code { background: var(--code-bg); padding: 2px 6px;
         border-radius: 3px; font-family: Consolas, monospace;
         font-size: .88em; }
  pre { background: var(--code-bg); padding: 16px;
        border-radius: 6px; overflow-x: auto; margin: 1em 0; }
  hr { border: none; border-top: 1px solid var(--border); margin: 2em 0; }
  table { border-collapse: collapse; width: 100%; margin: 1em 0; }
  th, td { padding: 8px 12px; border: 1px solid var(--border); }
  th { background: var(--surface); font-weight: 600; }
"""

READER_DARK_CSS = READER_CSS.replace(
    "--bg: #f4f1ec;   /* Krem — göz yormayan arka plan */",
    "--bg: #1a1814;"
).replace(
    "--fg: #2a2520;", "--fg: #d8d0c4;"
).replace(
    "--sub: #7a7060;", "--sub: #7a7060;"
).replace(
    "--surface: #ece9e2;", "--surface: #252118;"
).replace(
    "--border: #d8d4ca;", "--border: #353028;"
).replace(
    "--code-bg: #e8e4da;", "--code-bg: #1e1c18;"
).replace(
    "--link: #3a5080;", "--link: #7a98c0;"
)

READER_TEMPLATE = """<!DOCTYPE html>
<html><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<style>{css}</style>
</head><body>
<div class="wrap">
  <h1>{title}</h1>
  <div class="meta">PyWeb Okuma Modu &nbsp;&middot;&nbsp; {url}</div>
  {content}
</div></body></html>"""


class PageRenderer:
    """
    QWebEngineView için render yardımcıları.
    Okuma modu, yazdırma, PDF ve ekran görüntüsü.
    """

    def __init__(self, view: QWebEngineView):
        self._view = view

    # ── Okuma Modu ────────────────────────────
    def render_reader(self, dark: bool = False,
                      font_size: int = 18,
                      callback: Optional[Callable] = None) -> None:
        """
        Sayfanın ana içeriğini çıkarır ve okuma modunda gösterir.
        """
        title = self._view.title()
        url   = self._view.url().toString()

        self._view.page().runJavaScript(
            "document.body ? document.body.innerHTML : ''",
            lambda html: self._apply_reader(html or "", title, url,
                                            dark, font_size, callback)
        )

    def _apply_reader(self, html: str, title: str, url: str,
                      dark: bool, font_size: int,
                      callback: Optional[Callable]) -> None:
        # Script ve style etiketlerini temizle
        clean = re.sub(r"<script[^>]*>.*?</script>", "", html,
                       flags=re.DOTALL | re.IGNORECASE)
        clean = re.sub(r"<style[^>]*>.*?</style>", "", clean,
                       flags=re.DOTALL | re.IGNORECASE)
        # Satır içi olay işleyicilerini kaldır
        clean = re.sub(r'\bon\w+="[^"]*"', "", clean)
        clean = re.sub(r"\bon\w+='[^']*'", "", clean)

        css = (READER_DARK_CSS if dark else READER_CSS).replace("{fs}", str(font_size))
        rendered = READER_TEMPLATE.format(
            title   = self._escape(title),
            url     = url,
            css     = css,
            content = clean,
        )
        self._view.setHtml(rendered, QUrl(url))
        if callback:
            callback()

    # ── Yazdırma ──────────────────────────────
    def print_page(self, parent=None) -> None:
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        dlg = QPrintDialog(printer, parent)
        if dlg.exec() == QPrintDialog.DialogCode.Accepted:
            try:
                self._view.page().print(printer, lambda ok: None)
            except Exception as e:
                QMessageBox.warning(parent, "Yazdırma Hatası", str(e))

    # ── PDF Dışa Aktarma ──────────────────────
    def export_pdf(self, path: Optional[str] = None,
                   parent=None) -> None:
        if not path:
            path, _ = QFileDialog.getSaveFileName(
                parent, "PDF Olarak Kaydet", "sayfa.pdf", "PDF (*.pdf)"
            )
        if not path:
            return

        layout = QPageLayout(
            QPageSize(QPageSize.PageSizeId.A4),
            QPageLayout.Orientation.Portrait,
            __import__('PyQt6.QtCore', fromlist=['QMarginsF']).QMarginsF(10, 10, 10, 10)
        )
        self._view.page().printToPdf(path, layout)

    # ── Ekran Görüntüsü ───────────────────────
    def capture(self):
        """QPixmap olarak tam sayfa görüntüsü döndürür."""
        return self._view.grab()

    # ── Sayfa HTML kaydetme ───────────────────
    def save_html(self, path: Optional[str] = None,
                  parent=None) -> None:
        if not path:
            path, _ = QFileDialog.getSaveFileName(
                parent, "Sayfayı Kaydet", "sayfa.html", "HTML (*.html)"
            )
        if not path:
            return
        self._view.page().toHtml(lambda html: self._write(html, path, parent))

    @staticmethod
    def _write(html: str, path: str, parent) -> None:
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(html)
        except OSError as e:
            if parent:
                QMessageBox.warning(parent, "Kaydetme Hatası", str(e))

    # ── Kaynak görüntüleme ────────────────────
    def view_source(self) -> None:
        url = "view-source:" + self._view.url().toString()
        self._view.setUrl(QUrl(url))

    @staticmethod
    def _escape(text: str) -> str:
        return text.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
