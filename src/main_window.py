from __future__ import annotations

from collections import OrderedDict, deque
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime
import os
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QItemSelectionModel, QPoint, QRect, QSize, Qt, QTimer, Signal
from PySide6.QtGui import (
    QAction,
    QActionGroup,
    QBrush,
    QColor,
    QFont,
    QFontMetrics,
    QIcon,
    QImage,
    QImageReader,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFontComboBox,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
    QSizePolicy,
)

from src.flow_layout import FlowLayout
from src.models import IMAGE_EXTENSIONS, ImageFile
from src.image_metadata import read_image_metadata
from src.preview_window import ImagePreviewLabel, PreviewWindow
from src.app_paths import data_dir, thumbnail_dir
from src.settings import (
    AppSettings,
    CopyBehaviorSettings,
    THUMBNAIL_GENERATION_FOLDER,
    THUMBNAIL_GENERATION_VISIBLE,
)
from src.tag_dialogs import TagManagerDialog
from src.tag_store import Tag, TagCategory, TagStore
from src.thumbnail_cache import ThumbnailCache, create_thumbnail_file_for_cache_dir


def _thumbnail_worker_count() -> int:
    configured = os.environ.get("EPM_THUMBNAIL_WORKERS", "").strip()
    if configured:
        try:
            return max(1, int(configured))
        except ValueError:
            pass

    cpu_count = os.cpu_count() or 2
    return max(2, min(8, cpu_count - 2))


THUMBNAIL_WORKER_COUNT = _thumbnail_worker_count()
THUMBNAIL_POLL_INTERVAL_MS = 100
THUMBNAIL_UI_UPDATE_INTERVAL_MS = 50
THUMBNAIL_UI_UPDATES_PER_TICK = 12
THUMBNAIL_VISIBLE_PRIORITY_DELAY_MS = 80
THUMBNAIL_ICON_CACHE_LIMIT = 512
STATUS_BAR_VERTICAL_PADDING = 6
TAG_BADGE_MARGIN = 5
TAG_BADGE_WIDTH = 28
TAG_BADGE_HEIGHT = 16
TAG_BADGE_GAP = 3


TRANSLATIONS = {
    "en": {
        "app_title": "Earth Photo Manager",
        "file": "File",
        "view": "View",
        "tag": "Tag",
        "language": "Language",
        "help": "Help",
        "settings": "Settings",
        "exit": "Exit",
        "preview_window": "Preview Window",
        "japanese": "Japanese",
        "english": "English",
        "manage_tags": "Manage Tags...",
        "copy_image": "Copy Image",
        "copied_image": "Copied image to clipboard: {name}",
        "copy_image_failed": "Could not copy image: {error}",
        "add_related_tag": "Add Related Tag",
        "add_tag": "Add Tag",
        "clear_assigned_tags": "Clear Assigned Tags",
        "about": "About",
        "folders": "Folders",
        "tags": "Tags",
        "tag_filters": "Tag Filters",
        "include_tags": "Show Tags",
        "exclude_tags": "Exclude Tags",
        "include_tag_placeholder": "Add show tag...",
        "exclude_tag_placeholder": "Add exclude tag...",
        "clear_include_tags": "Clear Show",
        "clear_exclude_tags": "Clear Exclude",
        "clear_all_tag_filters": "Clear All",
        "remove_filter_tag": "Remove filter tag",
        "filtered_image_count": "{shown} of {total} image(s) in {folder}",
        "filtered_thumbnail_queue": (
            "{shown} of {total} image(s) in {folder} - thumbnail queue: {remaining}"
        ),
        "information": "Information",
        "add": "Add",
        "remove": "Remove",
        "ready": "Ready",
        "select_root_folder": "Select root folder",
        "add_root_prompt": "Add a root folder to begin.",
        "cannot_open_folder": "Cannot open folder: {error}",
        "image_count": "{count} image(s) in {folder}",
        "thumbnail_queue": "{count} image(s) in {folder} - thumbnail queue: {remaining}",
        "added_tags": "Added {tag} to {count} image(s).",
        "removed_tags": "Removed tag from {count} image(s).",
        "cleared_tags": "Cleared tags from {count} image(s).",
        "processing_tags": "Processing tags for {count} image(s)...",
        "add_related_tag_placeholder": "Add related tag...",
        "add_tag_placeholder": "Add tag...",
        "item": "Item",
        "value": "Value",
        "file_name": "File name",
        "full_path": "Full path",
        "root_folder": "Root folder",
        "folder": "Folder",
        "extension": "Extension",
        "file_size": "File size",
        "file_status": "File status",
        "unavailable": "Unavailable: {error}",
        "related": "Related",
        "settings_title": "Settings",
        "save_settings_changes_title": "Save settings?",
        "save_settings_changes_message": "Settings have changed. Save changes?",
        "general_settings": "General",
        "image_copy_settings": "Image Copy",
        "tag_settings": "Tag Settings",
        "thumbnail_settings": "Thumbnail Settings",
        "copy_behavior_settings": "Image Copy Behavior",
        "thumbnail_generation_mode": "Create thumbnails for",
        "thumbnail_generation_visible": "Files visible in the file list view only",
        "thumbnail_generation_folder": "All files in the selected folder",
        "related_tag_source_categories": "Categories used for related tag suggestions",
        "text_watermark": "Text Watermark",
        "image_watermark": "Image Watermark",
        "resize_on_copy": "Resize",
        "resize_keeps_aspect": "Keeps aspect ratio and fits within both limits.",
        "auto_tags_on_copy": "Tags Added on Copy",
        "enable": "Enable",
        "watermark_text": "Text",
        "font": "Font",
        "size": "Size",
        "color": "Color",
        "outline": "Outline",
        "outline_size": "Outline size",
        "outline_color": "Outline color",
        "x_position": "X",
        "y_position": "Y",
        "image_path": "Image file",
        "browse": "Browse...",
        "opacity": "Opacity",
        "max_width": "Max width",
        "max_height": "Max height",
        "choose_watermark_color": "Choose watermark color",
        "choose_watermark_image": "Choose watermark image",
        "image_file_filter": "Images (*.png *.jpg *.jpeg *.bmp *.gif *.webp *.tif *.tiff)",
        "preview_copy_behavior": "Preview",
        "copy_preview_title": "Copy Preview",
        "copy_preview_unavailable": "Preview unavailable",
        "copy_preview_click_hint": "Click the preview to set watermark coordinates.",
        "remove_tag": "Remove tag",
        "loading": "Loading...",
        "updated_at": "Modified",
        "dimensions": "Dimensions",
        "about_text": "Earth Photo Manager",
    },
    "ja": {
        "app_title": "Earth Photo Manager",
        "file": "ファイル",
        "view": "表示",
        "tag": "タグ",
        "language": "言語",
        "help": "ヘルプ",
        "settings": "設定",
        "exit": "終了",
        "preview_window": "プレビューウィンドウ",
        "japanese": "日本語",
        "english": "English",
        "manage_tags": "タグ管理...",
        "copy_image": "画像をコピー",
        "copied_image": "画像をクリップボードにコピーしました: {name}",
        "copy_image_failed": "画像をコピーできません: {error}",
        "add_related_tag": "関連タグを追加",
        "add_tag": "タグを追加",
        "clear_assigned_tags": "設定中のタグをクリア",
        "about": "このアプリについて",
        "folders": "フォルダー",
        "tags": "タグ",
        "tag_filters": "タグフィルタ",
        "include_tags": "表示対象",
        "exclude_tags": "除外対象",
        "include_tag_placeholder": "表示対象タグを追加...",
        "exclude_tag_placeholder": "除外対象タグを追加...",
        "clear_include_tags": "表示対象をクリア",
        "clear_exclude_tags": "除外対象をクリア",
        "clear_all_tag_filters": "全てクリア",
        "remove_filter_tag": "フィルタタグを削除",
        "filtered_image_count": "{folder} に {shown} / {total} 件の画像",
        "filtered_thumbnail_queue": (
            "{folder} に {shown} / {total} 件の画像 - サムネイル待ち: {remaining}"
        ),
        "information": "情報",
        "add": "追加",
        "remove": "削除",
        "ready": "準備完了",
        "select_root_folder": "ルートフォルダーを選択",
        "add_root_prompt": "ルートフォルダーを追加してください。",
        "cannot_open_folder": "フォルダーを開けません: {error}",
        "image_count": "{folder} に {count} 件の画像",
        "thumbnail_queue": "{folder} に {count} 件の画像 - サムネイル待ち: {remaining}",
        "added_tags": "{count} 件の画像に {tag} を追加しました。",
        "removed_tags": "{count} 件の画像からタグを削除しました。",
        "cleared_tags": "{count} 件の画像からタグをクリアしました。",
        "processing_tags": "{count} 件の画像のタグを処理中...",
        "add_related_tag_placeholder": "関連タグを追加...",
        "add_tag_placeholder": "タグを追加...",
        "item": "項目",
        "value": "値",
        "file_name": "ファイル名",
        "full_path": "フルパス",
        "root_folder": "ルートフォルダー",
        "folder": "フォルダー",
        "extension": "拡張子",
        "file_size": "ファイルサイズ",
        "file_status": "ファイル状態",
        "unavailable": "利用不可: {error}",
        "related": "関連",
        "settings_title": "設定",
        "save_settings_changes_title": "設定を保存しますか?",
        "save_settings_changes_message": "設定が変更されています。保存しますか?",
        "general_settings": "一般",
        "image_copy_settings": "画像コピー",
        "tag_settings": "タグ設定",
        "thumbnail_settings": "サムネイル設定",
        "copy_behavior_settings": "画像コピー時の動作",
        "thumbnail_generation_mode": "サムネイル作成対象",
        "thumbnail_generation_visible": "ファイル一覧ビューで表示されたファイルのみ",
        "thumbnail_generation_folder": "選択フォルダ内を全ファイル",
        "related_tag_source_categories": "関連タグ候補に使うカテゴリー",
        "text_watermark": "ウォーターマーク文字列",
        "image_watermark": "ウォーターマーク画像",
        "resize_on_copy": "リサイズ",
        "resize_keeps_aspect": "アスペクト比固定で最大幅・最大高さ内に収めます。",
        "auto_tags_on_copy": "コピー時に付加するタグ",
        "enable": "有効",
        "watermark_text": "文字列",
        "font": "フォント",
        "size": "サイズ",
        "color": "色",
        "outline": "縁取り",
        "outline_size": "縁の大きさ",
        "outline_color": "縁の色",
        "x_position": "X座標",
        "y_position": "Y座標",
        "image_path": "画像ファイル",
        "browse": "参照...",
        "opacity": "透明度",
        "max_width": "最大幅",
        "max_height": "最大高さ",
        "choose_watermark_color": "ウォーターマークの色を選択",
        "choose_watermark_image": "ウォーターマーク画像を選択",
        "image_file_filter": "画像 (*.png *.jpg *.jpeg *.bmp *.gif *.webp *.tif *.tiff)",
        "preview_copy_behavior": "プレビュー",
        "copy_preview_title": "コピープレビュー",
        "copy_preview_unavailable": "プレビューできません",
        "copy_preview_click_hint": "プレビュー上をクリックして座標を設定できます。",
        "remove_tag": "タグを削除",
        "loading": "読み込み中...",
        "updated_at": "更新日時",
        "dimensions": "大きさ",
        "about_text": "Earth Photo Manager",
    },
}

METADATA_LABELS_EN = {
    "撮影日時": "Date taken",
    "プログラム名": "Software",
    "カメラの製造元": "Camera maker",
    "カメラのモデル": "Camera model",
    "絞り値": "Aperture",
    "露出時間": "Exposure time",
    "ISO 速度": "ISO speed",
    "露出補正": "Exposure bias",
    "焦点距離": "Focal length",
    "最大絞り": "Max aperture",
    "測光モード": "Metering mode",
    "対象の距離": "Subject distance",
    "フラッシュ モード": "Flash mode",
    "35mm 焦点距離": "35mm focal length",
    "レンズ メーカー": "Lens maker",
    "レンズ モデル": "Lens model",
    "コントラスト": "Contrast",
    "明るさ": "Brightness",
    "光源": "Light source",
    "露出プログラム": "Exposure program",
    "彩度": "Saturation",
    "鮮明度": "Sharpness",
    "ホワイト バランス": "White balance",
    "デジタル ズーム": "Digital zoom",
    "EXIF バージョン": "EXIF version",
    "大きさ": "Dimensions",
    "幅": "Width",
    "高さ": "Height",
    "ビットの深さ": "Bit depth",
    "圧縮": "Compression",
    "色の表現": "Color representation",
    "水平方向の解像度": "Horizontal resolution",
    "垂直方向の解像度": "Vertical resolution",
    "解像度の単位": "Resolution unit",
    "圧縮ビット/ピクセル": "Compressed bits per pixel",
}


class TagChip(QWidget):
    def __init__(
        self,
        text: str,
        color: str,
        tooltip: str,
        remove_tooltip: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.tag_button = QPushButton(text)
        self.tag_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.tag_button.setToolTip(tooltip)
        self.tag_button.setMinimumHeight(28)
        self.remove_button = QPushButton("x")
        self.remove_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.remove_button.setFixedSize(16, 16)
        self.remove_button.setToolTip(remove_tooltip)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.tag_button)

        self.remove_button.setParent(self)
        self.setMinimumHeight(32)
        self._apply_style(QColor(color))

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self.remove_button.move(self.width() - self.remove_button.width(), 0)

    def _apply_style(self, background: QColor) -> None:
        if not background.isValid():
            background = QColor("#3b82f6")
        text_color = _readable_text_color(background)
        border_color = _chip_border_color(background, text_color)
        remove_text_color = "#111827" if text_color == "#ffffff" else "#ffffff"
        remove_background = text_color
        self.tag_button.setStyleSheet(
            "QPushButton {"
            f"background: {background.name()};"
            f"color: {text_color};"
            f"border: 1px solid {border_color};"
            "border-radius: 14px;"
            "padding: 4px 22px 4px 12px;"
            "font-weight: 600;"
            "}"
            "QPushButton:hover {"
            f"border: 2px solid {border_color};"
            "padding: 3px 21px 3px 11px;"
            "}"
            "QPushButton:pressed {"
            "padding-top: 5px;"
            "padding-bottom: 3px;"
            "}"
        )
        self.remove_button.setStyleSheet(
            "QPushButton {"
            f"background: {remove_background};"
            f"color: {remove_text_color};"
            f"border: 1px solid {border_color};"
            "border-radius: 8px;"
            "font-size: 10px;"
            "font-weight: 700;"
            "padding: 0px;"
            "}"
            "QPushButton:hover {"
            "background: #ef4444;"
            "color: #ffffff;"
            "border: 1px solid #b91c1c;"
            "}"
        )


class NoWheelSpinBox(QSpinBox):
    def wheelEvent(self, event) -> None:  # noqa: N802
        event.ignore()


class NoWheelFontComboBox(QFontComboBox):
    def wheelEvent(self, event) -> None:  # noqa: N802
        event.ignore()


class SettingsDialog(QDialog):
    def __init__(
        self,
        thumbnail_generation_mode: str,
        categories: list[TagCategory],
        tags: list[Tag],
        related_tag_source_category_ids: set[str],
        copy_behavior: CopyBehaviorSettings,
        copy_preview_image_path: Path | None,
        copy_preview_renderer: Callable[[Path, CopyBehaviorSettings], QImage],
        language: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.language = language
        self.copy_preview_image_path = copy_preview_image_path
        self.copy_preview_renderer = copy_preview_renderer
        self.copy_preview_window: CopyBehaviorPreviewWindow | None = None
        self.setWindowModality(Qt.WindowModality.WindowModal)
        self.setWindowTitle(self._tr("settings_title"))
        self.resize(620, 720)
        self.current_watermark_color = copy_behavior.text_watermark_color
        if not QColor(self.current_watermark_color).isValid():
            self.current_watermark_color = "#ffffff"
        self.current_watermark_outline_color = copy_behavior.text_watermark_outline_color
        if not QColor(self.current_watermark_outline_color).isValid():
            self.current_watermark_outline_color = "#111827"

        self.thumbnail_generation_combo = QComboBox()
        self.thumbnail_generation_combo.addItem(
            self._tr("thumbnail_generation_visible"),
            THUMBNAIL_GENERATION_VISIBLE,
        )
        self.thumbnail_generation_combo.addItem(
            self._tr("thumbnail_generation_folder"),
            THUMBNAIL_GENERATION_FOLDER,
        )
        thumbnail_generation_index = self.thumbnail_generation_combo.findData(
            thumbnail_generation_mode
        )
        if thumbnail_generation_index >= 0:
            self.thumbnail_generation_combo.setCurrentIndex(
                thumbnail_generation_index
            )
        self.related_category_checkboxes: dict[str, QCheckBox] = {}
        self.copy_tag_checkboxes: dict[str, QCheckBox] = {}
        self.copy_preview_button = QPushButton(self._tr("preview_copy_behavior"))
        self.copy_preview_button.setEnabled(copy_preview_image_path is not None)
        self.copy_preview_button.clicked.connect(self._show_copy_behavior_preview)

        related_category_panel = QWidget()
        related_category_layout = QVBoxLayout(related_category_panel)
        related_category_layout.setContentsMargins(0, 0, 0, 0)
        for category in categories:
            checkbox = QCheckBox(category.name)
            checkbox.setChecked(category.id in related_tag_source_category_ids)
            self.related_category_checkboxes[category.id] = checkbox
            related_category_layout.addWidget(checkbox)
        related_category_layout.addStretch(1)

        related_category_scroll = QScrollArea()
        related_category_scroll.setWidgetResizable(True)
        related_category_scroll.setWidget(related_category_panel)

        self.text_watermark_enabled_checkbox = QCheckBox(self._tr("enable"))
        self.text_watermark_enabled_checkbox.setChecked(
            copy_behavior.text_watermark_enabled
        )
        self.text_watermark_edit = QLineEdit(copy_behavior.text_watermark_text)
        self.text_watermark_font_combo = NoWheelFontComboBox()
        if copy_behavior.text_watermark_font:
            self.text_watermark_font_combo.setCurrentFont(
                QFont(copy_behavior.text_watermark_font)
            )
        self.text_watermark_size_spin = self._make_spinbox(
            1,
            512,
            copy_behavior.text_watermark_size,
        )
        self.text_watermark_color_button = QPushButton()
        self.text_watermark_color_button.clicked.connect(
            self._choose_watermark_color
        )
        self.text_watermark_opacity_spin = self._make_spinbox(
            0,
            100,
            copy_behavior.text_watermark_opacity,
        )
        self.text_watermark_outline_checkbox = QCheckBox()
        self.text_watermark_outline_checkbox.setChecked(
            copy_behavior.text_watermark_outline
        )
        self.text_watermark_outline_checkbox.toggled.connect(
            self._update_text_watermark_outline_controls
        )
        self.text_watermark_outline_size_spin = self._make_spinbox(
            1,
            128,
            copy_behavior.text_watermark_outline_size,
        )
        self.text_watermark_outline_color_button = QPushButton()
        self.text_watermark_outline_color_button.clicked.connect(
            self._choose_watermark_outline_color
        )
        self.text_watermark_x_spin = self._make_spinbox(
            -100000,
            100000,
            copy_behavior.text_watermark_x,
        )
        self.text_watermark_y_spin = self._make_spinbox(
            -100000,
            100000,
            copy_behavior.text_watermark_y,
        )
        self._apply_watermark_color_button()
        self._apply_watermark_outline_color_button()
        self._update_text_watermark_outline_controls()

        self.image_watermark_enabled_checkbox = QCheckBox(self._tr("enable"))
        self.image_watermark_enabled_checkbox.setChecked(
            copy_behavior.image_watermark_enabled
        )
        self.image_watermark_path_edit = QLineEdit(copy_behavior.image_watermark_path)
        self.image_watermark_browse_button = QPushButton(self._tr("browse"))
        self.image_watermark_browse_button.clicked.connect(
            self._choose_watermark_image
        )
        self.image_watermark_opacity_spin = self._make_spinbox(
            0,
            100,
            copy_behavior.image_watermark_opacity,
        )
        self.image_watermark_x_spin = self._make_spinbox(
            -100000,
            100000,
            copy_behavior.image_watermark_x,
        )
        self.image_watermark_y_spin = self._make_spinbox(
            -100000,
            100000,
            copy_behavior.image_watermark_y,
        )

        self.resize_enabled_checkbox = QCheckBox(self._tr("enable"))
        self.resize_enabled_checkbox.setChecked(copy_behavior.resize_enabled)
        self.resize_max_width_spin = self._make_spinbox(
            1,
            100000,
            copy_behavior.resize_max_width,
        )
        self.resize_max_height_spin = self._make_spinbox(
            1,
            100000,
            copy_behavior.resize_max_height,
        )

        auto_tag_panel = QWidget()
        auto_tag_layout = QVBoxLayout(auto_tag_panel)
        auto_tag_layout.setContentsMargins(0, 0, 0, 0)
        selected_auto_tag_ids = set(copy_behavior.auto_tag_ids or [])
        for tag in tags:
            checkbox = QCheckBox(self._tag_display_name(tag, categories))
            checkbox.setChecked(tag.id in selected_auto_tag_ids)
            self.copy_tag_checkboxes[tag.id] = checkbox
            auto_tag_layout.addWidget(checkbox)
        auto_tag_layout.addStretch(1)
        auto_tag_scroll = QScrollArea()
        auto_tag_scroll.setWidgetResizable(True)
        auto_tag_scroll.setMinimumHeight(120)
        auto_tag_scroll.setWidget(auto_tag_panel)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        general_content = QWidget()
        general_layout = QVBoxLayout(general_content)
        general_layout.addWidget(self._build_thumbnail_settings_group())
        general_layout.addWidget(
            self._build_related_category_settings_group(related_category_scroll)
        )
        general_layout.addStretch(1)

        copy_content = QWidget()
        copy_layout = QVBoxLayout(copy_content)
        copy_layout.addWidget(self._build_copy_behavior_group(auto_tag_scroll))
        copy_layout.addStretch(1)

        tabs = QTabWidget()
        tabs.addTab(self._scroll_widget(general_content), self._tr("general_settings"))
        tabs.addTab(self._scroll_widget(copy_content), self._tr("image_copy_settings"))

        layout = QVBoxLayout(self)
        layout.addWidget(tabs, 1)
        layout.addWidget(buttons)
        self.initial_settings_snapshot = self._settings_snapshot()

    def thumbnail_generation_mode(self) -> str:
        value = self.thumbnail_generation_combo.currentData()
        return str(value) if value else THUMBNAIL_GENERATION_VISIBLE

    def related_tag_source_category_ids(self) -> list[str]:
        return [
            category_id
            for category_id, checkbox in self.related_category_checkboxes.items()
            if checkbox.isChecked()
        ]

    def copy_behavior_settings(self) -> CopyBehaviorSettings:
        return CopyBehaviorSettings(
            text_watermark_enabled=self.text_watermark_enabled_checkbox.isChecked(),
            text_watermark_text=self.text_watermark_edit.text(),
            text_watermark_font=self.text_watermark_font_combo.currentFont().family(),
            text_watermark_size=self.text_watermark_size_spin.value(),
            text_watermark_color=self.current_watermark_color,
            text_watermark_opacity=self.text_watermark_opacity_spin.value(),
            text_watermark_outline=self.text_watermark_outline_checkbox.isChecked(),
            text_watermark_outline_size=self.text_watermark_outline_size_spin.value(),
            text_watermark_outline_color=self.current_watermark_outline_color,
            text_watermark_x=self.text_watermark_x_spin.value(),
            text_watermark_y=self.text_watermark_y_spin.value(),
            image_watermark_enabled=self.image_watermark_enabled_checkbox.isChecked(),
            image_watermark_path=self.image_watermark_path_edit.text().strip(),
            image_watermark_opacity=self.image_watermark_opacity_spin.value(),
            image_watermark_x=self.image_watermark_x_spin.value(),
            image_watermark_y=self.image_watermark_y_spin.value(),
            resize_enabled=self.resize_enabled_checkbox.isChecked(),
            resize_max_width=self.resize_max_width_spin.value(),
            resize_max_height=self.resize_max_height_spin.value(),
            auto_tag_ids=[
                tag_id
                for tag_id, checkbox in self.copy_tag_checkboxes.items()
                if checkbox.isChecked()
            ],
        )

    def _settings_snapshot(self) -> tuple[
        str,
        tuple[str, ...],
        CopyBehaviorSettings,
    ]:
        return (
            self.thumbnail_generation_mode(),
            tuple(self.related_tag_source_category_ids()),
            self.copy_behavior_settings(),
        )

    def _has_unsaved_changes(self) -> bool:
        return self._settings_snapshot() != self.initial_settings_snapshot

    def _confirm_save_unsaved_changes(self) -> QMessageBox.StandardButton:
        return QMessageBox.question(
            self,
            self._tr("save_settings_changes_title"),
            self._tr("save_settings_changes_message"),
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No
            | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Yes,
        )

    def _build_thumbnail_settings_group(self) -> QGroupBox:
        group = QGroupBox(self._tr("thumbnail_settings"))
        form = QFormLayout(group)
        form.addRow(self._tr("thumbnail_generation_mode"), self.thumbnail_generation_combo)
        return group

    @staticmethod
    def _scroll_widget(widget: QWidget) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(widget)
        return scroll

    def _build_related_category_settings_group(
        self,
        related_category_scroll: QScrollArea,
    ) -> QGroupBox:
        group = QGroupBox(self._tr("tag_settings"))
        layout = QVBoxLayout(group)
        layout.addWidget(QLabel(self._tr("related_tag_source_categories")))
        layout.addWidget(related_category_scroll)
        return group

    def _build_copy_behavior_group(self, auto_tag_scroll: QScrollArea) -> QGroupBox:
        group = QGroupBox(self._tr("copy_behavior_settings"))
        layout = QVBoxLayout(group)
        preview_row = QHBoxLayout()
        preview_row.addWidget(self.copy_preview_button)
        preview_row.addStretch(1)
        layout.addLayout(preview_row)
        preview_hint = QLabel(self._tr("copy_preview_click_hint"))
        preview_hint.setWordWrap(True)
        layout.addWidget(preview_hint)
        layout.addWidget(self._build_text_watermark_group())
        layout.addWidget(self._build_image_watermark_group())
        layout.addWidget(self._build_resize_group())
        layout.addWidget(self._build_auto_tags_group(auto_tag_scroll))
        return group

    def _build_text_watermark_group(self) -> QGroupBox:
        group = QGroupBox(self._tr("text_watermark"))
        form = QFormLayout(group)
        form.addRow("", self.text_watermark_enabled_checkbox)
        form.addRow(self._tr("watermark_text"), self.text_watermark_edit)
        form.addRow(self._tr("font"), self.text_watermark_font_combo)
        form.addRow(self._tr("size"), self.text_watermark_size_spin)
        form.addRow(self._tr("color"), self.text_watermark_color_button)
        form.addRow(self._tr("opacity"), self.text_watermark_opacity_spin)
        form.addRow(self._tr("outline"), self.text_watermark_outline_checkbox)
        form.addRow(self._tr("outline_size"), self.text_watermark_outline_size_spin)
        form.addRow(self._tr("outline_color"), self.text_watermark_outline_color_button)
        form.addRow(self._tr("x_position"), self.text_watermark_x_spin)
        form.addRow(self._tr("y_position"), self.text_watermark_y_spin)
        return group

    def _build_image_watermark_group(self) -> QGroupBox:
        group = QGroupBox(self._tr("image_watermark"))
        form = QFormLayout(group)
        path_row = QHBoxLayout()
        path_row.addWidget(self.image_watermark_path_edit, 1)
        path_row.addWidget(self.image_watermark_browse_button)
        form.addRow("", self.image_watermark_enabled_checkbox)
        form.addRow(self._tr("image_path"), path_row)
        form.addRow(self._tr("opacity"), self.image_watermark_opacity_spin)
        form.addRow(self._tr("x_position"), self.image_watermark_x_spin)
        form.addRow(self._tr("y_position"), self.image_watermark_y_spin)
        return group

    def _build_resize_group(self) -> QGroupBox:
        group = QGroupBox(self._tr("resize_on_copy"))
        form = QFormLayout(group)
        resize_note = QLabel(self._tr("resize_keeps_aspect"))
        resize_note.setWordWrap(True)
        form.addRow("", self.resize_enabled_checkbox)
        form.addRow("", resize_note)
        form.addRow(self._tr("max_width"), self.resize_max_width_spin)
        form.addRow(self._tr("max_height"), self.resize_max_height_spin)
        return group

    def _build_auto_tags_group(self, auto_tag_scroll: QScrollArea) -> QGroupBox:
        group = QGroupBox(self._tr("auto_tags_on_copy"))
        layout = QVBoxLayout(group)
        layout.addWidget(auto_tag_scroll)
        return group

    def _choose_watermark_color(self) -> None:
        color = QColorDialog.getColor(
            QColor(self.current_watermark_color),
            self,
            self._tr("choose_watermark_color"),
        )
        if color.isValid():
            self.current_watermark_color = color.name()
            self._apply_watermark_color_button()

    def _choose_watermark_outline_color(self) -> None:
        color = QColorDialog.getColor(
            QColor(self.current_watermark_outline_color),
            self,
            self._tr("choose_watermark_color"),
        )
        if color.isValid():
            self.current_watermark_outline_color = color.name()
            self._apply_watermark_outline_color_button()

    def _choose_watermark_image(self) -> None:
        path, _selected_filter = QFileDialog.getOpenFileName(
            self,
            self._tr("choose_watermark_image"),
            self.image_watermark_path_edit.text(),
            self._tr("image_file_filter"),
        )
        if path:
            self.image_watermark_path_edit.setText(path)

    def _apply_watermark_color_button(self) -> None:
        self.text_watermark_color_button.setText(self.current_watermark_color)
        self.text_watermark_color_button.setStyleSheet(
            f"background: {self.current_watermark_color};"
            f"color: {_readable_text_color(QColor(self.current_watermark_color))};"
        )

    def _apply_watermark_outline_color_button(self) -> None:
        self.text_watermark_outline_color_button.setText(
            self.current_watermark_outline_color
        )
        self.text_watermark_outline_color_button.setStyleSheet(
            f"background: {self.current_watermark_outline_color};"
            "color: "
            f"{_readable_text_color(QColor(self.current_watermark_outline_color))};"
        )

    def _update_text_watermark_outline_controls(self) -> None:
        enabled = self.text_watermark_outline_checkbox.isChecked()
        self.text_watermark_outline_size_spin.setEnabled(enabled)
        self.text_watermark_outline_color_button.setEnabled(enabled)

    @staticmethod
    def _make_spinbox(minimum: int, maximum: int, value: int) -> QSpinBox:
        spinbox = NoWheelSpinBox()
        spinbox.setRange(minimum, maximum)
        spinbox.setValue(max(minimum, min(maximum, value)))
        return spinbox

    @staticmethod
    def _tag_display_name(tag: Tag, categories: list[TagCategory]) -> str:
        category = next(
            (category for category in categories if category.id == tag.category_id),
            None,
        )
        if category is None:
            return tag.name
        return f"{category.name}: {tag.name}"

    def _show_copy_behavior_preview(self) -> None:
        if self.copy_preview_image_path is None:
            return
        preview_image = self.copy_preview_renderer(
            self.copy_preview_image_path,
            self.copy_behavior_settings(),
        )
        if self.copy_preview_window is None:
            self.copy_preview_window = CopyBehaviorPreviewWindow(
                self._tr("copy_preview_title"),
                self,
            )
            self.copy_preview_window.coordinate_selected.connect(
                self._set_watermark_coordinate_from_preview
            )
            self.copy_preview_window.destroyed.connect(
                self._on_copy_preview_window_destroyed
            )
        self._set_copy_preview_image(preview_image)
        self.copy_preview_window.show()
        self.copy_preview_window.raise_()

    def _set_copy_preview_image(self, preview_image: QImage) -> None:
        if self.copy_preview_window is None:
            return
        if preview_image.isNull():
            self.copy_preview_window.set_unavailable(
                self._tr("copy_preview_unavailable")
            )
        else:
            self.copy_preview_window.set_image(preview_image)

    def _refresh_copy_behavior_preview(self) -> None:
        if (
            self.copy_preview_window is None
            or self.copy_preview_image_path is None
        ):
            return
        self._set_copy_preview_image(
            self.copy_preview_renderer(
                self.copy_preview_image_path,
                self.copy_behavior_settings(),
            )
        )

    def _set_watermark_coordinate_from_preview(self, x: int, y: int) -> None:
        target = self._preview_coordinate_target(x, y)
        if target == "image":
            self.image_watermark_x_spin.setValue(x)
            self.image_watermark_y_spin.setValue(y)
        elif target == "text":
            self.text_watermark_x_spin.setValue(x)
            self.text_watermark_y_spin.setValue(y)
        else:
            return
        self._refresh_copy_behavior_preview()

    def _preview_coordinate_target(self, x: int, y: int) -> str | None:
        text_enabled = (
            self.text_watermark_enabled_checkbox.isChecked()
            and bool(self.text_watermark_edit.text().strip())
        )
        image_enabled = (
            self.image_watermark_enabled_checkbox.isChecked()
            and bool(self.image_watermark_path_edit.text().strip())
        )
        if text_enabled and not image_enabled:
            return "text"
        if image_enabled and not text_enabled:
            return "image"
        if not text_enabled and not image_enabled:
            return None

        text_distance = (
            (x - self.text_watermark_x_spin.value()) ** 2
            + (y - self.text_watermark_y_spin.value()) ** 2
        )
        image_distance = (
            (x - self.image_watermark_x_spin.value()) ** 2
            + (y - self.image_watermark_y_spin.value()) ** 2
        )
        return "text" if text_distance <= image_distance else "image"

    def _on_copy_preview_window_destroyed(self, *_args: object) -> None:
        self.copy_preview_window = None

    def done(self, result: int) -> None:
        if result == QDialog.DialogCode.Rejected and self._has_unsaved_changes():
            choice = self._confirm_save_unsaved_changes()
            if choice == QMessageBox.StandardButton.Cancel:
                return
            if choice == QMessageBox.StandardButton.Yes:
                result = QDialog.DialogCode.Accepted

        self._close_copy_preview_window()
        super().done(result)

    def closeEvent(self, event) -> None:  # noqa: N802
        super().closeEvent(event)

    def _close_copy_preview_window(self) -> None:
        if self.copy_preview_window is not None:
            preview_window = self.copy_preview_window
            self.copy_preview_window = None
            preview_window.close()

    def _tr(self, key: str, **values: object) -> str:
        text = TRANSLATIONS.get(self.language, TRANSLATIONS["en"]).get(
            key, TRANSLATIONS["en"].get(key, key)
        )
        return text.format(**values) if values else text


class CopyBehaviorPreviewLabel(QLabel):
    image_clicked = Signal(int, int)

    def __init__(self) -> None:
        super().__init__()
        self._image: QImage | None = None
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(360, 260)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setStyleSheet("background: #202124; color: #d7dce2;")

    def set_image(self, image: QImage) -> None:
        self._image = QImage(image)
        self.setText("")
        self._fit_image()

    def set_unavailable(self, text: str) -> None:
        self._image = None
        self.setPixmap(QPixmap())
        self.setText(text)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._fit_image()

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if (
            event.button() != Qt.MouseButton.LeftButton
            or self._image is None
            or self._image.isNull()
        ):
            super().mousePressEvent(event)
            return

        image_point = self._widget_point_to_image_point(event.position().toPoint())
        if image_point is None:
            super().mousePressEvent(event)
            return
        self.image_clicked.emit(image_point.x(), image_point.y())
        event.accept()

    def _fit_image(self) -> None:
        if self._image is None or self._image.isNull():
            return
        pixmap = QPixmap.fromImage(self._image).scaled(
            self.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.setPixmap(pixmap)

    def _widget_point_to_image_point(self, point: QPoint) -> QPoint | None:
        if self._image is None or self._image.isNull():
            return None
        displayed_size = self._image.size().scaled(
            self.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
        )
        left = (self.width() - displayed_size.width()) // 2
        top = (self.height() - displayed_size.height()) // 2
        image_rect = QRect(left, top, displayed_size.width(), displayed_size.height())
        if not image_rect.contains(point):
            return None

        x = int((point.x() - left) * self._image.width() / displayed_size.width())
        y = int((point.y() - top) * self._image.height() / displayed_size.height())
        return QPoint(
            max(0, min(self._image.width() - 1, x)),
            max(0, min(self._image.height() - 1, y)),
        )


class CopyBehaviorPreviewWindow(QMainWindow):
    coordinate_selected = Signal(int, int)

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent, Qt.WindowType.Window)
        self.setWindowTitle(title)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.resize(900, 650)
        self.preview = CopyBehaviorPreviewLabel()
        self.preview.image_clicked.connect(
            lambda x, y: self.coordinate_selected.emit(x, y)
        )
        self.setCentralWidget(self.preview)

    def set_image(self, image: QImage) -> None:
        self.preview.set_image(image)

    def set_unavailable(self, text: str) -> None:
        self.preview.set_unavailable(text)


class FileListWidget(QListWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._range_selection_anchor_row: int | None = None
        self._handled_shift_click = False

    def mousePressEvent(self, event) -> None:  # noqa: N802
        item = self.itemAt(event.position().toPoint())
        if event.button() == Qt.MouseButton.LeftButton and item is not None:
            row = self.row(item)
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                keep_existing = bool(
                    event.modifiers() & Qt.KeyboardModifier.ControlModifier
                )
                self._select_contiguous_range(row, keep_existing=keep_existing)
                self._handled_shift_click = True
                event.accept()
                return
            self._range_selection_anchor_row = row

        self._handled_shift_click = False
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._handled_shift_click:
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if self._handled_shift_click:
            self._handled_shift_click = False
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def _select_contiguous_range(self, target_row: int, keep_existing: bool) -> None:
        anchor_row = self._range_selection_anchor_row
        if anchor_row is None or not 0 <= anchor_row < self.count():
            current = self.currentRow()
            anchor_row = current if current >= 0 else target_row

        start_row = min(anchor_row, target_row)
        end_row = max(anchor_row, target_row)
        if not keep_existing:
            self.clearSelection()
        for row in range(start_row, end_row + 1):
            item = self.item(row)
            if item is not None:
                item.setSelected(True)
        target_item = self.item(target_row)
        if target_item is not None:
            self.setCurrentItem(target_item, QItemSelectionModel.SelectionFlag.NoUpdate)

    def reset_range_selection_anchor(self) -> None:
        self._range_selection_anchor_row = None
        self._handled_shift_click = False


def _readable_text_color(color: QColor) -> str:
    luminance = (
        0.299 * color.red()
        + 0.587 * color.green()
        + 0.114 * color.blue()
    )
    return "#111827" if luminance >= 150 else "#ffffff"


def _chip_border_color(color: QColor, text_color: str) -> str:
    if text_color == "#ffffff":
        lighter = color.lighter(135)
        return lighter.name()
    darker = color.darker(145)
    return darker.name()


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.resize(1280, 820)

        self.settings = AppSettings()
        self.language = self.settings.language()
        self.thumbnail_generation_mode = self.settings.thumbnail_generation_mode()
        self.tag_store = TagStore(self.settings.tag_database_path())
        self.related_tag_source_category_ids = (
            self.settings.related_tag_source_category_ids()
        )
        self.roots = self.settings.root_folders()
        self.thumbnail_executor = ThreadPoolExecutor(max_workers=THUMBNAIL_WORKER_COUNT)
        self.images: list[ImageFile] = []
        self.file_items_by_path: dict[str, QListWidgetItem] = {}
        self.include_filter_tag_ids: list[str] = []
        self.exclude_filter_tag_ids: list[str] = []
        self.current_folder: Path | None = None
        self.restore_selected_image_path = self.settings.selected_image_path()
        self.thumbnail_cache = ThumbnailCache(QSize(160, 120))
        self.thumbnail_queue: deque[Path] = deque()
        self.thumbnail_queued_paths: set[str] = set()
        self.thumbnail_futures: dict[Future, str] = {}
        self.thumbnail_paths_by_source: dict[str, str] = {}
        self.thumbnail_applied_paths_by_source: dict[str, str | None] = {}
        self.thumbnail_icon_cache: OrderedDict[
            tuple[str, str, tuple[str, ...]], QIcon
        ] = OrderedDict()
        self.related_tag_candidates_cache: list[Tag] | None = None
        self.thumbnail_poll_timer = QTimer(self)
        self.thumbnail_poll_timer.setInterval(THUMBNAIL_POLL_INTERVAL_MS)
        self.thumbnail_poll_timer.timeout.connect(self._poll_thumbnail_futures)
        self.pending_thumbnail_updates: dict[str, str] = {}
        self.thumbnail_update_timer = QTimer(self)
        self.thumbnail_update_timer.setInterval(THUMBNAIL_UI_UPDATE_INTERVAL_MS)
        self.thumbnail_update_timer.timeout.connect(self._flush_thumbnail_updates)
        self.thumbnail_visible_priority_timer = QTimer(self)
        self.thumbnail_visible_priority_timer.setSingleShot(True)
        self.thumbnail_visible_priority_timer.setInterval(
            THUMBNAIL_VISIBLE_PRIORITY_DELAY_MS
        )
        self.thumbnail_visible_priority_timer.timeout.connect(
            self._prioritize_visible_thumbnails
        )
        self.preview_window: PreviewWindow | None = None
        self.placeholder_icon = QIcon(self._make_placeholder_thumbnail())
        self.folder_label = QLabel()
        self.tag_filter_label = QLabel()
        self.include_filter_label = QLabel()
        self.exclude_filter_label = QLabel()
        self.tags_label = QLabel()
        self.information_label = QLabel()
        self.add_folder_button = QPushButton()
        self.remove_folder_button = QPushButton()
        self.copy_image_button = QPushButton()
        self.copy_image_button.clicked.connect(self._copy_current_image_to_clipboard)

        self.folder_tree = QTreeWidget()
        self.folder_tree.setHeaderHidden(True)
        self.folder_tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.folder_tree.currentItemChanged.connect(self._on_current_folder_changed)
        self.folder_tree.itemExpanded.connect(self._load_tree_item_children)
        self.folder_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.folder_tree.customContextMenuRequested.connect(
            self._open_folder_context_menu
        )

        self.file_list = FileListWidget()
        self.file_list.setViewMode(QListWidget.ViewMode.IconMode)
        self.file_list.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.file_list.setMovement(QListWidget.Movement.Static)
        self.file_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.file_list.setIconSize(QSize(160, 120))
        self.file_list.setGridSize(QSize(190, 168))
        self.file_list.setSpacing(8)
        self.file_list.setUniformItemSizes(True)
        self.file_list.setStyleSheet(
            """
            QListWidget {
                background: #ffffff;
                outline: 0;
            }
            QListWidget::item {
                border: 3px solid transparent;
                border-radius: 4px;
                padding: 6px;
                color: #1f2933;
            }
            QListWidget::item:selected {
                background: #d9ecff;
                border: 3px solid #0078d4;
                color: #001f33;
            }
            QListWidget::item:selected:active,
            QListWidget::item:selected:!active {
                background: #d9ecff;
                border: 3px solid #0078d4;
                color: #001f33;
            }
            QListWidget::item:hover {
                background: #eef6ff;
                border: 3px solid #8cc8ff;
            }
            """
        )
        self.file_list.currentItemChanged.connect(self._on_current_file_changed)
        self.file_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.file_list.customContextMenuRequested.connect(self._open_file_context_menu)
        self.file_list.verticalScrollBar().valueChanged.connect(
            self._schedule_visible_thumbnail_priority
        )

        self.include_filter_combo = QComboBox()
        self.include_filter_combo.setMinimumWidth(180)
        self.include_filter_combo.activated.connect(self._add_include_filter_tag)
        self.exclude_filter_combo = QComboBox()
        self.exclude_filter_combo.setMinimumWidth(180)
        self.exclude_filter_combo.activated.connect(self._add_exclude_filter_tag)
        self.clear_include_filter_button = QPushButton()
        self.clear_include_filter_button.clicked.connect(self._clear_include_filter_tags)
        self.clear_exclude_filter_button = QPushButton()
        self.clear_exclude_filter_button.clicked.connect(self._clear_exclude_filter_tags)
        self.clear_all_filter_button = QPushButton()
        self.clear_all_filter_button.clicked.connect(self._clear_all_filter_tags)
        self.include_filter_chip_container = QWidget()
        self.include_filter_chip_layout = FlowLayout(
            self.include_filter_chip_container,
            margin=2,
            spacing=4,
        )
        self.exclude_filter_chip_container = QWidget()
        self.exclude_filter_chip_layout = FlowLayout(
            self.exclude_filter_chip_container,
            margin=2,
            spacing=4,
        )

        self.preview = ImagePreviewLabel()
        self.preview.navigate_requested.connect(self._move_current_file)
        self.tag_chip_scroll = QScrollArea()
        self.tag_chip_scroll.setWidgetResizable(True)
        self.tag_chip_scroll.setMinimumHeight(52)
        self.tag_chip_scroll.setMaximumHeight(116)
        self.tag_chip_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.tag_chip_scroll.setStyleSheet(
            """
            QScrollArea {
                background: #ffffff;
                border: 1px solid #d0d5dd;
                border-radius: 4px;
            }
            """
        )
        self.tag_chip_container = QWidget()
        self.tag_chip_layout = FlowLayout(self.tag_chip_container, margin=6, spacing=6)
        self.tag_chip_scroll.setWidget(self.tag_chip_container)
        self.add_related_tag_combo = QComboBox()
        self.add_related_tag_combo.setMinimumWidth(180)
        self.add_related_tag_combo.activated.connect(
            self._add_selected_related_tag_to_current_image
        )
        self.add_tag_combo = QComboBox()
        self.add_tag_combo.setMinimumWidth(180)
        self.add_tag_combo.activated.connect(self._add_selected_tag_to_current_image)
        self.info_table = QTableWidget(0, 2)
        self.info_table.verticalHeader().hide()
        self.info_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self.info_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self.info_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.info_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)

        self.status = QLabel()
        self.status.setWordWrap(False)
        self.status.setMinimumWidth(0)
        self.status.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.status.setFixedHeight(
            self.status.fontMetrics().height() + STATUS_BAR_VERTICAL_PADDING
        )
        self.status.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)

        self._build_ui()
        self._retranslate_ui()
        self._refresh_folder_tree()
        self._resume_pending_thumbnails()

    def _build_ui(self) -> None:
        self._build_menu_bar()

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(8, 8, 8, 8)
        left_layout.addWidget(self.folder_label)
        left_layout.addWidget(self.folder_tree)

        button_row = QHBoxLayout()
        self.add_folder_button.clicked.connect(self.add_root_folder)
        self.remove_folder_button.clicked.connect(self.remove_selected_root)
        button_row.addWidget(self.add_folder_button)
        button_row.addWidget(self.remove_folder_button)
        left_layout.addLayout(button_row)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(8, 8, 8, 8)
        right_layout.addWidget(self.preview, 3)
        copy_row = QHBoxLayout()
        copy_row.addStretch(1)
        copy_row.addWidget(self.copy_image_button)
        right_layout.addLayout(copy_row)
        right_layout.addWidget(self.tags_label)
        related_tag_control_row = QHBoxLayout()
        related_tag_control_row.addWidget(self.add_related_tag_combo, 1)
        right_layout.addLayout(related_tag_control_row)
        tag_control_row = QHBoxLayout()
        tag_control_row.addWidget(self.add_tag_combo, 1)
        right_layout.addLayout(tag_control_row)
        right_layout.addWidget(self.tag_chip_scroll)
        right_layout.addWidget(self.information_label)
        right_layout.addWidget(self.info_table, 2)

        file_panel = QWidget()
        file_layout = QVBoxLayout(file_panel)
        file_layout.setContentsMargins(0, 0, 0, 0)
        file_layout.setSpacing(6)

        filter_panel = QWidget()
        filter_layout = QVBoxLayout(filter_panel)
        filter_layout.setContentsMargins(6, 6, 6, 2)
        filter_layout.setSpacing(4)
        filter_layout.addWidget(self.tag_filter_label)

        include_row = QHBoxLayout()
        include_row.addWidget(self.include_filter_label)
        include_row.addWidget(self.include_filter_combo, 1)
        include_row.addWidget(self.clear_include_filter_button)
        filter_layout.addLayout(include_row)
        filter_layout.addWidget(self.include_filter_chip_container)

        exclude_row = QHBoxLayout()
        exclude_row.addWidget(self.exclude_filter_label)
        exclude_row.addWidget(self.exclude_filter_combo, 1)
        exclude_row.addWidget(self.clear_exclude_filter_button)
        exclude_row.addWidget(self.clear_all_filter_button)
        filter_layout.addLayout(exclude_row)
        filter_layout.addWidget(self.exclude_filter_chip_container)

        file_layout.addWidget(filter_panel)
        file_layout.addWidget(self.file_list, 1)

        self.center_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.center_splitter.addWidget(file_panel)
        self.center_splitter.addWidget(right_panel)
        self.center_splitter.setSizes([720, 420])

        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.main_splitter.addWidget(left_panel)
        self.main_splitter.addWidget(self.center_splitter)
        self.main_splitter.setSizes([260, 1000])

        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.main_splitter)
        layout.addWidget(self.status)
        self.setCentralWidget(root)
        self._reload_add_tag_combo()
        self._reload_filter_tag_combos()
        self._refresh_filter_chips()
        self._refresh_current_image_tags()
        self._restore_window_layout()

    def _build_menu_bar(self) -> None:
        self.file_menu = self.menuBar().addMenu("")
        self.settings_action = QAction(self)
        self.settings_action.triggered.connect(self.open_settings)
        self.file_menu.addAction(self.settings_action)
        self.file_menu.addSeparator()
        self.exit_action = QAction(self)
        self.exit_action.triggered.connect(self.close)
        self.file_menu.addAction(self.exit_action)

        self.view_menu = self.menuBar().addMenu("")
        self.preview_window_action = QAction(self)
        self.preview_window_action.triggered.connect(self.open_preview_window)
        self.view_menu.addAction(self.preview_window_action)

        self.tag_menu = self.menuBar().addMenu("")
        self.tag_menu.aboutToShow.connect(self._rebuild_tag_menu)

        self.language_menu = self.menuBar().addMenu("")
        self.language_group = QActionGroup(self)
        self.language_group.setExclusive(True)
        self.japanese_action = QAction(self)
        self.japanese_action.setCheckable(True)
        self.japanese_action.setData("ja")
        self.english_action = QAction(self)
        self.english_action.setCheckable(True)
        self.english_action.setData("en")
        self.language_group.addAction(self.japanese_action)
        self.language_group.addAction(self.english_action)
        self.japanese_action.triggered.connect(lambda: self._set_language("ja"))
        self.english_action.triggered.connect(lambda: self._set_language("en"))
        self.language_menu.addAction(self.japanese_action)
        self.language_menu.addAction(self.english_action)

        self.help_menu = self.menuBar().addMenu("")
        self.about_action = QAction(self)
        self.about_action.triggered.connect(self._show_about)
        self.help_menu.addAction(self.about_action)

    def _rebuild_tag_menu(self) -> None:
        self.tag_menu.clear()
        images = self._selected_images()
        related_tag_menu = self.tag_menu.addMenu(self._tr("add_related_tag"))
        related_tags = self._related_tag_candidates_for_current_folder()
        related_tag_menu.setEnabled(bool(images) and bool(related_tags))
        if images:
            self._populate_flat_tag_menu(related_tag_menu, related_tags, images)

        tag_menu = self.tag_menu.addMenu(self._tr("add_tag"))
        tag_menu.setEnabled(bool(images) and bool(self.tag_store.tags))
        if images:
            self._populate_tag_menu(tag_menu, images)

        self.tag_menu.addSeparator()
        manage_action = self.tag_menu.addAction(self._tr("manage_tags"))
        manage_action.triggered.connect(self.open_tag_manager)

    def open_settings(self) -> None:
        current_image = self._current_image()
        dialog = SettingsDialog(
            self.thumbnail_generation_mode,
            self.tag_store.categories,
            self.tag_store.tags,
            self._effective_related_tag_source_category_ids(),
            self.settings.copy_behavior(),
            current_image.path if current_image is not None else None,
            self._copy_preview_image_for_settings,
            self.language,
            self,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        thumbnail_generation_mode = dialog.thumbnail_generation_mode()
        if thumbnail_generation_mode != self.thumbnail_generation_mode:
            self.thumbnail_generation_mode = thumbnail_generation_mode
            self.settings.set_thumbnail_generation_mode(thumbnail_generation_mode)
            self._restart_thumbnail_loading_for_current_mode()
        self.related_tag_source_category_ids = (
            dialog.related_tag_source_category_ids()
        )
        self.settings.set_related_tag_source_category_ids(
            self.related_tag_source_category_ids
        )
        self.settings.set_copy_behavior(dialog.copy_behavior_settings())
        self.related_tag_candidates_cache = None
        self._reload_add_related_tag_combo()

    def _copy_preview_image_for_settings(
        self,
        image_path: Path,
        copy_behavior: CopyBehaviorSettings,
    ) -> QImage:
        reader = QImageReader(str(image_path))
        reader.setAutoTransform(True)
        image = reader.read()
        if image.isNull():
            return QImage()
        return self._apply_copy_behavior_to_image(image, copy_behavior)

    def _set_language(self, language: str) -> None:
        if language == self.language:
            return
        self.language = language
        self.settings.set_language(language)
        self._retranslate_ui()
        self._reload_add_tag_combo()
        self._refresh_current_image_tags()
        current = self._current_image()
        if current is not None:
            self._show_info(current.path, current.root)
        else:
            self._set_info_rows([])
        if self.current_folder is not None:
            self._update_thumbnail_status()
        else:
            self.status.setText(self._tr("add_root_prompt"))

    def _retranslate_ui(self) -> None:
        self.setWindowTitle(self._tr("app_title"))
        self.file_menu.setTitle(self._tr("file"))
        self.view_menu.setTitle(self._tr("view"))
        self.preview_window_action.setText(self._tr("preview_window"))
        self.tag_menu.setTitle(self._tr("tag"))
        self.language_menu.setTitle(self._tr("language"))
        self.help_menu.setTitle(self._tr("help"))
        self.settings_action.setText(self._tr("settings"))
        self.exit_action.setText(self._tr("exit"))
        self.japanese_action.setText(self._tr("japanese"))
        self.english_action.setText(self._tr("english"))
        self.japanese_action.setChecked(self.language == "ja")
        self.english_action.setChecked(self.language == "en")
        self.about_action.setText(self._tr("about"))
        self.folder_label.setText(self._tr("folders"))
        self.copy_image_button.setText(self._tr("copy_image"))
        self.tag_filter_label.setText(self._tr("tag_filters"))
        self.include_filter_label.setText(self._tr("include_tags"))
        self.exclude_filter_label.setText(self._tr("exclude_tags"))
        self.tags_label.setText(self._tr("tags"))
        self.information_label.setText(self._tr("information"))
        self.add_folder_button.setText(self._tr("add"))
        self.remove_folder_button.setText(self._tr("remove"))
        self.clear_include_filter_button.setText(self._tr("clear_include_tags"))
        self.clear_exclude_filter_button.setText(self._tr("clear_exclude_tags"))
        self.clear_all_filter_button.setText(self._tr("clear_all_tag_filters"))
        self.info_table.setHorizontalHeaderLabels([self._tr("item"), self._tr("value")])
        self._reload_filter_tag_combos()
        self._refresh_filter_chips()
        if not self.status.text():
            self.status.setText(self._tr("ready"))

    def _show_about(self) -> None:
        QMessageBox.about(self, self._tr("about"), self._tr("about_text"))

    def _tr(self, key: str, **values: object) -> str:
        text = TRANSLATIONS.get(self.language, TRANSLATIONS["en"]).get(
            key, TRANSLATIONS["en"].get(key, key)
        )
        return text.format(**values) if values else text

    def _begin_busy_operation(self, message: str) -> None:
        self.status.setText(message)
        self.status.repaint()
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        QApplication.processEvents()

    @staticmethod
    def _end_busy_operation() -> None:
        QApplication.restoreOverrideCursor()
        QApplication.processEvents()

    def add_root_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, self._tr("select_root_folder"))
        if not folder:
            return

        path = Path(folder).expanduser().resolve()
        if path not in self.roots:
            self.roots.append(path)
            self.settings.set_root_folders(self.roots)
            self._refresh_folder_tree(select_path=path)

    def remove_selected_root(self) -> None:
        item = self.folder_tree.currentItem()
        if item is None:
            return
        root_value = item.data(0, Qt.ItemDataRole.UserRole + 1)
        if not root_value:
            return
        root = Path(root_value)
        self.roots = [registered for registered in self.roots if registered != root]
        self.settings.set_root_folders(self.roots)
        self._refresh_folder_tree()

    def refresh_current_folder(self) -> None:
        item = self.folder_tree.currentItem()
        if item is not None:
            folder_value = item.data(0, Qt.ItemDataRole.UserRole)
            if not folder_value:
                return
            item.setData(0, Qt.ItemDataRole.UserRole + 2, False)
            self._clear_tree_item_children(item)
            self._add_placeholder_if_needed(item, Path(folder_value))
            self._load_tree_item_children(item)
        self.load_folder_images(self.current_folder)

    def open_tag_manager(self) -> None:
        dialog = TagManagerDialog(self.tag_store, self.language, self)
        dialog.exec()
        self.related_tag_candidates_cache = None
        self.thumbnail_icon_cache.clear()
        valid_tag_ids = {tag.id for tag in self.tag_store.tags}
        valid_category_ids = {category.id for category in self.tag_store.categories}
        if self.related_tag_source_category_ids is not None:
            self.related_tag_source_category_ids = [
                category_id
                for category_id in self.related_tag_source_category_ids
                if category_id in valid_category_ids
            ]
            self.settings.set_related_tag_source_category_ids(
                self.related_tag_source_category_ids
            )
        self.include_filter_tag_ids = [
            tag_id for tag_id in self.include_filter_tag_ids if tag_id in valid_tag_ids
        ]
        self.exclude_filter_tag_ids = [
            tag_id for tag_id in self.exclude_filter_tag_ids if tag_id in valid_tag_ids
        ]
        self._reload_add_tag_combo()
        self._reload_filter_tag_combos()
        self._refresh_filter_chips()
        self._apply_tag_filters()
        self._refresh_current_image_tags()
        self._refresh_all_file_item_icons()

    def _open_file_context_menu(self, position: QPoint) -> None:
        item = self.file_list.itemAt(position)
        if item is None:
            return
        clicked_image = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(clicked_image, ImageFile):
            return
        if not item.isSelected():
            self.file_list.clearSelection()
            item.setSelected(True)
            self.file_list.setCurrentItem(item)

        images = self._selected_images()
        if not images:
            return

        menu = self._make_image_context_menu(
            images,
            self._related_tag_candidates_for_current_folder(),
            copy_image=clicked_image,
        )
        menu.exec(self.file_list.viewport().mapToGlobal(position))

    def _open_folder_context_menu(self, position: QPoint) -> None:
        item = self.folder_tree.itemAt(position)
        if item is None:
            return

        folder_value = item.data(0, Qt.ItemDataRole.UserRole)
        root_value = item.data(0, Qt.ItemDataRole.UserRole + 1)
        if not folder_value or not root_value:
            return

        self.folder_tree.setCurrentItem(item)
        folder = Path(folder_value)
        root = Path(root_value)
        try:
            images = [
                ImageFile(path=path, root=root)
                for path in self._image_paths_in_folder(folder)
            ]
        except OSError as exc:
            self.status.setText(self._tr("cannot_open_folder", error=exc))
            images = []

        menu = self._make_image_context_menu(
            images,
            self._related_tag_candidates_for_images(images),
        )
        menu.exec(self.folder_tree.viewport().mapToGlobal(position))

    def _make_image_context_menu(
        self,
        images: list[ImageFile],
        related_tags: list[Tag],
        copy_image: ImageFile | None = None,
    ) -> QMenu:
        menu = QMenu(self)
        if copy_image is not None:
            copy_action = menu.addAction(self._tr("copy_image"))
            copy_action.triggered.connect(
                lambda _checked=False, image=copy_image: (
                    self._copy_image_to_clipboard(image)
                )
            )
            menu.addSeparator()
        related_tag_menu = menu.addMenu(self._tr("add_related_tag"))
        related_tag_menu.setEnabled(bool(images) and bool(related_tags))
        self._populate_flat_tag_menu(related_tag_menu, related_tags, images)
        tag_menu = menu.addMenu(self._tr("add_tag"))
        tag_menu.setEnabled(bool(images) and bool(self.tag_store.tags))
        self._populate_tag_menu(tag_menu, images)
        clear_tags_action = menu.addAction(self._tr("clear_assigned_tags"))
        clear_tags_action.setEnabled(self._images_have_assigned_tags(images))
        clear_tags_action.triggered.connect(
            lambda _checked=False, target_images=images: (
                self._clear_tags_from_images(target_images)
            )
        )
        menu.addSeparator()
        manage_action = menu.addAction(self._tr("manage_tags"))
        manage_action.triggered.connect(self.open_tag_manager)
        return menu

    def _populate_tag_menu(self, menu: QMenu, images: list[ImageFile]) -> None:
        uncategorized_tags = sorted(
            [tag for tag in self.tag_store.tags if tag.category_id is None],
            key=lambda tag: tag.name,
        )
        for tag in uncategorized_tags:
            action = menu.addAction(tag.name)
            self._apply_tag_action_style(action, tag)
            action.triggered.connect(
                lambda _checked=False, selected_tag=tag: (
                    self._add_tag_to_images(selected_tag, images)
                )
            )

        if uncategorized_tags and self.tag_store.categories:
            menu.addSeparator()

        for category in self.tag_store.categories:
            tags = sorted(
                self.tag_store.tags_for_category(category.id),
                key=lambda tag: tag.name,
            )
            if not tags:
                continue
            category_menu = menu.addMenu(category.name)
            for tag in tags:
                action = category_menu.addAction(tag.name)
                self._apply_tag_action_style(action, tag)
                action.triggered.connect(
                    lambda _checked=False, selected_tag=tag: (
                        self._add_tag_to_images(selected_tag, images)
                    )
                )

    def _populate_flat_tag_menu(
        self, menu: QMenu, tags: list[Tag], images: list[ImageFile]
    ) -> None:
        for tag in tags:
            action = menu.addAction(self._tag_display_name(tag))
            self._apply_tag_action_style(action, tag)
            action.triggered.connect(
                lambda _checked=False, selected_tag=tag: (
                    self._add_tag_to_images(selected_tag, images)
                )
            )

    def _images_have_assigned_tags(self, images: list[ImageFile]) -> bool:
        return any(self.tag_store.image_tag_ids(image.path) for image in images)

    def load_folder_images(self, folder: Path | None) -> None:
        self.images.clear()
        self.file_list.clear()
        self.file_list.reset_range_selection_anchor()
        self.file_items_by_path.clear()
        self.thumbnail_applied_paths_by_source.clear()
        self.related_tag_candidates_cache = None
        self.preview.set_image(None)
        self._refresh_current_image_tags()
        self._set_info_rows([])
        self.current_folder = folder

        if folder is None:
            self._reload_filter_tag_combos()
            self.status.setText(self._tr("add_root_prompt"))
            self.settings.set_selected_folder_path(None)
            self.settings.set_selected_image_path(None)
            return

        self.settings.set_selected_folder_path(folder)
        root = self._root_for_folder(folder)
        try:
            image_paths = self._image_paths_in_folder(folder)
        except OSError as exc:
            self.status.setText(self._tr("cannot_open_folder", error=exc))
            return

        self.file_list.setUpdatesEnabled(False)
        try:
            for path in image_paths:
                self.images.append(ImageFile(path=path, root=root))
        finally:
            self.file_list.setUpdatesEnabled(True)

        # The tag panel is refreshed once while the previous folder is being
        # cleared, which caches an empty related-tag result. Invalidate that
        # result after the new folder's images are available so the following
        # refresh derives suggestions from their assigned tags.
        self.related_tag_candidates_cache = None
        self._apply_tag_filters(preserve_selection=False)
        self._reload_filter_tag_combos()
        self._update_thumbnail_status()
        self._restore_or_clear_selected_image(folder)
        self._scroll_file_list_to_top()
        if self._should_create_thumbnails_for_entire_folder():
            self._start_thumbnail_loading(image_paths, prioritize=True)
        self._schedule_visible_thumbnail_priority()

    def _image_paths_in_folder(self, folder: Path) -> list[Path]:
        image_paths: list[Path] = []
        with os.scandir(folder) as entries:
            for entry in entries:
                if not entry.is_file():
                    continue
                path = Path(entry.path)
                if path.suffix.lower() in IMAGE_EXTENSIONS:
                    image_paths.append(path)
        image_paths.sort(key=lambda path: path.name.lower())
        return image_paths

    def _refresh_folder_tree(self, select_path: Path | None = None) -> None:
        self.folder_tree.clear()
        for root in self.roots:
            item = self._make_folder_item(root, root)
            self.folder_tree.addTopLevelItem(item)
            self._add_placeholder_if_needed(item, root)

        target = select_path or self.settings.selected_folder_path()
        if target is None and self.restore_selected_image_path is not None:
            target = self.restore_selected_image_path.parent
        if target is None:
            target = self.roots[0] if self.roots else None
        if target is None:
            self.load_folder_images(None)
            return

        found = self._select_folder_path(target)
        if found is not None:
            self.folder_tree.setCurrentItem(found)
        else:
            fallback = self.roots[0] if self.roots else None
            self.load_folder_images(fallback)

    def _make_folder_item(self, folder: Path, root: Path) -> QTreeWidgetItem:
        item = QTreeWidgetItem([folder.name or str(folder)])
        item.setToolTip(0, str(folder))
        item.setData(0, Qt.ItemDataRole.UserRole, str(folder))
        item.setData(0, Qt.ItemDataRole.UserRole + 1, str(root))
        item.setData(0, Qt.ItemDataRole.UserRole + 2, False)
        return item

    def _add_placeholder_if_needed(self, item: QTreeWidgetItem, _folder: Path) -> None:
        item.addChild(QTreeWidgetItem([self._tr("loading")]))

    def _load_tree_item_children(self, item: QTreeWidgetItem) -> None:
        if item.data(0, Qt.ItemDataRole.UserRole + 2):
            return

        folder_value = item.data(0, Qt.ItemDataRole.UserRole)
        root_value = item.data(0, Qt.ItemDataRole.UserRole + 1)
        if not folder_value or not root_value:
            return

        folder = Path(folder_value)
        root = Path(root_value)
        self._clear_tree_item_children(item)

        try:
            internal_dirs = {data_dir().resolve(), thumbnail_dir().resolve()}
            folders = sorted(
                [
                    path
                    for path in folder.iterdir()
                    if path.is_dir() and path.resolve() not in internal_dirs
                ],
                key=lambda path: path.name.lower(),
            )
        except OSError:
            folders = []

        for child_folder in folders:
            child = self._make_folder_item(child_folder, root)
            item.addChild(child)
            self._add_placeholder_if_needed(child, child_folder)

        item.setData(0, Qt.ItemDataRole.UserRole + 2, True)

    def _clear_tree_item_children(self, item: QTreeWidgetItem) -> None:
        while item.childCount():
            item.removeChild(item.child(0))

    def _find_tree_item(self, folder: Path) -> QTreeWidgetItem | None:
        for index in range(self.folder_tree.topLevelItemCount()):
            item = self.folder_tree.topLevelItem(index)
            if Path(item.data(0, Qt.ItemDataRole.UserRole)) == folder:
                return item
        return None

    def _select_folder_path(self, folder: Path) -> QTreeWidgetItem | None:
        root_item: QTreeWidgetItem | None = None
        root_path: Path | None = None
        for index in range(self.folder_tree.topLevelItemCount()):
            item = self.folder_tree.topLevelItem(index)
            candidate = Path(item.data(0, Qt.ItemDataRole.UserRole))
            try:
                folder.relative_to(candidate)
            except ValueError:
                continue
            root_item = item
            root_path = candidate
            break

        if root_item is None or root_path is None:
            return None

        current_item = root_item
        current_path = root_path
        if current_path == folder:
            return current_item

        try:
            relative_parts = folder.relative_to(root_path).parts
        except ValueError:
            return None

        for part in relative_parts:
            self._load_tree_item_children(current_item)
            next_item = self._find_child_folder_item(current_item, current_path / part)
            if next_item is None:
                return None
            current_item.setExpanded(True)
            current_item = next_item
            current_path = current_path / part
        return current_item

    def _find_child_folder_item(
        self, parent: QTreeWidgetItem, folder: Path
    ) -> QTreeWidgetItem | None:
        for index in range(parent.childCount()):
            child = parent.child(index)
            child_path = child.data(0, Qt.ItemDataRole.UserRole)
            if child_path and Path(child_path) == folder:
                return child
        return None

    def _on_current_folder_changed(
        self, current: QTreeWidgetItem | None, _previous: QTreeWidgetItem | None
    ) -> None:
        if current is None:
            self.load_folder_images(None)
            return
        path = current.data(0, Qt.ItemDataRole.UserRole)
        if path:
            self.load_folder_images(Path(path))

    def _root_for_folder(self, folder: Path) -> Path:
        for root in self.roots:
            try:
                folder.relative_to(root)
                return root
            except ValueError:
                continue
        return folder

    def _add_image_item(self, image: ImageFile) -> None:
        self.images.append(image)
        self._add_file_list_item(image)

    def _add_file_list_item(self, image: ImageFile) -> None:
        item = QListWidgetItem()
        item.setText(image.name)
        item.setTextAlignment(Qt.AlignmentFlag.AlignHCenter)
        item.setToolTip(str(image.path))
        item.setData(Qt.ItemDataRole.UserRole, image)
        self._set_file_item_placeholder_icon(item, image)
        self.file_list.addItem(item)
        self.file_items_by_path[str(image.path)] = item

    def _apply_tag_filters(self, preserve_selection: bool = True) -> None:
        current = self._current_image()
        current_path = current.path if preserve_selection and current is not None else None
        selected_paths = {
            image.path
            for image in self._selected_images()
        } if preserve_selection else set()

        self.file_list.setUpdatesEnabled(False)
        self.file_list.clear()
        self.file_list.reset_range_selection_anchor()
        self.file_items_by_path.clear()
        try:
            for image in self.images:
                if self._image_matches_tag_filters(image):
                    self._add_file_list_item(image)
        finally:
            self.file_list.setUpdatesEnabled(True)

        restored_current_item: QListWidgetItem | None = None
        for path in selected_paths:
            item = self.file_items_by_path.get(str(path))
            if item is not None:
                item.setSelected(True)
        if current_path is not None:
            restored_current_item = self.file_items_by_path.get(str(current_path))
        if restored_current_item is not None:
            self.file_list.setCurrentItem(
                restored_current_item,
                QItemSelectionModel.SelectionFlag.NoUpdate,
            )
            image = restored_current_item.data(Qt.ItemDataRole.UserRole)
            if isinstance(image, ImageFile):
                self.settings.set_selected_image_path(image.path)
                self._show_image(image)
                self._refresh_current_image_tags()
        elif self.file_list.currentItem() is None:
            self.preview.set_image(None)
            self._refresh_current_image_tags()
            self._set_info_rows([])
            self.settings.set_selected_image_path(None)

        self._update_thumbnail_status()
        self._refresh_visible_thumbnail_icons()
        self._schedule_visible_thumbnail_priority()

    def _image_matches_tag_filters(self, image: ImageFile) -> bool:
        tag_ids = set(self.tag_store.image_tag_ids(image.path))
        if self.include_filter_tag_ids and not set(
            self.include_filter_tag_ids
        ).issubset(tag_ids):
            return False
        if self.exclude_filter_tag_ids and tag_ids.intersection(
            self.exclude_filter_tag_ids
        ):
            return False
        return True

    def _refresh_all_file_item_icons(self) -> None:
        self.thumbnail_icon_cache.clear()
        self.thumbnail_applied_paths_by_source.clear()
        for item in self.file_items_by_path.values():
            image = item.data(Qt.ItemDataRole.UserRole)
            if isinstance(image, ImageFile):
                self._set_file_item_placeholder_icon(item, image)
        self._refresh_visible_thumbnail_icons()

    def _refresh_image_item_icon(self, image: ImageFile) -> None:
        item = self.file_items_by_path.get(str(image.path))
        if item is not None:
            self.thumbnail_icon_cache.clear()
            self.thumbnail_applied_paths_by_source.pop(str(image.path), None)
            self._refresh_file_item_icon(item, image)

    def _refresh_file_item_icon(
        self, item: QListWidgetItem, image: ImageFile, thumbnail_path: str | None = None
    ) -> None:
        if thumbnail_path is None:
            thumbnail_path = self._known_thumbnail_path_for(image.path)
        if thumbnail_path is None:
            self._set_file_item_placeholder_icon(item, image)
            return

        source_key = str(image.path)
        if self.thumbnail_applied_paths_by_source.get(source_key) == thumbnail_path:
            return

        item.setIcon(self._thumbnail_icon_for_image(image, thumbnail_path))
        self.thumbnail_applied_paths_by_source[source_key] = thumbnail_path

    def _set_file_item_placeholder_icon(
        self, item: QListWidgetItem, image: ImageFile
    ) -> None:
        item.setIcon(self.placeholder_icon)
        self.thumbnail_applied_paths_by_source[str(image.path)] = None

    def _thumbnail_icon_for_image(
        self, image: ImageFile, thumbnail_path: str | None
    ) -> QIcon:
        tag_ids = tuple(self.tag_store.image_tag_ids(image.path))
        cache_key = (str(image.path), thumbnail_path or "", tag_ids)
        cached_icon = self.thumbnail_icon_cache.get(cache_key)
        if cached_icon is not None:
            self.thumbnail_icon_cache.move_to_end(cache_key)
            return cached_icon

        if thumbnail_path:
            pixmap = QPixmap(thumbnail_path)
            if pixmap.isNull():
                pixmap = QPixmap(self.placeholder_icon.pixmap(self.file_list.iconSize()))
        else:
            pixmap = QPixmap(self.placeholder_icon.pixmap(self.file_list.iconSize()))

        tags = self._tags_for_image(image)
        if tags:
            pixmap = self._pixmap_with_tag_badges(pixmap, tags)
        icon = QIcon(pixmap)
        self.thumbnail_icon_cache[cache_key] = icon
        if len(self.thumbnail_icon_cache) > THUMBNAIL_ICON_CACHE_LIMIT:
            self.thumbnail_icon_cache.popitem(last=False)
        return icon

    def _pixmap_with_tag_badges(self, source: QPixmap, tags: list[Tag]) -> QPixmap:
        pixmap = QPixmap(source)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        font = QFont(painter.font())
        font.setPixelSize(10)
        font.setBold(True)
        painter.setFont(font)

        max_badges = max(
            0,
            (
                pixmap.height()
                - (TAG_BADGE_MARGIN * 2)
                + TAG_BADGE_GAP
            )
            // (TAG_BADGE_HEIGHT + TAG_BADGE_GAP),
        )
        x = pixmap.width() - TAG_BADGE_MARGIN - TAG_BADGE_WIDTH
        y = TAG_BADGE_MARGIN
        for tag in tags[:max_badges]:
            background = QColor(tag.color)
            if not background.isValid():
                background = QColor("#3b82f6")
            text_color = QColor(_readable_text_color(background))
            border_color = QColor(_chip_border_color(background, text_color.name()))
            rect = QRect(x, y, TAG_BADGE_WIDTH, TAG_BADGE_HEIGHT)
            painter.setPen(border_color)
            painter.setBrush(background)
            painter.drawRoundedRect(rect, TAG_BADGE_HEIGHT // 2, TAG_BADGE_HEIGHT // 2)
            painter.setPen(text_color)
            painter.drawText(
                rect.adjusted(2, 0, -2, 0),
                Qt.AlignmentFlag.AlignCenter,
                tag.name[:2],
            )
            y += TAG_BADGE_HEIGHT + TAG_BADGE_GAP

        painter.end()
        return pixmap

    def _known_thumbnail_path_for(self, source_path: Path) -> str | None:
        source_key = str(source_path)
        thumbnail_path = self.thumbnail_paths_by_source.get(source_key)
        if thumbnail_path and Path(thumbnail_path).exists():
            return thumbnail_path
        if thumbnail_path:
            self.thumbnail_paths_by_source.pop(source_key, None)

        cache_path = self.thumbnail_cache.cached_path_for(source_path)
        if cache_path is not None:
            thumbnail_path = str(cache_path)
            self.thumbnail_paths_by_source[source_key] = thumbnail_path
            return thumbnail_path
        return None

    def _scroll_file_list_to_top(self) -> None:
        self.file_list.scrollToTop()
        self.file_list.verticalScrollBar().setValue(0)

    def _start_thumbnail_loading(
        self, image_paths: list[Path], prioritize: bool = False
    ) -> None:
        if not image_paths:
            return

        priority_paths: list[Path] = []
        active_paths = set(self.thumbnail_futures.values())
        for path in image_paths:
            key = str(path)
            if key in self.thumbnail_paths_by_source:
                continue
            if key in active_paths:
                continue
            if key in self.thumbnail_queued_paths:
                if prioritize:
                    try:
                        self.thumbnail_queue.remove(path)
                    except ValueError:
                        continue
                    priority_paths.append(path)
                continue
            if prioritize:
                priority_paths.append(path)
            else:
                self.thumbnail_queue.append(path)
            self.thumbnail_queued_paths.add(key)

        if priority_paths:
            self.thumbnail_queue.extendleft(reversed(priority_paths))

        self._start_next_thumbnail_job()

    def _schedule_visible_thumbnail_priority(self, *_args: object) -> None:
        if self.file_list.count():
            self.thumbnail_visible_priority_timer.start()

    def _prioritize_visible_thumbnails(self) -> None:
        self._refresh_visible_thumbnail_icons()
        visible_paths = self._visible_image_paths()
        if self._should_create_thumbnails_for_visible_files_only():
            self._start_thumbnail_loading(visible_paths, prioritize=True)
        if not visible_paths or not self.thumbnail_queue:
            return

        queued_paths = set(self.thumbnail_queue)
        priority_paths = [path for path in visible_paths if path in queued_paths]
        if not priority_paths:
            return

        priority_set = set(priority_paths)
        self.thumbnail_queue = deque(
            [
                *priority_paths,
                *[path for path in self.thumbnail_queue if path not in priority_set],
            ]
        )
        self._start_next_thumbnail_job()

    def _refresh_visible_thumbnail_icons(self, *_args: object) -> None:
        visible_items = self._visible_image_items()
        if not visible_items:
            return

        self.file_list.setUpdatesEnabled(False)
        try:
            for item, image in visible_items:
                thumbnail_path = self._known_thumbnail_path_for(image.path)
                if thumbnail_path is not None:
                    self._refresh_file_item_icon(item, image, thumbnail_path)
        finally:
            self.file_list.setUpdatesEnabled(True)

    def _visible_image_paths(self) -> list[Path]:
        return [image.path for _item, image in self._visible_image_items()]

    def _visible_image_items(self) -> list[tuple[QListWidgetItem, ImageFile]]:
        viewport_rect = self.file_list.viewport().rect()
        grid_size = self.file_list.gridSize()
        step_x = max(1, grid_size.width() // 2)
        step_y = max(1, grid_size.height() // 2)
        x_values = list(range(viewport_rect.left(), viewport_rect.right() + 1, step_x))
        y_values = list(range(viewport_rect.top(), viewport_rect.bottom() + 1, step_y))
        if not x_values or x_values[-1] != viewport_rect.right():
            x_values.append(viewport_rect.right())
        if not y_values or y_values[-1] != viewport_rect.bottom():
            y_values.append(viewport_rect.bottom())

        visible_items: list[tuple[QListWidgetItem, ImageFile]] = []
        seen_paths: set[Path] = set()
        for y in y_values:
            for x in x_values:
                item = self.file_list.itemAt(QPoint(x, y))
                if item is None:
                    continue
                image = item.data(Qt.ItemDataRole.UserRole)
                if isinstance(image, ImageFile) and image.path not in seen_paths:
                    seen_paths.add(image.path)
                    visible_items.append((item, image))
        return visible_items

    def _start_next_thumbnail_job(self) -> None:
        while self.thumbnail_queue and len(self.thumbnail_futures) < THUMBNAIL_WORKER_COUNT:
            image_path = self.thumbnail_queue.popleft()
            source_key = str(image_path)
            if self._known_thumbnail_path_for(image_path):
                self.thumbnail_queued_paths.discard(source_key)
                continue
            future = self.thumbnail_executor.submit(
                create_thumbnail_file_for_cache_dir,
                str(image_path),
                str(self.thumbnail_cache.cache_dir),
                self.thumbnail_cache.thumbnail_size.width(),
                self.thumbnail_cache.thumbnail_size.height(),
            )
            self.thumbnail_futures[future] = str(image_path)

        if self.thumbnail_futures and not self.thumbnail_poll_timer.isActive():
            self.thumbnail_poll_timer.start()

        self._update_thumbnail_status()

    def _cancel_thumbnail_worker(self, clear_saved_queue: bool = True) -> None:
        for future in self.thumbnail_futures:
            future.cancel()
        self.thumbnail_futures.clear()
        self.thumbnail_queue.clear()
        self.thumbnail_queued_paths.clear()
        self.pending_thumbnail_updates.clear()
        self.thumbnail_poll_timer.stop()
        self.thumbnail_update_timer.stop()
        self.thumbnail_visible_priority_timer.stop()
        if clear_saved_queue:
            self._save_pending_thumbnails()

    def _poll_thumbnail_futures(self) -> None:
        if not self.thumbnail_futures:
            self.thumbnail_poll_timer.stop()
            self._save_pending_thumbnails()
            return

        done_futures = [future for future in self.thumbnail_futures if future.done()]
        had_finished_work = bool(done_futures)
        for future in done_futures:
            source_path = self.thumbnail_futures.pop(future)
            self.thumbnail_queued_paths.discard(source_path)
            try:
                completed_source, thumbnail_path = future.result()
            except Exception:
                continue
            if thumbnail_path:
                self.thumbnail_paths_by_source[completed_source] = thumbnail_path
                self._queue_thumbnail_update(completed_source, thumbnail_path)

        self._start_next_thumbnail_job()
        if had_finished_work:
            self._save_pending_thumbnails()

    def _queue_thumbnail_update(self, source_path: str, thumbnail_path: str) -> None:
        self.pending_thumbnail_updates[source_path] = thumbnail_path
        if not self.thumbnail_update_timer.isActive():
            self.thumbnail_update_timer.start()

    def _flush_thumbnail_updates(self) -> None:
        if not self.pending_thumbnail_updates:
            self.thumbnail_update_timer.stop()
            return

        visible_source_paths = {
            str(image.path): (item, image)
            for item, image in self._visible_image_items()
        }
        updated = 0
        self.file_list.setUpdatesEnabled(False)
        try:
            for source_path in list(self.pending_thumbnail_updates):
                thumbnail_path = self.pending_thumbnail_updates.pop(source_path)
                visible_item = visible_source_paths.get(source_path)
                if visible_item is None:
                    continue
                item, image = visible_item
                self._refresh_file_item_icon(item, image, thumbnail_path)
                updated += 1
                if updated >= THUMBNAIL_UI_UPDATES_PER_TICK:
                    break
        finally:
            self.file_list.setUpdatesEnabled(True)

    def _update_thumbnail_status(self) -> None:
        if self.current_folder is None:
            return

        remaining = len(self.thumbnail_queue) + len(self.thumbnail_futures)
        is_filtered = bool(self.include_filter_tag_ids or self.exclude_filter_tag_ids)
        if remaining:
            key = "filtered_thumbnail_queue" if is_filtered else "thumbnail_queue"
            self.status.setText(
                self._tr(
                    key,
                    count=self.file_list.count(),
                    shown=self.file_list.count(),
                    total=len(self.images),
                    folder=self.current_folder,
                    remaining=remaining,
                )
            )
        else:
            key = "filtered_image_count" if is_filtered else "image_count"
            self.status.setText(
                self._tr(
                    key,
                    count=self.file_list.count(),
                    shown=self.file_list.count(),
                    total=len(self.images),
                    folder=self.current_folder,
                )
            )

    def _resume_pending_thumbnails(self) -> None:
        if self._should_create_thumbnails_for_visible_files_only():
            self.settings.set_pending_thumbnail_paths([])
            return

        pending_paths = [
            path
            for path in self.settings.pending_thumbnail_paths()
            if path.exists() and self.thumbnail_cache.cached_path_for(path) is None
        ]
        if pending_paths:
            self._start_thumbnail_loading(pending_paths)
        else:
            self.settings.set_pending_thumbnail_paths([])

    def _save_pending_thumbnails(self) -> None:
        if self._should_create_thumbnails_for_visible_files_only():
            self.settings.set_pending_thumbnail_paths([])
            return

        pending_paths = list(self.thumbnail_queue)
        pending_paths.extend(Path(path) for path in self.thumbnail_futures.values())
        self.settings.set_pending_thumbnail_paths(pending_paths)

    def _should_create_thumbnails_for_visible_files_only(self) -> bool:
        return self.thumbnail_generation_mode == THUMBNAIL_GENERATION_VISIBLE

    def _should_create_thumbnails_for_entire_folder(self) -> bool:
        return self.thumbnail_generation_mode == THUMBNAIL_GENERATION_FOLDER

    def _restart_thumbnail_loading_for_current_mode(self) -> None:
        self._cancel_thumbnail_worker(clear_saved_queue=False)
        self.settings.set_pending_thumbnail_paths([])
        if self.current_folder is None:
            self._update_thumbnail_status()
            return

        if self._should_create_thumbnails_for_entire_folder():
            self._start_thumbnail_loading(
                [image.path for image in self.images],
                prioritize=True,
            )
        else:
            self._refresh_visible_thumbnail_icons()
            self._schedule_visible_thumbnail_priority()
        self._update_thumbnail_status()

    def _make_placeholder_thumbnail(self) -> QPixmap:
        placeholder = QPixmap(160, 120)
        placeholder.fill(Qt.GlobalColor.darkGray)
        return placeholder

    def _on_current_file_changed(
        self, current: QListWidgetItem | None, _previous: QListWidgetItem | None
    ) -> None:
        if current is None:
            self.preview.set_image(None)
            self._refresh_current_image_tags()
            self._set_info_rows([])
            self.settings.set_selected_image_path(None)
            return

        image = current.data(Qt.ItemDataRole.UserRole)
        if not isinstance(image, ImageFile):
            return
        self.settings.set_selected_image_path(image.path)
        self._show_image(image)
        self._refresh_current_image_tags()

    def _restore_or_clear_selected_image(self, folder: Path) -> None:
        selected_path = self.restore_selected_image_path or self.settings.selected_image_path()
        if selected_path is None or selected_path.parent != folder:
            self.settings.set_selected_image_path(None)
            self.restore_selected_image_path = None
            return

        item = self.file_items_by_path.get(str(selected_path))
        if item is None:
            self.settings.set_selected_image_path(None)
            self.restore_selected_image_path = None
            return

        self.file_list.setCurrentItem(item)
        self.file_list.scrollToItem(item, QAbstractItemView.ScrollHint.PositionAtCenter)
        self.restore_selected_image_path = None

    def _show_image(self, image: ImageFile) -> None:
        self.preview.set_image(image.path)
        if self.preview_window is not None:
            self.preview_window.set_image(image.path)
        self._show_info(image.path, image.root)

    def open_preview_window(self) -> None:
        if self.preview_window is None:
            self.preview_window = PreviewWindow()
            self.preview_window.closed.connect(self._on_preview_window_closed)
            self.preview_window.navigate_requested.connect(self._move_current_file)
        current = self.file_list.currentItem()
        if current is not None:
            image = current.data(Qt.ItemDataRole.UserRole)
            if isinstance(image, ImageFile):
                self.preview_window.set_image(image.path)
        self.preview_window.show()
        self.preview_window.raise_()

    def _on_preview_window_closed(self) -> None:
        self.preview_window = None

    def _move_current_file(self, offset: int) -> None:
        if self.file_list.count() == 0 or offset == 0:
            return

        current_row = self.file_list.currentRow()
        if current_row < 0:
            target_row = 0 if offset > 0 else self.file_list.count() - 1
        else:
            target_row = max(
                0,
                min(self.file_list.count() - 1, current_row + offset),
            )
        if target_row == current_row:
            return

        item = self.file_list.item(target_row)
        if item is None:
            return
        self.file_list.setCurrentItem(
            item,
            QItemSelectionModel.SelectionFlag.ClearAndSelect,
        )
        self.file_list.scrollToItem(item, QAbstractItemView.ScrollHint.PositionAtCenter)

    def _show_info(self, path: Path, root: Path) -> None:
        metadata = read_image_metadata(path)
        rows: list[tuple[str, str]] = [
            (self._tr("file_name"), path.name),
            (self._tr("full_path"), str(path)),
            (self._tr("root_folder"), str(root)),
            (self._tr("folder"), str(path.parent)),
            (self._tr("extension"), path.suffix.lower()),
        ]

        try:
            stat = path.stat()
            captured_rows = [
                self._localized_info_row(row)
                for row in metadata.rows
                if row[0] == "撮影日時"
            ]
            rows.extend(
                [
                    (self._tr("file_size"), self._format_size(stat.st_size)),
                    *captured_rows,
                    (
                        self._tr("updated_at"),
                        datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                    ),
                ]
            )
        except OSError as exc:
            rows.append((self._tr("file_status"), self._tr("unavailable", error=exc)))

        reader = QImageReader(str(path))
        size = reader.size()
        if size.isValid() and metadata.width is None and metadata.height is None:
            rows.append((self._tr("dimensions"), f"{size.width()} x {size.height()}"))

        rows.extend(
            self._localized_info_row(row)
            for row in metadata.rows
            if row[0] != "撮影日時"
        )

        self._set_info_rows(rows)

    def _reload_filter_tag_combos(self) -> None:
        available_tag_ids = self._tag_ids_in_current_folder()
        self._reload_filter_tag_combo(
            self.include_filter_combo,
            self._tr("include_tag_placeholder"),
            self.include_filter_tag_ids,
            available_tag_ids,
        )
        self._reload_filter_tag_combo(
            self.exclude_filter_combo,
            self._tr("exclude_tag_placeholder"),
            self.exclude_filter_tag_ids,
            available_tag_ids,
        )
        has_tags = bool(available_tag_ids)
        self.include_filter_combo.setEnabled(has_tags)
        self.exclude_filter_combo.setEnabled(has_tags)

    def _reload_filter_tag_combo(
        self,
        combo: QComboBox,
        placeholder: str,
        selected_tag_ids: list[str],
        available_tag_ids: set[str],
    ) -> None:
        combo.blockSignals(True)
        try:
            combo.clear()
            combo.addItem(placeholder, None)
            selected_ids = set(selected_tag_ids)
            for tag in sorted(self.tag_store.tags, key=self._tag_sort_key):
                if tag.id in selected_ids or tag.id not in available_tag_ids:
                    continue
                combo.addItem(
                    self._tag_color_icon(tag),
                    self._tag_display_name(tag),
                    tag.id,
                )
                self._apply_tag_combo_item_style(combo, combo.count() - 1, tag)
            combo.setCurrentIndex(0)
        finally:
            combo.blockSignals(False)

    def _tag_ids_in_current_folder(self) -> set[str]:
        tag_ids: set[str] = set()
        for image in self.images:
            tag_ids.update(self.tag_store.image_tag_ids(image.path))
        valid_tag_ids = {tag.id for tag in self.tag_store.tags}
        return tag_ids.intersection(valid_tag_ids)

    def _refresh_filter_chips(self) -> None:
        self._refresh_filter_chip_layout(
            self.include_filter_chip_layout,
            self.include_filter_tag_ids,
            self._remove_include_filter_tag,
        )
        self._refresh_filter_chip_layout(
            self.exclude_filter_chip_layout,
            self.exclude_filter_tag_ids,
            self._remove_exclude_filter_tag,
        )
        has_include_filters = bool(self.include_filter_tag_ids)
        has_exclude_filters = bool(self.exclude_filter_tag_ids)
        self.clear_include_filter_button.setEnabled(has_include_filters)
        self.clear_exclude_filter_button.setEnabled(has_exclude_filters)
        self.clear_all_filter_button.setEnabled(
            has_include_filters or has_exclude_filters
        )

    def _refresh_filter_chip_layout(
        self,
        layout: FlowLayout,
        tag_ids: list[str],
        remove_callback,
    ) -> None:
        layout.clear()
        for tag_id in tag_ids:
            tag = self.tag_store.tag_by_id(tag_id)
            if tag is None:
                continue
            chip = TagChip(
                text=self._tag_display_name(tag),
                color=tag.color,
                tooltip=self._tag_tooltip(tag),
                remove_tooltip=self._tr("remove_filter_tag"),
            )
            chip.remove_button.clicked.connect(
                lambda _checked=False, selected_tag_id=tag.id: remove_callback(
                    selected_tag_id
                )
            )
            layout.addWidget(chip)

    def _add_include_filter_tag(self, *_args: object) -> None:
        tag_id = self.include_filter_combo.currentData()
        if not isinstance(tag_id, str):
            self.include_filter_combo.setCurrentIndex(0)
            return
        self.exclude_filter_tag_ids = [
            existing_id
            for existing_id in self.exclude_filter_tag_ids
            if existing_id != tag_id
        ]
        self._add_filter_tag(self.include_filter_tag_ids, tag_id)

    def _add_exclude_filter_tag(self, *_args: object) -> None:
        tag_id = self.exclude_filter_combo.currentData()
        if not isinstance(tag_id, str):
            self.exclude_filter_combo.setCurrentIndex(0)
            return
        self.include_filter_tag_ids = [
            existing_id
            for existing_id in self.include_filter_tag_ids
            if existing_id != tag_id
        ]
        self._add_filter_tag(self.exclude_filter_tag_ids, tag_id)

    def _add_filter_tag(self, tag_ids: list[str], tag_id: str) -> None:
        if tag_id not in tag_ids:
            tag_ids.append(tag_id)
        self._reload_filter_tag_combos()
        self._refresh_filter_chips()
        self._apply_tag_filters()

    def _remove_include_filter_tag(self, tag_id: str) -> None:
        self.include_filter_tag_ids = [
            existing_id for existing_id in self.include_filter_tag_ids if existing_id != tag_id
        ]
        self._reload_filter_tag_combos()
        self._refresh_filter_chips()
        self._apply_tag_filters()

    def _remove_exclude_filter_tag(self, tag_id: str) -> None:
        self.exclude_filter_tag_ids = [
            existing_id for existing_id in self.exclude_filter_tag_ids if existing_id != tag_id
        ]
        self._reload_filter_tag_combos()
        self._refresh_filter_chips()
        self._apply_tag_filters()

    def _clear_include_filter_tags(self) -> None:
        if not self.include_filter_tag_ids:
            return
        self.include_filter_tag_ids.clear()
        self._reload_filter_tag_combos()
        self._refresh_filter_chips()
        self._apply_tag_filters()

    def _clear_exclude_filter_tags(self) -> None:
        if not self.exclude_filter_tag_ids:
            return
        self.exclude_filter_tag_ids.clear()
        self._reload_filter_tag_combos()
        self._refresh_filter_chips()
        self._apply_tag_filters()

    def _clear_all_filter_tags(self) -> None:
        if not self.include_filter_tag_ids and not self.exclude_filter_tag_ids:
            return
        self.include_filter_tag_ids.clear()
        self.exclude_filter_tag_ids.clear()
        self._reload_filter_tag_combos()
        self._refresh_filter_chips()
        self._apply_tag_filters()

    def _reload_add_tag_combo(self) -> None:
        current_tag_id = self.add_tag_combo.currentData()
        self.add_tag_combo.blockSignals(True)
        try:
            self.add_tag_combo.clear()
            self.add_tag_combo.addItem(self._tr("add_tag_placeholder"), None)
            for tag in sorted(self.tag_store.tags, key=self._tag_sort_key):
                self.add_tag_combo.addItem(
                    self._tag_color_icon(tag),
                    self._tag_display_name(tag),
                    tag.id,
                )
                self._apply_tag_combo_item_style(
                    self.add_tag_combo,
                    self.add_tag_combo.count() - 1,
                    tag,
                )
            self._select_combo_data(self.add_tag_combo, current_tag_id)
        finally:
            self.add_tag_combo.blockSignals(False)

    def _reload_add_related_tag_combo(self) -> None:
        current_tag_id = self.add_related_tag_combo.currentData()
        self.add_related_tag_combo.blockSignals(True)
        try:
            self.add_related_tag_combo.clear()
            self.add_related_tag_combo.addItem(
                self._tr("add_related_tag_placeholder"),
                None,
            )
            for tag in self._related_tag_candidates_for_current_folder():
                self.add_related_tag_combo.addItem(
                    self._tag_color_icon(tag),
                    self._tag_display_name(tag),
                    tag.id,
                )
                self._apply_tag_combo_item_style(
                    self.add_related_tag_combo,
                    self.add_related_tag_combo.count() - 1,
                    tag,
                )
            self._select_combo_data(self.add_related_tag_combo, current_tag_id)
        finally:
            self.add_related_tag_combo.blockSignals(False)

    def _refresh_current_image_tags(self) -> None:
        self.tag_chip_layout.clear()
        self._reload_add_related_tag_combo()
        image = self._current_image()
        enabled = image is not None
        self.copy_image_button.setEnabled(enabled)
        self.add_tag_combo.setEnabled(enabled and bool(self.tag_store.tags))
        self.add_related_tag_combo.setEnabled(
            enabled and self.add_related_tag_combo.count() > 1
        )
        if image is None:
            return

        for tag_id in self.tag_store.image_tag_ids(image.path):
            tag = self.tag_store.tag_by_id(tag_id)
            if tag is None:
                continue
            chip = TagChip(
                text=self._tag_display_name(tag),
                color=tag.color,
                tooltip=self._tag_tooltip(tag),
                remove_tooltip=self._tr("remove_tag"),
            )
            chip.tag_button.clicked.connect(
                lambda _checked=False, selected_tag_id=tag.id: (
                    self._filter_by_tag(selected_tag_id)
                )
            )
            chip.remove_button.clicked.connect(
                lambda _checked=False, assigned_tag_id=tag.id: (
                    self._remove_tag_from_current_image(assigned_tag_id)
                )
            )
            self.tag_chip_layout.addWidget(chip)

    def _add_selected_tag_to_current_image(self, *_args: object) -> None:
        image = self._current_image()
        tag_id = self.add_tag_combo.currentData()
        tag = self.tag_store.tag_by_id(tag_id)
        if image is None or tag is None:
            self.add_tag_combo.setCurrentIndex(0)
            return

        self._add_tag_to_images(tag, self._target_images_for_tag_panel())
        self.add_tag_combo.setCurrentIndex(0)
        self._refresh_current_image_tags()

    def _add_selected_related_tag_to_current_image(self, *_args: object) -> None:
        image = self._current_image()
        tag_id = self.add_related_tag_combo.currentData()
        tag = self.tag_store.tag_by_id(tag_id)
        if image is None or tag is None:
            self.add_related_tag_combo.setCurrentIndex(0)
            return

        self._add_tag_to_images(tag, self._target_images_for_tag_panel())
        self.add_related_tag_combo.setCurrentIndex(0)
        self._refresh_current_image_tags()

    def _add_tag_to_images(self, tag: Tag, images: list[ImageFile]) -> None:
        show_busy = len(images) > 1
        if show_busy:
            self._begin_busy_operation(self._tr("processing_tags", count=len(images)))
        tag_ids_to_add = [tag.id, *self.tag_store.related_tag_ids_for(tag)]
        try:
            self.related_tag_candidates_cache = None
            self.thumbnail_icon_cache.clear()
            for image in images:
                current_ids = self.tag_store.image_tag_ids(image.path)
                current_ids.extend(tag_ids_to_add)
                self.tag_store.set_image_tag_ids(image.path, current_ids)
                self._refresh_image_item_icon(image)
            self._reload_filter_tag_combos()
            self._apply_tag_filters()
            self._refresh_current_image_tags()
        finally:
            if show_busy:
                self._end_busy_operation()
        if len(images) > 1:
            self.status.setText(
                self._tr("added_tags", tag=self._tag_display_name(tag), count=len(images))
            )

    def _remove_tag_from_current_image(self, tag_id: str) -> None:
        images = self._target_images_for_tag_panel()
        if not images:
            return
        show_busy = len(images) > 1
        if show_busy:
            self._begin_busy_operation(self._tr("processing_tags", count=len(images)))
        try:
            self.related_tag_candidates_cache = None
            self.thumbnail_icon_cache.clear()
            for image in images:
                remaining = [
                    assigned_id
                    for assigned_id in self.tag_store.image_tag_ids(image.path)
                    if assigned_id != tag_id
                ]
                self.tag_store.set_image_tag_ids(image.path, remaining)
                self._refresh_image_item_icon(image)
            self._reload_filter_tag_combos()
            self._apply_tag_filters()
            self._refresh_current_image_tags()
        finally:
            if show_busy:
                self._end_busy_operation()
        if len(images) > 1:
            self.status.setText(self._tr("removed_tags", count=len(images)))

    def _clear_tags_from_images(self, images: list[ImageFile]) -> None:
        tagged_images: list[ImageFile] = []
        show_busy = len(images) > 1
        if show_busy:
            self._begin_busy_operation(self._tr("processing_tags", count=len(images)))
        try:
            tagged_images = [
                image for image in images if self.tag_store.image_tag_ids(image.path)
            ]
            if tagged_images:
                self.related_tag_candidates_cache = None
                self.thumbnail_icon_cache.clear()
                for image in tagged_images:
                    self.tag_store.set_image_tag_ids(image.path, [])
                    self._refresh_image_item_icon(image)

                self._reload_filter_tag_combos()
                self._apply_tag_filters()
                self._refresh_current_image_tags()
        finally:
            if show_busy:
                self._end_busy_operation()

        if tagged_images:
            self.status.setText(self._tr("cleared_tags", count=len(tagged_images)))

    def _target_images_for_tag_panel(self) -> list[ImageFile]:
        current = self._current_image()
        if current is None:
            return []
        selected = self._selected_images()
        return selected if selected else [current]

    def _copy_current_image_to_clipboard(self) -> None:
        image = self._current_image()
        if image is None:
            return
        self._copy_image_to_clipboard(image)

    def _copy_image_to_clipboard(self, image: ImageFile) -> None:
        reader = QImageReader(str(image.path))
        reader.setAutoTransform(True)
        clipboard_image = reader.read()
        if clipboard_image.isNull():
            self.status.setText(
                self._tr("copy_image_failed", error=reader.errorString())
            )
            return

        copy_behavior = self.settings.copy_behavior()
        clipboard_image = self._apply_copy_behavior_to_image(
            clipboard_image,
            copy_behavior,
        )
        QApplication.clipboard().setImage(clipboard_image)
        self._add_copy_auto_tags(image, copy_behavior.auto_tag_ids or [])
        self.status.setText(self._tr("copied_image", name=image.name))

    def _apply_copy_behavior_to_image(
        self,
        image: QImage,
        copy_behavior: CopyBehaviorSettings,
    ) -> QImage:
        result = image.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
        if copy_behavior.resize_enabled:
            result = self._resized_copy_image(result, copy_behavior)

        if copy_behavior.image_watermark_enabled:
            result = self._image_with_image_watermark(result, copy_behavior)
        if (
            copy_behavior.text_watermark_enabled
            and copy_behavior.text_watermark_text.strip()
        ):
            result = self._image_with_text_watermark(result, copy_behavior)
        return result

    def _resized_copy_image(
        self,
        image: QImage,
        copy_behavior: CopyBehaviorSettings,
    ) -> QImage:
        max_width = max(1, copy_behavior.resize_max_width)
        max_height = max(1, copy_behavior.resize_max_height)
        if image.width() <= max_width and image.height() <= max_height:
            return image
        return image.scaled(
            QSize(max_width, max_height),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

    def _image_with_image_watermark(
        self,
        image: QImage,
        copy_behavior: CopyBehaviorSettings,
    ) -> QImage:
        watermark_path = Path(copy_behavior.image_watermark_path)
        if not watermark_path.is_file():
            return image
        reader = QImageReader(str(watermark_path))
        reader.setAutoTransform(True)
        watermark = reader.read()
        if watermark.isNull():
            return image

        result = QImage(image)
        painter = QPainter(result)
        painter.setOpacity(max(0, min(100, copy_behavior.image_watermark_opacity)) / 100)
        painter.drawImage(
            copy_behavior.image_watermark_x,
            copy_behavior.image_watermark_y,
            watermark,
        )
        painter.end()
        return result

    def _image_with_text_watermark(
        self,
        image: QImage,
        copy_behavior: CopyBehaviorSettings,
    ) -> QImage:
        result = QImage(image)
        font = QFont(copy_behavior.text_watermark_font)
        font.setPixelSize(max(1, copy_behavior.text_watermark_size))
        text_color = QColor(copy_behavior.text_watermark_color)
        if not text_color.isValid():
            text_color = QColor("#ffffff")

        metrics = QFontMetrics(font)
        baseline_y = copy_behavior.text_watermark_y + metrics.ascent()
        path = QPainterPath()
        path.addText(
            copy_behavior.text_watermark_x,
            baseline_y,
            font,
            copy_behavior.text_watermark_text,
        )

        painter = QPainter(result)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        painter.setOpacity(max(0, min(100, copy_behavior.text_watermark_opacity)) / 100)
        if copy_behavior.text_watermark_outline:
            outline_color = QColor(copy_behavior.text_watermark_outline_color)
            if not outline_color.isValid():
                outline_color = QColor("#111827")
            outline_width = max(1, copy_behavior.text_watermark_outline_size)
            painter.strokePath(
                path,
                QPen(
                    outline_color,
                    outline_width,
                    Qt.PenStyle.SolidLine,
                    Qt.PenCapStyle.RoundCap,
                    Qt.PenJoinStyle.RoundJoin,
                ),
            )
        painter.fillPath(path, text_color)
        painter.end()
        return result

    def _add_copy_auto_tags(self, image: ImageFile, tag_ids: list[str]) -> None:
        valid_tag_ids = [tag_id for tag_id in tag_ids if self.tag_store.tag_by_id(tag_id)]
        if not valid_tag_ids:
            return

        self.related_tag_candidates_cache = None
        self.thumbnail_icon_cache.clear()
        current_ids = self.tag_store.image_tag_ids(image.path)
        current_ids.extend(valid_tag_ids)
        self.tag_store.set_image_tag_ids(image.path, current_ids)
        self._refresh_image_item_icon(image)
        self._reload_filter_tag_combos()
        self._apply_tag_filters()
        self._refresh_current_image_tags()

    def _filter_by_tag(self, tag_id: str) -> None:
        if self.tag_store.tag_by_id(tag_id) is None:
            return
        self.exclude_filter_tag_ids = [
            existing_id
            for existing_id in self.exclude_filter_tag_ids
            if existing_id != tag_id
        ]
        self._add_filter_tag(self.include_filter_tag_ids, tag_id)

    def _current_image(self) -> ImageFile | None:
        item = self.file_list.currentItem()
        if item is None:
            return None
        image = item.data(Qt.ItemDataRole.UserRole)
        return image if isinstance(image, ImageFile) else None

    def _selected_images(self) -> list[ImageFile]:
        images: list[ImageFile] = []
        for item in self.file_list.selectedItems():
            image = item.data(Qt.ItemDataRole.UserRole)
            if isinstance(image, ImageFile):
                images.append(image)
        return images

    def _tags_for_image(self, image: ImageFile) -> list[Tag]:
        tags: list[Tag] = []
        for tag_id in self.tag_store.image_tag_ids(image.path):
            tag = self.tag_store.tag_by_id(tag_id)
            if tag is not None:
                tags.append(tag)
        return tags

    def _related_tag_candidates_for_current_folder(self) -> list[Tag]:
        if self.related_tag_candidates_cache is not None:
            return self.related_tag_candidates_cache

        self.related_tag_candidates_cache = self._related_tag_candidates_for_images(
            self.images
        )
        return self.related_tag_candidates_cache

    def _related_tag_candidates_for_images(
        self, images: list[ImageFile]
    ) -> list[Tag]:
        source_category_ids = self._effective_related_tag_source_category_ids()
        assigned_tag_ids: set[str] = set()
        candidate_ids: set[str] = set()
        for image in images:
            for tag_id in self.tag_store.image_tag_ids(image.path):
                tag = self.tag_store.tag_by_id(tag_id)
                if tag is None:
                    continue
                assigned_tag_ids.add(tag.id)
                if tag.category_id is None or tag.category_id not in source_category_ids:
                    continue
                candidate_ids.add(tag.id)
                candidate_ids.update(self.tag_store.connected_tag_ids_for(tag))

        candidates = [
            tag
            for tag in self.tag_store.tags
            if tag.id in candidate_ids
            and self._tag_matches_folder_related_tags(
                tag,
                assigned_tag_ids,
                source_category_ids,
            )
        ]
        return sorted(candidates, key=self._tag_sort_key)

    def _tag_matches_folder_related_tags(
        self,
        tag: Tag,
        assigned_tag_ids: set[str],
        source_category_ids: set[str],
    ) -> bool:
        source_tag_ids: set[str] = set()
        for assigned_id in assigned_tag_ids:
            assigned_tag = self.tag_store.tag_by_id(assigned_id)
            if assigned_tag is None or assigned_tag.category_id is None:
                continue
            if assigned_tag.category_id in source_category_ids:
                source_tag_ids.add(assigned_tag.id)

        if not source_tag_ids or tag.id in source_tag_ids:
            return True
        return any(
            related_tag_id in source_tag_ids
            for related_tag_id in tag.related_tag_ids_by_category.values()
        )

    def _effective_related_tag_source_category_ids(self) -> set[str]:
        valid_category_ids = {category.id for category in self.tag_store.categories}
        if self.related_tag_source_category_ids is not None:
            return {
                category_id
                for category_id in self.related_tag_source_category_ids
                if category_id in valid_category_ids
            }

        location_category_ids = {
            category.id
            for category in self.tag_store.categories
            if category.name in {"場所", "Location", "Place"}
        }
        if location_category_ids:
            return location_category_ids
        return valid_category_ids

    def _apply_tag_action_style(self, action: QAction, tag: Tag) -> None:
        action.setIcon(self._tag_color_icon(tag))

    def _apply_tag_combo_item_style(
        self,
        combo: QComboBox,
        index: int,
        tag: Tag,
    ) -> None:
        background = self._valid_tag_color(tag)
        combo.setItemData(
            index,
            QBrush(background),
            Qt.ItemDataRole.BackgroundRole,
        )
        combo.setItemData(
            index,
            QBrush(QColor(_readable_text_color(background))),
            Qt.ItemDataRole.ForegroundRole,
        )

    def _tag_color_icon(self, tag: Tag) -> QIcon:
        background = self._valid_tag_color(tag)
        text_color = QColor(_readable_text_color(background))
        border_color = QColor(_chip_border_color(background, text_color.name()))
        pixmap = QPixmap(28, 16)
        pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(border_color)
        painter.setBrush(background)
        painter.drawRoundedRect(QRect(1, 2, 26, 12), 6, 6)
        painter.end()
        return QIcon(pixmap)

    @staticmethod
    def _valid_tag_color(tag: Tag) -> QColor:
        color = QColor(tag.color)
        if not color.isValid():
            return QColor("#3b82f6")
        return color

    def _tag_display_name(self, tag: Tag) -> str:
        category = self.tag_store.category_by_id(tag.category_id)
        if category is None:
            return tag.name
        return f"{category.name}: {tag.name}"

    def _tag_tooltip(self, tag: Tag) -> str:
        related_names: list[str] = []
        for category_id, related_tag_id in tag.related_tag_ids_by_category.items():
            category = self.tag_store.category_by_id(category_id)
            related_tag = self.tag_store.tag_by_id(related_tag_id)
            if category is None or related_tag is None:
                continue
            related_names.append(f"{category.name}: {related_tag.name}")
        if not related_names:
            return tag.name
        return f"{tag.name}\n{self._tr('related')}: {', '.join(related_names)}"

    def _tag_sort_key(self, tag: Tag) -> tuple[str, str]:
        category = self.tag_store.category_by_id(tag.category_id)
        return (category.name if category else "", tag.name)

    @staticmethod
    def _select_combo_data(combo: QComboBox, value: object) -> None:
        for index in range(combo.count()):
            if combo.itemData(index) == value:
                combo.setCurrentIndex(index)
                return
        combo.setCurrentIndex(0)

    def _set_info_rows(self, rows: list[tuple[str, str]]) -> None:
        self.info_table.setRowCount(len(rows))
        for row, (key, value) in enumerate(rows):
            self.info_table.setItem(row, 0, QTableWidgetItem(key))
            self.info_table.setItem(row, 1, QTableWidgetItem(value))

    def _localized_info_row(self, row: tuple[str, str]) -> tuple[str, str]:
        key, value = row
        if self.language == "en":
            return METADATA_LABELS_EN.get(key, key), value
        return key, value

    def _restore_window_layout(self) -> None:
        geometry = self.settings.window_geometry()
        if geometry is not None:
            self.restoreGeometry(geometry)

        main_splitter_state = self.settings.main_splitter_state()
        if main_splitter_state is not None:
            self.main_splitter.restoreState(main_splitter_state)

        center_splitter_state = self.settings.center_splitter_state()
        if center_splitter_state is not None:
            self.center_splitter.restoreState(center_splitter_state)

    def _save_window_layout(self) -> None:
        self.settings.set_window_geometry(self.saveGeometry())
        self.settings.set_main_splitter_state(self.main_splitter.saveState())
        self.settings.set_center_splitter_state(self.center_splitter.saveState())

    @staticmethod
    def _format_size(size: int) -> str:
        value = float(size)
        for unit in ("B", "KB", "MB", "GB"):
            if value < 1024 or unit == "GB":
                return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
            value /= 1024
        return f"{size} B"

    def closeEvent(self, event) -> None:  # noqa: N802
        self._save_window_layout()
        self._save_pending_thumbnails()
        self._cancel_thumbnail_worker(clear_saved_queue=False)
        self.thumbnail_executor.shutdown(wait=False, cancel_futures=True)
        self.tag_store.close()
        if self.preview_window is not None:
            self.preview_window.close()
        super().closeEvent(event)
