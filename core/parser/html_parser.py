# ─────────────────────────────────────────────────────────────
#  PyWeb  –  core/parser/html_parser.py
#  Ham HTML'i DOM ağacına (düğüm listesi) çeviren state-machine
#  parser. Gerçek render için QtWebEngine kullanılır;
#  bu parser meta-analiz, okuma modu, link çıkarma içindir.
# ─────────────────────────────────────────────────────────────
from __future__ import annotations
import re
from typing import Optional
from dataclasses import dataclass, field


# ─────────────────────────────────────────────
# DOM Düğümleri
# ─────────────────────────────────────────────
@dataclass
class DOMNode:
    tag:        str
    attrs:      dict[str, str]         = field(default_factory=dict)
    children:   list["DOMNode"]        = field(default_factory=list)
    text:       str                    = ""
    parent:     Optional["DOMNode"]    = field(default=None, repr=False, compare=False)
    is_text:    bool                   = False

    def __str__(self) -> str:
        if self.is_text:
            return self.text[:60]
        return f"<{self.tag} {self.attrs}>"

    def get_text(self, separator: str = " ") -> str:
        """Tüm alt metin içeriğini birleştirir."""
        parts = []
        if self.is_text:
            parts.append(self.text)
        for child in self.children:
            parts.append(child.get_text(separator))
        return separator.join(p for p in parts if p.strip())

    def find(self, tag: str) -> Optional["DOMNode"]:
        """İlk eşleşen etiketi bulur (DFS)."""
        if self.tag == tag:
            return self
        for child in self.children:
            r = child.find(tag)
            if r:
                return r
        return None

    def find_all(self, tag: str) -> list["DOMNode"]:
        """Tüm eşleşen etiketleri bulur."""
        result = []
        if self.tag == tag:
            result.append(self)
        for child in self.children:
            result.extend(child.find_all(tag))
        return result

    def find_by_attr(self, attr: str, value: str) -> Optional["DOMNode"]:
        """Belirtilen attribute=value çiftini arar."""
        if self.attrs.get(attr) == value:
            return self
        for child in self.children:
            r = child.find_by_attr(attr, value)
            if r:
                return r
        return None

    @property
    def inner_text(self) -> str:
        return self.get_text(" ")

    @property
    def href(self) -> str:
        return self.attrs.get("href", "")

    @property
    def src(self) -> str:
        return self.attrs.get("src", "")

    @property
    def class_list(self) -> list[str]:
        return self.attrs.get("class","").split()


# ─────────────────────────────────────────────
# Parser (State Machine)
# ─────────────────────────────────────────────
class HTMLParser:
    """
    Basit, hızlı tek-geçişli HTML ayrıştırıcı.
    Hatalı HTML'i tolere eder.
    Çıkış: DOMNode ağacı (root düğümü).
    """

    VOID_TAGS = frozenset({
        "area","base","br","col","embed","hr","img","input",
        "link","meta","param","source","track","wbr",
    })
    SKIP_TAGS = frozenset({"script","style","svg","math"})

    def __init__(self):
        self._pos   = 0
        self._html  = ""
        self._root  = DOMNode(tag="document")
        self._stack: list[DOMNode] = []

    def parse(self, html: str) -> DOMNode:
        """HTML string'i alır, DOM ağacı döndürür."""
        self._html  = html
        self._pos   = 0
        self._root  = DOMNode(tag="document")
        self._stack = [self._root]

        while self._pos < len(self._html):
            if self._html[self._pos] == "<":
                self._parse_tag()
            else:
                self._parse_text()

        return self._root

    # ── Tag ayrıştırma ────────────────────────
    def _parse_tag(self):
        i = self._pos + 1
        html = self._html

        # Yorum: <!-- ... -->
        if html[i:i+3] == "!--":
            end = html.find("-->", i)
            self._pos = end + 3 if end >= 0 else len(html)
            return

        # DOCTYPE
        if html[i:i+7].upper() == "DOCTYPE":
            end = html.find(">", i)
            self._pos = end + 1 if end >= 0 else len(html)
            return

        # Kapanan tag
        if i < len(html) and html[i] == "/":
            end = html.find(">", i)
            if end < 0:
                self._pos = len(html); return
            tag_name = html[i+1:end].strip().lower().split()[0] if html[i+1:end].strip() else ""
            self._pos = end + 1
            self._close_tag(tag_name)
            return

        # Açılan tag
        end = html.find(">", i)
        if end < 0:
            self._pos = len(html); return

        self_close = html[end-1] == "/"
        content    = html[i:end-1 if self_close else end]
        tag_name, attrs = self._parse_open_tag(content)
        self._pos  = end + 1

        if not tag_name or not tag_name.isalpha() and not re.match(r"[a-z][a-z0-9\-]*", tag_name):
            return

        node = DOMNode(tag=tag_name, attrs=attrs, parent=self._stack[-1])
        self._stack[-1].children.append(node)

        if tag_name in self.SKIP_TAGS:
            # Script/style içeriğini atla
            close_marker = f"</{tag_name}"
            end2 = html.lower().find(close_marker, self._pos)
            if end2 >= 0:
                end3 = html.find(">", end2)
                self._pos = end3 + 1 if end3 >= 0 else len(html)
            return

        if tag_name not in self.VOID_TAGS and not self_close:
            self._stack.append(node)

    def _close_tag(self, tag_name: str):
        for i in range(len(self._stack)-1, 0, -1):
            if self._stack[i].tag == tag_name:
                self._stack = self._stack[:i]
                return

    @staticmethod
    def _parse_open_tag(content: str) -> tuple[str, dict]:
        content = content.strip()
        if not content:
            return "", {}
        parts = re.split(r"\s+", content, 1)
        tag   = parts[0].lower()
        attrs: dict[str,str] = {}

        if len(parts) > 1:
            attr_str = parts[1]
            for m in re.finditer(
                r'([\w\-:]+)(?:\s*=\s*(?:"([^"]*)"'
                r"|'([^']*)'|([^\s>]*)))?",
                attr_str
            ):
                key = m.group(1).lower()
                val = m.group(2) or m.group(3) or m.group(4) or ""
                attrs[key] = val

        return tag, attrs

    # ── Metin ayrıştırma ─────────────────────
    def _parse_text(self):
        end  = self._html.find("<", self._pos)
        text = self._html[self._pos: end if end >= 0 else None]
        self._pos = end if end >= 0 else len(self._html)

        clean = self._decode_entities(text)
        if clean.strip():
            node = DOMNode(tag="#text", text=clean, is_text=True, parent=self._stack[-1])
            self._stack[-1].children.append(node)

    @staticmethod
    def _decode_entities(text: str) -> str:
        text = text.replace("&amp;",  "&")
        text = text.replace("&lt;",   "<")
        text = text.replace("&gt;",   ">")
        text = text.replace("&quot;", '"')
        text = text.replace("&#39;",  "'")
        text = text.replace("&nbsp;", " ")
        text = re.sub(r"&#(\d+);",  lambda m: chr(int(m.group(1))),    text)
        text = re.sub(r"&#x([0-9a-fA-F]+);", lambda m: chr(int(m.group(1),16)), text)
        return text


# ─────────────────────────────────────────────
# Yardımcı: Meta bilgisi çıkarma
# ─────────────────────────────────────────────
def extract_meta(dom: DOMNode) -> dict:
    meta = {"title":"","description":"","keywords":"","author":"","canonical":""}

    title_node = dom.find("title")
    if title_node:
        meta["title"] = title_node.get_text().strip()

    for node in dom.find_all("meta"):
        name    = node.attrs.get("name","").lower()
        prop    = node.attrs.get("property","").lower()
        content = node.attrs.get("content","")
        if name in ("description","keywords","author"):
            meta[name] = content
        elif prop == "og:title" and not meta["title"]:
            meta["title"] = content
        elif prop == "og:description" and not meta["description"]:
            meta["description"] = content

    for node in dom.find_all("link"):
        if node.attrs.get("rel","").lower() == "canonical":
            meta["canonical"] = node.attrs.get("href","")

    return meta


def extract_links(dom: DOMNode, base_url: str = "") -> list[dict]:
    """Tüm <a href> bağlantılarını çıkarır."""
    links = []
    for node in dom.find_all("a"):
        href = node.attrs.get("href","").strip()
        if href and not href.startswith("#"):
            links.append({
                "href":  href,
                "text":  node.get_text().strip()[:80],
                "title": node.attrs.get("title",""),
            })
    return links


def extract_images(dom: DOMNode) -> list[dict]:
    """Tüm <img src> görsellerini çıkarır."""
    imgs = []
    for node in dom.find_all("img"):
        src = node.attrs.get("src","").strip()
        if src:
            imgs.append({
                "src":   src,
                "alt":   node.attrs.get("alt",""),
                "width": node.attrs.get("width",""),
                "height":node.attrs.get("height",""),
            })
    return imgs


def extract_article_text(dom: DOMNode) -> str:
    """
    Sayfanın ana içerik metnini çıkarmaya çalışır.
    Önce <article>, <main> bakar; yoksa <body>'yi kullanır.
    """
    for tag in ("article", "main", "body"):
        node = dom.find(tag)
        if node:
            text = node.get_text("\n")
            if len(text.strip()) > 200:
                return text
    return dom.get_text("\n")
