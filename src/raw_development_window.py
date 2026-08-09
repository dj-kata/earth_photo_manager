from __future__ import annotations

import math
from pathlib import Path

from PySide6.QtCore import QPoint, QRect, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QColor, QImage, QImageWriter, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from src.models import RAW_EXTENSIONS

try:
    import numpy as np
except ImportError:  # pragma: no cover - user-facing startup path
    np = None

try:
    import rawpy
except ImportError:  # pragma: no cover - user-facing startup path
    rawpy = None


MAX_PREVIEW_SIDE = 1800
JPEG_OUTPUT_QUALITY = 95
RAW_OUTPUT_DPI = 350
RAW_OUTPUT_DOTS_PER_METER = round(RAW_OUTPUT_DPI / 0.0254)
WB_CAMERA = "camera"
WB_AUTO = "auto"
WB_CUSTOM = "custom"
OUTPUT_SIZE_HALF = "half"
OUTPUT_SIZE_FULL = "full"

RAW_TRANSLATIONS = {
    "en": {
        "window_title": "RAW development - {name}",
        "open_raw_file": "Open a RAW file",
        "file": "File",
        "save_settings": "Save development settings",
        "overwrite_source": "Overwrite source JPG",
        "export": "Export developed image...",
        "close": "Close",
        "raw_development": "RAW development",
        "dependencies_missing": "rawpy and numpy are required.",
        "settings_saved": "Development settings saved",
        "save_settings_prompt": "Save development settings",
        "save_settings_before_close": "Development settings have changed. Save before closing?",
        "histogram": "Histogram",
        "raw": "RAW",
        "wb": "WB",
        "wb_camera": "Camera WB",
        "wb_auto": "Auto WB",
        "wb_custom": "Custom Temp/Tint",
        "half_size_preview": "Half-size preview decode",
        "temperature": "Temperature",
        "tint": "Tint",
        "output_size": "Output size",
        "output_half": "Half",
        "output_full": "Full",
        "tone": "Tone",
        "brightness": "Brightness",
        "contrast": "Contrast",
        "highlights": "Highlights",
        "shadows": "Shadows",
        "color": "Color",
        "hue": "Hue",
        "saturation": "Saturation",
        "green_magenta": "Green/Magenta",
        "red": "Red",
        "green": "Green",
        "blue": "Blue",
        "reset": "Reset",
        "reset_adjustments": "Reset adjustments",
        "aspect": "Aspect",
        "aspect_none": "None",
        "trim": "Trim",
        "decoding_raw": "Decoding RAW...",
        "loaded": "Loaded {name}",
        "raw_load_failed": "Could not read RAW file.\n\n{error}",
        "drag_trim": "Drag to select a trim range.",
        "trim_too_small": "Trim selection is too small.",
        "trim_selected": "Trim range selected. Press Trim to enable it.",
        "select_trim_first": "Select a trim range on the preview first.",
        "trim_enabled": "Trim enabled.",
        "select_trim_before_enable": "Select a trim range before enabling Trim.",
        "overwrite_title": "Overwrite",
        "overwrite_confirm": "Overwrite {name} with the developed image?",
        "export_title": "Export developed image",
        "rendering_output": "Rendering output...",
        "save_failed": "Could not save.\n\n{path}",
        "saved": "Saved {name}",
        "export_failed": "Failed to export developed image.\n\n{error}",
    },
    "ja": {
        "window_title": "RAW現像 - {name}",
        "open_raw_file": "RAWファイルを開いています",
        "file": "ファイル",
        "save_settings": "現像設定を保存",
        "overwrite_source": "元のJPGを上書き保存",
        "export": "現像出力...",
        "close": "閉じる",
        "raw_development": "RAW現像",
        "dependencies_missing": "rawpy と numpy が必要です。",
        "settings_saved": "現像設定を保存しました",
        "save_settings_prompt": "現像設定を保存",
        "save_settings_before_close": "現像設定が変更されています。閉じる前に保存しますか?",
        "histogram": "ヒストグラム",
        "raw": "RAW",
        "wb": "ホワイトバランス",
        "wb_camera": "カメラ設定",
        "wb_auto": "自動",
        "wb_custom": "色温度/色かぶり補正",
        "half_size_preview": "プレビューを半分サイズでデコード",
        "temperature": "色温度",
        "tint": "色かぶり補正",
        "output_size": "出力サイズ",
        "output_half": "半分",
        "output_full": "フル",
        "tone": "階調",
        "brightness": "明るさ",
        "contrast": "コントラスト",
        "highlights": "ハイライト",
        "shadows": "シャドウ",
        "color": "色",
        "hue": "色相",
        "saturation": "彩度",
        "green_magenta": "グリーン/マゼンタ",
        "red": "赤",
        "green": "緑",
        "blue": "青",
        "reset": "リセット",
        "reset_adjustments": "調整をリセット",
        "aspect": "比率",
        "aspect_none": "なし",
        "trim": "トリミング",
        "decoding_raw": "RAWをデコードしています...",
        "loaded": "{name} を読み込みました",
        "raw_load_failed": "RAWファイルを読み込めませんでした。\n\n{error}",
        "drag_trim": "ドラッグしてトリミング範囲を選択してください。",
        "trim_too_small": "トリミング範囲が小さすぎます。",
        "trim_selected": "トリミング範囲を選択しました。トリミングを押すと有効になります。",
        "select_trim_first": "先にプレビュー上でトリミング範囲を選択してください。",
        "trim_enabled": "トリミングを有効にしました。",
        "select_trim_before_enable": "トリミングを有効にする前に範囲を選択してください。",
        "overwrite_title": "上書き保存",
        "overwrite_confirm": "{name} を現像結果で上書きしますか?",
        "export_title": "現像出力",
        "rendering_output": "出力をレンダリングしています...",
        "save_failed": "保存できませんでした。\n\n{path}",
        "saved": "{name} を保存しました",
        "export_failed": "現像出力に失敗しました。\n\n{error}",
    },
}


class HistogramWidget(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setMinimumHeight(180)
        self._histograms: dict[str, np.ndarray] = {}
        self._visible_channels = {"Y": True, "R": True, "G": True, "B": True}

    def set_visible_channels(self, visible_channels: dict[str, bool]) -> None:
        self._visible_channels = visible_channels
        self.update()

    def set_image(self, image: np.ndarray | None) -> None:
        if image is None:
            self._histograms = {}
            self.update()
            return

        rgb = np.clip(image, 0.0, 1.0)
        y = 0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2]
        self._histograms = {
            "Y": np.histogram(y, bins=256, range=(0.0, 1.0))[0],
            "R": np.histogram(rgb[..., 0], bins=256, range=(0.0, 1.0))[0],
            "G": np.histogram(rgb[..., 1], bins=256, range=(0.0, 1.0))[0],
            "B": np.histogram(rgb[..., 2], bins=256, range=(0.0, 1.0))[0],
        }
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt override
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#14171c"))
        if not self._histograms:
            painter.setPen(QColor("#aeb6c2"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No histogram")
            return

        margin = 12
        rect = self.rect().adjusted(margin, margin, -margin, -margin)
        painter.setPen(QPen(QColor("#303743"), 1))
        for i in range(5):
            y = rect.top() + round(rect.height() * i / 4)
            painter.drawLine(rect.left(), y, rect.right(), y)

        visible_histograms = {
            name: hist for name, hist in self._histograms.items() if self._visible_channels.get(name, True)
        }
        if not visible_histograms:
            painter.setPen(QColor("#aeb6c2"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No channels enabled")
            return

        max_value = max(float(np.percentile(hist, 99.5)) for hist in visible_histograms.values())
        max_value = max(max_value, 1.0)
        colors = {
            "Y": QColor(235, 238, 245, 190),
            "R": QColor(255, 92, 92, 165),
            "G": QColor(97, 214, 131, 165),
            "B": QColor(95, 149, 255, 165),
        }
        width = max(1, rect.width())
        for name, hist in visible_histograms.items():
            painter.setPen(QPen(colors[name], 1.4))
            last_x = rect.left()
            last_y = rect.bottom()
            for i, value in enumerate(hist):
                x = rect.left() + round(width * i / 255)
                scaled = min(float(value) / max_value, 1.0)
                y = rect.bottom() - round(rect.height() * scaled)
                if i > 0:
                    painter.drawLine(last_x, last_y, x, y)
                last_x, last_y = x, y


class SliderRow(QWidget):
    def __init__(
        self,
        minimum: int,
        maximum: int,
        value: int,
        suffix: str = "",
        reset_label: str = "Reset",
    ) -> None:
        super().__init__()
        self._default_value = value
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(minimum, maximum)
        self.slider.setValue(value)
        self.spin = QSpinBox()
        self.spin.setRange(minimum, maximum)
        self.spin.setValue(value)
        self.spin.setSuffix(suffix)
        self.reset_button = QPushButton(reset_label)
        self.reset_button.setFixedWidth(56)
        self.slider.valueChanged.connect(self.spin.setValue)
        self.spin.valueChanged.connect(self.slider.setValue)
        self.reset_button.clicked.connect(self.reset)
        layout = QGridLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.slider, 0, 0)
        layout.addWidget(self.spin, 0, 1)
        layout.addWidget(self.reset_button, 0, 2)

    @property
    def valueChanged(self):  # noqa: N802 - Qt-style property
        return self.slider.valueChanged

    def value(self) -> int:
        return self.slider.value()

    def setValue(self, value: int) -> None:  # noqa: N802 - Qt-style helper
        self.slider.setValue(value)

    def reset(self) -> None:
        self.setValue(self._default_value)


class SignedEvSpinBox(QDoubleSpinBox):
    def textFromValue(self, value: float) -> str:  # noqa: N802 - Qt override
        return f"{value:+.2f} EV"


class EvSliderRow(QWidget):
    def __init__(
        self,
        minimum: float,
        maximum: float,
        value: float,
        reset_label: str = "Reset",
    ) -> None:
        super().__init__()
        self._scale = 100
        self._default_value = value
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(round(minimum * self._scale), round(maximum * self._scale))
        self.slider.setValue(round(value * self._scale))
        self.spin = SignedEvSpinBox()
        self.spin.setRange(minimum, maximum)
        self.spin.setDecimals(2)
        self.spin.setSingleStep(0.05)
        self.spin.setValue(value)
        self.reset_button = QPushButton(reset_label)
        self.reset_button.setFixedWidth(56)
        self.slider.valueChanged.connect(self._sync_spin)
        self.spin.valueChanged.connect(self._sync_slider)
        self.reset_button.clicked.connect(self.reset)

        layout = QGridLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.slider, 0, 0)
        layout.addWidget(self.spin, 0, 1)
        layout.addWidget(self.reset_button, 0, 2)

    @property
    def valueChanged(self):  # noqa: N802 - Qt-style property
        return self.slider.valueChanged

    def value_ev(self) -> float:
        return self.slider.value() / self._scale

    def set_ev(self, value: float) -> None:
        value = min(max(value, self.spin.minimum()), self.spin.maximum())
        self.slider.setValue(round(value * self._scale))

    def reset(self) -> None:
        self.set_ev(self._default_value)

    def _sync_spin(self, value: int) -> None:
        self.spin.blockSignals(True)
        self.spin.setValue(value / self._scale)
        self.spin.blockSignals(False)

    def _sync_slider(self, value: float) -> None:
        self.slider.setValue(round(value * self._scale))


class TrimPreviewLabel(QLabel):
    trim_drag_started = Signal(QPoint)
    trim_drag_moved = Signal(QPoint)
    trim_drag_finished = Signal(QPoint)

    def __init__(self, text: str = "") -> None:
        super().__init__(text)
        self._trim_dragging = False

    def mousePressEvent(self, event) -> None:  # noqa: N802 - Qt override
        if event.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return

        point = self._image_point(event.position().toPoint(), clamp=False)
        if point is not None:
            self._trim_dragging = True
            self.trim_drag_started.emit(point)
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802 - Qt override
        if not self._trim_dragging:
            super().mouseMoveEvent(event)
            return
        point = self._image_point(event.position().toPoint(), clamp=True)
        if point is not None:
            self.trim_drag_moved.emit(point)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802 - Qt override
        if not self._trim_dragging or event.button() != Qt.MouseButton.LeftButton:
            super().mouseReleaseEvent(event)
            return
        self._trim_dragging = False
        point = self._image_point(event.position().toPoint(), clamp=True)
        if point is not None:
            self.trim_drag_finished.emit(point)

    def _image_point(self, point: QPoint, clamp: bool) -> QPoint | None:
        pixmap = self.pixmap()
        if pixmap is None:
            return None

        pixmap_rect = QRect(0, 0, pixmap.width(), pixmap.height())
        pixmap_rect.moveCenter(self.rect().center())
        if not clamp and not pixmap_rect.contains(point):
            return None

        x = min(max(point.x(), pixmap_rect.left()), pixmap_rect.right())
        y = min(max(point.y(), pixmap_rect.top()), pixmap_rect.bottom())
        return QPoint(x - pixmap_rect.left(), y - pixmap_rect.top())


class RawDevelopmentWindow(QMainWindow):
    developed = Signal(Path)
    settings_save_requested = Signal(object)

    def __init__(
        self,
        raw_path: Path,
        source_image_path: Path | None = None,
        initial_settings: dict | None = None,
        language: str = "en",
    ) -> None:
        super().__init__()
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.resize(1280, 860)
        self.raw_path = raw_path
        self.source_image_path = source_image_path
        self.language = language if language in RAW_TRANSLATIONS else "en"
        self.base_rgb: np.ndarray | None = None
        self.preview_rgb: np.ndarray | None = None
        self.trim_rect: tuple[float, float, float, float] | None = None
        self._trim_start: tuple[float, float] | None = None
        self._last_saved_settings: dict | None = None
        self._applying_settings = False
        self._render_timer = QTimer(self)
        self._render_timer.setSingleShot(True)
        self._render_timer.setInterval(120)
        self._render_timer.timeout.connect(self.render_preview)

        self.image_label = TrimPreviewLabel(self._tr("open_raw_file"))
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setMinimumSize(640, 420)
        self.image_label.setStyleSheet("background:#101216;color:#aeb6c2;")
        self.image_label.trim_drag_started.connect(self._trim_drag_started)
        self.image_label.trim_drag_moved.connect(self._trim_drag_moved)
        self.image_label.trim_drag_finished.connect(self._trim_drag_finished)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.image_label)

        self.histogram = HistogramWidget()
        histogram_controls = self._build_histogram_controls()
        controls = self._build_controls()
        side = QWidget()
        side_layout = QVBoxLayout(side)
        side_layout.addWidget(histogram_controls)
        side_layout.addWidget(self.histogram)
        side_layout.addWidget(controls)
        side_layout.addStretch(1)
        side_layout.addWidget(self._build_bottom_actions())

        splitter = QSplitter()
        splitter.addWidget(scroll)
        splitter.addWidget(side)
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 1)
        self.setCentralWidget(splitter)
        self._build_menu()
        self.setWindowTitle(self._tr("window_title", name=raw_path.name))
        if initial_settings:
            self.apply_settings(initial_settings)
        self._last_saved_settings = self.current_settings()
        self.queue_full_render()

    @classmethod
    def can_open(cls, raw_path: Path) -> bool:
        return raw_path.suffix.casefold() in RAW_EXTENSIONS

    @staticmethod
    def dependencies_available() -> bool:
        return rawpy is not None and np is not None

    def _tr(self, key: str, **values: object) -> str:
        text = RAW_TRANSLATIONS.get(self.language, RAW_TRANSLATIONS["en"]).get(
            key, RAW_TRANSLATIONS["en"].get(key, key)
        )
        return text.format(**values) if values else text

    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu(self._tr("file"))
        save_settings_action = QAction(self._tr("save_settings"), self)
        save_settings_action.setEnabled(self.source_image_path is not None)
        save_settings_action.triggered.connect(self.save_development_settings)
        file_menu.addAction(save_settings_action)
        file_menu.addSeparator()
        self.overwrite_action = QAction(self._tr("overwrite_source"), self)
        self.overwrite_action.setEnabled(self.source_image_path is not None)
        self.overwrite_action.triggered.connect(self.overwrite_source_image)
        file_menu.addAction(self.overwrite_action)
        export_action = QAction(self._tr("export"), self)
        export_action.triggered.connect(self.export_developed_image)
        file_menu.addAction(export_action)
        file_menu.addSeparator()
        close_action = QAction(self._tr("close"), self)
        close_action.triggered.connect(self.close)
        file_menu.addAction(close_action)

    def current_settings(self) -> dict:
        return {
            "version": 1,
            "wb_mode": self.wb_mode.currentData(),
            "half_size": self.half_size.isChecked(),
            "output_size": self.output_size.currentData(),
            "temperature": self.temperature.value(),
            "tint": self.tint.value(),
            "brightness_ev": self.brightness_ev.value_ev(),
            "contrast": self.contrast.value(),
            "highlights": self.highlights.value(),
            "shadows": self.shadows.value(),
            "hue": self.hue.value(),
            "saturation": self.saturation.value(),
            "green_magenta": self.green_magenta.value(),
            "red": self.red.value(),
            "green": self.green.value(),
            "blue": self.blue.value(),
            "trim_enabled": self.trim_enabled.isChecked(),
            "trim_rect": list(self.trim_rect) if self.trim_rect is not None else None,
            "trim_aspect": self._selected_trim_aspect_key(),
        }

    def apply_settings(self, settings: dict) -> None:
        self._applying_settings = True
        try:
            wb_mode = self._wb_mode_setting(settings.get("wb_mode", WB_CAMERA))
            wb_index = self.wb_mode.findData(wb_mode)
            self.wb_mode.setCurrentIndex(max(0, wb_index))
            self.half_size.setChecked(bool(settings.get("half_size", True)))
            output_size = str(settings.get("output_size", OUTPUT_SIZE_HALF))
            output_index = self.output_size.findData(output_size)
            self.output_size.setCurrentIndex(max(0, output_index))
            self.temperature.setValue(self._int_setting(settings, "temperature", 5500))
            self.tint.setValue(self._int_setting(settings, "tint", 0))
            self.brightness_ev.set_ev(self._float_setting(settings, "brightness_ev", 0.0))
            self.contrast.setValue(self._int_setting(settings, "contrast", 0))
            self.highlights.setValue(self._int_setting(settings, "highlights", 0))
            self.shadows.setValue(self._int_setting(settings, "shadows", 0))
            self.hue.setValue(self._int_setting(settings, "hue", 0))
            self.saturation.setValue(self._int_setting(settings, "saturation", 0))
            self.green_magenta.setValue(self._int_setting(settings, "green_magenta", 0))
            self.red.setValue(self._int_setting(settings, "red", 0))
            self.green.setValue(self._int_setting(settings, "green", 0))
            self.blue.setValue(self._int_setting(settings, "blue", 0))
            self.trim_rect = self._trim_rect_setting(settings.get("trim_rect"))
            self._trim_start = None
            self._set_trim_aspect(str(settings.get("trim_aspect", "none")))
            self.trim_enabled.setChecked(
                bool(settings.get("trim_enabled", False)) and self.trim_rect is not None
            )
            self.trim_button.setEnabled(self.trim_rect is not None)
        finally:
            self._applying_settings = False

    def save_development_settings(self) -> bool:
        if self.source_image_path is None:
            return False
        settings = self.current_settings()
        self.settings_save_requested.emit(
            {
                "raw_path": self.raw_path,
                "source_image_path": self.source_image_path,
                "settings": settings,
            }
        )
        self._last_saved_settings = dict(settings)
        self.statusBar().showMessage(self._tr("settings_saved"), 4000)
        return True

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt override
        if not self._has_unsaved_settings():
            event.accept()
            return

        result = QMessageBox.warning(
            self,
            self._tr("save_settings_prompt"),
            self._tr("save_settings_before_close"),
            (
                QMessageBox.StandardButton.Save
                | QMessageBox.StandardButton.Discard
                | QMessageBox.StandardButton.Cancel
            ),
            QMessageBox.StandardButton.Save,
        )
        if result == QMessageBox.StandardButton.Cancel:
            event.ignore()
            return
        if result == QMessageBox.StandardButton.Save and not self.save_development_settings():
            event.ignore()
            return
        event.accept()

    def _has_unsaved_settings(self) -> bool:
        return (
            self.source_image_path is not None
            and self._last_saved_settings is not None
            and self.current_settings() != self._last_saved_settings
        )

    @staticmethod
    def _int_setting(settings: dict, key: str, default: int) -> int:
        try:
            return int(settings.get(key, default))
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _float_setting(settings: dict, key: str, default: float) -> float:
        try:
            return float(settings.get(key, default))
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _wb_mode_setting(value: object) -> str:
        text = str(value)
        return {
            WB_CAMERA: WB_CAMERA,
            WB_AUTO: WB_AUTO,
            WB_CUSTOM: WB_CUSTOM,
            "Camera WB": WB_CAMERA,
            "Auto WB": WB_AUTO,
            "Custom Temp/Tint": WB_CUSTOM,
            "カメラ設定": WB_CAMERA,
            "自動": WB_AUTO,
            "色温度/色かぶり補正": WB_CUSTOM,
        }.get(text, WB_CAMERA)

    @staticmethod
    def _trim_rect_setting(value: object) -> tuple[float, float, float, float] | None:
        if not isinstance(value, (list, tuple)) or len(value) != 4:
            return None
        try:
            left, top, right, bottom = (float(item) for item in value)
        except (TypeError, ValueError):
            return None
        left, right = sorted((min(max(left, 0.0), 1.0), min(max(right, 0.0), 1.0)))
        top, bottom = sorted((min(max(top, 0.0), 1.0), min(max(bottom, 0.0), 1.0)))
        if right - left <= 0.001 or bottom - top <= 0.001:
            return None
        return (left, top, right, bottom)

    def _build_histogram_controls(self) -> QWidget:
        root = QGroupBox(self._tr("histogram"))
        layout = QHBoxLayout(root)
        self.histogram_checks: dict[str, QCheckBox] = {}
        for channel in ("Y", "R", "G", "B"):
            checkbox = QCheckBox(channel)
            checkbox.setChecked(True)
            checkbox.stateChanged.connect(self.update_histogram_channels)
            self.histogram_checks[channel] = checkbox
            layout.addWidget(checkbox)
        layout.addStretch(1)
        return root

    def _build_controls(self) -> QWidget:
        root = QWidget()
        layout = QVBoxLayout(root)

        reset_label = self._tr("reset")

        raw_box = QGroupBox(self._tr("raw"))
        raw_form = QFormLayout(raw_box)
        self.wb_mode = QComboBox()
        self.wb_mode.addItem(self._tr("wb_camera"), WB_CAMERA)
        self.wb_mode.addItem(self._tr("wb_auto"), WB_AUTO)
        self.wb_mode.addItem(self._tr("wb_custom"), WB_CUSTOM)
        self.wb_mode.currentIndexChanged.connect(self.queue_full_render)
        self.half_size = QCheckBox(self._tr("half_size_preview"))
        self.half_size.setChecked(True)
        self.half_size.stateChanged.connect(self.queue_full_render)
        self.output_size = QComboBox()
        self.output_size.addItem(self._tr("output_half"), OUTPUT_SIZE_HALF)
        self.output_size.addItem(self._tr("output_full"), OUTPUT_SIZE_FULL)
        self.temperature = SliderRow(2500, 10000, 5500, " K", reset_label)
        self.tint = SliderRow(-100, 100, 0, reset_label=reset_label)
        self.temperature.valueChanged.connect(self._custom_wb_value_changed)
        self.tint.valueChanged.connect(self._custom_wb_value_changed)
        raw_form.addRow(self._tr("wb"), self.wb_mode)
        raw_form.addRow(self._tr("temperature"), self.temperature)
        raw_form.addRow(self._tr("tint"), self.tint)
        raw_form.addRow("", self.half_size)
        raw_form.addRow(self._tr("output_size"), self.output_size)
        layout.addWidget(raw_box)

        tone_box = QGroupBox(self._tr("tone"))
        tone_form = QFormLayout(tone_box)
        self.brightness_ev = EvSliderRow(-5.0, 5.0, 0.0, reset_label)
        self.contrast = SliderRow(-100, 100, 0, reset_label=reset_label)
        self.highlights = SliderRow(-100, 100, 0, reset_label=reset_label)
        self.shadows = SliderRow(-100, 100, 0, reset_label=reset_label)
        for row in (self.brightness_ev, self.contrast, self.highlights, self.shadows):
            row.valueChanged.connect(self.queue_adjust_render)
        tone_form.addRow(self._tr("brightness"), self.brightness_ev)
        tone_form.addRow(self._tr("contrast"), self.contrast)
        tone_form.addRow(self._tr("highlights"), self.highlights)
        tone_form.addRow(self._tr("shadows"), self.shadows)
        layout.addWidget(tone_box)

        color_box = QGroupBox(self._tr("color"))
        color_form = QFormLayout(color_box)
        self.hue = SliderRow(-180, 180, 0, " deg", reset_label)
        self.saturation = SliderRow(-100, 100, 0, reset_label=reset_label)
        self.green_magenta = SliderRow(-100, 100, 0, reset_label=reset_label)
        self.green_magenta.slider.setStyleSheet(
            "QSlider::groove:horizontal {"
            "height: 6px;"
            "background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #d84bd9, stop:1 #2ee66d);"
            "}"
        )
        self.red = SliderRow(-100, 100, 0, reset_label=reset_label)
        self.green = SliderRow(-100, 100, 0, reset_label=reset_label)
        self.blue = SliderRow(-100, 100, 0, reset_label=reset_label)
        for row in (self.hue, self.saturation, self.green_magenta, self.red, self.green, self.blue):
            row.valueChanged.connect(self.queue_adjust_render)
        color_form.addRow(self._tr("hue"), self.hue)
        color_form.addRow(self._tr("saturation"), self.saturation)
        color_form.addRow(self._tr("green_magenta"), self.green_magenta)
        color_form.addRow(self._tr("red"), self.red)
        color_form.addRow(self._tr("green"), self.green)
        color_form.addRow(self._tr("blue"), self.blue)
        layout.addWidget(color_box)

        reset_button = QPushButton(self._tr("reset_adjustments"))
        reset_button.clicked.connect(self.reset_adjustments)
        layout.addWidget(reset_button)

        trim_aspect_row = QWidget()
        trim_aspect_layout = QHBoxLayout(trim_aspect_row)
        trim_aspect_layout.setContentsMargins(0, 0, 0, 0)
        trim_aspect_layout.addWidget(QLabel(self._tr("aspect")))
        self.trim_aspect_group = QButtonGroup(self)
        self.trim_aspect_buttons: dict[str, QRadioButton] = {}
        for key, label in (
            ("none", self._tr("aspect_none")),
            ("4:3", "4:3"),
            ("3:4", "3:4"),
            ("16:9", "16:9"),
            ("9:16", "9:16"),
        ):
            button = QRadioButton(label)
            button.setChecked(key == "none")
            self.trim_aspect_group.addButton(button)
            self.trim_aspect_buttons[key] = button
            trim_aspect_layout.addWidget(button)
        trim_aspect_layout.addStretch(1)
        layout.addWidget(trim_aspect_row)

        trim_row = QWidget()
        trim_layout = QHBoxLayout(trim_row)
        trim_layout.setContentsMargins(0, 0, 0, 0)
        self.trim_enabled = QCheckBox(self._tr("trim"))
        self.trim_enabled.stateChanged.connect(self._trim_enabled_changed)
        self.trim_button = QPushButton(self._tr("trim"))
        self.trim_button.setEnabled(False)
        self.trim_button.clicked.connect(self.enable_trim_from_selection)
        trim_layout.addWidget(self.trim_enabled)
        trim_layout.addWidget(self.trim_button)
        trim_layout.addStretch(1)
        layout.addWidget(trim_row)
        return root

    def _build_bottom_actions(self) -> QWidget:
        root = QWidget()
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        self.save_settings_button = QPushButton(self._tr("save_settings"))
        self.save_settings_button.setEnabled(self.source_image_path is not None)
        self.save_settings_button.clicked.connect(self.save_development_settings)
        export_button = QPushButton(self._tr("export"))
        export_button.clicked.connect(self.export_developed_image)
        overwrite_button = QPushButton(self._tr("overwrite_source"))
        overwrite_button.setEnabled(self.source_image_path is not None)
        overwrite_button.clicked.connect(self.overwrite_source_image)
        layout.addWidget(self.save_settings_button)
        layout.addWidget(export_button)
        layout.addWidget(overwrite_button)
        return root

    def update_histogram_channels(self) -> None:
        self.histogram.set_visible_channels(
            {channel: checkbox.isChecked() for channel, checkbox in self.histogram_checks.items()}
        )

    def queue_full_render(self) -> None:
        self._render_timer.start()

    def _custom_wb_value_changed(self) -> None:
        if self._applying_settings:
            return
        if self.wb_mode.currentData() != WB_CUSTOM:
            custom_index = self.wb_mode.findData(WB_CUSTOM)
            self.wb_mode.setCurrentIndex(max(0, custom_index))
            return
        self.queue_full_render()

    def queue_adjust_render(self) -> None:
        if self.base_rgb is None:
            return
        self.preview_rgb = self.apply_adjustments(self.base_rgb)
        self.update_image()

    def render_preview(self) -> None:
        if not self.dependencies_available():
            QMessageBox.critical(
                self,
                self._tr("raw_development"),
                self._tr("dependencies_missing"),
            )
            self.close()
            return
        self.statusBar().showMessage(self._tr("decoding_raw"))
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            rgb = self._decode_raw(fit_preview=True)
            self.base_rgb = rgb
            self.preview_rgb = self.apply_adjustments(rgb)
            self.update_image()
            self.statusBar().showMessage(self._tr("loaded", name=self.raw_path.name), 4000)
        except Exception as exc:  # pragma: no cover - defensive GUI path
            QMessageBox.warning(
                self,
                self._tr("raw_development"),
                self._tr("raw_load_failed", error=exc),
            )
            self.close()
        finally:
            QApplication.restoreOverrideCursor()

    def _decode_raw(self, fit_preview: bool, *, half_size_decode: bool | None = None) -> np.ndarray:
        with rawpy.imread(str(self.raw_path)) as raw:
            rgb16 = raw.postprocess(
                **self._rawpy_params(
                    fit_preview=fit_preview,
                    half_size_decode=half_size_decode,
                )
            )
        rgb = rgb16.astype(np.float32) / 65535.0
        if fit_preview:
            rgb = self._fit_preview(rgb)
        return rgb

    def _rawpy_params(
        self,
        fit_preview: bool,
        *,
        half_size_decode: bool | None = None,
    ) -> dict:
        wb_mode = self.wb_mode.currentData()
        if half_size_decode is None:
            half_size_decode = fit_preview and self.half_size.isChecked()
        params = {
            "output_bps": 16,
            "no_auto_bright": True,
            "use_camera_wb": wb_mode == WB_CAMERA,
            "use_auto_wb": wb_mode == WB_AUTO,
            "half_size": half_size_decode,
            "median_filter_passes": 1,
        }
        demosaic_algorithms = getattr(rawpy, "DemosaicAlgorithm", None)
        demosaic_algorithm = getattr(demosaic_algorithms, "AHD", None)
        if demosaic_algorithm is not None:
            params["demosaic_algorithm"] = demosaic_algorithm
        fbdd_noise_reductions = getattr(rawpy, "FBDDNoiseReductionMode", None)
        fbdd_noise_reduction = getattr(fbdd_noise_reductions, "Full", None)
        if fbdd_noise_reduction is not None:
            params["fbdd_noise_reduction"] = fbdd_noise_reduction
        if wb_mode == WB_CUSTOM:
            params["user_wb"] = self._custom_wb_multipliers()
        return params

    def _custom_wb_multipliers(self) -> list[float]:
        temp = float(self.temperature.value())
        tint = float(self.tint.value()) / 100.0
        temp_offset = (temp - 5500.0) / 5500.0
        red = 1.0 - temp_offset * 0.65 + tint * 0.18
        blue = 1.0 + temp_offset * 0.85 + tint * 0.18
        green = 1.0 - tint * 0.25
        return [max(0.2, red), max(0.2, green), max(0.2, blue), max(0.2, green)]

    def apply_adjustments(self, rgb: np.ndarray) -> np.ndarray:
        image = rgb.copy()
        image *= math.pow(2.0, self.brightness_ev.value_ev())

        shadows = self.shadows.value() / 100.0
        highlights = self.highlights.value() / 100.0
        luma = self._luma(image)[..., None]
        shadow_mask = np.clip((0.55 - luma) / 0.55, 0.0, 1.0)
        highlight_mask = np.clip((luma - 0.45) / 0.55, 0.0, 1.0)
        image += shadow_mask * shadows * 0.35
        image += highlight_mask * highlights * 0.35

        contrast = self.contrast.value() / 100.0
        image = (image - 0.5) * (1.0 + contrast * 1.4) + 0.5

        image[..., 0] *= 1.0 + self.red.value() / 100.0
        image[..., 1] *= 1.0 + self.green.value() / 100.0
        image[..., 2] *= 1.0 + self.blue.value() / 100.0
        green_magenta = self.green_magenta.value() / 100.0
        image[..., 0] *= 1.0 - green_magenta * 0.3
        image[..., 1] *= 1.0 + green_magenta * 0.6
        image[..., 2] *= 1.0 - green_magenta * 0.3

        image = np.clip(image, 0.0, 1.0)
        image = self._adjust_hue_saturation(image, self.hue.value(), self.saturation.value() / 100.0)
        return np.clip(image, 0.0, 1.0)

    def _adjust_hue_saturation(self, image: np.ndarray, hue_degrees: int, saturation: float) -> np.ndarray:
        if hue_degrees == 0 and saturation == 0:
            return image
        flat = image.reshape(-1, 3)
        r, g, b = flat[:, 0], flat[:, 1], flat[:, 2]
        maxc = flat.max(axis=1)
        minc = flat.min(axis=1)
        delta = maxc - minc

        hue = np.zeros_like(maxc)
        nonzero = delta > 1e-6
        red_max = nonzero & (maxc == r)
        green_max = nonzero & (maxc == g)
        blue_max = nonzero & (maxc == b)
        hue[red_max] = ((g[red_max] - b[red_max]) / delta[red_max]) % 6.0
        hue[green_max] = ((b[green_max] - r[green_max]) / delta[green_max]) + 2.0
        hue[blue_max] = ((r[blue_max] - g[blue_max]) / delta[blue_max]) + 4.0
        hue = (hue / 6.0 + hue_degrees / 360.0) % 1.0

        sat = np.zeros_like(maxc)
        sat[maxc > 1e-6] = delta[maxc > 1e-6] / maxc[maxc > 1e-6]
        sat = np.clip(sat * (1.0 + saturation), 0.0, 1.0)
        val = maxc
        out = self._hsv_to_rgb(hue, sat, val)
        return out.reshape(image.shape)

    @staticmethod
    def _hsv_to_rgb(hue: np.ndarray, sat: np.ndarray, val: np.ndarray) -> np.ndarray:
        h = hue * 6.0
        i = np.floor(h).astype(np.int32)
        f = h - i
        p = val * (1.0 - sat)
        q = val * (1.0 - sat * f)
        t = val * (1.0 - sat * (1.0 - f))
        i = i % 6
        out = np.empty((hue.size, 3), dtype=np.float32)
        choices = [
            (val, t, p),
            (q, val, p),
            (p, val, t),
            (p, q, val),
            (t, p, val),
            (val, p, q),
        ]
        for index, channels in enumerate(choices):
            mask = i == index
            if np.any(mask):
                out[mask, 0] = channels[0][mask]
                out[mask, 1] = channels[1][mask]
                out[mask, 2] = channels[2][mask]
        return out

    @staticmethod
    def _luma(image: np.ndarray) -> np.ndarray:
        return 0.2126 * image[..., 0] + 0.7152 * image[..., 1] + 0.0722 * image[..., 2]

    @staticmethod
    def _fit_preview(image: np.ndarray) -> np.ndarray:
        height, width = image.shape[:2]
        longest = max(height, width)
        if longest <= MAX_PREVIEW_SIDE:
            return image
        step = math.ceil(longest / MAX_PREVIEW_SIDE)
        return image[::step, ::step, :]

    def update_image(self) -> None:
        if self.preview_rgb is None:
            return
        image = self._to_qimage(self.preview_rgb)
        pixmap = QPixmap.fromImage(image)
        self._draw_trim_overlay(pixmap)
        self.image_label.setPixmap(pixmap)
        self.image_label.resize(pixmap.size())
        self.histogram.set_image(self.preview_rgb)

    def _trim_drag_started(self, point: QPoint) -> None:
        if self.preview_rgb is None:
            return
        normalized = self._normalized_preview_point(point)
        if normalized is None:
            return
        self._trim_start = normalized
        self.trim_rect = None
        self.trim_button.setEnabled(False)
        if self.trim_enabled.isChecked():
            self.trim_enabled.setChecked(False)
        self.statusBar().showMessage(self._tr("drag_trim"), 4000)
        self.update_image()

    def _trim_drag_moved(self, point: QPoint) -> None:
        if self._trim_start is None:
            return
        normalized = self._normalized_preview_point(point)
        if normalized is None:
            return
        self.trim_rect = self._constrained_trim_rect(self._trim_start, normalized)
        self.trim_button.setEnabled(self.trim_rect is not None)
        self.update_image()

    def _trim_drag_finished(self, point: QPoint) -> None:
        if self._trim_start is None:
            return
        normalized = self._normalized_preview_point(point)
        if normalized is not None:
            self.trim_rect = self._constrained_trim_rect(self._trim_start, normalized)
        self._trim_start = None
        self.trim_button.setEnabled(self.trim_rect is not None)
        if self.trim_rect is None:
            self.statusBar().showMessage(self._tr("trim_too_small"), 4000)
        else:
            self.statusBar().showMessage(self._tr("trim_selected"), 4000)
        self.update_image()

    def _normalized_preview_point(self, point: QPoint) -> tuple[float, float] | None:
        if self.preview_rgb is None:
            return None
        height, width = self.preview_rgb.shape[:2]
        if width <= 0 or height <= 0:
            return None
        x = min(max(point.x() / width, 0.0), 1.0)
        y = min(max(point.y() / height, 0.0), 1.0)
        return (x, y)

    def _constrained_trim_rect(
        self,
        start: tuple[float, float],
        end: tuple[float, float],
    ) -> tuple[float, float, float, float] | None:
        aspect = self._selected_trim_aspect()
        if aspect is None or self.preview_rgb is None:
            return self._trim_rect_setting((*start, *end))

        image_height, image_width = self.preview_rgb.shape[:2]
        start_x, start_y = start
        end_x, end_y = end
        dx = (end_x - start_x) * image_width
        dy = (end_y - start_y) * image_height
        abs_dx = abs(dx)
        abs_dy = abs(dy)
        if abs_dx <= 1.0 and abs_dy <= 1.0:
            return None

        sign_x = 1.0 if dx >= 0 else -1.0
        sign_y = 1.0 if dy >= 0 else -1.0
        fit_width = (abs_dx + abs_dy / aspect) / (1.0 + 1.0 / (aspect * aspect))
        max_width = image_width * (1.0 - start_x if sign_x > 0 else start_x)
        max_height = image_height * (1.0 - start_y if sign_y > 0 else start_y)
        fit_width = min(max(fit_width, 1.0), max_width, max_height * aspect)
        fit_height = fit_width / aspect
        constrained_x = start_x + sign_x * fit_width / image_width
        constrained_y = start_y + sign_y * fit_height / image_height
        return self._trim_rect_setting((start_x, start_y, constrained_x, constrained_y))

    def _selected_trim_aspect_key(self) -> str:
        for key, button in self.trim_aspect_buttons.items():
            if button.isChecked():
                return key
        return "none"

    def _selected_trim_aspect(self) -> float | None:
        key = self._selected_trim_aspect_key()
        if key == "4:3":
            return 4.0 / 3.0
        if key == "3:4":
            return 3.0 / 4.0
        if key == "16:9":
            return 16.0 / 9.0
        if key == "9:16":
            return 9.0 / 16.0
        return None

    def _set_trim_aspect(self, key: str) -> None:
        button = self.trim_aspect_buttons.get(key, self.trim_aspect_buttons["none"])
        button.setChecked(True)

    def enable_trim_from_selection(self) -> None:
        if self.trim_rect is None:
            self.statusBar().showMessage(self._tr("select_trim_first"), 4000)
            return
        self.trim_enabled.setChecked(True)
        self.statusBar().showMessage(self._tr("trim_enabled"), 4000)
        self.update_image()

    def _trim_enabled_changed(self) -> None:
        if self.trim_enabled.isChecked() and self.trim_rect is None:
            self.trim_enabled.blockSignals(True)
            self.trim_enabled.setChecked(False)
            self.trim_enabled.blockSignals(False)
            self.statusBar().showMessage(self._tr("select_trim_before_enable"), 4000)
            return
        self.update_image()

    def _draw_trim_overlay(self, pixmap: QPixmap) -> None:
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        rect = self._trim_rect_to_pixmap_rect(pixmap)
        if rect is None:
            if self._trim_start is not None:
                x = round(self._trim_start[0] * pixmap.width())
                y = round(self._trim_start[1] * pixmap.height())
                painter.setPen(QPen(QColor("#ffd34d"), 2))
                painter.drawLine(x - 10, y, x + 10, y)
                painter.drawLine(x, y - 10, x, y + 10)
            return

        overlay = QColor(0, 0, 0, 120 if self.trim_enabled.isChecked() else 80)
        painter.fillRect(QRect(0, 0, pixmap.width(), rect.top()), overlay)
        painter.fillRect(
            QRect(
                0,
                rect.bottom() + 1,
                pixmap.width(),
                pixmap.height() - rect.bottom() - 1,
            ),
            overlay,
        )
        painter.fillRect(QRect(0, rect.top(), rect.left(), rect.height()), overlay)
        painter.fillRect(
            QRect(
                rect.right() + 1,
                rect.top(),
                pixmap.width() - rect.right() - 1,
                rect.height(),
            ),
            overlay,
        )
        painter.setPen(QPen(QColor("#ffd34d"), 3))
        painter.drawRect(rect)
        painter.setPen(QPen(QColor("#101216"), 1))
        painter.drawRect(rect.adjusted(3, 3, -3, -3))

    def _trim_rect_to_pixmap_rect(self, pixmap: QPixmap) -> QRect | None:
        if self.trim_rect is None:
            return None
        left, top, right, bottom = self.trim_rect
        x1 = round(left * pixmap.width())
        y1 = round(top * pixmap.height())
        x2 = round(right * pixmap.width())
        y2 = round(bottom * pixmap.height())
        return QRect(x1, y1, max(1, x2 - x1), max(1, y2 - y1))

    def overwrite_source_image(self) -> None:
        if self.source_image_path is None:
            return
        if QMessageBox.question(
            self,
            self._tr("overwrite_title"),
            self._tr("overwrite_confirm", name=self.source_image_path.name),
        ) != QMessageBox.StandardButton.Yes:
            return
        self._save_developed_image(self.source_image_path)

    def export_developed_image(self) -> None:
        default = self.source_image_path or self.raw_path.with_suffix(".jpg")
        path, _selected_filter = QFileDialog.getSaveFileName(
            self,
            self._tr("export_title"),
            str(default),
            "JPEG (*.jpg *.jpeg);;PNG (*.png);;TIFF (*.tif *.tiff)",
        )
        if path:
            self._save_developed_image(Path(path))

    def _save_developed_image(self, path: Path) -> None:
        self.statusBar().showMessage(self._tr("rendering_output"))
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            full_rgb = self._decode_raw(
                fit_preview=False,
                half_size_decode=self.output_size.currentData() == OUTPUT_SIZE_HALF,
            )
            adjusted = self.apply_adjustments(full_rgb)
            image = self._to_qimage(self._crop_to_trim(adjusted))
            image.setDotsPerMeterX(RAW_OUTPUT_DOTS_PER_METER)
            image.setDotsPerMeterY(RAW_OUTPUT_DOTS_PER_METER)
            if not self._write_image(path, image):
                QMessageBox.critical(
                    self,
                    self._tr("raw_development"),
                    self._tr("save_failed", path=path),
                )
                return
            self.statusBar().showMessage(self._tr("saved", name=path.name), 4000)
            self.developed.emit(path)
        except Exception as exc:  # pragma: no cover - defensive GUI path
            QMessageBox.critical(
                self,
                self._tr("raw_development"),
                self._tr("export_failed", error=exc),
            )
        finally:
            QApplication.restoreOverrideCursor()

    @staticmethod
    def _write_image(path: Path, image: QImage) -> bool:
        writer = QImageWriter(str(path))
        if path.suffix.casefold() in {".jpg", ".jpeg"}:
            writer.setQuality(JPEG_OUTPUT_QUALITY)
        return writer.write(image)

    @staticmethod
    def _to_qimage(rgb: np.ndarray) -> QImage:
        arr = (np.clip(rgb, 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8)
        arr = np.ascontiguousarray(arr)
        height, width, channels = arr.shape
        image = QImage(
            arr.data,
            width,
            height,
            channels * width,
            QImage.Format.Format_RGB888,
        )
        return image.copy()

    def _crop_to_trim(self, image: np.ndarray) -> np.ndarray:
        if not self.trim_enabled.isChecked() or self.trim_rect is None:
            return image
        height, width = image.shape[:2]
        left, top, right, bottom = self.trim_rect
        x1 = min(max(math.floor(left * width), 0), width - 1)
        y1 = min(max(math.floor(top * height), 0), height - 1)
        x2 = min(max(math.ceil(right * width), x1 + 1), width)
        y2 = min(max(math.ceil(bottom * height), y1 + 1), height)
        return image[y1:y2, x1:x2, :]

    def reset_adjustments(self) -> None:
        for row in (
            self.contrast,
            self.highlights,
            self.shadows,
            self.hue,
            self.saturation,
            self.green_magenta,
            self.red,
            self.green,
            self.blue,
        ):
            row.setValue(0)
        self.brightness_ev.set_ev(0.0)
        self.temperature.setValue(5500)
        self.tint.setValue(0)
        self.queue_adjust_render()
