from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings


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
