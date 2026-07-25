from __future__ import annotations

import hashlib
import re
from os import stat_result
from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QImageReader

from src.app_paths import THUMBNAIL_DIR_NAME, thumbnail_dir

CACHE_DIR_NAME = THUMBNAIL_DIR_NAME


class ThumbnailCache:
    def __init__(self, thumbnail_size: QSize) -> None:
        self.thumbnail_size = thumbnail_size
        self.cache_dir = thumbnail_dir()

    def path_for(self, source_path: Path) -> Path | None:
        try:
            stat = source_path.stat()
        except OSError:
            return None

        return self.path_for_stat(source_path, stat)

    def path_for_stat(self, source_path: Path, stat: stat_result) -> Path:
        return make_thumbnail_path(
            self.cache_dir,
            source_path,
            stat,
            self.thumbnail_size.width(),
            self.thumbnail_size.height(),
        )

    def cached_path_for(self, source_path: Path) -> Path | None:
        cache_path = self.path_for(source_path)
        if cache_path is not None and cache_path.exists():
            return cache_path
        return None


def make_thumbnail_path(
    cache_dir: Path,
    source_path: Path,
    stat: stat_result,
    width: int,
    height: int,
) -> Path:
    digest, filename = make_thumbnail_digest_and_filename(
        source_path,
        stat,
        width,
        height,
    )
    return cache_dir / digest[:2] / filename


def make_thumbnail_digest_and_filename(
    source_path: Path,
    stat: stat_result,
    width: int,
    height: int,
) -> tuple[str, str]:
    try:
        normalized_path = str(source_path.resolve())
    except OSError:
        normalized_path = str(source_path)

    key = "|".join(
        [
            normalized_path,
            str(stat.st_mtime_ns),
            str(stat.st_size),
            str(width),
            str(height),
        ]
    )
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()
    safe_stem = re.sub(r"[^A-Za-z0-9_.-]+", "_", source_path.stem).strip("._")
    if not safe_stem:
        safe_stem = "image"
    filename = f"{safe_stem}_{digest[:16]}.jpg"
    return digest, filename


def create_thumbnail_file_for_cache_dir(
    source_path_text: str,
    cache_dir_text: str,
    width: int,
    height: int,
) -> tuple[str, str | None]:
    source_path = Path(source_path_text)
    try:
        stat = source_path.stat()
    except OSError:
        return source_path_text, None

    cache_dir = Path(cache_dir_text)
    cache_path = make_thumbnail_path(
        cache_dir,
        source_path,
        stat,
        width,
        height,
    )
    if cache_path.exists():
        return source_path_text, str(cache_path)

    return create_thumbnail_file(source_path_text, str(cache_path), width, height)


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
    target_size = QSize(width, height)
    if original_size.isValid():
        scaled_size = original_size.scaled(
            target_size,
            Qt.AspectRatioMode.KeepAspectRatio,
        )
        if (
            scaled_size.width() < original_size.width()
            or scaled_size.height() < original_size.height()
        ):
            reader.setScaledSize(scaled_size)

    image = reader.read()
    if image.isNull():
        return source_path_text, None

    if image.width() > width or image.height() > height:
        image = image.scaled(
            target_size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    if not image.save(str(cache_path), "JPG", 82):
        return source_path_text, None
    return source_path_text, cache_path_text
