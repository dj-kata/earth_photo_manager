from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QByteArray, QSettings

from src.app_paths import tag_database_path


THUMBNAIL_GENERATION_VISIBLE = "visible"
THUMBNAIL_GENERATION_FOLDER = "folder"
THUMBNAIL_GENERATION_MODES = {
    THUMBNAIL_GENERATION_VISIBLE,
    THUMBNAIL_GENERATION_FOLDER,
}


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

    def language(self) -> str:
        value = self._settings.value("language", "en", str)
        return value if value in {"en", "ja"} else "en"

    def set_language(self, language: str) -> None:
        self._settings.setValue("language", language if language in {"en", "ja"} else "en")

    def qsettings(self) -> QSettings:
        return self._settings

    def tag_database_path(self) -> Path:
        return tag_database_path()
