from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QLabel, QMainWindow, QWidget, QVBoxLayout


class ImagePreviewLabel(QLabel):
    def __init__(self) -> None:
        super().__init__()
        self._pixmap: QPixmap | None = None
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(240, 180)
        self.setText("No image selected")
        self.setStyleSheet("background: #202124; color: #d7dce2;")

    def set_image(self, path: Path | None) -> None:
        if path is None:
            self._pixmap = None
            self.setText("No image selected")
            self.setPixmap(QPixmap())
            return

        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            self._pixmap = None
            self.setText("Preview unavailable")
            self.setPixmap(QPixmap())
            return

        self._pixmap = pixmap
        self.setText("")
        self._fit_pixmap()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._fit_pixmap()

    def _fit_pixmap(self) -> None:
        if self._pixmap is None or self._pixmap.isNull():
            return
        scaled = self._pixmap.scaled(
            self.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.setPixmap(scaled)


class PreviewWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Preview")
        self.resize(900, 650)

        self.preview = ImagePreviewLabel()
        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.preview)
        self.setCentralWidget(central)

    def set_image(self, path: Path | None) -> None:
        if path is not None:
            self.setWindowTitle(path.name)
        else:
            self.setWindowTitle("Preview")
        self.preview.set_image(path)
