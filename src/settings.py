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
FILE_DELETE_MODE_TRASH = "trash"
FILE_DELETE_MODE_PERMANENT = "permanent"
FILE_DELETE_MODES = {
    FILE_DELETE_MODE_TRASH,
    FILE_DELETE_MODE_PERMANENT,
}
TWEET_TEXT_DELIMITER_SPACE = "space"
TWEET_TEXT_DELIMITER_NEWLINE = "newline"
TWEET_TEXT_DELIMITER_CUSTOM = "custom"
TWEET_TEXT_DELIMITER_MODES = {
    TWEET_TEXT_DELIMITER_SPACE,
    TWEET_TEXT_DELIMITER_NEWLINE,
    TWEET_TEXT_DELIMITER_CUSTOM,
}
DATE_STAMP_FORMAT_YEAR_DOT = "year_dot"
DATE_STAMP_FORMAT_SHORT_YEAR_DOT = "short_year_dot"
DATE_STAMP_FORMAT_YEAR_SLASH = "year_slash"
DATE_STAMP_FORMAT_SHORT_YEAR_SLASH = "short_year_slash"
DATE_STAMP_FORMAT_YEAR_HYPHEN = "year_hyphen"
DATE_STAMP_FORMAT_SHORT_YEAR_HYPHEN = "short_year_hyphen"
DATE_STAMP_FORMATS = {
    DATE_STAMP_FORMAT_YEAR_DOT,
    DATE_STAMP_FORMAT_SHORT_YEAR_DOT,
    DATE_STAMP_FORMAT_YEAR_SLASH,
    DATE_STAMP_FORMAT_SHORT_YEAR_SLASH,
    DATE_STAMP_FORMAT_YEAR_HYPHEN,
    DATE_STAMP_FORMAT_SHORT_YEAR_HYPHEN,
}


@dataclass
class CopyBehaviorSettings:
    mark_posted_on_copy: bool = False
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
    date_stamp_enabled: bool = False
    date_stamp_format: str = DATE_STAMP_FORMAT_YEAR_DOT
    date_stamp_font: str = ""
    date_stamp_size: int = 32
    date_stamp_color: str = "#f97316"
    date_stamp_opacity: int = 100
    date_stamp_outline: bool = True
    date_stamp_outline_size: int = 3
    date_stamp_outline_color: str = "#111827"
    date_stamp_x: int = 24
    date_stamp_y: int = 24
    resize_enabled: bool = False
    resize_max_width: int = 1600
    resize_max_height: int = 1600
    auto_tag_ids: list[str] | None = None

    def __post_init__(self) -> None:
        if self.auto_tag_ids is None:
            self.auto_tag_ids = []
        if self.date_stamp_format not in DATE_STAMP_FORMATS:
            self.date_stamp_format = DATE_STAMP_FORMAT_YEAR_DOT


@dataclass
class TweetTextSettings:
    category_ids: list[str] | None = None
    delimiter_mode: str = TWEET_TEXT_DELIMITER_SPACE
    custom_delimiter: str = ""

    def __post_init__(self) -> None:
        if self.category_ids is None:
            self.category_ids = []
        if self.delimiter_mode not in TWEET_TEXT_DELIMITER_MODES:
            self.delimiter_mode = TWEET_TEXT_DELIMITER_SPACE

    def delimiter(self) -> str:
        if self.delimiter_mode == TWEET_TEXT_DELIMITER_NEWLINE:
            return "\n"
        if self.delimiter_mode == TWEET_TEXT_DELIMITER_CUSTOM:
            return self.custom_delimiter
        return " "


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

    def file_delete_mode(self) -> str:
        value = self._settings.value(
            "file_delete_mode",
            FILE_DELETE_MODE_TRASH,
            str,
        )
        return value if value in FILE_DELETE_MODES else FILE_DELETE_MODE_TRASH

    def set_file_delete_mode(self, mode: str) -> None:
        value = mode if mode in FILE_DELETE_MODES else FILE_DELETE_MODE_TRASH
        self._settings.setValue("file_delete_mode", value)

    def confirm_file_delete(self) -> bool:
        return self._setting_bool("confirm_file_delete", True)

    def set_confirm_file_delete(self, confirm: bool) -> None:
        self._settings.setValue("confirm_file_delete", confirm)

    def delete_raw_files_with_images(self) -> bool:
        return self._setting_bool("delete_raw_files_with_images", False)

    def set_delete_raw_files_with_images(self, delete_raw_files: bool) -> None:
        self._settings.setValue("delete_raw_files_with_images", delete_raw_files)

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
            mark_posted_on_copy=self._setting_bool(
                "copy_behavior/mark_posted_on_copy",
                False,
            ),
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
            date_stamp_enabled=self._setting_bool(
                "copy_behavior/date_stamp_enabled",
                False,
            ),
            date_stamp_format=values.value(
                "copy_behavior/date_stamp_format",
                DATE_STAMP_FORMAT_YEAR_DOT,
                str,
            ),
            date_stamp_font=values.value(
                "copy_behavior/date_stamp_font",
                "",
                str,
            ),
            date_stamp_size=self._setting_int("copy_behavior/date_stamp_size", 32),
            date_stamp_color=values.value(
                "copy_behavior/date_stamp_color",
                "#f97316",
                str,
            ),
            date_stamp_opacity=self._setting_int(
                "copy_behavior/date_stamp_opacity",
                100,
            ),
            date_stamp_outline=self._setting_bool(
                "copy_behavior/date_stamp_outline",
                True,
            ),
            date_stamp_outline_size=self._setting_int(
                "copy_behavior/date_stamp_outline_size",
                3,
            ),
            date_stamp_outline_color=values.value(
                "copy_behavior/date_stamp_outline_color",
                "#111827",
                str,
            ),
            date_stamp_x=self._setting_int("copy_behavior/date_stamp_x", 24),
            date_stamp_y=self._setting_int("copy_behavior/date_stamp_y", 24),
            resize_enabled=self._setting_bool("copy_behavior/resize_enabled", False),
            resize_max_width=self._setting_int("copy_behavior/resize_max_width", 1600),
            resize_max_height=self._setting_int("copy_behavior/resize_max_height", 1600),
            auto_tag_ids=[str(value) for value in auto_tag_ids if value],
        )

    def set_copy_behavior(self, behavior: CopyBehaviorSettings) -> None:
        values = self._settings
        values.setValue(
            "copy_behavior/mark_posted_on_copy",
            behavior.mark_posted_on_copy,
        )
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
        values.setValue(
            "copy_behavior/date_stamp_enabled",
            behavior.date_stamp_enabled,
        )
        values.setValue("copy_behavior/date_stamp_format", behavior.date_stamp_format)
        values.setValue("copy_behavior/date_stamp_font", behavior.date_stamp_font)
        values.setValue("copy_behavior/date_stamp_size", behavior.date_stamp_size)
        values.setValue("copy_behavior/date_stamp_color", behavior.date_stamp_color)
        values.setValue(
            "copy_behavior/date_stamp_opacity",
            behavior.date_stamp_opacity,
        )
        values.setValue(
            "copy_behavior/date_stamp_outline",
            behavior.date_stamp_outline,
        )
        values.setValue(
            "copy_behavior/date_stamp_outline_size",
            behavior.date_stamp_outline_size,
        )
        values.setValue(
            "copy_behavior/date_stamp_outline_color",
            behavior.date_stamp_outline_color,
        )
        values.setValue("copy_behavior/date_stamp_x", behavior.date_stamp_x)
        values.setValue("copy_behavior/date_stamp_y", behavior.date_stamp_y)
        values.setValue("copy_behavior/resize_enabled", behavior.resize_enabled)
        values.setValue("copy_behavior/resize_max_width", behavior.resize_max_width)
        values.setValue("copy_behavior/resize_max_height", behavior.resize_max_height)
        values.setValue("copy_behavior/auto_tag_ids", behavior.auto_tag_ids or [])

    def tweet_text_settings(self) -> TweetTextSettings:
        values = self._settings
        category_ids = values.value("tweet_text/category_ids", [], list)
        if isinstance(category_ids, str):
            category_ids = [category_ids]
        delimiter_mode = values.value(
            "tweet_text/delimiter_mode",
            TWEET_TEXT_DELIMITER_SPACE,
            str,
        )
        return TweetTextSettings(
            category_ids=[str(value) for value in category_ids if value],
            delimiter_mode=(
                delimiter_mode
                if delimiter_mode in TWEET_TEXT_DELIMITER_MODES
                else TWEET_TEXT_DELIMITER_SPACE
            ),
            custom_delimiter=values.value("tweet_text/custom_delimiter", "", str),
        )

    def has_tweet_text_category_settings(self) -> bool:
        return self._settings.contains("tweet_text/category_ids")

    def set_tweet_text_settings(self, settings: TweetTextSettings) -> None:
        self._settings.setValue("tweet_text/category_ids", settings.category_ids or [])
        self._settings.setValue("tweet_text/delimiter_mode", settings.delimiter_mode)
        self._settings.setValue(
            "tweet_text/custom_delimiter",
            settings.custom_delimiter,
        )

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
