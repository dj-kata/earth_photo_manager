from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path


DATA_DIR_NAME = "data"
THUMBNAIL_DIR_NAME = "thumbnail"
DATABASE_FILENAME = "earth_photo_manager.db"
RESOURCES_DIR_NAME = "resources"
APP_ICON_FILENAME = "icon.ico"


def app_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def data_dir() -> Path:
    path = user_data_dir()
    path.mkdir(parents=True, exist_ok=True)
    return path


def user_data_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
        return base / "earth_photo_manager"

    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "earth_photo_manager"

    base = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    return base / "earth_photo_manager"


def legacy_data_dir() -> Path:
    return app_root() / DATA_DIR_NAME


def resource_path(*parts: str) -> Path:
    return app_root() / RESOURCES_DIR_NAME / Path(*parts)


def app_icon_path() -> Path:
    return resource_path(APP_ICON_FILENAME)


def thumbnail_dir() -> Path:
    return data_dir() / THUMBNAIL_DIR_NAME


def tag_database_path() -> Path:
    path = data_dir() / DATABASE_FILENAME
    _migrate_legacy_database(path)
    return path


def legacy_tag_database_path() -> Path:
    return legacy_data_dir() / DATABASE_FILENAME


def _migrate_legacy_database(destination: Path) -> None:
    if destination.exists():
        return

    source = legacy_tag_database_path()
    if not source.exists() or source.resolve() == destination.resolve():
        return

    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        shutil.copy2(source, destination)
    except OSError:
        destination.unlink(missing_ok=True)
        raise
