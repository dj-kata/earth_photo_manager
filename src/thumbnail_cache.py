from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QImageReader


CACHE_DIR_NAME = ".earth_photo_manager_thumbnails"


class ThumbnailCache:
    def __init__(self, thumbnail_size: QSize) -> None:
        self.thumbnail_size = thumbnail_size
        self.cache_dir = self._app_root() / CACHE_DIR_NAME

    def _app_root(self) -> Path:
        if getattr(sys, "frozen", False):
            return Path(sys.executable).resolve().parent
        return Path(__file__).resolve().parents[1]

    def path_for(self, source_path: Path) -> Path | None:
        try:
            stat = source_path.stat()
        except OSError:
            return None

        key = "|".join(
            [
                str(source_path.resolve()),
                str(stat.st_mtime_ns),
                str(stat.st_size),
                str(self.thumbnail_size.width()),
                str(self.thumbnail_size.height()),
            ]
        )
        digest = hashlib.sha1(key.encode("utf-8")).hexdigest()
        safe_stem = re.sub(r"[^A-Za-z0-9_.-]+", "_", source_path.stem).strip("._")
        if not safe_stem:
            safe_stem = "image"
        filename = f"{safe_stem}_{digest[:16]}.jpg"
        return self.cache_dir / filename

    def cached_path_for(self, source_path: Path) -> Path | None:
        cache_path = self.path_for(source_path)
        if cache_path is not None and cache_path.exists():
            return cache_path
        return None


def create_thumbnail_file(
    source_path_text: str,
    cache_path_text: str,
    width: int,
    height: int,
) -> tuple[str, str | None]:
    source_path = Path(source_path_text)
    cache_path = Path(cache_path_text)
    if cache_path.exists():
        return source_path_text, cache_path_text

    reader = QImageReader(str(source_path))
    reader.setAutoTransform(True)

    original_size = reader.size()
    if original_size.isValid():
        scaled_size = original_size.scaled(
            QSize(width, height),
            Qt.AspectRatioMode.KeepAspectRatio,
        )
        reader.setScaledSize(scaled_size)

    image = reader.read()
    if image.isNull():
        return source_path_text, None

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    if not image.save(str(cache_path), "JPG", 82):
        return source_path_text, None
    return source_path_text, cache_path_text
