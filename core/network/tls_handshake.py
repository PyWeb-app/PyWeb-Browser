# ─────────────────────────────────────────────────────────────
#  PyWeb  –  core/network/tls_handshake.py
#  HTTPS bağlantıları için TLS/SSL katmanı.
#  Sertifika doğrulama, SNI, protokol müzakeresi yönetir.
# ─────────────────────────────────────────────────────────────
import ssl
import socket
import datetime
from typing import Optional
from dataclasses import dataclass, field


@dataclass
class CertInfo:
    """Sunucu sertifikasından çekilen bilgiler."""
    subject:     str  = ""
    issuer:      str  = ""
    not_before:  str  = ""
    not_after:   str  = ""
    san:         list = field(default_factory=list)   # Subject Alternative Names
    is_valid:    bool = False
    error:       str  = ""

    @property
    def is_expired(self) -> bool:
        try:
            exp = datetime.datetime.strptime(self.not_after, "%b %d %H:%M:%S %Y %Z")
            return exp < datetime.datetime.utcnow()
        except ValueError:
            return False

    @property
    def days_remaining(self) -> int:
        try:
            exp = datetime.datetime.strptime(self.not_after, "%b %d %H:%M:%S %Y %Z")
            delta = exp - datetime.datetime.utcnow()
            return max(0, delta.days)
        except ValueError:
            return 0


class TLSHandshake:
    """
    Bir host ile TLS el sıkışması (handshake) gerçekleştirir.
    Sertifika bilgisini çeker ve doğrular.
    PyWebEngineView HTTPS'i zaten yönettiği için bu sınıf
    ek güvenlik kontrolü ve bilgi gösterimi içindir.
    """

    # Desteklenen minimum TLS sürümü
    MIN_PROTOCOL = ssl.TLSVersion.TLSv1_2

    def __init__(self, verify: bool = True, timeout: float = 5.0):
        self.verify  = verify
        self.timeout = timeout

    # ── Bağlantı ve sertifika çekme ───────────
    def get_cert_info(self, host: str, port: int = 443) -> CertInfo:
        """
        Sunucunun TLS sertifikasını çeker ve ayrıştırır.
        """
        ctx = self._build_context()
        try:
            raw = socket.create_connection((host, port), timeout=self.timeout)
            tls = ctx.wrap_socket(raw, server_hostname=host)
            cert_dict = tls.getpeercert()
            tls.close(); raw.close()
            return self._parse_cert(cert_dict)

        except ssl.SSLCertVerificationError as e:
            return CertInfo(is_valid=False, error=f"Cert verification failed: {e.reason}")
        except ssl.SSLError as e:
            return CertInfo(is_valid=False, error=f"SSL error: {e}")
        except (socket.timeout, ConnectionRefusedError, OSError) as e:
            return CertInfo(is_valid=False, error=f"Connection error: {e}")

    def handshake_info(self, host: str, port: int = 443) -> dict:
        """
        Tam TLS el sıkışma bilgisini döndürür:
        protokol sürümü, cipher suite, sertifika.
        """
        ctx = self._build_context()
        result = {
            "host": host, "port": port,
            "tls_version": None, "cipher": None,
            "cert": None, "error": None,
        }
        try:
            raw = socket.create_connection((host, port), timeout=self.timeout)
            tls = ctx.wrap_socket(raw, server_hostname=host)
            result["tls_version"] = tls.version()
            result["cipher"]      = tls.cipher()
            result["cert"]        = self._parse_cert(tls.getpeercert())
            tls.close(); raw.close()
        except ssl.SSLError as e:
            result["error"] = str(e)
        except OSError as e:
            result["error"] = str(e)
        return result

    # ── Context oluşturma ─────────────────────
    def _build_context(self) -> ssl.SSLContext:
        if self.verify:
            ctx = ssl.create_default_context()
        else:
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            ctx.check_hostname = False
            ctx.verify_mode    = ssl.CERT_NONE

        try:
            ctx.minimum_version = self.MIN_PROTOCOL
        except AttributeError:
            pass
        return ctx

    # ── Sertifika ayrıştırma ─────────────────
    @staticmethod
    def _parse_cert(cert: dict) -> CertInfo:
        def _dn(tuples) -> str:
            """((key,val),...) → "CN=..., O=..."  biçimine çevirir."""
            if not tuples:
                return ""
            parts = []
            for pair in tuples:
                for k, v in pair:
                    parts.append(f"{k}={v}")
            return ", ".join(parts)

        subject    = _dn(cert.get("subject", ()))
        issuer     = _dn(cert.get("issuer", ()))
        not_before = cert.get("notBefore", "")
        not_after  = cert.get("notAfter",  "")

        # Subject Alternative Names
        san = []
        for kind, val in cert.get("subjectAltName", ()):
            san.append(f"{kind}:{val}")

        return CertInfo(
            subject    = subject,
            issuer     = issuer,
            not_before = not_before,
            not_after  = not_after,
            san        = san,
            is_valid   = True,
        )

    # ── HSTS kontrolü ─────────────────────────
    @staticmethod
    def check_hsts(headers: dict) -> bool:
        """
        HTTP yanıt başlıklarından HSTS direktifi var mı diye bakar.
        headers: {'Strict-Transport-Security': 'max-age=...'} formatında.
        """
        key = next((k for k in headers if k.lower() == "strict-transport-security"), None)
        return key is not None

    # ── Sertifika parmak izi ─────────────────
    @staticmethod
    def fingerprint(cert_der: bytes, algo: str = "sha256") -> str:
        """DER formatındaki sertifikanın parmak izini üretir."""
        import hashlib
        h = hashlib.new(algo, cert_der).hexdigest()
        return ":".join(h[i:i+2] for i in range(0, len(h), 2)).upper()
