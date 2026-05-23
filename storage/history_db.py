# ─────────────────────────────────────────────────────────────
#  PyWeb  –  storage/history_db.py
#  Gezinme geçmişini JSON dosyasında saklar.
#  Sorgulama, arama, silme ve dışa aktarma destekler.
# ─────────────────────────────────────────────────────────────
from __future__ import annotations
import json
import os
import datetime
from typing import Optional
from dataclasses import dataclass, field, asdict

DATA_DIR = os.path.join(os.path.expanduser("~"), ".pyweb")
os.makedirs(DATA_DIR, exist_ok=True)
HISTORY_FILE = os.path.join(DATA_DIR, "history.json")


@dataclass
class HistoryEntry:
    url:       str
    title:     str   = ""
    date:      str   = ""           # "2025-05-17"
    time_str:  str   = ""           # "14:32"
    visit_count: int = 1
    favicon:   str   = ""

    def __post_init__(self):
        if not self.date:
            now = datetime.datetime.now()
            self.date     = now.strftime("%Y-%m-%d")
            self.time_str = now.strftime("%H:%M")


class HistoryDB:
    """
    Gezinme geçmişi veritabanı.
    Maksimum 5000 kayıt tutar; eskiler silinir.
    """

    MAX_ENTRIES = 5000

    def __init__(self, path: str = HISTORY_FILE):
        self._path    = path
        self._entries: list[HistoryEntry] = []
        self._load()

    # ── CRUD ─────────────────────────────────
    def add(self, url: str, title: str = "") -> None:
        if not url or url.startswith("pyweb://"):
            return
        # Aynı URL varsa ziyaret sayısını artır
        for entry in self._entries:
            if entry.url == url:
                entry.visit_count += 1
                entry.title = title or entry.title
                now = datetime.datetime.now()
                entry.date     = now.strftime("%Y-%m-%d")
                entry.time_str = now.strftime("%H:%M")
                self._save()
                return
        new_entry = HistoryEntry(url=url, title=title or url)
        self._entries.insert(0, new_entry)
        if len(self._entries) > self.MAX_ENTRIES:
            self._entries = self._entries[:self.MAX_ENTRIES]
        self._save()

    def delete(self, url: str) -> bool:
        before = len(self._entries)
        self._entries = [e for e in self._entries if e.url != url]
        if len(self._entries) < before:
            self._save()
            return True
        return False

    def delete_at(self, index: int) -> bool:
        if 0 <= index < len(self._entries):
            self._entries.pop(index)
            self._save()
            return True
        return False

    def clear(self) -> None:
        self._entries.clear()
        self._save()

    def clear_today(self) -> None:
        today = datetime.date.today().isoformat()
        self._entries = [e for e in self._entries if e.date != today]
        self._save()

    # ── Sorgulama ─────────────────────────────
    def all(self) -> list[HistoryEntry]:
        return list(self._entries)

    def search(self, query: str) -> list[HistoryEntry]:
        q = query.lower()
        return [e for e in self._entries
                if q in e.url.lower() or q in e.title.lower()]

    def recent(self, n: int = 50) -> list[HistoryEntry]:
        return self._entries[:n]

    def by_date(self, date_str: str) -> list[HistoryEntry]:
        return [e for e in self._entries if e.date == date_str]

    def most_visited(self, n: int = 10) -> list[HistoryEntry]:
        return sorted(self._entries, key=lambda e: e.visit_count, reverse=True)[:n]

    def as_dicts(self) -> list[dict]:
        return [asdict(e) for e in self._entries]

    # ── Dosya işlemleri ───────────────────────
    def _load(self) -> None:
        try:
            if os.path.exists(self._path):
                with open(self._path, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                self._entries = [HistoryEntry(**r) for r in raw if isinstance(r, dict)]
        except Exception:
            self._entries = []

    def _save(self) -> None:
        try:
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump([asdict(e) for e in self._entries], f,
                          ensure_ascii=False, indent=2)
        except Exception:
            pass

    def export_html(self, path: str) -> None:
        """Geçmişi okunabilir HTML dosyasına aktarır."""
        rows = "".join(
            f"<tr><td>{e.date} {e.time_str}</td>"
            f"<td><a href='{e.url}'>{e.title or e.url}</a></td>"
            f"<td>{e.visit_count}</td></tr>"
            for e in self._entries
        )
        html = (
            "<!DOCTYPE html><html><head><meta charset='utf-8'>"
            "<title>PyWeb Geçmiş</title>"
            "<style>body{font-family:sans-serif;padding:20px}"
            "table{border-collapse:collapse;width:100%}"
            "th,td{padding:8px;border:1px solid #ccc;text-align:left}"
            "a{color:#333}</style></head><body>"
            "<h2>PyWeb Gezinme Geçmişi</h2>"
            f"<table><tr><th>Tarih</th><th>URL</th><th>Ziyaret</th></tr>{rows}</table>"
            "</body></html>"
        )
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)

    @property
    def count(self) -> int:
        return len(self._entries)
