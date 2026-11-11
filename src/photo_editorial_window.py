from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt, QTimer, Signal
from PySide6.QtGui import QCloseEvent, QImage, QImageReader, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from src.models import ImageFile
from src.photo_editorial_model import (
    EditorialDocument,
    EditorialPhoto,
    MAGAZINE_FEATURE_TEMPLATE_ID,
    NEWSPAPER_ARTICLE_TEMPLATE_ID,
    PHOTO_ESSAY_TEMPLATE_ID,
    PROFILE_FEATURE_TEMPLATE_ID,
)
from src.photo_editorial_renderer import (
    PAGE_SIZE,
    PREVIEW_HEIGHT,
    PREVIEW_WIDTH,
    PhotoEditorialRenderer,
)


class EditorialPreviewLabel(QLabel):
    def __init__(self) -> None:
        super().__init__()
        self._image: QImage | None = None
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(360, 480)
        self.setStyleSheet("background: #30343b; color: #f3f4f6;")

    def set_image(self, image: QImage) -> None:
        self._image = QImage(image)
        self._fit_image()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._fit_image()

    def _fit_image(self) -> None:
        if self._image is None or self._image.isNull():
            self.setPixmap(QPixmap())
            return
        pixmap = QPixmap.fromImage(self._image).scaled(
            self.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.setPixmap(pixmap)


class PhotoEditorialWindow(QMainWindow):
    closed = Signal()

    def __init__(self, images: list[ImageFile], texts: dict[str, str]) -> None:
        super().__init__()
        self._texts = texts
        self._renderer = PhotoEditorialRenderer()
        self._updating_caption = False
        self._last_render_missing_paths: list[Path] = []
        self.document = EditorialDocument(
            photos=[EditorialPhoto(image.path) for image in images]
        )

        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.setWindowTitle(self._tr("window_title"))
        self.resize(1320, 880)

        self.format_combo = QComboBox()
        self.format_combo.addItem(
            self._tr("format_magazine"), MAGAZINE_FEATURE_TEMPLATE_ID
        )
        self.format_combo.addItem(
            self._tr("format_newspaper"), NEWSPAPER_ARTICLE_TEMPLATE_ID
        )
        self.format_combo.addItem(
            self._tr("format_photo_essay"), PHOTO_ESSAY_TEMPLATE_ID
        )
        self.format_combo.addItem(
            self._tr("format_profile"), PROFILE_FEATURE_TEMPLATE_ID
        )
        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText(self._tr("title_placeholder"))
        self.body_edit = QPlainTextEdit()
        self.body_edit.setPlaceholderText(self._tr("body_placeholder"))
        self.body_edit.setMinimumHeight(220)
        self.photo_list = QListWidget()
        self.photo_list.setIconSize(QSize(96, 72))
        self.photo_list.setMinimumHeight(150)
        self.caption_edit = QPlainTextEdit()
        self.caption_edit.setPlaceholderText(self._tr("caption_placeholder"))
        self.caption_edit.setMaximumHeight(110)
        self.preview = EditorialPreviewLabel()
        self.warning_label = QLabel()
        self.warning_label.setWordWrap(True)
        self.warning_label.setStyleSheet("color: #b45309;")
        self.status_label = QLabel()
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("color: #166534;")
        self.copy_button = QPushButton(self._tr("copy_image"))
        self.save_button = QPushButton(self._tr("save_png"))

        self._populate_photo_list()
        self._build_ui()

        self._render_timer = QTimer(self)
        self._render_timer.setSingleShot(True)
        self._render_timer.setInterval(180)
        self._render_timer.timeout.connect(self._render_preview)
        self.format_combo.currentIndexChanged.connect(self._format_changed)
        self.title_edit.textChanged.connect(self._schedule_preview)
        self.body_edit.textChanged.connect(self._schedule_preview)
        self.caption_edit.textChanged.connect(self._caption_changed)
        self.photo_list.currentRowChanged.connect(self._photo_selection_changed)
        self.copy_button.clicked.connect(self._copy_to_clipboard)
        self.save_button.clicked.connect(self._save_png)

        if self.photo_list.count():
            self.photo_list.setCurrentRow(0)
        self._render_preview()

    def _build_ui(self) -> None:
        controls = QWidget()
        controls_layout = QVBoxLayout(controls)
        form = QFormLayout()
        form.addRow(self._tr("format"), self.format_combo)
        form.addRow(self._tr("title"), self.title_edit)
        form.addRow(self._tr("body"), self.body_edit)
        controls_layout.addLayout(form)
        controls_layout.addWidget(QLabel(self._tr("selected_photos")))
        controls_layout.addWidget(self.photo_list)
        controls_layout.addWidget(QLabel(self._tr("caption")))
        controls_layout.addWidget(self.caption_edit)
        controls_layout.addStretch(1)
        button_row = QHBoxLayout()
        button_row.addWidget(self.copy_button)
        button_row.addWidget(self.save_button)
        controls_layout.addLayout(button_row)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(controls)
        scroll.setMinimumWidth(400)

        preview_container = QWidget()
        preview_layout = QVBoxLayout(preview_container)
        preview_layout.addWidget(self.preview, 1)
        preview_layout.addWidget(self.warning_label)
        preview_layout.addWidget(self.status_label)

        splitter = QSplitter()
        splitter.addWidget(scroll)
        splitter.addWidget(preview_container)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        central = QWidget()
        layout = QHBoxLayout(central)
        layout.addWidget(splitter)
        self.setCentralWidget(central)

    def _populate_photo_list(self) -> None:
        for index, photo in enumerate(self.document.photos):
            item = QListWidgetItem(photo.source_path.name)
            item.setToolTip(str(photo.source_path))
            thumbnail = self._read_thumbnail(photo.source_path)
            if not thumbnail.isNull():
                item.setIcon(QPixmap.fromImage(thumbnail))
            if index == 0:
                item.setText(self._tr("hero_photo", name=photo.source_path.name))
            self.photo_list.addItem(item)

    def _read_thumbnail(self, path: Path) -> QImage:
        reader = QImageReader(str(path))
        reader.setAutoTransform(True)
        source_size = reader.size()
        if source_size.isValid():
            reader.setScaledSize(
                source_size.scaled(
                    QSize(192, 144), Qt.AspectRatioMode.KeepAspectRatio
                )
            )
        return reader.read()

    def _photo_selection_changed(self, row: int) -> None:
        self._updating_caption = True
        try:
            caption = self.document.photos[row].caption if row >= 0 else ""
            self.caption_edit.setPlainText(caption)
            self.caption_edit.setEnabled(row >= 0)
        finally:
            self._updating_caption = False

    def _caption_changed(self) -> None:
        if self._updating_caption:
            return
        row = self.photo_list.currentRow()
        if 0 <= row < len(self.document.photos):
            self.document.photos[row].caption = self.caption_edit.toPlainText()
            self._schedule_preview()

    def _format_changed(self) -> None:
        template_id = self.format_combo.currentData()
        if isinstance(template_id, str):
            self.document.template_id = template_id
            self.status_label.clear()
            self._schedule_preview()

    def _schedule_preview(self) -> None:
        self.status_label.clear()
        self._render_timer.start()

    def _sync_document_text(self) -> None:
        self.document.title = self.title_edit.text()
        self.document.body = self.body_edit.toPlainText()

    def _render_preview(self) -> None:
        self._sync_document_text()
        result = self._renderer.render(
            self.document, QSize(PREVIEW_WIDTH, PREVIEW_HEIGHT)
        )
        self._last_render_missing_paths = result.missing_paths
        self.preview.set_image(result.image)
        warnings: list[str] = []
        if result.missing_paths:
            warnings.append(
                self._tr(
                    "missing_photos",
                    names=", ".join(path.name for path in result.missing_paths),
                )
            )
        if result.text_overflow:
            warnings.append(self._tr("text_overflow"))
        self.warning_label.setText("\n".join(warnings))

    def _copy_to_clipboard(self) -> None:
        self._sync_document_text()
        result = self._renderer.render(self.document, PAGE_SIZE)
        QApplication.clipboard().setImage(result.image)
        self.status_label.setText(self._tr("copied_image"))

    def _save_png(self) -> None:
        self._sync_document_text()
        initial_dir = self.document.photos[0].source_path.parent
        initial_path = initial_dir / self._tr("default_filename")
        path_text, _selected_filter = QFileDialog.getSaveFileName(
            self,
            self._tr("save_dialog_title"),
            str(initial_path),
            self._tr("png_filter"),
        )
        if not path_text:
            return
        path = Path(path_text)
        if path.suffix.casefold() != ".png":
            path = path.with_suffix(".png")
        if path.exists():
            choice = QMessageBox.question(
                self,
                self._tr("overwrite_title"),
                self._tr("overwrite_message", name=path.name),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if choice != QMessageBox.StandardButton.Yes:
                return

        result = self._renderer.render(self.document, PAGE_SIZE)
        if not result.image.save(str(path), "PNG"):
            QMessageBox.critical(
                self,
                self._tr("save_failed_title"),
                self._tr("save_failed_message", path=path),
            )
            return
        QMessageBox.information(
            self,
            self._tr("save_complete_title"),
            self._tr("save_complete_message", path=path),
        )

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        self.closed.emit()
        super().closeEvent(event)

    def _tr(self, key: str, **kwargs: object) -> str:
        return self._texts.get(key, key).format(**kwargs)
