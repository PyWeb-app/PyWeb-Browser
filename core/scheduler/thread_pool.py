# ─────────────────────────────────────────────────────────────
#  PyWeb  –  core/scheduler/thread_pool.py
#  Ağ yüklemeleri ve ağır işleri arka planda yapan
#  iş parçacığı havuzu. UI'ın donmasını engeller.
# ─────────────────────────────────────────────────────────────
from __future__ import annotations
import threading
import queue
import time
from typing import Callable, Optional, Any
from PyQt6.QtCore import QObject, QThread, pyqtSignal


# ─────────────────────────────────────────────
# Çalışan iş parçacığı
# ─────────────────────────────────────────────
class _Worker(QThread):
    """
    Görev kuyruğundan iş çeker ve çalıştırır.
    Sonucu Qt sinyali ile ana iş parçacığına iletir.
    """
    task_done  = pyqtSignal(object, object)   # (task_id, result)
    task_error = pyqtSignal(object, str)      # (task_id, error_msg)

    def __init__(self, task_queue: queue.Queue,
                 parent: Optional[QObject] = None):
        super().__init__(parent)
        self._q       = task_queue
        self._running = True

    def run(self) -> None:
        while self._running:
            try:
                item = self._q.get(timeout=0.2)
            except queue.Empty:
                continue
            task_id, fn, args, kwargs = item
            try:
                result = fn(*args, **kwargs)
                self.task_done.emit(task_id, result)
            except Exception as e:
                self.task_error.emit(task_id, str(e))
            finally:
                self._q.task_done()

    def stop(self) -> None:
        self._running = False


# ─────────────────────────────────────────────
# Görev kaydı
# ─────────────────────────────────────────────
class TaskRecord:
    """Bir arka plan görevinin durumunu izler."""
    __slots__ = ("task_id","submitted_at","done","result","error","callback")

    def __init__(self, task_id: Any, callback: Optional[Callable]):
        self.task_id      = task_id
        self.submitted_at = time.monotonic()
        self.done         = False
        self.result       = None
        self.error:  Optional[str] = None
        self.callback     = callback

    @property
    def elapsed_ms(self) -> float:
        return (time.monotonic() - self.submitted_at) * 1000


# ─────────────────────────────────────────────
# İş parçacığı havuzu
# ─────────────────────────────────────────────
class ThreadPool(QObject):
    """
    Sabit boyutlu iş parçacığı havuzu.

    Kullanım:
        pool = ThreadPool(max_workers=4)
        pool.start()
        tid = pool.submit(requests.get, "https://...",
                          callback=lambda r: print(r.status_code))
    """

    all_done = pyqtSignal()   # Tüm bekleyen görevler bitti

    def __init__(self, max_workers: int = 4,
                 parent: Optional[QObject] = None):
        super().__init__(parent)
        self._max     = max_workers
        self._q: queue.Queue = queue.Queue()
        self._workers: list[_Worker] = []
        self._tasks:  dict[Any, TaskRecord] = {}
        self._counter = 0
        self._lock    = threading.Lock()

    # ── Havuz kontrolü ───────────────────────
    def start(self) -> None:
        for _ in range(self._max):
            w = _Worker(self._q, self)
            w.task_done.connect(self._on_done)
            w.task_error.connect(self._on_error)
            w.start()
            self._workers.append(w)

    def stop(self, wait: bool = True) -> None:
        for w in self._workers:
            w.stop()
        if wait:
            for w in self._workers:
                w.wait(2000)
        self._workers.clear()

    # ── Görev gönderme ────────────────────────
    def submit(self, fn: Callable,
               *args,
               callback: Optional[Callable[[Any], None]] = None,
               error_cb: Optional[Callable[[str], None]] = None,
               **kwargs) -> Any:
        """
        fn'i arka planda çalıştırır.
        callback: başarı durumunda result ile çağrılır
        error_cb: hata durumunda mesaj ile çağrılır
        Döndürür: task_id
        """
        with self._lock:
            self._counter += 1
            task_id = self._counter

        record = TaskRecord(task_id, callback)
        record.error_cb = error_cb   # type: ignore
        with self._lock:
            self._tasks[task_id] = record

        self._q.put((task_id, fn, args, kwargs))
        return task_id

    def cancel(self, task_id: Any) -> bool:
        """
        Görevi iptal etmeye çalışır.
        Zaten başlamışsa iptal edilemez; False döner.
        """
        with self._lock:
            rec = self._tasks.get(task_id)
            if rec and not rec.done:
                rec.callback = None
                return True
        return False

    # ── Sinyal işleyiciler ────────────────────
    def _on_done(self, task_id: Any, result: Any) -> None:
        with self._lock:
            rec = self._tasks.pop(task_id, None)
        if rec:
            rec.done   = True
            rec.result = result
            if rec.callback:
                try:
                    rec.callback(result)
                except Exception:
                    pass
        if self._q.empty() and not self._tasks:
            self.all_done.emit()

    def _on_error(self, task_id: Any, error_msg: str) -> None:
        with self._lock:
            rec = self._tasks.pop(task_id, None)
        if rec:
            rec.done  = True
            rec.error = error_msg
            cb = getattr(rec, "error_cb", None)
            if cb:
                try:
                    cb(error_msg)
                except Exception:
                    pass

    # ── Durum bilgisi ─────────────────────────
    @property
    def pending_count(self) -> int:
        return self._q.qsize()

    @property
    def worker_count(self) -> int:
        return len(self._workers)

    def is_idle(self) -> bool:
        return self._q.empty() and not self._tasks
