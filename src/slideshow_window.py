from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import (
    QEasingCurve,
    QPropertyAnimation,
    QRect,
    QSize,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import QAction, QImageReader, QPixmap
from PySide6.QtWidgets import (
    QGraphicsOpacityEffect,
    QLabel,
    QMainWindow,
    QMenu,
)

from src.settings import SLIDESHOW_TRANSITION_FADE, SlideshowSettings


class SlideshowImageLabel(QLabel):
    def __init__(self) -> None:
        super().__init__()
        self._pixmap: QPixmap | None = None
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet("background: #000000; color: #d7dce2;")

    def set_image(self, path: Path | None) -> None:
        if path is None:
            self._pixmap = None
            self.setPixmap(QPixmap())
            return

        pixmap = self._read_pixmap(path)
        if pixmap.isNull():
            self._pixmap = None
            self.setPixmap(QPixmap())
            self.setText(path.name)
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
        self.setPixmap(
            self._pixmap.scaled(
                self.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

    def _read_pixmap(self, path: Path) -> QPixmap:
        reader = QImageReader(str(path))
        reader.setAutoTransform(True)
        target_size = self.size()
        if not target_size.isValid() or target_size.isEmpty():
            target_size = QSize(1920, 1080)

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


class SlideshowWindow(QMainWindow):
    closed = Signal()

    def __init__(
        self,
        image_paths: list[Path],
        start_index: int,
        settings: SlideshowSettings,
        close_text: str,
        screen_geometry: QRect | None = None,
    ) -> None:
        super().__init__()
        self.image_paths = image_paths
        self.index = max(0, min(len(image_paths) - 1, start_index))
        self.settings = settings
        self.close_text = close_text
        self.setWindowTitle("Slideshow")
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        self.setStyleSheet("background: #000000;")

        self.label = SlideshowImageLabel()
        self.setCentralWidget(self.label)
        self.opacity_effect = QGraphicsOpacityEffect(self.label)
        self.label.setGraphicsEffect(self.opacity_effect)
        self.fade_animation = QPropertyAnimation(self.opacity_effect, b"opacity", self)
        self.fade_animation.setDuration(350)
        self.fade_animation.setEasingCurve(QEasingCurve.Type.OutCubic)

        self.advance_timer = QTimer(self)
        self.advance_timer.timeout.connect(self.next_image)

        self.exit_action = QAction(close_text, self)
        self.exit_action.triggered.connect(self.close)
        self.addAction(self.exit_action)

        if screen_geometry is not None:
            self.setGeometry(screen_geometry)
        self._show_current_image()

    def start(self) -> None:
        self.showFullScreen()
        self.raise_()
        self.activateWindow()
        self._restart_timer()

    def next_image(self) -> None:
        self._move(1)

    def previous_image(self) -> None:
        self._move(-1)

    def keyPressEvent(self, event) -> None:  # noqa: N802
        key = event.key()
        if key == Qt.Key.Key_Escape:
            self.close()
            event.accept()
            return
        if key in {
            Qt.Key.Key_Right,
            Qt.Key.Key_Down,
            Qt.Key.Key_Return,
            Qt.Key.Key_Enter,
        }:
            self.next_image()
            event.accept()
            return
        if key in {Qt.Key.Key_Left, Qt.Key.Key_Up}:
            self.previous_image()
            event.accept()
            return
        super().keyPressEvent(event)

    def wheelEvent(self, event) -> None:  # noqa: N802
        delta = event.angleDelta().y()
        if delta == 0:
            delta = event.pixelDelta().y()
        if delta == 0:
            super().wheelEvent(event)
            return
        if delta > 0:
            self.previous_image()
        else:
            self.next_image()
        event.accept()

    def contextMenuEvent(self, event) -> None:  # noqa: N802
        menu = QMenu(self)
        menu.addAction(self.exit_action)
        menu.exec(event.globalPos())

    def closeEvent(self, event) -> None:  # noqa: N802
        self.advance_timer.stop()
        self.fade_animation.stop()
        self.closed.emit()
        super().closeEvent(event)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self.label.resize(self.size())

    def _move(self, offset: int) -> None:
        if not self.image_paths:
            self.close()
            return

        target_index = self.index + offset
        if target_index < 0 or target_index >= len(self.image_paths):
            if self.settings.loop_enabled:
                target_index %= len(self.image_paths)
            elif offset > 0:
                self.close()
                return
            else:
                target_index = 0

        if target_index == self.index:
            self._restart_timer()
            return

        self.index = target_index
        self._show_current_image()
        self._restart_timer()

    def _show_current_image(self) -> None:
        if not self.image_paths:
            self.close()
            return
        self.label.set_image(self.image_paths[self.index])
        if self.settings.transition_mode == SLIDESHOW_TRANSITION_FADE:
            self.fade_animation.stop()
            self.opacity_effect.setOpacity(0.0)
            self.fade_animation.setStartValue(0.0)
            self.fade_animation.setEndValue(1.0)
            self.fade_animation.start()
        else:
            self.fade_animation.stop()
            self.opacity_effect.setOpacity(1.0)

    def _restart_timer(self) -> None:
        self.advance_timer.stop()
        if self.settings.interval_seconds > 0 and len(self.image_paths) > 1:
            self.advance_timer.start(self.settings.interval_seconds * 1000)
