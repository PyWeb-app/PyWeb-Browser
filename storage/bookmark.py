# ─────────────────────────────────────────────────────────────
#  PyWeb  –  storage/bookmark.py
#  Sık kullanılanlar (yer imleri) yönetim modülü.
#  Klasör hiyerarşisi, etiket sistemi ve arama destekler.
# ─────────────────────────────────────────────────────────────
from __future__ import annotations
import json
import os
import datetime
from typing import Optional
from dataclasses import dataclass, field, asdict

DATA_DIR       = os.path.join(os.path.expanduser("~"), ".pyweb")
BOOKMARKS_FILE = os.path.join(DATA_DIR, "bookmarks.json")


@dataclass
class Bookmark:
    url:        str
    title:      str  = ""
    folder:     str  = "Genel"
    tags:       list = field(default_factory=list)
    added:      str  = ""       # ISO tarih
    favicon:    str  = ""
    notes:      str  = ""

    def __post_init__(self):
        if not self.added:
            self.added = datetime.date.today().isoformat()
        if not self.title:
            self.title = self.url


class BookmarkManager:
    """
    Yer imi yöneticisi.
    - Klasör bazlı organizasyon
    - Etiket tabanlı arama
    - Kopyalama / taşıma
    - JSON serileştirme
    """

    def __init__(self, path: str = BOOKMARKS_FILE):
        self._path: str = path
        self._items: list[Bookmark] = []
        self._load()

    # ── Ekleme / güncelleme ───────────────────
    def add(self, url: str, title: str = "",
            folder: str = "Genel", tags: Optional[list] = None,
            notes: str = "") -> Bookmark:
        # Zaten varsa güncelle
        for bm in self._items:
            if bm.url == url:
                bm.title  = title or bm.title
                bm.folder = folder
                bm.notes  = notes or bm.notes
                if tags:
                    bm.tags = list(set(bm.tags + tags))
                self._save()
                return bm
        bm = Bookmark(url=url, title=title or url, folder=folder,
                      tags=tags or [], notes=notes)
        self._items.append(bm)
        self._save()
        return bm

    def update(self, url: str, **kwargs) -> bool:
        for bm in self._items:
            if bm.url == url:
                for k, v in kwargs.items():
                    if hasattr(bm, k):
                        setattr(bm, k, v)
                self._save()
                return True
        return False

    # ── Sorgulama ─────────────────────────────
    def contains(self, url: str) -> bool:
        return any(bm.url == url for bm in self._items)

    def get(self, url: str) -> Optional[Bookmark]:
        return next((bm for bm in self._items if bm.url == url), None)

    def all(self) -> list[Bookmark]:
        return list(self._items)

    def by_folder(self, folder: str) -> list[Bookmark]:
        return [bm for bm in self._items if bm.folder == folder]

    def by_tag(self, tag: str) -> list[Bookmark]:
        return [bm for bm in self._items if tag in bm.tags]

    def search(self, query: str) -> list[Bookmark]:
        q = query.lower()
        return [bm for bm in self._items
                if q in bm.url.lower()
                or q in bm.title.lower()
                or q in bm.notes.lower()
                or any(q in t.lower() for t in bm.tags)]

    def folders(self) -> list[str]:
        return sorted(set(bm.folder for bm in self._items))

    def all_tags(self) -> list[str]:
        tags: set[str] = set()
        for bm in self._items:
            tags.update(bm.tags)
        return sorted(tags)

    # ── Silme ─────────────────────────────────
    def remove(self, url: str) -> bool:
        before = len(self._items)
        self._items = [bm for bm in self._items if bm.url != url]
        changed = len(self._items) < before
        if changed:
            self._save()
        return changed

    def remove_folder(self, folder: str) -> int:
        before = len(self._items)
        self._items = [bm for bm in self._items if bm.folder != folder]
        removed = before - len(self._items)
        if removed:
            self._save()
        return removed

    def clear(self) -> None:
        self._items.clear()
        self._save()

    # ── Yeniden adlandırma / taşıma ───────────
    def move_to_folder(self, url: str, new_folder: str) -> bool:
        return self.update(url, folder=new_folder)

    def rename_folder(self, old: str, new: str) -> int:
        count = 0
        for bm in self._items:
            if bm.folder == old:
                bm.folder = new
                count += 1
        if count:
            self._save()
        return count

    # ── Dışa / içe aktarma ───────────────────
    def export_html(self, path: str) -> None:
        """Netscape Bookmark Format'ında dışa aktarır (tüm tarayıcılar destekler)."""
        lines = [
            "<!DOCTYPE NETSCAPE-Bookmark-file-1>",
            "<META HTTP-EQUIV='Content-Type' CONTENT='text/html; charset=UTF-8'>",
            "<TITLE>Yer İmleri</TITLE>",
            "<H1>PyWeb Yer İmleri</H1>",
            "<DL><p>",
        ]
        current_folder = None
        for bm in sorted(self._items, key=lambda b: b.folder):
            if bm.folder != current_folder:
                if current_folder is not None:
                    lines.append("</DL><p>")
                current_folder = bm.folder
                lines.append(f"<DT><H3>{bm.folder}</H3>")
                lines.append("<DL><p>")
            lines.append(
                f'<DT><A HREF="{bm.url}" ADD_DATE="{bm.added}">'
                f'{bm.title}</A>'
            )
        if current_folder:
            lines.append("</DL><p>")
        lines.append("</DL><p>")
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

    def import_urls(self, urls: list[str],
                    folder: str = "İçe Aktarılan") -> int:
        count = 0
        for url in urls:
            if url.startswith("http") and not self.contains(url):
                self.add(url, folder=folder)
                count += 1
        return count

    # ── İstatistik ────────────────────────────
    @property
    def count(self) -> int:
        return len(self._items)

    def as_dicts(self) -> list[dict]:
        return [asdict(bm) for bm in self._items]

    # ── Dosya işlemleri ───────────────────────
    def _load(self) -> None:
        try:
            if os.path.exists(self._path):
                with open(self._path, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                self._items = [Bookmark(**r) for r in raw if isinstance(r, dict)]
        except Exception:
            self._items = []

    def _save(self) -> None:
        try:
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump(self.as_dicts(), f, ensure_ascii=False, indent=2)
        except Exception:
            pass
