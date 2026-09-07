from __future__ import annotations

from pathlib import Path
from typing import Callable

from PySide6.QtCore import (
    QEasingCurve,
    QEvent,
    QPoint,
    QPropertyAnimation,
    QRect,
    QSize,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import QAction, QImageReader, QMouseEvent, QPixmap
from PySide6.QtWidgets import (
    QHBoxLayout,
    QGraphicsOpacityEffect,
    QLabel,
    QMainWindow,
    QMenu,
    QPushButton,
    QStyle,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from src.settings import (
    SLIDESHOW_TRANSITION_FADE,
    SlideshowNavigationSettings,
    SlideshowSettings,
)


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
        navigation_settings: SlideshowNavigationSettings,
        save_navigation_settings: Callable[[SlideshowNavigationSettings], None],
        navigation_labels: dict[str, str],
        screen_geometry: QRect | None = None,
    ) -> None:
        super().__init__()
        self.image_paths = image_paths
        self.index = max(0, min(len(image_paths) - 1, start_index))
        self.settings = settings
        self.close_text = close_text
        self.navigation_settings = navigation_settings
        self.save_navigation_settings = save_navigation_settings
        self.navigation_labels = navigation_labels
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
        self.show_navigation_action = QAction(
            navigation_labels["show_navigation"],
            self,
        )
        self.show_navigation_action.triggered.connect(self.show_navigation_panel)
        self.addAction(self.show_navigation_action)

        self.navigation_panel = SlideshowNavigationWindow(navigation_labels, self)
        self.navigation_panel.previous_requested.connect(self.previous_image)
        self.navigation_panel.next_requested.connect(self.next_image)
        self.navigation_panel.close_slideshow_requested.connect(self.close)
        self.navigation_panel.close_panel_requested.connect(self.hide_navigation_panel)
        self.navigation_panel.moved.connect(self._on_navigation_panel_moved)
        self.navigation_panel.hide()

        if screen_geometry is not None:
            self.setGeometry(screen_geometry)
        self._show_current_image()

    def start(self) -> None:
        self.showFullScreen()
        self.raise_()
        self.activateWindow()
        if self.navigation_settings.visible:
            self.show_navigation_panel()
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
        menu.setStyleSheet(
            """
            QMenu {
                background: #ffffff;
                color: #111827;
                border: 1px solid #94a3b8;
            }
            QMenu::item {
                padding: 6px 18px;
                background: transparent;
                color: #111827;
            }
            QMenu::item:selected {
                background: #dbeafe;
                color: #111827;
            }
            """
        )
        menu.addAction(self.show_navigation_action)
        menu.addAction(self.exit_action)
        menu.exec(event.globalPos())

    def closeEvent(self, event) -> None:  # noqa: N802
        self.advance_timer.stop()
        self.fade_animation.stop()
        self._save_navigation_state()
        self.navigation_panel.prepare_for_slideshow_close()
        self.navigation_panel.close()
        self.closed.emit()
        super().closeEvent(event)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self.label.resize(self.size())
        if self.navigation_panel.isVisible():
            self._keep_navigation_panel_inside()

    def show_navigation_panel(self) -> None:
        self.navigation_settings.visible = True
        self.navigation_panel.show()
        self.navigation_panel.raise_()
        self._restore_navigation_panel_position()
        self._update_navigation_panel()
        self._save_navigation_state()

    def hide_navigation_panel(self) -> None:
        self.navigation_settings.visible = False
        self.navigation_panel.hide()
        self._save_navigation_state()

    def _on_navigation_panel_moved(self) -> None:
        self._keep_navigation_panel_inside()
        self._save_navigation_state()

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
        self._update_navigation_panel()
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
        self._update_navigation_panel()

    def _restart_timer(self) -> None:
        self.advance_timer.stop()
        if self.settings.interval_seconds > 0 and len(self.image_paths) > 1:
            self.advance_timer.start(self.settings.interval_seconds * 1000)

    def _update_navigation_panel(self) -> None:
        self.navigation_panel.set_count(self.index + 1, len(self.image_paths))

    def _restore_navigation_panel_position(self) -> None:
        self.navigation_panel.adjustSize()
        if self.navigation_settings.position is None:
            x = max(16, (self.width() - self.navigation_panel.width()) // 2)
            y = max(16, self.height() - self.navigation_panel.height() - 48)
            position = QPoint(x, y)
        else:
            position = self.navigation_settings.position
        self.navigation_panel.move(self.mapToGlobal(position))
        self._keep_navigation_panel_inside()

    def _keep_navigation_panel_inside(self) -> None:
        margin = 8
        bounds = self.frameGeometry().adjusted(margin, margin, -margin, -margin)
        panel_rect = self.navigation_panel.frameGeometry()
        max_x = max(bounds.left(), bounds.right() - panel_rect.width())
        max_y = max(bounds.top(), bounds.bottom() - panel_rect.height())
        x = min(max(bounds.left(), panel_rect.left()), max_x)
        y = min(max(bounds.top(), panel_rect.top()), max_y)
        position = QPoint(x, y)
        if panel_rect.topLeft() != position:
            self.navigation_panel.move(position)

    def _save_navigation_state(self) -> None:
        if hasattr(self, "navigation_panel"):
            self.navigation_settings.position = self.mapFromGlobal(
                self.navigation_panel.frameGeometry().topLeft()
            )
        self.save_navigation_settings(self.navigation_settings)


class SlideshowNavigationWindow(QWidget):
    previous_requested = Signal()
    next_requested = Signal()
    close_slideshow_requested = Signal()
    close_panel_requested = Signal()
    moved = Signal()

    def __init__(self, labels: dict[str, str], parent: QWidget | None = None) -> None:
        super().__init__(
            parent,
            Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.FramelessWindowHint,
        )
        self._closing_slideshow = False
        self._drag_origin: QPoint | None = None
        self.setWindowTitle(labels["navigation_title"])
        self.setStyleSheet(
            """
            QWidget {
                background: #f8fafc;
                color: #111827;
            }
            QWidget#TitleBar {
                background: #1f2937;
                color: #f8fafc;
            }
            QLabel {
                background: transparent;
                border: 0;
            }
            QLabel#TitleLabel {
                color: #f8fafc;
                font-size: 11px;
                padding-left: 6px;
            }
            QLabel#CountLabel {
                color: #111827;
                font-weight: 700;
                min-width: 58px;
            }
            QToolButton {
                background: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 3px;
            }
            QToolButton:hover {
                background: #e0f2fe;
                border-color: #38bdf8;
            }
            QToolButton:pressed {
                background: #bae6fd;
            }
            QToolButton#PanelCloseButton {
                background: transparent;
                border: 0;
                color: #f8fafc;
                font-weight: 700;
            }
            QToolButton#PanelCloseButton:hover {
                background: #ef4444;
            }
            QPushButton {
                background: #fee2e2;
                color: #7f1d1d;
                border: 1px solid #fca5a5;
                border-radius: 3px;
                padding: 0 10px;
                font-weight: 700;
            }
            QPushButton:hover {
                background: #fecaca;
            }
            QPushButton:pressed {
                background: #fca5a5;
            }
            """
        )

        self.count_label = QLabel()
        self.count_label.setObjectName("CountLabel")
        self.count_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        previous_button = self._make_tool_button(
            labels["previous"],
            QStyle.StandardPixmap.SP_ArrowBack,
        )
        previous_button.clicked.connect(self.previous_requested.emit)
        next_button = self._make_tool_button(
            labels["next"],
            QStyle.StandardPixmap.SP_ArrowForward,
        )
        next_button.clicked.connect(self.next_requested.emit)
        close_slideshow_button = QPushButton(labels["exit"])
        close_slideshow_button.setFixedHeight(26)
        close_slideshow_button.clicked.connect(self.close_slideshow_requested.emit)
        close_panel_button = QToolButton()
        close_panel_button.setObjectName("PanelCloseButton")
        close_panel_button.setFixedSize(18, 18)
        close_panel_button.setText("x")
        close_panel_button.setToolTip(labels["close_panel"])
        close_panel_button.clicked.connect(self.close_panel_requested.emit)

        title_bar = QWidget()
        title_bar.setObjectName("TitleBar")
        title_bar.setFixedHeight(22)
        title_bar.installEventFilter(self)
        title_label = QLabel(labels["navigation_title"])
        title_label.setObjectName("TitleLabel")
        title_label.installEventFilter(self)
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(4, 2, 3, 2)
        title_layout.setSpacing(3)
        title_layout.addWidget(title_label, 1)
        title_layout.addWidget(close_panel_button)

        control_layout = QHBoxLayout()
        control_layout.setContentsMargins(8, 6, 8, 8)
        control_layout.setSpacing(5)
        control_layout.addWidget(self.count_label)
        control_layout.addWidget(previous_button)
        control_layout.addWidget(next_button)
        control_layout.addWidget(close_slideshow_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(1, 1, 1, 1)
        layout.setSpacing(0)
        layout.addWidget(title_bar)
        layout.addLayout(control_layout)
        self.setFixedHeight(self.sizeHint().height())

    def set_count(self, current: int, total: int) -> None:
        self.count_label.setText(f"{current} / {total}")
        self.adjustSize()
        self.setFixedHeight(self.sizeHint().height())

    def prepare_for_slideshow_close(self) -> None:
        self._closing_slideshow = True

    def moveEvent(self, event) -> None:  # noqa: N802
        super().moveEvent(event)
        if self.isVisible():
            self.moved.emit()

    def closeEvent(self, event) -> None:  # noqa: N802
        if self._closing_slideshow:
            super().closeEvent(event)
            return
        self.close_panel_requested.emit()
        event.ignore()
        self.hide()

    def eventFilter(self, watched, event) -> bool:  # noqa: N802
        if event.type() == QEvent.Type.MouseButtonPress:
            return self._handle_title_mouse_press(event)
        if event.type() == QEvent.Type.MouseMove:
            return self._handle_title_mouse_move(event)
        if event.type() == QEvent.Type.MouseButtonRelease:
            return self._handle_title_mouse_release(event)
        return super().eventFilter(watched, event)

    def _make_tool_button(
        self,
        tooltip: str,
        standard_icon: QStyle.StandardPixmap,
    ) -> QToolButton:
        button = QToolButton()
        button.setFixedSize(26, 26)
        button.setIcon(self.style().standardIcon(standard_icon))
        button.setIconSize(QSize(16, 16))
        button.setToolTip(tooltip)
        button.setAutoRaise(False)
        return button

    def _handle_title_mouse_press(self, event: QMouseEvent) -> bool:
        if event.button() != Qt.MouseButton.LeftButton:
            return False
        self._drag_origin = event.globalPosition().toPoint() - self.pos()
        event.accept()
        return True

    def _handle_title_mouse_move(self, event: QMouseEvent) -> bool:
        if self._drag_origin is None:
            return False
        self.move(event.globalPosition().toPoint() - self._drag_origin)
        event.accept()
        return True

    def _handle_title_mouse_release(self, event: QMouseEvent) -> bool:
        if self._drag_origin is None:
            return False
        self._drag_origin = None
        self.moved.emit()
        event.accept()
        return True
