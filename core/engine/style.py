# ─────────────────────────────────────────────────────────────
#  PyWeb  –  core/engine/style.py
#  DOM + CSSOM birleştirip Computed Styles üretir.
# ─────────────────────────────────────────────────────────────
from __future__ import annotations
from typing import Optional
import re

# Default browser stylesheet (simplified)
_USER_AGENT_STYLES: dict[str, dict[str,str]] = {
    "body":     {"margin":"8px","display":"block"},
    "h1":       {"font-size":"2em","font-weight":"bold","margin":"0.67em 0"},
    "h2":       {"font-size":"1.5em","font-weight":"bold","margin":"0.75em 0"},
    "h3":       {"font-size":"1.17em","font-weight":"bold","margin":"0.83em 0"},
    "p":        {"margin":"1em 0","display":"block"},
    "a":        {"color":"#0000ee","text-decoration":"underline","cursor":"pointer"},
    "strong":   {"font-weight":"bold"},
    "em":       {"font-style":"italic"},
    "code":     {"font-family":"monospace"},
    "pre":      {"font-family":"monospace","white-space":"pre","margin":"1em 0"},
    "ul":       {"list-style-type":"disc","margin":"1em 0","padding-left":"40px"},
    "ol":       {"list-style-type":"decimal","margin":"1em 0","padding-left":"40px"},
    "li":       {"display":"list-item"},
    "table":    {"border-collapse":"separate","border-spacing":"2px","display":"table"},
    "th":       {"font-weight":"bold","text-align":"center"},
    "img":      {"display":"inline"},
    "div":      {"display":"block"},
    "span":     {"display":"inline"},
    "input":    {"display":"inline-block"},
    "button":   {"cursor":"pointer"},
    "hr":       {"border":"1px inset","margin":"0.5em auto"},
    "blockquote":{"margin":"1em 40px"},
}


class StyleEngine:
    """
    DOM düğümü ve CSSOM kurallarını alarak
    her element için hesaplanmış stil (ComputedStyle) üretir.
    """

    def __init__(self, stylesheet=None):
        from core.parser.css_parser import StyleSheet
        self.sheet: Optional[StyleSheet] = stylesheet

    def compute(self, tag: str, classes: list[str] = None,
                id_: str = "", inline_style: str = "") -> dict[str,str]:
        """
        Verilen element için tam stil sözlüğü döndürür.
        Öncelik: inline > id > class > element > user-agent
        """
        computed: dict[str,str] = {}
        classes = classes or []

        # 1. User-agent varsayılanları
        computed.update(_USER_AGENT_STYLES.get(tag, {}))

        # 2. Stylesheet kuralları
        if self.sheet:
            for rule in self.sheet.rules:
                for sel in rule.selectors:
                    sel = sel.strip()
                    if self._sel_matches(sel, tag, classes, id_):
                        for decl in rule.declarations:
                            computed[decl.property] = decl.value
                        break

        # 3. Inline style
        if inline_style:
            for stmt in inline_style.split(";"):
                if ":" in stmt:
                    k, _, v = stmt.partition(":")
                    computed[k.strip().lower()] = v.strip()

        return computed

    @staticmethod
    def _sel_matches(sel: str, tag: str, classes: list[str], id_: str) -> bool:
        sel = sel.strip()
        if sel == "*":           return True
        if sel == tag:           return True
        if f"#{id_}" in sel:    return True
        for cls in classes:
            if f".{cls}" in sel: return True
        return False

    def get_color(self, tag: str, **kw) -> Optional[str]:
        return self.compute(tag, **kw).get("color")

    def get_font_size(self, tag: str, **kw) -> str:
        return self.compute(tag, **kw).get("font-size", "16px")

    @staticmethod
    def px(value: str, parent_px: int = 16) -> int:
        """CSS uzunluk değerini piksel sayısına çevirir."""
        value = value.strip()
        if value.endswith("px"):
            return int(float(value[:-2]))
        if value.endswith("em"):
            return int(float(value[:-2]) * parent_px)
        if value.endswith("rem"):
            return int(float(value[:-3]) * 16)
        if value.endswith("%"):
            return int(float(value[:-1]) / 100 * parent_px)
        try:
            return int(float(value))
        except ValueError:
            return 0
