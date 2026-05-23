# ─────────────────────────────────────────────────────────────
#  PyWeb  –  core/scheduler/event_loop.py
#  JS görevleri ve UI olaylarını sıraya koyan olay döngüsü.
#  Qt'nin kendi olay döngüsüyle entegre çalışır.
# ─────────────────────────────────────────────────────────────
from __future__ import annotations
import time
import heapq
from typing import Callable, Optional
from PyQt6.QtCore import QObject, QTimer, pyqtSignal


class ScheduledTask:
    """Tek bir zamanlanmış görev."""
    __slots__ = ("run_at", "callback", "repeat_ms", "_id")
    _counter = 0

    def __init__(self, callback: Callable, run_at: float,
                 repeat_ms: int = 0):
        ScheduledTask._counter += 1
        self._id       = ScheduledTask._counter
        self.callback  = callback
        self.run_at    = run_at
        self.repeat_ms = repeat_ms   # 0 = tek seferlik

    def __lt__(self, other: "ScheduledTask") -> bool:
        return self.run_at < other.run_at

    def __repr__(self) -> str:
        return f"Task(id={self._id}, at={self.run_at:.2f})"


class EventLoop(QObject):
    """
    Tarayıcı olay döngüsü.
    - Zamanlayıcı tabanlı görev kuyruğu (min-heap)
    - setTimeout / setInterval benzeri API
    - Qt sinyal entegrasyonu
    - Görev iptali
    """

    tick = pyqtSignal()    # Her döngü adımında yayınlanır

    def __init__(self, interval_ms: int = 16, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._heap:    list[ScheduledTask]   = []
        self._cancelled: set[int]            = set()
        self._running  = False

        self._qt_timer = QTimer(self)
        self._qt_timer.setInterval(interval_ms)
        self._qt_timer.timeout.connect(self._process)

    # ── Döngü kontrolü ───────────────────────
    def start(self) -> None:
        if not self._running:
            self._running = True
            self._qt_timer.start()

    def stop(self) -> None:
        self._running = False
        self._qt_timer.stop()

    # ── Görev zamanlama ───────────────────────
    def set_timeout(self, callback: Callable,
                    delay_ms: int = 0) -> int:
        """delay_ms sonra callback'i bir kez çalıştırır."""
        run_at = time.monotonic() + delay_ms / 1000.0
        task   = ScheduledTask(callback, run_at, repeat_ms=0)
        heapq.heappush(self._heap, task)
        return task._id

    def set_interval(self, callback: Callable,
                     interval_ms: int) -> int:
        """Her interval_ms'de bir callback'i çalıştırır."""
        run_at = time.monotonic() + interval_ms / 1000.0
        task   = ScheduledTask(callback, run_at, repeat_ms=interval_ms)
        heapq.heappush(self._heap, task)
        return task._id

    def clear(self, task_id: int) -> None:
        """Zamanlanmış görevi iptal eder."""
        self._cancelled.add(task_id)

    def post(self, callback: Callable) -> int:
        """Görevi hemen (sonraki tick'te) çalıştırır."""
        return self.set_timeout(callback, delay_ms=0)

    # ── Döngü adımı ──────────────────────────
    def _process(self) -> None:
        now = time.monotonic()
        while self._heap and self._heap[0].run_at <= now:
            task = heapq.heappop(self._heap)
            if task._id in self._cancelled:
                self._cancelled.discard(task._id)
                continue
            try:
                task.callback()
            except Exception:
                pass
            # Tekrarlı görev: yeniden kuyruğa ekle
            if task.repeat_ms > 0 and task._id not in self._cancelled:
                task.run_at = now + task.repeat_ms / 1000.0
                heapq.heappush(self._heap, task)
        self.tick.emit()

    @property
    def pending_count(self) -> int:
        return len(self._heap)
