# ─────────────────────────────────────────────────────────────
#  PyWeb  –  core/engine/layout.py
#  DOM + ComputedStyles → piksel koordinatları (Layout Tree).
#  Gerçek render QtWebEngine yapar; bu modül
#  PDF dışa aktarma, erişilebilirlik ve test amaçlıdır.
# ─────────────────────────────────────────────────────────────
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Rect:
    """Ekrandaki bir dikdörtgen alan."""
    x:      float = 0
    y:      float = 0
    width:  float = 0
    height: float = 0

    @property
    def right(self)  -> float: return self.x + self.width
    @property
    def bottom(self) -> float: return self.y + self.height

    def contains(self, px: float, py: float) -> bool:
        return self.x <= px <= self.right and self.y <= py <= self.bottom

    def __repr__(self) -> str:
        return f"Rect(x={self.x:.0f},y={self.y:.0f},w={self.width:.0f},h={self.height:.0f})"


@dataclass
class LayoutBox:
    """Tek bir DOM düğümünün layout bilgisi."""
    tag:      str
    rect:     Rect                  = field(default_factory=Rect)
    style:    dict                  = field(default_factory=dict)
    children: list["LayoutBox"]     = field(default_factory=list)
    text:     str                   = ""

    display: str = "block"   # block | inline | flex | grid | none

    @property
    def is_visible(self) -> bool:
        return (self.style.get("display","block") != "none"
                and self.style.get("visibility","visible") != "hidden"
                and self.style.get("opacity","1") != "0")


class LayoutEngine:
    """
    Basit blok-akış yerleşim motoru.
    Sadece block / inline display destekler.
    Gerçek box model (margin/padding/border) hesabı dahil.
    """

    LINE_HEIGHT_DEFAULT = 1.4

    def __init__(self, viewport_width: int = 1280, viewport_height: int = 900):
        self.vw = viewport_width
        self.vh = viewport_height

    def layout(self, dom, style_engine) -> LayoutBox:
        """
        DOM ağacından layout ağacı üretir.
        dom: DOMNode  |  style_engine: StyleEngine
        """
        root_box = LayoutBox(tag="__root__", rect=Rect(0, 0, self.vw, self.vh))
        self._layout_children(dom, root_box, style_engine, cursor_y=0)
        return root_box

    def _layout_children(self, dom_node, parent_box: LayoutBox,
                         se, cursor_y: float) -> float:
        """
        Dom düğümlerini parent_box içine yerleştirir.
        cursor_y: bir sonraki block'un başlayacağı y koordinatı.
        """
        from core.parser.html_parser import DOMNode

        for child in dom_node.children:
            if not isinstance(child, DOMNode):
                continue

            if child.is_text:
                # Inline metin kutusu
                text = child.text.strip()
                if not text:
                    continue
                font_size = self._font_size(parent_box.style)
                height    = font_size * self.LINE_HEIGHT_DEFAULT
                box = LayoutBox(
                    tag  = "#text",
                    text = text,
                    rect = Rect(parent_box.rect.x, cursor_y,
                                parent_box.rect.width, height),
                    style = parent_box.style,
                )
                parent_box.children.append(box)
                cursor_y += height
                continue

            computed = se.compute(
                child.tag,
                classes = child.class_list,
                id_     = child.attrs.get("id",""),
                inline_style = child.attrs.get("style",""),
            )
            display = computed.get("display","block")
            if display == "none":
                continue

            margin_top    = se.px(computed.get("margin-top","0"))
            margin_bottom = se.px(computed.get("margin-bottom","0"))
            padding_top   = se.px(computed.get("padding-top","0"))
            padding_bottom= se.px(computed.get("padding-bottom","0"))

            cursor_y += margin_top

            box = LayoutBox(
                tag     = child.tag,
                style   = computed,
                display = display,
                rect    = Rect(
                    parent_box.rect.x,
                    cursor_y,
                    parent_box.rect.width,
                    0,   # yükseklik içerikle belirlenir
                ),
            )

            # İçerik yüksekliği
            inner_y = cursor_y + padding_top
            inner_y = self._layout_children(child, box, se, inner_y)
            inner_y += padding_bottom

            box.rect.height = inner_y - cursor_y
            cursor_y = inner_y + margin_bottom
            parent_box.children.append(box)

        return cursor_y

    @staticmethod
    def _font_size(style: dict) -> float:
        raw = style.get("font-size","16px")
        try:
            if raw.endswith("px"):  return float(raw[:-2])
            if raw.endswith("em"):  return float(raw[:-2]) * 16
            if raw.endswith("rem"): return float(raw[:-3]) * 16
            return float(raw)
        except ValueError:
            return 16.0

    def find_at(self, root: LayoutBox, px: float, py: float) -> Optional[LayoutBox]:
        """Belirtilen ekran koordinatındaki layout box'ı bulur."""
        if not root.rect.contains(px, py):
            return None
        for child in reversed(root.children):
            r = self.find_at(child, px, py)
            if r:
                return r
        return root

    @staticmethod
    def total_height(root: LayoutBox) -> float:
        """Tüm içeriğin toplam piksel yüksekliğini döndürür."""
        if not root.children:
            return root.rect.height
        last = root.children[-1]
        return last.rect.bottom
