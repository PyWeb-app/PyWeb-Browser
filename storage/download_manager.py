# ─────────────────────────────────────────────────────────────
#  PyWeb  –  storage/download_manager.py
#  Dosya indirmelerini yöneten modül.
#  Kuyruk, ilerleme takibi, duraklat/devam et, geçmiş.
# ─────────────────────────────────────────────────────────────
from __future__ import annotations
import os
import json
import time
import datetime
from enum import Enum, auto
from typing import Optional, Callable
from dataclasses import dataclass, field
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWebEngineCore import QWebEngineDownloadRequest

DATA_DIR      = os.path.join(os.path.expanduser("~"), ".pyweb")
DOWNLOADS_DIR = os.path.join(os.path.expanduser("~"), "Downloads")
DL_LOG_FILE   = os.path.join(DATA_DIR, "downloads.json")


class DLStatus(Enum):
    BEKLIYOR   = auto()
    INDIRILIYOR = auto()
    TAMAMLANDI = auto()
    HATA       = auto()
    IPTAL      = auto()
    DURAKLATILDI = auto()


@dataclass
class DownloadItem:
    filename:     str
    url:          str
    save_path:    str
    status:       DLStatus = DLStatus.BEKLIYOR
    total_bytes:  int      = 0
    recv_bytes:   int      = 0
    started_at:   float    = field(default_factory=time.time)
    finished_at:  float    = 0.0
    error_msg:    str      = ""

    # Qt download nesnesi (serileştirilmez)
    _qt_item: Optional[QWebEngineDownloadRequest] = field(
        default=None, repr=False, compare=False
    )

    @property
    def progress(self) -> int:
        if self.total_bytes <= 0:
            return 0
        return min(100, int(self.recv_bytes / self.total_bytes * 100))

    @property
    def speed_bps(self) -> float:
        elapsed = time.time() - self.started_at
        if elapsed <= 0 or self.recv_bytes <= 0:
            return 0.0
        return self.recv_bytes / elapsed

    @property
    def eta_sec(self) -> float:
        remaining = self.total_bytes - self.recv_bytes
        speed = self.speed_bps
        if speed <= 0 or remaining <= 0:
            return 0.0
        return remaining / speed

    @property
    def size_str(self) -> str:
        def fmt(b: int) -> str:
            if b < 1024:       return f"{b} B"
            if b < 1024**2:    return f"{b/1024:.1f} KB"
            if b < 1024**3:    return f"{b/1024**2:.1f} MB"
            return f"{b/1024**3:.2f} GB"
        if self.total_bytes:
            return f"{fmt(self.recv_bytes)} / {fmt(self.total_bytes)}"
        return fmt(self.recv_bytes)

    @property
    def speed_str(self) -> str:
        s = self.speed_bps
        if s < 1024:       return f"{s:.0f} B/sn"
        if s < 1024**2:    return f"{s/1024:.0f} KB/sn"
        return f"{s/1024**2:.1f} MB/sn"

    def to_log_dict(self) -> dict:
        return {
            "filename":    self.filename,
            "url":         self.url,
            "save_path":   self.save_path,
            "status":      self.status.name,
            "total_bytes": self.total_bytes,
            "recv_bytes":  self.recv_bytes,
            "started_at":  datetime.datetime.fromtimestamp(self.started_at).strftime("%Y-%m-%d %H:%M"),
            "finished_at": datetime.datetime.fromtimestamp(self.finished_at).strftime("%Y-%m-%d %H:%M") if self.finished_at else "",
            "error_msg":   self.error_msg,
        }


class DownloadManager(QObject):
    """
    Tüm indirme işlemlerini merkezi olarak yönetir.
    Qt sinyalleri ile UI güncellemelerini tetikler.
    """

    # Sinyaller
    download_started    = pyqtSignal(str)   # filename
    download_progress   = pyqtSignal(str, int, str, str)  # filename, %, size_str, speed_str
    download_finished   = pyqtSignal(str)   # filename
    download_error      = pyqtSignal(str, str)   # filename, error
    download_cancelled  = pyqtSignal(str)   # filename

    def __init__(self, default_dir: str = DOWNLOADS_DIR,
                 parent: Optional[QObject] = None):
        super().__init__(parent)
        self.default_dir = default_dir
        os.makedirs(default_dir, exist_ok=True)
        self._active:  dict[str, DownloadItem] = {}   # filename -> item
        self._history: list[DownloadItem]      = []
        self._load_log()

    # ── Yeni indirme başlatma ─────────────────
    def handle(self, qt_item: QWebEngineDownloadRequest,
               save_path: Optional[str] = None) -> DownloadItem:
        """
        QWebEngineDownloadRequest'i alır, kayıt oluşturur,
        Qt sinyallerine bağlanır.
        """
        filename  = qt_item.suggestedFileName()
        save_path = save_path or os.path.join(self.default_dir, filename)

        qt_item.setDownloadDirectory(os.path.dirname(save_path))
        qt_item.setDownloadFileName(os.path.basename(save_path))
        qt_item.accept()

        item = DownloadItem(
            filename  = filename,
            url       = qt_item.url().toString(),
            save_path = save_path,
            status    = DLStatus.INDIRILIYOR,
            _qt_item  = qt_item,
        )
        self._active[filename] = item

        # İlerleme bağlantıları
        qt_item.receivedBytesChanged.connect(
            lambda: self._on_progress(item, qt_item)
        )
        qt_item.isFinishedChanged.connect(
            lambda: self._on_finished(item, qt_item)
        )

        self.download_started.emit(filename)
        return item

    # ── İlerleme güncellemesi ─────────────────
    def _on_progress(self, item: DownloadItem,
                     qt: QWebEngineDownloadRequest) -> None:
        item.recv_bytes  = qt.receivedBytes()
        item.total_bytes = qt.totalBytes()
        self.download_progress.emit(
            item.filename, item.progress,
            item.size_str, item.speed_str
        )

    def _on_finished(self, item: DownloadItem,
                     qt: QWebEngineDownloadRequest) -> None:
        if not qt.isFinished():
            return
        item.finished_at = time.time()
        item.recv_bytes  = qt.receivedBytes()
        item.total_bytes = qt.totalBytes()

        state = qt.state()
        from PyQt6.QtWebEngineCore import QWebEngineDownloadRequest as _DL
        if state == _DL.DownloadState.DownloadCompleted:
            item.status = DLStatus.TAMAMLANDI
            self.download_finished.emit(item.filename)
        elif state == _DL.DownloadState.DownloadCancelled:
            item.status = DLStatus.IPTAL
            self.download_cancelled.emit(item.filename)
        else:
            item.status   = DLStatus.HATA
            item.error_msg = "İndirme başarısız"
            self.download_error.emit(item.filename, item.error_msg)

        self._active.pop(item.filename, None)
        self._history.insert(0, item)
        if len(self._history) > 500:
            self._history = self._history[:500]
        self._save_log()

    # ── Kontrol ───────────────────────────────
    def cancel(self, filename: str) -> bool:
        item = self._active.get(filename)
        if item and item._qt_item:
            item._qt_item.cancel()
            return True
        return False

    def pause(self, filename: str) -> bool:
        item = self._active.get(filename)
        if item and item._qt_item:
            try:
                item._qt_item.pause()
                item.status = DLStatus.DURAKLATILDI
                return True
            except Exception:
                pass
        return False

    def resume(self, filename: str) -> bool:
        item = self._active.get(filename)
        if item and item._qt_item:
            try:
                item._qt_item.resume()
                item.status = DLStatus.INDIRILIYOR
                return True
            except Exception:
                pass
        return False

    def open_file(self, filename: str) -> bool:
        item = next((i for i in self._history if i.filename == filename), None)
        if item and os.path.exists(item.save_path):
            import subprocess, sys
            if sys.platform == "win32":
                os.startfile(item.save_path)
            elif sys.platform == "darwin":
                subprocess.run(["open", item.save_path])
            else:
                subprocess.run(["xdg-open", item.save_path])
            return True
        return False

    def open_folder(self, filename: str) -> bool:
        item = next((i for i in self._history if i.filename == filename), None)
        if item:
            folder = os.path.dirname(item.save_path)
            if os.path.exists(folder):
                import subprocess, sys
                if sys.platform == "win32":
                    subprocess.run(["explorer", folder])
                elif sys.platform == "darwin":
                    subprocess.run(["open", folder])
                else:
                    subprocess.run(["xdg-open", folder])
                return True
        return False

    # ── Sorgulama ─────────────────────────────
    @property
    def active(self) -> list[DownloadItem]:
        return list(self._active.values())

    @property
    def history(self) -> list[DownloadItem]:
        return list(self._history)

    def clear_history(self) -> None:
        self._history = [i for i in self._history
                         if i.status == DLStatus.INDIRILIYOR]
        self._save_log()

    # ── Kayıt ─────────────────────────────────
    def _load_log(self) -> None:
        try:
            if os.path.exists(DL_LOG_FILE):
                with open(DL_LOG_FILE, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                for r in raw[:200]:
                    try:
                        r["status"]  = DLStatus[r.get("status", "TAMAMLANDI")]
                        self._history.append(DownloadItem(**{
                            k: v for k, v in r.items()
                            if k in DownloadItem.__dataclass_fields__
                        }))
                    except Exception:
                        pass
        except Exception:
            pass

    def _save_log(self) -> None:
        try:
            data = [i.to_log_dict() for i in self._history[:200]]
            with open(DL_LOG_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
