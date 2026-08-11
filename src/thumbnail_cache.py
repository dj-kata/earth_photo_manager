from __future__ import annotations

import ctypes
from datetime import datetime
import hashlib
import json
import os
import re
from os import stat_result
from pathlib import Path
import struct
import sys
import threading
import time

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QImage, QImageReader, QTransform

from src.app_paths import THUMBNAIL_DIR_NAME, data_dir, thumbnail_dir

CACHE_DIR_NAME = THUMBNAIL_DIR_NAME
JPEG_THUMBNAIL_MAX_SCAN_BYTES = 1024 * 1024
THUMBNAIL_PROFILE_ENV = "EPM_THUMBNAIL_PROFILE"
THUMBNAIL_PROFILE_LOG_ENV = "EPM_THUMBNAIL_PROFILE_LOG"
_THUMBNAIL_PROFILE_TRUE_VALUES = {"1", "true", "yes", "on"}
_thumbnail_profile_lock = threading.Lock()
_ProfileSteps = list[tuple[str, float]]


def _thumbnail_profile_enabled() -> bool:
    value = os.environ.get(THUMBNAIL_PROFILE_ENV, "").strip().casefold()
    return value in _THUMBNAIL_PROFILE_TRUE_VALUES


def _thumbnail_profile_step_start(profile_steps: _ProfileSteps | None) -> float:
    if profile_steps is None:
        return 0.0
    return time.perf_counter()


def _add_thumbnail_profile_step(
    profile_steps: _ProfileSteps | None,
    name: str,
    start: float,
) -> None:
    if profile_steps is None:
        return
    profile_steps.append((name, round((time.perf_counter() - start) * 1000, 3)))


def _write_thumbnail_profile(
    source_path: Path,
    cache_path: Path | None,
    route: str,
    success: bool,
    start: float,
    profile_steps: _ProfileSteps | None,
) -> None:
    if not _thumbnail_profile_enabled():
        return

    steps = profile_steps or []
    event = {
        "timestamp": datetime.now().isoformat(timespec="milliseconds"),
        "thread": threading.current_thread().name,
        "source_path": str(source_path),
        "cache_path": str(cache_path) if cache_path is not None else None,
        "route": route,
        "success": success,
        "total_ms": round((time.perf_counter() - start) * 1000, 3),
        "steps_ms": [
            {"name": name, "ms": elapsed_ms}
            for name, elapsed_ms in steps
        ],
    }
    log_path_text = os.environ.get(THUMBNAIL_PROFILE_LOG_ENV, "").strip()
    log_path = (
        Path(log_path_text)
        if log_path_text
        else data_dir() / "thumbnail_profile.log"
    )
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(event, ensure_ascii=False, separators=(",", ":"))
        with _thumbnail_profile_lock, log_path.open("a", encoding="utf-8") as file:
            file.write(f"{line}\n")
    except OSError:
        pass


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
    profile_enabled = _thumbnail_profile_enabled()
    profile_start = time.perf_counter() if profile_enabled else 0.0
    profile_steps: _ProfileSteps | None = [] if profile_enabled else None
    source_path = Path(source_path_text)
    step_start = _thumbnail_profile_step_start(profile_steps)
    try:
        stat = source_path.stat()
    except OSError:
        _add_thumbnail_profile_step(profile_steps, "stat", step_start)
        _write_thumbnail_profile(
            source_path,
            None,
            "stat_failed",
            False,
            profile_start,
            profile_steps,
        )
        return source_path_text, None
    _add_thumbnail_profile_step(profile_steps, "stat", step_start)

    cache_dir = Path(cache_dir_text)
    step_start = _thumbnail_profile_step_start(profile_steps)
    cache_path = make_thumbnail_path(
        cache_dir,
        source_path,
        stat,
        width,
        height,
    )
    _add_thumbnail_profile_step(profile_steps, "make_cache_path", step_start)
    step_start = _thumbnail_profile_step_start(profile_steps)
    if cache_path.exists():
        _add_thumbnail_profile_step(profile_steps, "cache_exists", step_start)
        _write_thumbnail_profile(
            source_path,
            cache_path,
            "cache_hit",
            True,
            profile_start,
            profile_steps,
        )
        return source_path_text, str(cache_path)
    _add_thumbnail_profile_step(profile_steps, "cache_exists", step_start)

    return create_thumbnail_file(
        source_path_text,
        str(cache_path),
        width,
        height,
        profile_start=profile_start,
        profile_steps=profile_steps,
    )


def create_thumbnail_file(
    source_path_text: str,
    cache_path_text: str,
    width: int,
    height: int,
    *,
    profile_start: float | None = None,
    profile_steps: _ProfileSteps | None = None,
) -> tuple[str, str | None]:
    profile_enabled = profile_steps is not None or _thumbnail_profile_enabled()
    if profile_start is None:
        profile_start = time.perf_counter() if profile_enabled else 0.0
    if profile_steps is None and profile_enabled:
        profile_steps = []

    source_path = Path(source_path_text)
    cache_path = Path(cache_path_text)
    step_start = _thumbnail_profile_step_start(profile_steps)
    if cache_path.exists():
        _add_thumbnail_profile_step(profile_steps, "cache_exists", step_start)
        _write_thumbnail_profile(
            source_path,
            cache_path,
            "cache_hit",
            True,
            profile_start,
            profile_steps,
        )
        return source_path_text, cache_path_text
    _add_thumbnail_profile_step(profile_steps, "cache_exists", step_start)

    target_size = QSize(width, height)
    if _save_windows_shell_thumbnail(
        source_path,
        cache_path,
        target_size,
        cache_only=True,
        profile_steps=profile_steps,
        profile_prefix="shell_cache",
    ):
        _write_thumbnail_profile(
            source_path,
            cache_path,
            "shell_cache",
            True,
            profile_start,
            profile_steps,
        )
        return source_path_text, cache_path_text

    if _save_embedded_jpeg_thumbnail(
        source_path,
        cache_path,
        target_size,
        profile_steps=profile_steps,
    ):
        _write_thumbnail_profile(
            source_path,
            cache_path,
            "embedded_jpeg",
            True,
            profile_start,
            profile_steps,
        )
        return source_path_text, cache_path_text

    if _save_windows_shell_thumbnail(
        source_path,
        cache_path,
        target_size,
        cache_only=False,
        profile_steps=profile_steps,
        profile_prefix="shell_generate",
    ):
        _write_thumbnail_profile(
            source_path,
            cache_path,
            "shell_generate",
            True,
            profile_start,
            profile_steps,
        )
        return source_path_text, cache_path_text

    step_start = _thumbnail_profile_step_start(profile_steps)
    reader = QImageReader(str(source_path))
    reader.setAutoTransform(True)

    original_size = reader.size()
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
    _add_thumbnail_profile_step(profile_steps, "qimage_setup", step_start)

    step_start = _thumbnail_profile_step_start(profile_steps)
    image = reader.read()
    _add_thumbnail_profile_step(profile_steps, "qimage_read", step_start)
    if image.isNull():
        _write_thumbnail_profile(
            source_path,
            cache_path,
            "qimage_read_failed",
            False,
            profile_start,
            profile_steps,
        )
        return source_path_text, None

    if image.width() > width or image.height() > height:
        step_start = _thumbnail_profile_step_start(profile_steps)
        image = image.scaled(
            target_size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        _add_thumbnail_profile_step(profile_steps, "qimage_scale", step_start)

    step_start = _thumbnail_profile_step_start(profile_steps)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    if not image.save(str(cache_path), "JPG", 82):
        _add_thumbnail_profile_step(profile_steps, "qimage_save", step_start)
        _write_thumbnail_profile(
            source_path,
            cache_path,
            "qimage_save_failed",
            False,
            profile_start,
            profile_steps,
        )
        return source_path_text, None
    _add_thumbnail_profile_step(profile_steps, "qimage_save", step_start)
    _write_thumbnail_profile(
        source_path,
        cache_path,
        "qimage",
        True,
        profile_start,
        profile_steps,
    )
    return source_path_text, cache_path_text


def _save_image_thumbnail(
    image: QImage,
    cache_path: Path,
    target_size: QSize,
    *,
    profile_steps: _ProfileSteps | None = None,
    profile_prefix: str = "image",
) -> bool:
    if image.isNull():
        return False

    if (
        image.width() > target_size.width()
        or image.height() > target_size.height()
    ):
        step_start = _thumbnail_profile_step_start(profile_steps)
        image = image.scaled(
            target_size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        _add_thumbnail_profile_step(
            profile_steps,
            f"{profile_prefix}_scale",
            step_start,
        )

    step_start = _thumbnail_profile_step_start(profile_steps)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    saved = image.save(str(cache_path), "JPG", 82)
    _add_thumbnail_profile_step(
        profile_steps,
        f"{profile_prefix}_save",
        step_start,
    )
    return saved


def _save_embedded_jpeg_thumbnail(
    source_path: Path,
    cache_path: Path,
    target_size: QSize,
    *,
    profile_steps: _ProfileSteps | None = None,
) -> bool:
    if source_path.suffix.casefold() not in {".jpg", ".jpeg"}:
        return False

    step_start = _thumbnail_profile_step_start(profile_steps)
    try:
        with source_path.open("rb") as file:
            data = file.read(JPEG_THUMBNAIL_MAX_SCAN_BYTES)
    except OSError:
        _add_thumbnail_profile_step(profile_steps, "embedded_read_bytes", step_start)
        return False
    _add_thumbnail_profile_step(profile_steps, "embedded_read_bytes", step_start)

    step_start = _thumbnail_profile_step_start(profile_steps)
    thumbnail_data, orientation = _extract_exif_jpeg_thumbnail(data)
    _add_thumbnail_profile_step(profile_steps, "embedded_parse_exif", step_start)
    if not thumbnail_data:
        return False

    step_start = _thumbnail_profile_step_start(profile_steps)
    image = QImage.fromData(thumbnail_data, "JPG")
    _add_thumbnail_profile_step(profile_steps, "embedded_decode", step_start)
    step_start = _thumbnail_profile_step_start(profile_steps)
    image = _apply_exif_orientation(image, orientation)
    _add_thumbnail_profile_step(profile_steps, "embedded_orientation", step_start)
    return _save_image_thumbnail(
        image,
        cache_path,
        target_size,
        profile_steps=profile_steps,
        profile_prefix="embedded",
    )


def _extract_exif_jpeg_thumbnail(data: bytes) -> tuple[bytes | None, int]:
    if len(data) < 4 or data[:2] != b"\xff\xd8":
        return None, 1

    index = 2
    while index + 4 <= len(data):
        if data[index] != 0xFF:
            return None, 1
        while index < len(data) and data[index] == 0xFF:
            index += 1
        if index >= len(data):
            return None, 1

        marker = data[index]
        index += 1
        if marker in {0xDA, 0xD9}:
            return None, 1
        if index + 2 > len(data):
            return None, 1

        segment_length = int.from_bytes(data[index:index + 2], "big")
        if segment_length < 2:
            return None, 1
        segment_start = index + 2
        segment_end = segment_start + segment_length - 2
        if segment_end > len(data):
            return None, 1

        segment = data[segment_start:segment_end]
        if marker == 0xE1 and segment.startswith(b"Exif\x00\x00"):
            return _extract_exif_thumbnail_from_app1(segment[6:])
        index = segment_end
    return None, 1


def _extract_exif_thumbnail_from_app1(tiff: bytes) -> tuple[bytes | None, int]:
    if len(tiff) < 8:
        return None, 1
    if tiff[:2] == b"II":
        endian = "<"
    elif tiff[:2] == b"MM":
        endian = ">"
    else:
        return None, 1
    if _unpack_u16(tiff, 2, endian) != 42:
        return None, 1

    first_ifd_offset = _unpack_u32(tiff, 4, endian)
    orientation = 1
    for tag, value in _ifd_entries(tiff, first_ifd_offset, endian):
        if tag == 0x0112:
            orientation = value
            break

    thumbnail_ifd_offset = _next_ifd_offset(tiff, first_ifd_offset, endian)
    if thumbnail_ifd_offset is None:
        return None, orientation

    jpeg_offset = None
    jpeg_length = None
    for tag, value in _ifd_entries(tiff, thumbnail_ifd_offset, endian):
        if tag == 0x0201:
            jpeg_offset = value
        elif tag == 0x0202:
            jpeg_length = value

    if jpeg_offset is None or jpeg_length is None or jpeg_length <= 0:
        return None, orientation
    end = jpeg_offset + jpeg_length
    if jpeg_offset < 0 or end > len(tiff):
        return None, orientation
    thumbnail = tiff[jpeg_offset:end]
    if not thumbnail.startswith(b"\xff\xd8"):
        return None, orientation
    return thumbnail, orientation


def _apply_exif_orientation(image: QImage, orientation: int) -> QImage:
    if image.isNull() or orientation == 1:
        return image

    transform = QTransform()
    if orientation == 2:
        transform.scale(-1, 1)
    elif orientation == 3:
        transform.rotate(180)
    elif orientation == 4:
        transform.scale(1, -1)
    elif orientation == 5:
        transform.scale(-1, 1)
        transform.rotate(90)
    elif orientation == 6:
        transform.rotate(90)
    elif orientation == 7:
        transform.scale(-1, 1)
        transform.rotate(270)
    elif orientation == 8:
        transform.rotate(270)
    else:
        return image
    return image.transformed(transform, Qt.TransformationMode.SmoothTransformation)


def _ifd_entries(
    tiff: bytes,
    ifd_offset: int,
    endian: str,
) -> list[tuple[int, int]]:
    if ifd_offset < 0 or ifd_offset + 2 > len(tiff):
        return []
    count = _unpack_u16(tiff, ifd_offset, endian)
    entries: list[tuple[int, int]] = []
    for entry_index in range(count):
        offset = ifd_offset + 2 + entry_index * 12
        if offset + 12 > len(tiff):
            return entries
        tag = _unpack_u16(tiff, offset, endian)
        value = _ifd_entry_inline_value(tiff, offset, endian)
        entries.append((tag, value))
    return entries


def _ifd_entry_inline_value(tiff: bytes, offset: int, endian: str) -> int:
    field_type = _unpack_u16(tiff, offset + 2, endian)
    count = _unpack_u32(tiff, offset + 4, endian)
    value_offset = offset + 8
    if field_type == 3 and count == 1:
        return _unpack_u16(tiff, value_offset, endian)
    if field_type == 4 and count == 1:
        return _unpack_u32(tiff, value_offset, endian)
    return _unpack_u32(tiff, value_offset, endian)


def _next_ifd_offset(tiff: bytes, ifd_offset: int, endian: str) -> int | None:
    if ifd_offset < 0 or ifd_offset + 2 > len(tiff):
        return None
    count = _unpack_u16(tiff, ifd_offset, endian)
    next_offset_position = ifd_offset + 2 + count * 12
    if next_offset_position + 4 > len(tiff):
        return None
    next_offset = _unpack_u32(tiff, next_offset_position, endian)
    return next_offset or None


def _unpack_u16(data: bytes, offset: int, endian: str) -> int:
    return struct.unpack_from(f"{endian}H", data, offset)[0]


def _unpack_u32(data: bytes, offset: int, endian: str) -> int:
    return struct.unpack_from(f"{endian}I", data, offset)[0]


def _save_windows_shell_thumbnail(
    source_path: Path,
    cache_path: Path,
    target_size: QSize,
    *,
    cache_only: bool,
    profile_steps: _ProfileSteps | None = None,
    profile_prefix: str = "shell",
) -> bool:
    if sys.platform != "win32":
        return False
    step_start = _thumbnail_profile_step_start(profile_steps)
    try:
        image = _windows_shell_thumbnail(source_path, target_size, cache_only=cache_only)
    except OSError:
        _add_thumbnail_profile_step(
            profile_steps,
            f"{profile_prefix}_api",
            step_start,
        )
        return False
    _add_thumbnail_profile_step(profile_steps, f"{profile_prefix}_api", step_start)
    return _save_image_thumbnail(
        image,
        cache_path,
        target_size,
        profile_steps=profile_steps,
        profile_prefix=profile_prefix,
    )


if sys.platform == "win32":
    from ctypes import wintypes

    class _GUID(ctypes.Structure):
        _fields_ = [
            ("Data1", ctypes.c_ulong),
            ("Data2", ctypes.c_ushort),
            ("Data3", ctypes.c_ushort),
            ("Data4", ctypes.c_ubyte * 8),
        ]

    class _SIZE(ctypes.Structure):
        _fields_ = [("cx", ctypes.c_long), ("cy", ctypes.c_long)]

    class _BITMAP(ctypes.Structure):
        _fields_ = [
            ("bmType", wintypes.LONG),
            ("bmWidth", wintypes.LONG),
            ("bmHeight", wintypes.LONG),
            ("bmWidthBytes", wintypes.LONG),
            ("bmPlanes", wintypes.WORD),
            ("bmBitsPixel", wintypes.WORD),
            ("bmBits", wintypes.LPVOID),
        ]

    class _BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [
            ("biSize", wintypes.DWORD),
            ("biWidth", wintypes.LONG),
            ("biHeight", wintypes.LONG),
            ("biPlanes", wintypes.WORD),
            ("biBitCount", wintypes.WORD),
            ("biCompression", wintypes.DWORD),
            ("biSizeImage", wintypes.DWORD),
            ("biXPelsPerMeter", wintypes.LONG),
            ("biYPelsPerMeter", wintypes.LONG),
            ("biClrUsed", wintypes.DWORD),
            ("biClrImportant", wintypes.DWORD),
        ]

    class _BITMAPINFO(ctypes.Structure):
        _fields_ = [
            ("bmiHeader", _BITMAPINFOHEADER),
            ("bmiColors", wintypes.DWORD * 3),
        ]

    _IID_ISHELL_ITEM_IMAGE_FACTORY = _GUID(
        0xBCC18B79,
        0xBA16,
        0x442F,
        (ctypes.c_ubyte * 8)(0x80, 0xC4, 0x8A, 0x59, 0xC3, 0x0C, 0x46, 0x3B),
    )
    _COINIT_APARTMENTTHREADED = 0x2
    _RPC_E_CHANGED_MODE = 0x80010106
    _SIIGBF_BIGGERSIZEOK = 0x1
    _SIIGBF_MEMORYONLY = 0x2
    _SIIGBF_THUMBNAILONLY = 0x8
    _SIIGBF_INCACHEONLY = 0x10
    _BI_RGB = 0
    _DIB_RGB_COLORS = 0

    _ole32 = ctypes.OleDLL("ole32")
    _shell32 = ctypes.OleDLL("shell32")
    _gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
    _user32 = ctypes.WinDLL("user32", use_last_error=True)

    _ole32.CoInitializeEx.argtypes = [wintypes.LPVOID, wintypes.DWORD]
    _ole32.CoInitializeEx.restype = ctypes.HRESULT
    _ole32.CoUninitialize.argtypes = []
    _ole32.CoUninitialize.restype = None
    _shell32.SHCreateItemFromParsingName.argtypes = [
        wintypes.LPCWSTR,
        wintypes.LPVOID,
        ctypes.POINTER(_GUID),
        ctypes.POINTER(wintypes.LPVOID),
    ]
    _shell32.SHCreateItemFromParsingName.restype = ctypes.HRESULT
    _gdi32.GetObjectW.argtypes = [wintypes.HGDIOBJ, ctypes.c_int, wintypes.LPVOID]
    _gdi32.GetObjectW.restype = ctypes.c_int
    _gdi32.GetDIBits.argtypes = [
        wintypes.HDC,
        wintypes.HBITMAP,
        wintypes.UINT,
        wintypes.UINT,
        wintypes.LPVOID,
        ctypes.POINTER(_BITMAPINFO),
        wintypes.UINT,
    ]
    _gdi32.GetDIBits.restype = ctypes.c_int
    _gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
    _gdi32.DeleteObject.restype = wintypes.BOOL
    _user32.GetDC.argtypes = [wintypes.HWND]
    _user32.GetDC.restype = wintypes.HDC
    _user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
    _user32.ReleaseDC.restype = ctypes.c_int

    def _windows_shell_thumbnail(
        source_path: Path,
        target_size: QSize,
        *,
        cache_only: bool,
    ) -> QImage:
        initialized = _initialize_com_for_thread()
        item = wintypes.LPVOID()
        hbitmap = wintypes.HBITMAP()
        try:
            hr = _shell32.SHCreateItemFromParsingName(
                str(source_path),
                None,
                ctypes.byref(_IID_ISHELL_ITEM_IMAGE_FACTORY),
                ctypes.byref(item),
            )
            if hr < 0 or not item:
                raise OSError(hr, "SHCreateItemFromParsingName failed")

            flags = _SIIGBF_BIGGERSIZEOK | _SIIGBF_THUMBNAILONLY
            if cache_only:
                flags |= _SIIGBF_INCACHEONLY | _SIIGBF_MEMORYONLY

            vtable = ctypes.cast(
                item,
                ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p)),
            ).contents
            get_image = ctypes.WINFUNCTYPE(
                ctypes.HRESULT,
                wintypes.LPVOID,
                _SIZE,
                ctypes.c_int,
                ctypes.POINTER(wintypes.HBITMAP),
            )(vtable[3])
            size = _SIZE(target_size.width(), target_size.height())
            hr = get_image(item, size, flags, ctypes.byref(hbitmap))
            if hr < 0 or not hbitmap:
                raise OSError(hr, "IShellItemImageFactory.GetImage failed")
            return _qimage_from_hbitmap(hbitmap)
        finally:
            if hbitmap:
                _gdi32.DeleteObject(hbitmap)
            if item:
                _release_com_object(item)
            if initialized:
                _ole32.CoUninitialize()

    def _initialize_com_for_thread() -> bool:
        hr = _ole32.CoInitializeEx(None, _COINIT_APARTMENTTHREADED)
        if hr == _RPC_E_CHANGED_MODE:
            return False
        if hr < 0:
            raise OSError(hr, "CoInitializeEx failed")
        return True

    def _release_com_object(com_object: wintypes.LPVOID) -> None:
        vtable = ctypes.cast(
            com_object,
            ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p)),
        ).contents
        release = ctypes.WINFUNCTYPE(ctypes.c_ulong, wintypes.LPVOID)(vtable[2])
        release(com_object)

    def _qimage_from_hbitmap(hbitmap: wintypes.HBITMAP) -> QImage:
        bitmap = _BITMAP()
        if not _gdi32.GetObjectW(
            hbitmap,
            ctypes.sizeof(bitmap),
            ctypes.byref(bitmap),
        ):
            raise OSError(ctypes.get_last_error(), "GetObjectW failed")

        width = int(bitmap.bmWidth)
        height = abs(int(bitmap.bmHeight))
        if width <= 0 or height <= 0:
            return QImage()

        stride = width * 4
        pixel_count = stride * height
        pixels = (ctypes.c_ubyte * pixel_count)()
        bitmap_info = _BITMAPINFO()
        bitmap_info.bmiHeader.biSize = ctypes.sizeof(_BITMAPINFOHEADER)
        bitmap_info.bmiHeader.biWidth = width
        bitmap_info.bmiHeader.biHeight = -height
        bitmap_info.bmiHeader.biPlanes = 1
        bitmap_info.bmiHeader.biBitCount = 32
        bitmap_info.bmiHeader.biCompression = _BI_RGB

        hdc = _user32.GetDC(None)
        if not hdc:
            raise OSError(ctypes.get_last_error(), "GetDC failed")
        try:
            lines = _gdi32.GetDIBits(
                hdc,
                hbitmap,
                0,
                height,
                pixels,
                ctypes.byref(bitmap_info),
                _DIB_RGB_COLORS,
            )
        finally:
            _user32.ReleaseDC(None, hdc)
        if lines == 0:
            raise OSError(ctypes.get_last_error(), "GetDIBits failed")

        data = bytes(pixels)
        return QImage(data, width, height, stride, QImage.Format.Format_RGB32).copy()

else:

    def _windows_shell_thumbnail(
        source_path: Path,
        target_size: QSize,
        *,
        cache_only: bool,
    ) -> QImage:
        return QImage()
