# ─────────────────────────────────────────────────────────────
#  PyWeb  –  core/parser/css_parser.py
#  CSS kodunu okuyup stil kurallarına (CSSOM) çeviren lexer.
#  Gerçek render için QtWebEngine kullanılır;
#  bu parser tema enjeksiyonu ve özel CSS çözümleme içindir.
# ─────────────────────────────────────────────────────────────
from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import Optional


# ─────────────────────────────────────────────
# Veri modelleri
# ─────────────────────────────────────────────
@dataclass
class Declaration:
    """Tek bir CSS özellik: değer çifti."""
    property:  str
    value:     str
    important: bool = False

    def __str__(self) -> str:
        imp = " !important" if self.important else ""
        return f"{self.property}: {self.value}{imp}"


@dataclass
class Rule:
    """Bir selector grubuna ait tanım bloğu."""
    selectors:    list[str]           = field(default_factory=list)
    declarations: list[Declaration]   = field(default_factory=list)
    specificity:  tuple               = (0, 0, 0)   # (id, class, element)

    def matches_tag(self, tag: str) -> bool:
        return any(s.strip() == tag for s in self.selectors)

    def matches_class(self, cls: str) -> bool:
        return any(f".{cls}" in s for s in self.selectors)

    def matches_id(self, id_: str) -> bool:
        return any(f"#{id_}" in s for s in self.selectors)

    def get(self, prop: str) -> Optional[str]:
        for d in reversed(self.declarations):
            if d.property == prop:
                return d.value
        return None

    def __str__(self) -> str:
        sels = ", ".join(self.selectors)
        decls = "; ".join(str(d) for d in self.declarations)
        return f"{sels} {{ {decls} }}"


@dataclass
class AtRule:
    """@media, @keyframes, @import gibi özel kurallar."""
    name:    str
    params:  str
    rules:   list[Rule]   = field(default_factory=list)
    raw:     str          = ""


@dataclass
class StyleSheet:
    """Tüm CSS kurallarını tutan CSSOM nesnesi."""
    rules:    list[Rule]   = field(default_factory=list)
    at_rules: list[AtRule] = field(default_factory=list)
    source:   str          = ""

    def get_rules_for(self, tag: str = "",
                      classes: list[str] = None,
                      id_: str = "") -> list[Rule]:
        """Belirtilen element için uygulanan kuralları döndürür."""
        classes = classes or []
        matched = []
        for rule in self.rules:
            for sel in rule.selectors:
                sel = sel.strip()
                if (tag and sel == tag) or \
                   any(f".{c}" in sel for c in classes) or \
                   (id_ and f"#{id_}" in sel) or \
                   sel == "*":
                    matched.append(rule)
                    break
        return matched

    def compute_style(self, tag: str = "",
                      classes: list[str] = None,
                      id_: str = "") -> dict[str,str]:
        """Element için hesaplanmış stil sözlüğü döndürür."""
        rules = self.get_rules_for(tag, classes, id_)
        computed: dict[str,str] = {}
        for rule in rules:
            for decl in rule.declarations:
                computed[decl.property] = decl.value
        return computed


# ─────────────────────────────────────────────
# Lexer
# ─────────────────────────────────────────────
class CSSLexer:
    """CSS kaynak kodunu token listesine çevirir."""

    def __init__(self, source: str):
        self._src = source
        self._pos = 0

    def strip_comments(self) -> str:
        """/* ... */ yorumlarını kaldırır."""
        return re.sub(r"/\*.*?\*/", "", self._src, flags=re.DOTALL)

    def tokenize(self) -> list[tuple[str,str]]:
        """
        Basit token çıkarımı.
        Token türleri: AT, SELECTOR, LBRACE, RBRACE, DECL, STRING
        """
        tokens = []
        src    = self.strip_comments()
        i      = 0
        while i < len(src):
            c = src[i]
            # Boşluk atla
            if c in " \t\n\r":
                i += 1; continue
            # @rule
            if c == "@":
                end = src.find("{", i)
                semi= src.find(";", i)
                if semi >= 0 and (end < 0 or semi < end):
                    tokens.append(("AT_STMT", src[i:semi].strip()))
                    i = semi + 1
                else:
                    end = end if end >= 0 else len(src)
                    tokens.append(("AT_START", src[i:end].strip()))
                    tokens.append(("LBRACE", "{"))
                    i = end + 1
            elif c == "{":
                tokens.append(("LBRACE", "{")); i += 1
            elif c == "}":
                tokens.append(("RBRACE", "}")); i += 1
            elif c == ";":
                i += 1
            else:
                end_brace = src.find("{", i)
                end_semi  = src.find(";", i)
                end_rbrace= src.find("}", i)
                ends = [e for e in [end_brace,end_semi,end_rbrace] if e >= 0]
                end  = min(ends) if ends else len(src)
                chunk = src[i:end].strip()
                if chunk:
                    tokens.append(("CHUNK", chunk))
                i = end
        return tokens


# ─────────────────────────────────────────────
# Parser
# ─────────────────────────────────────────────
class CSSParser:
    """
    CSS kaynak kodunu StyleSheet nesnesine çevirir.
    """

    def parse(self, source: str) -> StyleSheet:
        lexer  = CSSLexer(source)
        tokens = lexer.tokenize()
        sheet  = StyleSheet(source=source)
        i      = 0

        while i < len(tokens):
            kind, val = tokens[i]

            if kind == "AT_START":
                at_rule, i = self._parse_at_rule(val, tokens, i+1)
                sheet.at_rules.append(at_rule)

            elif kind == "AT_STMT":
                # @import, @charset vs.
                name = re.match(r"@(\w+)", val)
                if name:
                    sheet.at_rules.append(AtRule(
                        name   = name.group(1),
                        params = val[name.end():].strip(),
                        raw    = val,
                    ))
                i += 1

            elif kind == "CHUNK":
                selectors = [s.strip() for s in val.split(",") if s.strip()]
                # Sonraki token { olmalı
                if i+1 < len(tokens) and tokens[i+1][0] == "LBRACE":
                    decls_raw, i = self._collect_block(tokens, i+2)
                    rule = Rule(
                        selectors    = selectors,
                        declarations = self._parse_declarations(decls_raw),
                        specificity  = self._specificity(selectors[0] if selectors else ""),
                    )
                    sheet.rules.append(rule)
                else:
                    i += 1
            else:
                i += 1

        return sheet

    def _parse_at_rule(self, header: str, tokens: list, i: int) -> tuple[AtRule,int]:
        m      = re.match(r"@(\w+)\s*(.*)", header)
        name   = m.group(1) if m else "unknown"
        params = m.group(2).strip() if m else ""
        inner_rules: list[Rule] = []
        raw_chunks: list[str]   = []

        depth = 1
        while i < len(tokens) and depth > 0:
            kind, val = tokens[i]
            if kind == "LBRACE":   depth += 1
            elif kind == "RBRACE": depth -= 1
            elif kind == "CHUNK" and depth == 1:
                sels = [s.strip() for s in val.split(",") if s.strip()]
                if i+1 < len(tokens) and tokens[i+1][0] == "LBRACE":
                    decls_raw, i = self._collect_block(tokens, i+2)
                    inner_rules.append(Rule(
                        selectors    = sels,
                        declarations = self._parse_declarations(decls_raw),
                    ))
                    continue
            raw_chunks.append(val)
            i += 1

        return AtRule(name=name, params=params, rules=inner_rules, raw=" ".join(raw_chunks)), i

    def _collect_block(self, tokens: list, i: int) -> tuple[list[str], int]:
        """{ ... } bloğu içindeki CHUNK'ları toplar."""
        chunks: list[str] = []
        depth  = 1
        while i < len(tokens) and depth > 0:
            kind, val = tokens[i]
            if kind == "LBRACE":    depth += 1
            elif kind == "RBRACE":  depth -= 1; 
            else: chunks.append(val)
            i += 1
        return chunks, i

    @staticmethod
    def _parse_declarations(chunks: list[str]) -> list[Declaration]:
        decls = []
        for chunk in chunks:
            for stmt in chunk.split(";"):
                stmt = stmt.strip()
                if ":" not in stmt:
                    continue
                prop, _, val = stmt.partition(":")
                prop = prop.strip().lower()
                val  = val.strip()
                important = False
                if val.lower().endswith("!important"):
                    important = True
                    val = val[:-10].strip()
                if prop:
                    decls.append(Declaration(property=prop, value=val, important=important))
        return decls

    @staticmethod
    def _specificity(selector: str) -> tuple[int,int,int]:
        """
        Basit özgüllük (specificity) hesabı.
        (id_count, class_count, element_count)
        """
        ids      = len(re.findall(r"#[\w\-]+", selector))
        classes  = len(re.findall(r"\.[\w\-]+|:[\w\-]+|\[[\w\-]+", selector))
        elements = len(re.findall(r"(?<![#.\[:])(?:^|[\s>+~])([a-z][a-z0-9]*)", selector))
        return (ids, classes, elements)


# ─────────────────────────────────────────────
# CSS değişken çözümleyici (CSS Custom Properties)
# ─────────────────────────────────────────────
def resolve_vars(css: str, variables: dict[str,str]) -> str:
    """
    var(--name) ifadelerini sözlükteki değerlerle değiştirir.
    """
    def replacer(m: re.Match) -> str:
        name    = m.group(1).strip()
        default = m.group(2).strip() if m.group(2) else ""
        return variables.get(name, default)

    return re.sub(r"var\(\s*(--[\w\-]+)(?:\s*,\s*([^)]+))?\s*\)", replacer, css)


def minify(css: str) -> str:
    """CSS'i basitçe küçültür (boşluk, yorum kaldırma)."""
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)
    css = re.sub(r"\s+", " ", css)
    css = re.sub(r"\s*([{}:;,>+~])\s*", r"\1", css)
    return css.strip()
