# ─────────────────────────────────────────────────────────────
#  PyWeb  –  core/network/http_client.py
#  Ham TCP/TLS üzerinden HTTP/1.1 istek ve yanıt yönetimi.
#  QtWebEngine'in kullandığı chromium ağ katmanından bağımsız;
#  dahili sayfa yüklemeleri ve özel protokol istekleri için.
# ─────────────────────────────────────────────────────────────
import socket
import ssl
import gzip
import zlib
import time
import re
from typing import Optional
from dataclasses import dataclass, field


@dataclass
class HttpResponse:
    """Bir HTTP yanıtını temsil eder."""
    status_code: int            = 0
    reason:      str            = ""
    headers:     dict           = field(default_factory=dict)
    body:        bytes          = b""
    url:         str            = ""
    elapsed_ms:  float          = 0.0
    error:       Optional[str]  = None

    @property
    def ok(self) -> bool:
        return 200 <= self.status_code < 300

    @property
    def text(self) -> str:
        charset = self._charset()
        return self.body.decode(charset, errors="replace")

    def _charset(self) -> str:
        ct = self.headers.get("content-type", "")
        m  = re.search(r"charset=([^\s;]+)", ct, re.IGNORECASE)
        return m.group(1) if m else "utf-8"

    @property
    def content_type(self) -> str:
        return self.headers.get("content-type","").split(";")[0].strip()

    def header(self, name: str) -> str:
        return self.headers.get(name.lower(), "")


class HttpClient:
    """
    Hafif, bağımlılıksız HTTP/1.1 istemcisi.
    Sadece GET/HEAD/POST destekler.
    Yeniden yönlendirme (redirect), sıkıştırma (gzip/deflate),
    chunked transfer encoding desteklenir.
    """

    DEFAULT_HEADERS = {
        "User-Agent": "PyWeb/1.0",
        "Accept":     "text/html,application/xhtml+xml,*/*;q=0.8",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "close",
    }
    MAX_REDIRECTS = 8
    BUFFER        = 4096

    def __init__(self, timeout: float = 10.0, verify_tls: bool = True):
        self.timeout    = timeout
        self.verify_tls = verify_tls

    # ── Genel istek metodu ────────────────────
    def request(self, method: str, url: str,
                headers: Optional[dict] = None,
                body: Optional[bytes]   = None,
                follow_redirects: bool  = True) -> HttpResponse:
        method  = method.upper()
        redirects = 0
        current_url = url

        while redirects <= self.MAX_REDIRECTS:
            resp = self._do_request(method, current_url, headers, body)
            if resp.error:
                return resp

            if follow_redirects and resp.status_code in (301,302,303,307,308):
                location = resp.header("location")
                if not location:
                    break
                current_url = self._resolve_redirect(current_url, location)
                # 303 → GET
                if resp.status_code == 303:
                    method = "GET"; body = None
                redirects += 1
                continue
            break

        return resp

    def get(self, url: str, **kw)  -> HttpResponse:
        return self.request("GET",  url, **kw)

    def head(self, url: str, **kw) -> HttpResponse:
        return self.request("HEAD", url, **kw)

    def post(self, url: str, body: bytes, content_type: str = "application/x-www-form-urlencoded",
             **kw) -> HttpResponse:
        h = (kw.pop("headers", None) or {})
        h["Content-Type"]   = content_type
        h["Content-Length"] = str(len(body))
        return self.request("POST", url, headers=h, body=body, **kw)

    # ── Tek istek ─────────────────────────────
    def _do_request(self, method: str, url: str,
                    extra_headers: Optional[dict],
                    body: Optional[bytes]) -> HttpResponse:
        t0 = time.monotonic()
        try:
            scheme, host, port, path = self._parse_url(url)
        except ValueError as e:
            return HttpResponse(error=str(e), url=url)

        # Başlıklar
        hdrs = dict(self.DEFAULT_HEADERS)
        hdrs["Host"] = host
        if extra_headers:
            hdrs.update(extra_headers)

        # İstek satırı
        req_line = f"{method} {path} HTTP/1.1\r\n"
        req_line += "".join(f"{k}: {v}\r\n" for k, v in hdrs.items())
        req_line += "\r\n"
        raw_req  = req_line.encode("latin-1")
        if body:
            raw_req += body

        # Soket
        try:
            sock = socket.create_connection((host, port), timeout=self.timeout)
            if scheme == "https":
                ctx = self._tls_context()
                sock = ctx.wrap_socket(sock, server_hostname=host)

            sock.sendall(raw_req)
            raw_resp = self._recv_all(sock)
            sock.close()
        except ssl.SSLError as e:
            return HttpResponse(error=f"TLS error: {e}", url=url)
        except (socket.timeout, ConnectionRefusedError, OSError) as e:
            return HttpResponse(error=f"Connection error: {e}", url=url)

        elapsed = (time.monotonic() - t0) * 1000
        return self._parse_response(raw_resp, url, elapsed)

    # ── Yanıt ayrıştırma ─────────────────────
    def _parse_response(self, raw: bytes, url: str, elapsed: float) -> HttpResponse:
        if not raw:
            return HttpResponse(error="Empty response", url=url, elapsed_ms=elapsed)

        # Başlık / gövde ayırımı
        sep = raw.find(b"\r\n\r\n")
        if sep < 0:
            return HttpResponse(error="Malformed response", url=url, elapsed_ms=elapsed)

        header_bytes = raw[:sep]
        body         = raw[sep+4:]

        lines = header_bytes.split(b"\r\n")
        status_line = lines[0].decode("latin-1", errors="replace")

        m = re.match(r"HTTP/[\d.]+ (\d+)\s*(.*)", status_line)
        if not m:
            return HttpResponse(error="Bad status line", url=url, elapsed_ms=elapsed)

        status_code = int(m.group(1))
        reason      = m.group(2).strip()

        headers = {}
        for line in lines[1:]:
            if b":" in line:
                k, _, v = line.partition(b":")
                headers[k.strip().decode("latin-1").lower()] = v.strip().decode("latin-1")

        # Chunked transfer
        if headers.get("transfer-encoding","").lower() == "chunked":
            body = self._decode_chunked(body)

        # Sıkıştırma
        enc = headers.get("content-encoding","").lower()
        try:
            if enc == "gzip":
                body = gzip.decompress(body)
            elif enc in ("deflate","zlib"):
                body = zlib.decompress(body)
        except Exception:
            pass

        return HttpResponse(
            status_code = status_code,
            reason      = reason,
            headers     = headers,
            body        = body,
            url         = url,
            elapsed_ms  = elapsed,
        )

    # ── Chunked decode ────────────────────────
    @staticmethod
    def _decode_chunked(data: bytes) -> bytes:
        out = bytearray()
        i   = 0
        while i < len(data):
            end = data.find(b"\r\n", i)
            if end < 0:
                break
            try:
                size = int(data[i:end], 16)
            except ValueError:
                break
            if size == 0:
                break
            i   = end + 2
            out += data[i:i+size]
            i  += size + 2
        return bytes(out)

    # ── Alım ─────────────────────────────────
    def _recv_all(self, sock: socket.socket) -> bytes:
        parts = []
        while True:
            try:
                chunk = sock.recv(self.BUFFER)
                if not chunk:
                    break
                parts.append(chunk)
            except socket.timeout:
                break
        return b"".join(parts)

    # ── URL ayrıştırma ────────────────────────
    @staticmethod
    def _parse_url(url: str) -> tuple:
        m = re.match(r"(https?)://([^/:]+)(?::(\d+))?(/.*)?$", url, re.IGNORECASE)
        if not m:
            raise ValueError(f"Cannot parse URL: {url}")
        scheme = m.group(1).lower()
        host   = m.group(2)
        port   = int(m.group(3)) if m.group(3) else (443 if scheme=="https" else 80)
        path   = m.group(4) or "/"
        return scheme, host, port, path

    @staticmethod
    def _resolve_redirect(base: str, location: str) -> str:
        if location.startswith("http"):
            return location
        m = re.match(r"(https?://[^/]+)", base)
        if m:
            return m.group(1) + ("/" if not location.startswith("/") else "") + location
        return location

    def _tls_context(self) -> ssl.SSLContext:
        if self.verify_tls:
            return ssl.create_default_context()
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.check_hostname = False
        ctx.verify_mode    = ssl.CERT_NONE
        return ctx
