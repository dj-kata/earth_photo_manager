from __future__ import annotations

import sys
from pathlib import Path


DATA_DIR_NAME = "data"
THUMBNAIL_DIR_NAME = "thumbnail"
DATABASE_FILENAME = "earth_photo_manager.db"


def app_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def data_dir() -> Path:
    path = app_root() / DATA_DIR_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def thumbnail_dir() -> Path:
    return data_dir() / THUMBNAIL_DIR_NAME


def tag_database_path() -> Path:
    return data_dir() / DATABASE_FILENAME
