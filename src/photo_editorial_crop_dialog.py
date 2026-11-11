from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QImage, QImageReader, QPainter, QPen
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)


class CropPreviewWidget(QWidget):
    cropChanged = Signal()

    def __init__(self, image: QImage, target_aspect: float) -> None:
        super().__init__()
        self.image = image
        self.target_aspect = max(0.1, target_aspect)
        self.center_x = 0.5
        self.center_y = 0.5
        self.zoom = 1.0
        self.setMinimumSize(520, 360)

    def set_crop(self, center_x: float, center_y: float, zoom: float) -> None:
        self.center_x = center_x
        self.center_y = center_y
        self.zoom = max(1.0, zoom)
        self.update()
        self.cropChanged.emit()

    def crop_rect(self) -> QRectF:
        if self.image.isNull() or self.image.height() <= 0:
            return QRectF(0.0, 0.0, 1.0, 1.0)
        source_aspect = self.image.width() / self.image.height()
        if source_aspect >= self.target_aspect:
            base_width = self.target_aspect / source_aspect
            base_height = 1.0
        else:
            base_width = 1.0
            base_height = source_aspect / self.target_aspect
        width = base_width / self.zoom
        height = base_height / self.zoom
        center_x = min(1.0 - width / 2.0, max(width / 2.0, self.center_x))
        center_y = min(1.0 - height / 2.0, max(height / 2.0, self.center_y))
        return QRectF(center_x - width / 2.0, center_y - height / 2.0, width, height)

    def paintEvent(self, event) -> None:  # noqa: N802
        super().paintEvent(event)
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#20242a"))
        if self.image.isNull():
            return
        scaled = self.image.scaled(
            self.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        image_rect = QRectF(
            (self.width() - scaled.width()) / 2.0,
            (self.height() - scaled.height()) / 2.0,
            scaled.width(),
            scaled.height(),
        )
        painter.drawImage(image_rect, scaled)
        crop = self.crop_rect()
        crop_rect = QRectF(
            image_rect.x() + crop.x() * image_rect.width(),
            image_rect.y() + crop.y() * image_rect.height(),
            crop.width() * image_rect.width(),
            crop.height() * image_rect.height(),
        )
        shade = QColor(0, 0, 0, 145)
        painter.fillRect(QRectF(image_rect.left(), image_rect.top(), image_rect.width(), crop_rect.top() - image_rect.top()), shade)
        painter.fillRect(QRectF(image_rect.left(), crop_rect.bottom(), image_rect.width(), image_rect.bottom() - crop_rect.bottom()), shade)
        painter.fillRect(QRectF(image_rect.left(), crop_rect.top(), crop_rect.left() - image_rect.left(), crop_rect.height()), shade)
        painter.fillRect(QRectF(crop_rect.right(), crop_rect.top(), image_rect.right() - crop_rect.right(), crop_rect.height()), shade)
        painter.setPen(QPen(QColor("#ffffff"), 3.0))
        painter.drawRect(crop_rect)
        painter.setPen(QPen(QColor(255, 255, 255, 150), 1.0))
        painter.drawLine(crop_rect.left() + crop_rect.width() / 3.0, crop_rect.top(), crop_rect.left() + crop_rect.width() / 3.0, crop_rect.bottom())
        painter.drawLine(crop_rect.left() + crop_rect.width() * 2.0 / 3.0, crop_rect.top(), crop_rect.left() + crop_rect.width() * 2.0 / 3.0, crop_rect.bottom())
        painter.drawLine(crop_rect.left(), crop_rect.top() + crop_rect.height() / 3.0, crop_rect.right(), crop_rect.top() + crop_rect.height() / 3.0)
        painter.drawLine(crop_rect.left(), crop_rect.top() + crop_rect.height() * 2.0 / 3.0, crop_rect.right(), crop_rect.top() + crop_rect.height() * 2.0 / 3.0)


class PhotoCropDialog(QDialog):
    def __init__(
        self,
        path: Path,
        target_aspect: float,
        crop_rect: QRectF,
        texts: dict[str, str],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._texts = texts
        reader = QImageReader(str(path))
        reader.setAutoTransform(True)
        image = reader.read()
        self.preview = CropPreviewWidget(image, target_aspect)
        self.setWindowTitle(self._tr("crop_title"))
        self.resize(720, 620)

        self.horizontal_slider = QSlider(Qt.Orientation.Horizontal)
        self.vertical_slider = QSlider(Qt.Orientation.Horizontal)
        self.zoom_slider = QSlider(Qt.Orientation.Horizontal)
        for slider in (self.horizontal_slider, self.vertical_slider):
            slider.setRange(0, 1000)
        self.zoom_slider.setRange(100, 400)
        self.zoom_value = QLabel()
        self.reset_button = QPushButton(self._tr("crop_reset"))

        center_x = crop_rect.x() + crop_rect.width() / 2.0
        center_y = crop_rect.y() + crop_rect.height() / 2.0
        base_rect = self.preview.crop_rect()
        zoom = max(
            base_rect.width() / max(0.02, crop_rect.width()),
            base_rect.height() / max(0.02, crop_rect.height()),
        )
        self.horizontal_slider.setValue(round(center_x * 1000))
        self.vertical_slider.setValue(round(center_y * 1000))
        self.zoom_slider.setValue(round(min(4.0, max(1.0, zoom)) * 100))

        form = QFormLayout()
        form.addRow(self._tr("crop_horizontal"), self.horizontal_slider)
        form.addRow(self._tr("crop_vertical"), self.vertical_slider)
        zoom_row = QVBoxLayout()
        zoom_row.addWidget(self.zoom_slider)
        zoom_row.addWidget(self.zoom_value)
        form.addRow(self._tr("crop_zoom"), zoom_row)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        self.reset_button.clicked.connect(self._reset)
        layout = QVBoxLayout(self)
        layout.addWidget(self.preview, 1)
        layout.addLayout(form)
        layout.addWidget(self.reset_button)
        layout.addWidget(buttons)

        self.horizontal_slider.valueChanged.connect(self._update_crop)
        self.vertical_slider.valueChanged.connect(self._update_crop)
        self.zoom_slider.valueChanged.connect(self._update_crop)
        self._update_crop()

    def selected_crop_rect(self) -> QRectF:
        return self.preview.crop_rect()

    def _update_crop(self) -> None:
        zoom = self.zoom_slider.value() / 100.0
        self.zoom_value.setText(f"{self.zoom_slider.value()}%")
        self.preview.set_crop(
            self.horizontal_slider.value() / 1000.0,
            self.vertical_slider.value() / 1000.0,
            zoom,
        )

    def _reset(self) -> None:
        self.horizontal_slider.setValue(500)
        self.vertical_slider.setValue(500)
        self.zoom_slider.setValue(100)

    def _tr(self, key: str) -> str:
        return self._texts.get(key, key)
