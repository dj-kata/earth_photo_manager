from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QByteArray, QSettings

from src.app_paths import tag_database_path


THUMBNAIL_GENERATION_VISIBLE = "visible"
THUMBNAIL_GENERATION_FOLDER = "folder"
THUMBNAIL_GENERATION_MODES = {
    THUMBNAIL_GENERATION_VISIBLE,
    THUMBNAIL_GENERATION_FOLDER,
}


@dataclass
class CopyBehaviorSettings:
    text_watermark_enabled: bool = False
    text_watermark_text: str = ""
    text_watermark_font: str = ""
    text_watermark_size: int = 32
    text_watermark_color: str = "#ffffff"
    text_watermark_opacity: int = 100
    text_watermark_outline: bool = True
    text_watermark_outline_size: int = 3
    text_watermark_outline_color: str = "#111827"
    text_watermark_x: int = 24
    text_watermark_y: int = 24
    image_watermark_enabled: bool = False
    image_watermark_path: str = ""
    image_watermark_opacity: int = 60
    image_watermark_x: int = 24
    image_watermark_y: int = 24
    resize_enabled: bool = False
    resize_max_width: int = 1600
    resize_max_height: int = 1600
    auto_tag_ids: list[str] | None = None

    def __post_init__(self) -> None:
        if self.auto_tag_ids is None:
            self.auto_tag_ids = []


class AppSettings:
    def __init__(self) -> None:
        self._settings = QSettings("earth_photo_manager", "earth_photo_manager")

    def root_folders(self) -> list[Path]:
        values = self._settings.value("root_folders", [], list)
        if isinstance(values, str):
            values = [values]
        return [Path(value) for value in values if value and Path(value).exists()]

    def set_root_folders(self, folders: list[Path]) -> None:
        unique: list[str] = []
        seen: set[str] = set()
        for folder in folders:
            normalized = str(folder.expanduser().resolve())
            if normalized not in seen:
                seen.add(normalized)
                unique.append(normalized)
        self._settings.setValue("root_folders", unique)

    def pending_thumbnail_paths(self) -> list[Path]:
        values = self._settings.value("pending_thumbnail_paths", [], list)
        if isinstance(values, str):
            values = [values]
        return [Path(value) for value in values if value]

    def set_pending_thumbnail_paths(self, paths: list[Path]) -> None:
        unique: list[str] = []
        seen: set[str] = set()
        for path in paths:
            normalized = str(path)
            if normalized not in seen:
                seen.add(normalized)
                unique.append(normalized)
        self._settings.setValue("pending_thumbnail_paths", unique)

    def selected_folder_path(self) -> Path | None:
        value = self._settings.value("selected_folder_path", "", str)
        path = Path(value) if value else None
        return path if path is not None and path.exists() and path.is_dir() else None

    def set_selected_folder_path(self, path: Path | None) -> None:
        self._settings.setValue("selected_folder_path", str(path) if path else "")

    def selected_image_path(self) -> Path | None:
        value = self._settings.value("selected_image_path", "", str)
        path = Path(value) if value else None
        return path if path is not None and path.exists() and path.is_file() else None

    def set_selected_image_path(self, path: Path | None) -> None:
        self._settings.setValue("selected_image_path", str(path) if path else "")

    def window_geometry(self) -> QByteArray | None:
        value = self._settings.value("window_geometry", QByteArray())
        return value if isinstance(value, QByteArray) and not value.isEmpty() else None

    def set_window_geometry(self, geometry: QByteArray) -> None:
        self._settings.setValue("window_geometry", geometry)

    def main_splitter_state(self) -> QByteArray | None:
        value = self._settings.value("main_splitter_state", QByteArray())
        return value if isinstance(value, QByteArray) and not value.isEmpty() else None

    def set_main_splitter_state(self, state: QByteArray) -> None:
        self._settings.setValue("main_splitter_state", state)

    def center_splitter_state(self) -> QByteArray | None:
        value = self._settings.value("center_splitter_state", QByteArray())
        return value if isinstance(value, QByteArray) and not value.isEmpty() else None

    def set_center_splitter_state(self, state: QByteArray) -> None:
        self._settings.setValue("center_splitter_state", state)

    def thumbnail_generation_mode(self) -> str:
        value = self._settings.value(
            "thumbnail_generation_mode",
            THUMBNAIL_GENERATION_VISIBLE,
            str,
        )
        return (
            value
            if value in THUMBNAIL_GENERATION_MODES
            else THUMBNAIL_GENERATION_VISIBLE
        )

    def set_thumbnail_generation_mode(self, mode: str) -> None:
        value = (
            mode if mode in THUMBNAIL_GENERATION_MODES else THUMBNAIL_GENERATION_VISIBLE
        )
        self._settings.setValue("thumbnail_generation_mode", value)

    def related_tag_source_category_ids(self) -> list[str] | None:
        if not self._settings.contains("related_tag_source_category_ids"):
            return None
        values = self._settings.value("related_tag_source_category_ids", [], list)
        if isinstance(values, str):
            values = [values]
        return [str(value) for value in values if value]

    def set_related_tag_source_category_ids(self, category_ids: list[str]) -> None:
        unique: list[str] = []
        seen: set[str] = set()
        for category_id in category_ids:
            if category_id in seen:
                continue
            seen.add(category_id)
            unique.append(category_id)
        self._settings.setValue("related_tag_source_category_ids", unique)

    def copy_behavior(self) -> CopyBehaviorSettings:
        values = self._settings
        auto_tag_ids = values.value("copy_behavior/auto_tag_ids", [], list)
        if isinstance(auto_tag_ids, str):
            auto_tag_ids = [auto_tag_ids]
        return CopyBehaviorSettings(
            text_watermark_enabled=self._setting_bool(
                "copy_behavior/text_watermark_enabled",
                False,
            ),
            text_watermark_text=values.value(
                "copy_behavior/text_watermark_text",
                "",
                str,
            ),
            text_watermark_font=values.value(
                "copy_behavior/text_watermark_font",
                "",
                str,
            ),
            text_watermark_size=self._setting_int(
                "copy_behavior/text_watermark_size",
                32,
            ),
            text_watermark_color=values.value(
                "copy_behavior/text_watermark_color",
                "#ffffff",
                str,
            ),
            text_watermark_opacity=self._setting_int(
                "copy_behavior/text_watermark_opacity",
                100,
            ),
            text_watermark_outline=self._setting_bool(
                "copy_behavior/text_watermark_outline",
                True,
            ),
            text_watermark_outline_size=self._setting_int(
                "copy_behavior/text_watermark_outline_size",
                3,
            ),
            text_watermark_outline_color=values.value(
                "copy_behavior/text_watermark_outline_color",
                "#111827",
                str,
            ),
            text_watermark_x=self._setting_int("copy_behavior/text_watermark_x", 24),
            text_watermark_y=self._setting_int("copy_behavior/text_watermark_y", 24),
            image_watermark_enabled=self._setting_bool(
                "copy_behavior/image_watermark_enabled",
                False,
            ),
            image_watermark_path=values.value(
                "copy_behavior/image_watermark_path",
                "",
                str,
            ),
            image_watermark_opacity=self._setting_int(
                "copy_behavior/image_watermark_opacity",
                60,
            ),
            image_watermark_x=self._setting_int("copy_behavior/image_watermark_x", 24),
            image_watermark_y=self._setting_int("copy_behavior/image_watermark_y", 24),
            resize_enabled=self._setting_bool("copy_behavior/resize_enabled", False),
            resize_max_width=self._setting_int("copy_behavior/resize_max_width", 1600),
            resize_max_height=self._setting_int("copy_behavior/resize_max_height", 1600),
            auto_tag_ids=[str(value) for value in auto_tag_ids if value],
        )

    def set_copy_behavior(self, behavior: CopyBehaviorSettings) -> None:
        values = self._settings
        values.setValue(
            "copy_behavior/text_watermark_enabled",
            behavior.text_watermark_enabled,
        )
        values.setValue("copy_behavior/text_watermark_text", behavior.text_watermark_text)
        values.setValue("copy_behavior/text_watermark_font", behavior.text_watermark_font)
        values.setValue("copy_behavior/text_watermark_size", behavior.text_watermark_size)
        values.setValue("copy_behavior/text_watermark_color", behavior.text_watermark_color)
        values.setValue(
            "copy_behavior/text_watermark_opacity",
            behavior.text_watermark_opacity,
        )
        values.setValue(
            "copy_behavior/text_watermark_outline",
            behavior.text_watermark_outline,
        )
        values.setValue(
            "copy_behavior/text_watermark_outline_size",
            behavior.text_watermark_outline_size,
        )
        values.setValue(
            "copy_behavior/text_watermark_outline_color",
            behavior.text_watermark_outline_color,
        )
        values.setValue("copy_behavior/text_watermark_x", behavior.text_watermark_x)
        values.setValue("copy_behavior/text_watermark_y", behavior.text_watermark_y)
        values.setValue(
            "copy_behavior/image_watermark_enabled",
            behavior.image_watermark_enabled,
        )
        values.setValue("copy_behavior/image_watermark_path", behavior.image_watermark_path)
        values.setValue(
            "copy_behavior/image_watermark_opacity",
            behavior.image_watermark_opacity,
        )
        values.setValue("copy_behavior/image_watermark_x", behavior.image_watermark_x)
        values.setValue("copy_behavior/image_watermark_y", behavior.image_watermark_y)
        values.setValue("copy_behavior/resize_enabled", behavior.resize_enabled)
        values.setValue("copy_behavior/resize_max_width", behavior.resize_max_width)
        values.setValue("copy_behavior/resize_max_height", behavior.resize_max_height)
        values.setValue("copy_behavior/auto_tag_ids", behavior.auto_tag_ids or [])

    def language(self) -> str:
        value = self._settings.value("language", "en", str)
        return value if value in {"en", "ja"} else "en"

    def set_language(self, language: str) -> None:
        self._settings.setValue("language", language if language in {"en", "ja"} else "en")

    def qsettings(self) -> QSettings:
        return self._settings

    def tag_database_path(self) -> Path:
        return tag_database_path()

    def _setting_bool(self, key: str, default: bool) -> bool:
        value = self._settings.value(key, default)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in {"1", "true", "yes"}
        return bool(value)

    def _setting_int(self, key: str, default: int) -> int:
        value = self._settings.value(key, default)
        try:
            return int(value)
        except (TypeError, ValueError):
            return default
