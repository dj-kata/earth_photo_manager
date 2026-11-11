from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt, QTimer, Signal
from PySide6.QtGui import QCloseEvent, QImage, QImageReader, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
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
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.models import ImageFile
from src.photo_editorial_model import (
    EditorialDocument,
    EditorialPhoto,
    EditorialProfileField,
    EditorialSection,
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
        self.setPixmap(
            QPixmap.fromImage(self._image).scaled(
                self.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )


class PhotoEditorialWindow(QMainWindow):
    closed = Signal()

    def __init__(self, images: list[ImageFile], texts: dict[str, str]) -> None:
        super().__init__()
        self._texts = texts
        self._renderer = PhotoEditorialRenderer()
        self._updating_caption = False
        self._updating_section = False
        self._updating_profile = False
        self.document = EditorialDocument(
            photos=[EditorialPhoto(image.path) for image in images],
            sections=[EditorialSection()],
        )

        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.setWindowTitle(self._tr("window_title"))
        self.resize(1400, 920)

        self._create_basic_controls()
        self._create_section_controls()
        self._create_profile_controls()
        self._create_photo_controls()
        self._create_output_controls()
        self._build_ui()
        self._connect_signals()
        self._populate_section_list()
        self._populate_profile_table()
        self._populate_photo_list()

        self._render_timer = QTimer(self)
        self._render_timer.setSingleShot(True)
        self._render_timer.setInterval(180)
        self._render_timer.timeout.connect(self._render_preview)

        if self.section_list.count():
            self.section_list.setCurrentRow(0)
        if self.photo_list.count():
            self.photo_list.setCurrentRow(0)
        self._update_format_visibility()
        self._render_preview()

    def _create_basic_controls(self) -> None:
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
        self.subtitle_edit = QLineEdit()
        self.subtitle_edit.setPlaceholderText(self._tr("subtitle_placeholder"))
        self.lead_edit = QPlainTextEdit()
        self.lead_edit.setPlaceholderText(self._tr("lead_placeholder"))
        self.lead_edit.setMaximumHeight(90)
        self.category_edit = QLineEdit()
        self.date_edit = QLineEdit()
        self.author_edit = QLineEdit()
        self.pull_quote_edit = QLineEdit()
        self.pull_quote_edit.setPlaceholderText(self._tr("pull_quote_placeholder"))

    def _create_section_controls(self) -> None:
        self.section_list = QListWidget()
        self.section_list.setMinimumHeight(90)
        self.section_heading_edit = QLineEdit()
        self.section_heading_edit.setPlaceholderText(
            self._tr("section_heading_placeholder")
        )
        self.section_body_edit = QPlainTextEdit()
        self.section_body_edit.setPlaceholderText(self._tr("section_body_placeholder"))
        self.section_body_edit.setMinimumHeight(130)
        self.body_edit = self.section_body_edit
        self.add_section_button = QPushButton(self._tr("add"))
        self.remove_section_button = QPushButton(self._tr("remove"))
        self.section_up_button = QPushButton(self._tr("move_up"))
        self.section_down_button = QPushButton(self._tr("move_down"))

    def _create_profile_controls(self) -> None:
        self.profile_table = QTableWidget(0, 2)
        self.profile_table.setHorizontalHeaderLabels(
            [self._tr("profile_label"), self._tr("profile_value")]
        )
        self.profile_table.horizontalHeader().setStretchLastSection(True)
        self.profile_table.setMinimumHeight(145)
        self.add_profile_button = QPushButton(self._tr("add"))
        self.remove_profile_button = QPushButton(self._tr("remove"))
        self.profile_up_button = QPushButton(self._tr("move_up"))
        self.profile_down_button = QPushButton(self._tr("move_down"))

    def _create_photo_controls(self) -> None:
        self.photo_list = QListWidget()
        self.photo_list.setIconSize(QSize(96, 72))
        self.photo_list.setMinimumHeight(150)
        self.caption_edit = QPlainTextEdit()
        self.caption_edit.setPlaceholderText(self._tr("caption_placeholder"))
        self.caption_edit.setMaximumHeight(90)
        self.hero_button = QPushButton(self._tr("set_hero"))
        self.photo_up_button = QPushButton(self._tr("move_up"))
        self.photo_down_button = QPushButton(self._tr("move_down"))

    def _create_output_controls(self) -> None:
        self.preview = EditorialPreviewLabel()
        self.warning_label = QLabel()
        self.warning_label.setWordWrap(True)
        self.warning_label.setStyleSheet("color: #b45309;")
        self.status_label = QLabel()
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("color: #166534;")
        self.copy_button = QPushButton(self._tr("copy_image"))
        self.save_button = QPushButton(self._tr("save_png"))

    def _build_ui(self) -> None:
        controls = QWidget()
        controls_layout = QVBoxLayout(controls)
        controls_layout.addWidget(self._build_basic_group())
        controls_layout.addWidget(self._build_sections_group())
        self.profile_group = self._build_profile_group()
        controls_layout.addWidget(self.profile_group)
        controls_layout.addWidget(self._build_photos_group())
        controls_layout.addStretch(1)
        output_row = QHBoxLayout()
        output_row.addWidget(self.copy_button)
        output_row.addWidget(self.save_button)
        controls_layout.addLayout(output_row)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(controls)
        scroll.setMinimumWidth(470)

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

    def _build_basic_group(self) -> QGroupBox:
        group = QGroupBox(self._tr("basic_information"))
        form = QFormLayout(group)
        form.addRow(self._tr("format"), self.format_combo)
        form.addRow(self._tr("title"), self.title_edit)
        form.addRow(self._tr("subtitle"), self.subtitle_edit)
        form.addRow(self._tr("lead"), self.lead_edit)
        form.addRow(self._tr("category"), self.category_edit)
        form.addRow(self._tr("date"), self.date_edit)
        form.addRow(self._tr("author"), self.author_edit)
        form.addRow(self._tr("pull_quote"), self.pull_quote_edit)
        return group

    def _build_sections_group(self) -> QGroupBox:
        group = QGroupBox(self._tr("article_sections"))
        layout = QVBoxLayout(group)
        layout.addWidget(self.section_list)
        buttons = QHBoxLayout()
        for button in (
            self.add_section_button,
            self.remove_section_button,
            self.section_up_button,
            self.section_down_button,
        ):
            buttons.addWidget(button)
        layout.addLayout(buttons)
        form = QFormLayout()
        form.addRow(self._tr("section_heading"), self.section_heading_edit)
        form.addRow(self._tr("section_body"), self.section_body_edit)
        layout.addLayout(form)
        return group

    def _build_profile_group(self) -> QGroupBox:
        group = QGroupBox(self._tr("profile_fields"))
        layout = QVBoxLayout(group)
        layout.addWidget(self.profile_table)
        buttons = QHBoxLayout()
        for button in (
            self.add_profile_button,
            self.remove_profile_button,
            self.profile_up_button,
            self.profile_down_button,
        ):
            buttons.addWidget(button)
        layout.addLayout(buttons)
        return group

    def _build_photos_group(self) -> QGroupBox:
        group = QGroupBox(self._tr("selected_photos"))
        layout = QVBoxLayout(group)
        layout.addWidget(self.photo_list)
        buttons = QHBoxLayout()
        buttons.addWidget(self.hero_button)
        buttons.addWidget(self.photo_up_button)
        buttons.addWidget(self.photo_down_button)
        layout.addLayout(buttons)
        layout.addWidget(QLabel(self._tr("caption")))
        layout.addWidget(self.caption_edit)
        return group

    def _connect_signals(self) -> None:
        self.format_combo.currentIndexChanged.connect(self._format_changed)
        for control in (
            self.title_edit,
            self.subtitle_edit,
            self.category_edit,
            self.date_edit,
            self.author_edit,
            self.pull_quote_edit,
        ):
            control.textChanged.connect(self._schedule_preview)
        self.lead_edit.textChanged.connect(self._schedule_preview)
        self.section_list.currentRowChanged.connect(self._section_selection_changed)
        self.section_heading_edit.textChanged.connect(self._section_changed)
        self.section_body_edit.textChanged.connect(self._section_changed)
        self.add_section_button.clicked.connect(self._add_section)
        self.remove_section_button.clicked.connect(self._remove_section)
        self.section_up_button.clicked.connect(lambda: self._move_section(-1))
        self.section_down_button.clicked.connect(lambda: self._move_section(1))
        self.profile_table.cellChanged.connect(self._profile_changed)
        self.add_profile_button.clicked.connect(self._add_profile_field)
        self.remove_profile_button.clicked.connect(self._remove_profile_field)
        self.profile_up_button.clicked.connect(lambda: self._move_profile_field(-1))
        self.profile_down_button.clicked.connect(lambda: self._move_profile_field(1))
        self.photo_list.currentRowChanged.connect(self._photo_selection_changed)
        self.caption_edit.textChanged.connect(self._caption_changed)
        self.hero_button.clicked.connect(self._set_selected_photo_as_hero)
        self.photo_up_button.clicked.connect(lambda: self._move_photo(-1))
        self.photo_down_button.clicked.connect(lambda: self._move_photo(1))
        self.copy_button.clicked.connect(self._copy_to_clipboard)
        self.save_button.clicked.connect(self._save_png)

    def _populate_section_list(self, selected_row: int | None = None) -> None:
        current = self.section_list.currentRow() if selected_row is None else selected_row
        self.section_list.blockSignals(True)
        self.section_list.clear()
        for index, section in enumerate(self.document.sections):
            label = section.heading.strip() or self._tr("section_number", number=index + 1)
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, section.id)
            self.section_list.addItem(item)
        self.section_list.blockSignals(False)
        if self.section_list.count():
            self.section_list.setCurrentRow(max(0, min(current, self.section_list.count() - 1)))
        else:
            self._section_selection_changed(-1)

    def _section_selection_changed(self, row: int) -> None:
        self._updating_section = True
        try:
            valid = 0 <= row < len(self.document.sections)
            section = self.document.sections[row] if valid else EditorialSection()
            self.section_heading_edit.setText(section.heading)
            self.section_body_edit.setPlainText(section.body)
            self.section_heading_edit.setEnabled(valid)
            self.section_body_edit.setEnabled(valid)
        finally:
            self._updating_section = False

    def _section_changed(self) -> None:
        if self._updating_section:
            return
        row = self.section_list.currentRow()
        if not 0 <= row < len(self.document.sections):
            return
        section = self.document.sections[row]
        section.heading = self.section_heading_edit.text()
        section.body = self.section_body_edit.toPlainText()
        item = self.section_list.item(row)
        if item is not None:
            item.setText(section.heading.strip() or self._tr("section_number", number=row + 1))
        self._schedule_preview()

    def _add_section(self) -> None:
        self.document.sections.append(EditorialSection())
        self._populate_section_list(len(self.document.sections) - 1)
        self.section_heading_edit.setFocus()
        self._schedule_preview()

    def _remove_section(self) -> None:
        row = self.section_list.currentRow()
        if 0 <= row < len(self.document.sections):
            self.document.sections.pop(row)
            self._populate_section_list(min(row, len(self.document.sections) - 1))
            self._schedule_preview()

    def _move_section(self, offset: int) -> None:
        row = self.section_list.currentRow()
        target = row + offset
        if not 0 <= row < len(self.document.sections) or not 0 <= target < len(
            self.document.sections
        ):
            return
        self.document.sections[row], self.document.sections[target] = (
            self.document.sections[target],
            self.document.sections[row],
        )
        self._populate_section_list(target)
        self._schedule_preview()

    def _populate_profile_table(self, selected_row: int | None = None) -> None:
        current = self.profile_table.currentRow() if selected_row is None else selected_row
        self._updating_profile = True
        try:
            self.profile_table.setRowCount(len(self.document.profile_fields))
            for row, profile_field in enumerate(self.document.profile_fields):
                label_item = QTableWidgetItem(profile_field.label)
                label_item.setData(Qt.ItemDataRole.UserRole, profile_field.id)
                self.profile_table.setItem(row, 0, label_item)
                self.profile_table.setItem(row, 1, QTableWidgetItem(profile_field.value))
        finally:
            self._updating_profile = False
        if self.profile_table.rowCount():
            self.profile_table.setCurrentCell(
                max(0, min(current, self.profile_table.rowCount() - 1)), 0
            )

    def _profile_changed(self, row: int, _column: int) -> None:
        if self._updating_profile or not 0 <= row < len(self.document.profile_fields):
            return
        label_item = self.profile_table.item(row, 0)
        value_item = self.profile_table.item(row, 1)
        profile_field = self.document.profile_fields[row]
        profile_field.label = label_item.text() if label_item is not None else ""
        profile_field.value = value_item.text() if value_item is not None else ""
        self._schedule_preview()

    def _add_profile_field(self) -> None:
        self.document.profile_fields.append(EditorialProfileField())
        self._populate_profile_table(len(self.document.profile_fields) - 1)
        self.profile_table.editItem(
            self.profile_table.item(len(self.document.profile_fields) - 1, 0)
        )
        self._schedule_preview()

    def _remove_profile_field(self) -> None:
        row = self.profile_table.currentRow()
        if 0 <= row < len(self.document.profile_fields):
            self.document.profile_fields.pop(row)
            self._populate_profile_table(min(row, len(self.document.profile_fields) - 1))
            self._schedule_preview()

    def _move_profile_field(self, offset: int) -> None:
        row = self.profile_table.currentRow()
        target = row + offset
        if not 0 <= row < len(self.document.profile_fields) or not 0 <= target < len(
            self.document.profile_fields
        ):
            return
        self.document.profile_fields[row], self.document.profile_fields[target] = (
            self.document.profile_fields[target],
            self.document.profile_fields[row],
        )
        self._populate_profile_table(target)
        self._schedule_preview()

    def _populate_photo_list(self, selected_row: int = 0) -> None:
        self.photo_list.blockSignals(True)
        self.photo_list.clear()
        for index, photo in enumerate(self.document.photos):
            name = photo.source_path.name
            item = QListWidgetItem(
                self._tr("hero_photo", name=name) if index == 0 else name
            )
            item.setToolTip(str(photo.source_path))
            thumbnail = self._read_thumbnail(photo.source_path)
            if not thumbnail.isNull():
                item.setIcon(QPixmap.fromImage(thumbnail))
            self.photo_list.addItem(item)
        self.photo_list.blockSignals(False)
        if self.photo_list.count():
            self.photo_list.setCurrentRow(
                max(0, min(selected_row, self.photo_list.count() - 1))
            )

    def _read_thumbnail(self, path: Path) -> QImage:
        reader = QImageReader(str(path))
        reader.setAutoTransform(True)
        source_size = reader.size()
        if source_size.isValid():
            reader.setScaledSize(
                source_size.scaled(QSize(192, 144), Qt.AspectRatioMode.KeepAspectRatio)
            )
        return reader.read()

    def _photo_selection_changed(self, row: int) -> None:
        self._updating_caption = True
        try:
            valid = 0 <= row < len(self.document.photos)
            self.caption_edit.setPlainText(
                self.document.photos[row].caption if valid else ""
            )
            self.caption_edit.setEnabled(valid)
        finally:
            self._updating_caption = False

    def _caption_changed(self) -> None:
        if self._updating_caption:
            return
        row = self.photo_list.currentRow()
        if 0 <= row < len(self.document.photos):
            self.document.photos[row].caption = self.caption_edit.toPlainText()
            self._schedule_preview()

    def _set_selected_photo_as_hero(self) -> None:
        row = self.photo_list.currentRow()
        if not 0 <= row < len(self.document.photos):
            return
        self.document.set_hero_photo(row)
        self._populate_photo_list(0)
        self._schedule_preview()

    def _move_photo(self, offset: int) -> None:
        row = self.photo_list.currentRow()
        target = self.document.move_photo(row, offset)
        if target != row:
            self._populate_photo_list(target)
            self._schedule_preview()

    def _format_changed(self) -> None:
        template_id = self.format_combo.currentData()
        if isinstance(template_id, str):
            self.document.template_id = template_id
            self._update_format_visibility()
            self._schedule_preview()

    def _update_format_visibility(self) -> None:
        self.profile_group.setVisible(
            self.document.template_id == PROFILE_FEATURE_TEMPLATE_ID
        )

    def _schedule_preview(self) -> None:
        self.status_label.clear()
        if hasattr(self, "_render_timer"):
            self._render_timer.start()

    def _sync_document_text(self) -> None:
        self.document.title = self.title_edit.text()
        self.document.subtitle = self.subtitle_edit.text()
        self.document.lead = self.lead_edit.toPlainText()
        self.document.metadata.category = self.category_edit.text()
        self.document.metadata.date = self.date_edit.text()
        self.document.metadata.author = self.author_edit.text()
        self.document.pull_quote = self.pull_quote_edit.text()
        self.document.body = self.document.sections[0].body if self.document.sections else ""

    def _render_preview(self) -> None:
        self._sync_document_text()
        result = self._renderer.render(
            self.document, QSize(PREVIEW_WIDTH, PREVIEW_HEIGHT)
        )
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
        initial_path = self.document.photos[0].source_path.parent / self._tr(
            "default_filename"
        )
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
