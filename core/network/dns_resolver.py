# ─────────────────────────────────────────────────────────────
#  PyWeb  –  core/network/dns_resolver.py
#  Alan adını IP adresine çevirir.
#  Önbellekleme, DoH desteği ve TTL yönetimi içerir.
# ─────────────────────────────────────────────────────────────
import socket
import time
import threading
from typing import Optional


class DNSCache:
    """Thread-safe in-memory DNS önbelleği."""

    def __init__(self, ttl: int = 300):
        self._store: dict[str, tuple[str, float]] = {}   # host -> (ip, expire_time)
        self._lock  = threading.Lock()
        self.ttl    = ttl

    def get(self, host: str) -> Optional[str]:
        with self._lock:
            entry = self._store.get(host)
            if entry and time.time() < entry[1]:
                return entry[0]
            if entry:
                del self._store[host]   # expire
        return None

    def set(self, host: str, ip: str) -> None:
        with self._lock:
            self._store[host] = (ip, time.time() + self.ttl)

    def invalidate(self, host: str) -> None:
        with self._lock:
            self._store.pop(host, None)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()

    @property
    def size(self) -> int:
        return len(self._store)


class DNSResolver:
    """
    Alan adını IP adresine çeviren DNS çözümleyici.

    Önce önbelleğe bakar; bulamazsa sistem DNS'ini kullanır.
    İleride DoH (DNS over HTTPS) desteği için DoH metodu iskelet halinde hazır.
    """

    def __init__(self, use_cache: bool = True, cache_ttl: int = 300):
        self.use_cache = use_cache
        self.cache     = DNSCache(ttl=cache_ttl) if use_cache else None
        self._stats    = {"hits": 0, "misses": 0, "errors": 0}

    # ── Temel çözümleme ───────────────────────
    def resolve(self, host: str, timeout: float = 3.0) -> Optional[str]:
        """
        Verilen host için IPv4 adresi döndürür.
        Başarısız olursa None döner.
        """
        # 1. IP adresi ise doğrudan döndür
        if self._is_ip(host):
            return host

        # 2. Önbellekten bak
        if self.use_cache and self.cache:
            cached = self.cache.get(host)
            if cached:
                self._stats["hits"] += 1
                return cached

        # 3. Sistem DNS'i ile çöz
        try:
            old_timeout = socket.getdefaulttimeout()
            socket.setdefaulttimeout(timeout)
            ip = socket.gethostbyname(host)
            socket.setdefaulttimeout(old_timeout)

            if self.use_cache and self.cache:
                self.cache.set(host, ip)

            self._stats["misses"] += 1
            return ip

        except (socket.gaierror, socket.herror, OSError):
            self._stats["errors"] += 1
            return None

    def resolve_all(self, host: str) -> list[str]:
        """
        Bir host için tüm IP adreslerini döndürür (IPv4 + IPv6).
        """
        try:
            infos = socket.getaddrinfo(host, None)
            return list({info[4][0] for info in infos})
        except OSError:
            return []

    # ── DoH (DNS over HTTPS) ── iskelet ───────
    def resolve_doh(self, host: str,
                    doh_server: str = "https://cloudflare-dns.com/dns-query",
                    timeout: float = 4.0) -> Optional[str]:
        """
        Cloudflare veya Google DoH sunucusu üzerinden DNS çözümler.
        PyQt6 QNetworkAccessManager ile entegrasyon için genişletilebilir.
        Şimdilik basit HTTPS GET ile çalışır.
        """
        import urllib.request
        import json

        url = f"{doh_server}?name={host}&type=A"
        headers = {
            "Accept": "application/dns-json",
            "User-Agent": "PyWeb/1.0",
        }
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read())
                answers = data.get("Answer", [])
                for answer in answers:
                    if answer.get("type") == 1:   # A record
                        ip = answer.get("data", "")
                        if ip and self._is_ip(ip):
                            if self.use_cache and self.cache:
                                ttl = answer.get("TTL", 300)
                                self.cache._store[host] = (ip, time.time() + ttl)
                            return ip
        except Exception:
            pass
        return None

    # ── Yardımcı ──────────────────────────────
    @staticmethod
    def _is_ip(host: str) -> bool:
        """IPv4 veya IPv6 adresi mi?"""
        try:
            socket.inet_pton(socket.AF_INET, host)
            return True
        except OSError:
            pass
        try:
            socket.inet_pton(socket.AF_INET6, host)
            return True
        except OSError:
            return False

    def is_reachable(self, host: str, port: int = 80, timeout: float = 2.0) -> bool:
        """TCP bağlantısı kurulabiliyor mu?"""
        try:
            ip = self.resolve(host)
            if not ip:
                return False
            s = socket.create_connection((ip, port), timeout=timeout)
            s.close()
            return True
        except OSError:
            return False

    @property
    def stats(self) -> dict:
        return dict(self._stats)
