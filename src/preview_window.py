from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEvent, QSize, Qt, Signal
from PySide6.QtGui import QImageReader, QPixmap
from PySide6.QtWidgets import QLabel, QMainWindow, QWidget, QVBoxLayout


class ImagePreviewLabel(QLabel):
    navigate_requested = Signal(int)

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

        pixmap = self._read_preview_pixmap(path)
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

    def wheelEvent(self, event) -> None:  # noqa: N802
        delta = event.angleDelta().y()
        if delta == 0:
            delta = event.pixelDelta().y()
        if delta == 0:
            super().wheelEvent(event)
            return
        self.navigate_requested.emit(-1 if delta > 0 else 1)
        event.accept()

    def _fit_pixmap(self) -> None:
        if self._pixmap is None or self._pixmap.isNull():
            return
        scaled = self._pixmap.scaled(
            self.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.setPixmap(scaled)

    def _read_preview_pixmap(self, path: Path) -> QPixmap:
        reader = QImageReader(str(path))
        reader.setAutoTransform(True)
        target_size = self.size()
        if not target_size.isValid() or target_size.isEmpty():
            target_size = QSize(900, 650)

        original_size = reader.size()
        if original_size.isValid():
            scaled_size = original_size.scaled(
                target_size,
                Qt.AspectRatioMode.KeepAspectRatio,
            )
            if (
                scaled_size.width() < original_size.width()
                or scaled_size.height() < original_size.height()
            ):
                reader.setScaledSize(scaled_size)

        image = reader.read()
        if image.isNull():
            return QPixmap()
        return QPixmap.fromImage(image)


class PreviewWindow(QMainWindow):
    closed = Signal()
    navigate_requested = Signal(int)

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Preview")
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.resize(900, 650)

        self.preview = ImagePreviewLabel()
        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.preview)
        self.setCentralWidget(central)
        self.preview.installEventFilter(self)

    def set_image(self, path: Path | None) -> None:
        if path is not None:
            self.setWindowTitle(path.name)
        else:
            self.setWindowTitle("Preview")
        self.preview.set_image(path)

    def eventFilter(self, watched, event) -> bool:  # noqa: N802
        if watched is self.preview and event.type() == QEvent.Type.MouseButtonDblClick:
            self._toggle_full_screen()
            event.accept()
            return True
        if watched is self.preview and event.type() == QEvent.Type.Wheel:
            if self._emit_wheel_navigation(event):
                event.accept()
                return True
        return super().eventFilter(watched, event)

    def wheelEvent(self, event) -> None:  # noqa: N802
        if self._emit_wheel_navigation(event):
            event.accept()
            return
        super().wheelEvent(event)

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() == Qt.Key.Key_Left:
            self.navigate_requested.emit(-1)
            event.accept()
            return
        if event.key() == Qt.Key.Key_Right:
            self.navigate_requested.emit(1)
            event.accept()
            return
        super().keyPressEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        self._toggle_full_screen()
        event.accept()

    def closeEvent(self, event) -> None:  # noqa: N802
        self.closed.emit()
        super().closeEvent(event)

    def _toggle_full_screen(self) -> None:
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def _emit_wheel_navigation(self, event) -> bool:
        delta = event.angleDelta().y()
        if delta == 0:
            delta = event.pixelDelta().y()
        if delta == 0:
            return False
        self.navigate_requested.emit(-1 if delta > 0 else 1)
        return True
