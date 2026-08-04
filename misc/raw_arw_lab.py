from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QColor, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QApplication,
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
    QScrollArea,
    QSlider,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

try:
    import numpy as np
except ImportError:  # pragma: no cover - shown in GUI startup path
    np = None

try:
    import rawpy
except ImportError:  # pragma: no cover - shown in GUI/CLI startup path
    rawpy = None


MAX_PREVIEW_SIDE = 1800


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
    def __init__(self, minimum: int, maximum: int, value: int, suffix: str = "") -> None:
        super().__init__()
        self._default_value = value
        self.suffix = suffix
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(minimum, maximum)
        self.slider.setValue(value)
        self.spin = QSpinBox()
        self.spin.setRange(minimum, maximum)
        self.spin.setValue(value)
        self.spin.setSuffix(suffix)
        self.reset_button = QPushButton("Reset")
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
    def __init__(self, minimum: float, maximum: float, value: float) -> None:
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
        self.reset_button = QPushButton("Reset")
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


class RawLabWindow(QMainWindow):
    def __init__(self, initial_path: Path | None) -> None:
        super().__init__()
        self.setWindowTitle("ARW RAW Lab")
        self.resize(1280, 860)
        self.raw_path: Path | None = None
        self.base_rgb: np.ndarray | None = None
        self.preview_rgb: np.ndarray | None = None
        self._render_timer = QTimer(self)
        self._render_timer.setSingleShot(True)
        self._render_timer.setInterval(120)
        self._render_timer.timeout.connect(self.render_preview)

        self.image_label = QLabel("Open an ARW file")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setMinimumSize(640, 420)
        self.image_label.setStyleSheet("background:#101216;color:#aeb6c2;")
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

        splitter = QSplitter()
        splitter.addWidget(scroll)
        splitter.addWidget(side)
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 1)
        self.setCentralWidget(splitter)
        self._build_menu()

        if initial_path:
            self.load_raw(initial_path)

    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("File")
        open_action = QAction("Open ARW...", self)
        open_action.triggered.connect(self.open_dialog)
        file_menu.addAction(open_action)
        save_action = QAction("Save preview PNG...", self)
        save_action.triggered.connect(self.save_preview)
        file_menu.addAction(save_action)

    def _build_histogram_controls(self) -> QWidget:
        root = QGroupBox("Histogram")
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

        open_button = QPushButton("Open ARW...")
        open_button.clicked.connect(self.open_dialog)
        layout.addWidget(open_button)

        raw_box = QGroupBox("RAW")
        raw_form = QFormLayout(raw_box)
        self.wb_mode = QComboBox()
        self.wb_mode.addItems(["Camera WB", "Auto WB", "Custom Temp/Tint"])
        self.wb_mode.currentIndexChanged.connect(self.queue_full_render)
        self.half_size = QCheckBox("Half-size decode")
        self.half_size.setChecked(True)
        self.half_size.stateChanged.connect(self.queue_full_render)
        self.temperature = SliderRow(2500, 10000, 5500, " K")
        self.tint = SliderRow(-100, 100, 0)
        self.temperature.valueChanged.connect(self.queue_full_render)
        self.tint.valueChanged.connect(self.queue_full_render)
        raw_form.addRow("WB", self.wb_mode)
        raw_form.addRow("Temperature", self.temperature)
        raw_form.addRow("Tint", self.tint)
        raw_form.addRow("", self.half_size)
        layout.addWidget(raw_box)

        tone_box = QGroupBox("Tone")
        tone_form = QFormLayout(tone_box)
        self.brightness_ev = EvSliderRow(-5.0, 5.0, 0.0)
        self.contrast = SliderRow(-100, 100, 0)
        self.highlights = SliderRow(-100, 100, 0)
        self.shadows = SliderRow(-100, 100, 0)
        for row in (self.brightness_ev, self.contrast, self.highlights, self.shadows):
            row.valueChanged.connect(self.queue_adjust_render)
        tone_form.addRow("Brightness", self.brightness_ev)
        tone_form.addRow("Contrast", self.contrast)
        tone_form.addRow("Highlights", self.highlights)
        tone_form.addRow("Shadows", self.shadows)
        layout.addWidget(tone_box)

        color_box = QGroupBox("Color")
        color_form = QFormLayout(color_box)
        self.hue = SliderRow(-180, 180, 0, " deg")
        self.saturation = SliderRow(-100, 100, 0)
        self.red = SliderRow(-100, 100, 0)
        self.green = SliderRow(-100, 100, 0)
        self.blue = SliderRow(-100, 100, 0)
        self.green_magenta = SliderRow(-100, 100, 0)
        self.green_magenta.slider.setStyleSheet(
            "QSlider::groove:horizontal {"
            "height: 6px;"
            "background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #d84bd9, stop:1 #2ee66d);"
            "}"
        )
        for row in (self.hue, self.saturation, self.green_magenta, self.red, self.green, self.blue):
            row.valueChanged.connect(self.queue_adjust_render)
        color_form.addRow("Hue", self.hue)
        color_form.addRow("Saturation", self.saturation)
        color_form.addRow("Green/Magenta", self.green_magenta)
        color_form.addRow("Red", self.red)
        color_form.addRow("Green", self.green)
        color_form.addRow("Blue", self.blue)
        layout.addWidget(color_box)

        reset_button = QPushButton("Reset adjustments")
        reset_button.clicked.connect(self.reset_adjustments)
        layout.addWidget(reset_button)
        return root

    def update_histogram_channels(self) -> None:
        self.histogram.set_visible_channels(
            {channel: checkbox.isChecked() for channel, checkbox in self.histogram_checks.items()}
        )

    def open_dialog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open RAW file",
            str(Path.home()),
            "RAW files (*.arw *.ARW);;All files (*.*)",
        )
        if path:
            self.load_raw(Path(path))

    def save_preview(self) -> None:
        if self.preview_rgb is None:
            return
        default = self.raw_path.with_suffix(".preview.png") if self.raw_path else Path("preview.png")
        path, _ = QFileDialog.getSaveFileName(self, "Save preview PNG", str(default), "PNG (*.png)")
        if not path:
            return
        image = self._to_qimage(self.preview_rgb)
        image.save(path)

    def load_raw(self, path: Path) -> None:
        if rawpy is None or np is None:
            QMessageBox.critical(
                self,
                "RAW dependencies are required",
                "rawpy and numpy are required.\n\n"
                "Example:\n"
                "  $WUV run --with rawpy --with numpy python misc/raw_arw_lab.py image.ARW",
            )
            return
        if not path.exists():
            QMessageBox.warning(self, "File not found", str(path))
            return
        self.raw_path = path
        self.setWindowTitle(f"ARW RAW Lab - {path.name}")
        self.queue_full_render()

    def queue_full_render(self) -> None:
        self._render_timer.start()

    def queue_adjust_render(self) -> None:
        if self.base_rgb is None:
            return
        self.preview_rgb = self.apply_adjustments(self.base_rgb)
        self.update_image()

    def render_preview(self) -> None:
        if self.raw_path is None or rawpy is None:
            return
        self.statusBar().showMessage("Decoding RAW...")
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            with rawpy.imread(str(self.raw_path)) as raw:
                params = self._rawpy_params()
                rgb16 = raw.postprocess(**params)
            rgb = rgb16.astype(np.float32) / 65535.0
            rgb = self._fit_preview(rgb)
            self.base_rgb = rgb
            self.preview_rgb = self.apply_adjustments(rgb)
            self.update_image()
            self.statusBar().showMessage(f"Loaded {self.raw_path.name}", 4000)
        except Exception as exc:  # pragma: no cover - defensive GUI path
            QMessageBox.critical(self, "RAW decode failed", str(exc))
            self.statusBar().clearMessage()
        finally:
            QApplication.restoreOverrideCursor()

    def _rawpy_params(self) -> dict:
        wb_mode = self.wb_mode.currentText()
        params = {
            "output_bps": 16,
            "no_auto_bright": True,
            "use_camera_wb": wb_mode == "Camera WB",
            "use_auto_wb": wb_mode == "Auto WB",
            "half_size": self.half_size.isChecked(),
        }
        if wb_mode == "Custom Temp/Tint":
            params["user_wb"] = self._custom_wb_multipliers()
        return params

    def _custom_wb_multipliers(self) -> list[float]:
        temp = float(self.temperature.value())
        tint = float(self.tint.value()) / 100.0
        # Simple preview-oriented approximation: lower K warms by lifting red,
        # higher K cools by lifting blue. Tint shifts green against magenta.
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
        self.image_label.setPixmap(pixmap)
        self.image_label.resize(pixmap.size())
        self.histogram.set_image(self.preview_rgb)

    @staticmethod
    def _to_qimage(rgb: np.ndarray) -> QImage:
        arr = (np.clip(rgb, 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8)
        arr = np.ascontiguousarray(arr)
        height, width, channels = arr.shape
        image = QImage(arr.data, width, height, channels * width, QImage.Format.Format_RGB888)
        return image.copy()

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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Standalone ARW RAW development lab.")
    parser.add_argument("raw_file", nargs="?", type=Path, help="ARW file to open")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    app = QApplication(sys.argv)
    window = RawLabWindow(args.raw_file)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
