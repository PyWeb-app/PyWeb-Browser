# ─────────────────────────────────────────────────────────────
#  PyWeb  –  security/sandbox.py
#  Sekme izolasyonu ve yerel kaynak erişim kısıtlamaları.
#  Sayfaların dosya sistemi, Python ortamı ve ağa
#  izinsiz erişimini engeller.
# ─────────────────────────────────────────────────────────────
from __future__ import annotations
import os
import re
from typing import Optional
from PyQt6.QtWebEngineCore import (
    QWebEngineProfile, QWebEngineSettings, QWebEnginePage,
    QWebEngineUrlRequestInterceptor, QWebEngineUrlRequestInfo,
)
from PyQt6.QtCore import QUrl


# ─────────────────────────────────────────────
# URL İstek Dinleyici (Request Interceptor)
# ─────────────────────────────────────────────
class PyWebRequestInterceptor(QWebEngineUrlRequestInterceptor):
    """
    Sayfadan çıkan tüm ağ isteklerini yakalar.
    - file:// erişimini engeller
    - Kara listedeki alan adlarını engeller
    - Tracker JS dosyalarını bloke eder
    - İstek başlıklarına güvenlik ekler
    """

    # Kesin engellenen şemalar
    BLOCKED_SCHEMES = frozenset({"file", "chrome", "qrc", "data"})

    # Engellenen içerik kalıpları (regex)
    BLOCKED_PATTERNS = [
        r"doubleclick\.net",
        r"googlesyndication\.com",
        r"adservice\.google\.",
        r"facebook\.net/en_US/fbevents",
        r"connect\.facebook\.net.*sdk\.js",
        r"hotjar\.com",
        r"fullstory\.com",
        r"\.ads\.",
        r"/ads/",
        r"/adserver/",
        r"tracking\.",
        r"tracker\.",
        r"analytics\.",
    ]

    def __init__(self, blocked_sites: Optional[list[str]] = None,
                 ad_block: bool = True,
                 allow_local: bool = False):
        super().__init__()
        self.blocked_sites = blocked_sites or []
        self.ad_block      = ad_block
        self.allow_local   = allow_local
        self._compiled     = [re.compile(p, re.IGNORECASE)
                              for p in self.BLOCKED_PATTERNS]
        self._block_count  = 0

    def interceptRequest(self, info: QWebEngineUrlRequestInfo) -> None:
        url     = info.requestUrl().toString()
        scheme  = info.requestUrl().scheme()
        host    = info.requestUrl().host().lower()

        # 1. Şema kontrolü
        if not self.allow_local and scheme in self.BLOCKED_SCHEMES:
            info.block(True)
            self._block_count += 1
            return

        # 2. Engellenen siteler (kullanıcı listesi)
        for site in self.blocked_sites:
            if site.lower() in host:
                info.block(True)
                self._block_count += 1
                return

        # 3. Reklam / tracker engelleme
        if self.ad_block:
            for pattern in self._compiled:
                if pattern.search(url):
                    info.block(True)
                    self._block_count += 1
                    return

        # 4. Güvenlik başlıkları ekle
        info.setHttpHeader(b"X-Frame-Options", b"SAMEORIGIN")
        info.setHttpHeader(b"X-Content-Type-Options", b"nosniff")

    def add_blocked_site(self, domain: str) -> None:
        if domain not in self.blocked_sites:
            self.blocked_sites.append(domain.lower())

    def remove_blocked_site(self, domain: str) -> None:
        self.blocked_sites = [s for s in self.blocked_sites
                               if s != domain.lower()]

    @property
    def blocked_count(self) -> int:
        return self._block_count


# ─────────────────────────────────────────────
# Sandbox Profil Yapılandırması
# ─────────────────────────────────────────────
class SandboxProfile:
    """
    QWebEngineProfile'a güvenlik kısıtlamalarını uygular.
    Her çağrı için ayrı profil oluşturulabilir (konteyner desteği).
    """

    def __init__(self, profile: QWebEngineProfile,
                 interceptor: Optional[PyWebRequestInterceptor] = None):
        self._profile     = profile
        self._interceptor = interceptor or PyWebRequestInterceptor()
        self._apply()

    def _apply(self) -> None:
        p = self._profile

        # İstek dinleyici
        p.setUrlRequestInterceptor(self._interceptor)

        # Ayarlar
        s = p.settings()
        s.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled,          True)
        s.setAttribute(QWebEngineSettings.WebAttribute.LocalStorageEnabled,        True)
        s.setAttribute(QWebEngineSettings.WebAttribute.AutoLoadImages,             True)
        s.setAttribute(QWebEngineSettings.WebAttribute.PluginsEnabled,             False)
        s.setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanOpenWindows,   False)
        s.setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanAccessClipboard, False)
        # Yerel dosya erişimini engelle
        s.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, False)
        s.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls,   False)

    def apply_incognito(self) -> None:
        """Gizli mod: çerez ve önbellek depolamasını devre dışı bırakır."""
        self._profile.setPersistentCookiesPolicy(
            QWebEngineProfile.PersistentCookiesPolicy.NoPersistentCookies
        )
        self._profile.setHttpCacheType(
            QWebEngineProfile.HttpCacheType.MemoryHttpCache
        )

    def apply_strict(self) -> None:
        """
        Sıkı mod: JS, çerezler ve yerel depolamayı kapatır.
        Sadece içerik okuma modunda kullanılır.
        """
        s = self._profile.settings()
        s.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled,   False)
        s.setAttribute(QWebEngineSettings.WebAttribute.LocalStorageEnabled, False)
        self._profile.setPersistentCookiesPolicy(
            QWebEngineProfile.PersistentCookiesPolicy.NoPersistentCookies
        )

    def set_ua(self, ua: str) -> None:
        self._profile.setHttpUserAgent(ua)

    @property
    def blocked_count(self) -> int:
        return self._interceptor.blocked_count


# ─────────────────────────────────────────────
# İzin Yöneticisi
# ─────────────────────────────────────────────
class PermissionManager:
    """
    Kamera, mikrofon, konum gibi izinleri yönetir.
    QWebEnginePage.permissionRequested sinyaline bağlanır.
    """

    def __init__(self, default_deny: bool = True):
        self.default_deny = default_deny
        self._grants:  set[tuple[str, int]] = set()   # (origin, feature)
        self._denials: set[tuple[str, int]] = set()

    def connect(self, page: QWebEnginePage) -> None:
        page.permissionRequested.connect(self._handle)

    def _handle(self, permission) -> None:
        origin  = permission.origin().toString()
        feature = permission.feature()
        key     = (origin, int(feature))

        if key in self._grants:
            permission.grant()
        elif key in self._denials or self.default_deny:
            permission.deny()

    def grant(self, origin: str, feature: int) -> None:
        key = (origin, feature)
        self._grants.add(key)
        self._denials.discard(key)

    def deny(self, origin: str, feature: int) -> None:
        key = (origin, feature)
        self._denials.add(key)
        self._grants.discard(key)

    def reset(self, origin: str) -> None:
        self._grants  = {k for k in self._grants  if k[0] != origin}
        self._denials = {k for k in self._denials if k[0] != origin}
