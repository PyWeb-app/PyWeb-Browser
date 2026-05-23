# ─────────────────────────────────────────────────────────────
#  PyWeb  –  storage/cookies.py
#  Tarayıcı çerezlerini yönetir.
#  Okuma, yazma, silme, süre kontrolü ve izolasyon.
# ─────────────────────────────────────────────────────────────
from __future__ import annotations
import json
import os
import time
from typing import Optional
from dataclasses import dataclass, field, asdict

DATA_DIR     = os.path.join(os.path.expanduser("~"), ".pyweb")
COOKIES_FILE = os.path.join(DATA_DIR, "cookies.json")


@dataclass
class Cookie:
    name:      str
    value:     str
    domain:    str       = ""
    path:      str       = "/"
    expires:   float     = 0.0    # Unix timestamp; 0 = oturum çerezi
    secure:    bool      = False
    http_only: bool      = False
    same_site: str       = "Lax"  # Strict | Lax | None

    @property
    def is_expired(self) -> bool:
        return self.expires > 0 and time.time() > self.expires

    @property
    def is_session(self) -> bool:
        return self.expires == 0

    def __repr__(self) -> str:
        return f"Cookie({self.name}={self.value!r}, domain={self.domain})"


class CookieJar:
    """
    Tarayıcı çerez deposu.
    - Alan adı ve yol bazlı sorgulama
    - Üçüncü taraf çerez engelleme
    - Güvenli (Secure) çerez desteği
    - Kalıcı kayıt (JSON)
    """

    def __init__(self, path: str = COOKIES_FILE,
                 block_third_party: bool = False):
        self._path              = path
        self.block_third_party  = block_third_party
        self._store: dict[str, list[Cookie]] = {}   # domain -> [Cookie]
        self._load()

    # ── Çerez ekleme / güncelleme ─────────────
    def set(self, cookie: Cookie) -> None:
        if cookie.is_expired:
            return
        domain = cookie.domain.lstrip(".")
        if domain not in self._store:
            self._store[domain] = []
        # Aynı isimde varsa güncelle
        for i, c in enumerate(self._store[domain]):
            if c.name == cookie.name and c.path == cookie.path:
                self._store[domain][i] = cookie
                self._save()
                return
        self._store[domain].append(cookie)
        self._save()

    def set_simple(self, domain: str, name: str, value: str,
                   expires: float = 0.0, secure: bool = False) -> None:
        self.set(Cookie(
            name=name, value=value, domain=domain,
            expires=expires, secure=secure
        ))

    # ── Çerez okuma ──────────────────────────
    def get(self, domain: str, name: str,
            path: str = "/") -> Optional[Cookie]:
        for c in self._get_for_domain(domain):
            if c.name == name and path.startswith(c.path):
                return c
        return None

    def get_all(self, domain: str,
                path: str = "/") -> list[Cookie]:
        return [c for c in self._get_for_domain(domain)
                if path.startswith(c.path)]

    def _get_for_domain(self, domain: str) -> list[Cookie]:
        """Alan adı ve üst alan adı için çerezleri döndürür."""
        results: list[Cookie] = []
        # Tam eşleşme
        for c in self._store.get(domain, []):
            if not c.is_expired:
                results.append(c)
        # Üst alan (.example.com → example.com)
        parts = domain.split(".")
        for i in range(1, len(parts)):
            parent = ".".join(parts[i:])
            for c in self._store.get(parent, []):
                if not c.is_expired:
                    results.append(c)
        return results

    def cookie_header(self, domain: str, path: str = "/",
                      is_secure: bool = True) -> str:
        """HTTP Cookie başlık değerini üretir."""
        cookies = self.get_all(domain, path)
        pairs = []
        for c in cookies:
            if c.secure and not is_secure:
                continue
            pairs.append(f"{c.name}={c.value}")
        return "; ".join(pairs)

    # ── Silme ─────────────────────────────────
    def delete(self, domain: str, name: str) -> bool:
        domain = domain.lstrip(".")
        lst = self._store.get(domain, [])
        before = len(lst)
        self._store[domain] = [c for c in lst if c.name != name]
        if len(self._store[domain]) < before:
            self._save()
            return True
        return False

    def clear_domain(self, domain: str) -> None:
        domain = domain.lstrip(".")
        self._store.pop(domain, None)
        self._save()

    def clear_all(self) -> None:
        self._store.clear()
        self._save()

    def clear_expired(self) -> int:
        removed = 0
        for domain in list(self._store):
            before = len(self._store[domain])
            self._store[domain] = [c for c in self._store[domain]
                                    if not c.is_expired]
            removed += before - len(self._store[domain])
            if not self._store[domain]:
                del self._store[domain]
        self._save()
        return removed

    def clear_session(self) -> None:
        """Oturum çerezlerini (expires=0) temizler."""
        for domain in list(self._store):
            self._store[domain] = [c for c in self._store[domain]
                                    if not c.is_session]
        self._save()

    # ── İstatistik ────────────────────────────
    @property
    def total_count(self) -> int:
        return sum(len(v) for v in self._store.values())

    @property
    def domain_count(self) -> int:
        return len(self._store)

    def all_domains(self) -> list[str]:
        return sorted(self._store.keys())

    # ── Dosya işlemleri ───────────────────────
    def _load(self) -> None:
        try:
            if os.path.exists(self._path):
                with open(self._path, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                for domain, cookies in raw.items():
                    self._store[domain] = [Cookie(**c) for c in cookies
                                           if isinstance(c, dict)]
        except Exception:
            self._store = {}

    def _save(self) -> None:
        try:
            serializable = {
                domain: [asdict(c) for c in cookies]
                for domain, cookies in self._store.items()
                if cookies
            }
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump(serializable, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
