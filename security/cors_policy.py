# ─────────────────────────────────────────────────────────────
#  PyWeb  –  security/cors_policy.py
#  Siteler arası istek politikasını yönetir (CORS).
#  İzin verilen originleri, header kontrolünü ve
#  preflight önbelleklemesini ele alır.
# ─────────────────────────────────────────────────────────────
from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class CORSRule:
    """Tek bir CORS politika kuralı."""
    origin_pattern: str               # "*" veya "https://example.com" veya regex
    allowed_methods: list[str]        = field(default_factory=lambda: ["GET","POST"])
    allowed_headers: list[str]        = field(default_factory=lambda: ["Content-Type"])
    allow_credentials: bool           = False
    max_age_sec: int                  = 86400   # preflight önbellek süresi

    def matches_origin(self, origin: str) -> bool:
        if self.origin_pattern == "*":
            return True
        if self.origin_pattern == origin:
            return True
        try:
            return bool(re.fullmatch(self.origin_pattern, origin))
        except re.error:
            return False


class CORSPolicy:
    """
    CORS politika motoru.
    - Kaynak (origin) doğrulama
    - Preflight istek yanıtı üretimi
    - Güvenli kaynak listesi
    """

    # Varsayılan güvenilir kaynaklar
    TRUSTED_ORIGINS = {
        "https://accounts.google.com",
        "https://www.google.com",
        "https://api.github.com",
    }

    def __init__(self, strict_mode: bool = True):
        self.strict      = strict_mode
        self._rules: list[CORSRule] = []
        self._blocked: set[str] = set()
        self._cache:  dict[str, bool] = {}   # origin -> allow

    # ── Kural yönetimi ────────────────────────
    def add_rule(self, rule: CORSRule) -> None:
        self._rules.append(rule)
        self._cache.clear()

    def add_trusted(self, origin: str) -> None:
        self.TRUSTED_ORIGINS.add(origin)
        self._cache.clear()

    def block_origin(self, origin: str) -> None:
        self._blocked.add(origin)
        self._cache.pop(origin, None)

    def unblock_origin(self, origin: str) -> None:
        self._blocked.discard(origin)
        self._cache.pop(origin, None)

    # ── Kontrol ───────────────────────────────
    def is_allowed(self, origin: str, method: str = "GET",
                   header: Optional[str] = None) -> bool:
        """
        Belirtilen origin için CORS isteğine izin verilip
        verilmeyeceğini döndürür.
        """
        if origin in self._blocked:
            return False
        if origin in self.TRUSTED_ORIGINS:
            return True
        if origin in self._cache:
            return self._cache[origin]

        for rule in self._rules:
            if rule.matches_origin(origin):
                m_ok = method.upper() in [m.upper() for m in rule.allowed_methods]
                h_ok = header is None or header in rule.allowed_headers or "*" in rule.allowed_headers
                if m_ok and h_ok:
                    self._cache[origin] = True
                    return True

        result = not self.strict
        self._cache[origin] = result
        return result

    def preflight_headers(self, origin: str,
                          request_method: str = "POST") -> dict[str, str]:
        """
        OPTIONS preflight isteği için yanıt başlıklarını üretir.
        """
        for rule in self._rules:
            if rule.matches_origin(origin):
                return {
                    "Access-Control-Allow-Origin":  origin,
                    "Access-Control-Allow-Methods": ", ".join(rule.allowed_methods),
                    "Access-Control-Allow-Headers": ", ".join(rule.allowed_headers),
                    "Access-Control-Max-Age":       str(rule.max_age_sec),
                    **({"Access-Control-Allow-Credentials": "true"}
                       if rule.allow_credentials else {}),
                }
        if origin in self.TRUSTED_ORIGINS:
            return {
                "Access-Control-Allow-Origin":  origin,
                "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type, Authorization",
                "Access-Control-Max-Age":       "86400",
            }
        return {}

    def is_same_origin(self, url1: str, url2: str) -> bool:
        """İki URL aynı originde mi?"""
        def _origin(u: str) -> str:
            m = re.match(r"(https?://[^/]+)", u)
            return m.group(1).lower() if m else ""
        return _origin(url1) == _origin(url2) and _origin(url1) != ""

    @property
    def blocked_origins(self) -> list[str]:
        return sorted(self._blocked)
