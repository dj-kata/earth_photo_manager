from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QAction, QIcon, QImageReader, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QToolBar,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.models import IMAGE_EXTENSIONS, ImageFile
from src.preview_window import ImagePreviewLabel, PreviewWindow
from src.settings import AppSettings


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Earth Photo Manager")
        self.resize(1280, 820)

        self.settings = AppSettings()
        self.roots = self.settings.root_folders()
        self.images: list[ImageFile] = []
        self.current_folder: Path | None = None
        self.preview_window: PreviewWindow | None = None
        self.use_external_preview = False

        self.folder_tree = QTreeWidget()
        self.folder_tree.setHeaderHidden(True)
        self.folder_tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.folder_tree.currentItemChanged.connect(self._on_current_folder_changed)
        self.folder_tree.itemExpanded.connect(self._load_tree_item_children)

        self.file_list = QListWidget()
        self.file_list.setViewMode(QListWidget.ViewMode.IconMode)
        self.file_list.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.file_list.setMovement(QListWidget.Movement.Static)
        self.file_list.setIconSize(QSize(160, 120))
        self.file_list.setGridSize(QSize(190, 168))
        self.file_list.setSpacing(8)
        self.file_list.setUniformItemSizes(True)
        self.file_list.currentItemChanged.connect(self._on_current_file_changed)

        self.preview = ImagePreviewLabel()
        self.info_table = QTableWidget(0, 2)
        self.info_table.setHorizontalHeaderLabels(["Item", "Value"])
        self.info_table.verticalHeader().hide()
        self.info_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self.info_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self.info_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.info_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)

        self.status = QLabel("Ready")

        self._build_ui()
        self._refresh_folder_tree()

    def _build_ui(self) -> None:
        toolbar = QToolBar("Main")
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(18, 18))
        self.addToolBar(toolbar)

        add_action = QAction("Add Folder", self)
        add_action.triggered.connect(self.add_root_folder)
        toolbar.addAction(add_action)

        remove_action = QAction("Remove Folder", self)
        remove_action.triggered.connect(self.remove_selected_root)
        toolbar.addAction(remove_action)

        refresh_action = QAction("Refresh", self)
        refresh_action.triggered.connect(self.refresh_current_folder)
        toolbar.addAction(refresh_action)

        toolbar.addSeparator()
        preview_action = QAction("External Preview", self)
        preview_action.setCheckable(True)
        preview_action.toggled.connect(self._set_external_preview)
        toolbar.addAction(preview_action)

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(8, 8, 8, 8)
        left_layout.addWidget(QLabel("Folders"))
        left_layout.addWidget(self.folder_tree)

        button_row = QHBoxLayout()
        add_button = QPushButton("Add")
        add_button.clicked.connect(self.add_root_folder)
        remove_button = QPushButton("Remove")
        remove_button.clicked.connect(self.remove_selected_root)
        button_row.addWidget(add_button)
        button_row.addWidget(remove_button)
        left_layout.addLayout(button_row)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(8, 8, 8, 8)
        right_layout.addWidget(self.preview, 3)
        right_layout.addWidget(QLabel("Information"))
        right_layout.addWidget(self.info_table, 2)

        center_splitter = QSplitter(Qt.Orientation.Horizontal)
        center_splitter.addWidget(self.file_list)
        center_splitter.addWidget(right_panel)
        center_splitter.setSizes([720, 420])

        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        main_splitter.addWidget(left_panel)
        main_splitter.addWidget(center_splitter)
        main_splitter.setSizes([260, 1000])

        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(main_splitter)
        layout.addWidget(self.status)
        self.setCentralWidget(root)

    def add_root_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Select root folder")
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

    def load_folder_images(self, folder: Path | None) -> None:
        self.images.clear()
        self.file_list.clear()
        self.preview.set_image(None)
        self._set_info_rows([])
        self.current_folder = folder

        if folder is None:
            self.status.setText("Add a root folder to begin.")
            return

        root = self._root_for_folder(folder)
        count = 0
        try:
            children = sorted(folder.iterdir(), key=lambda path: path.name.lower())
        except OSError as exc:
            self.status.setText(f"Cannot open folder: {exc}")
            return

        for path in children:
            if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS:
                self._add_image_item(ImageFile(path=path, root=root))
                count += 1

        self.status.setText(f"{count} image(s) in {folder}")

    def _refresh_folder_tree(self, select_path: Path | None = None) -> None:
        self.folder_tree.clear()
        for root in self.roots:
            item = self._make_folder_item(root, root)
            self.folder_tree.addTopLevelItem(item)
            self._add_placeholder_if_needed(item, root)

        target = select_path or (self.roots[0] if self.roots else None)
        if target is None:
            self.load_folder_images(None)
            return

        found = self._find_tree_item(target)
        if found is not None:
            self.folder_tree.setCurrentItem(found)
        else:
            self.load_folder_images(target)

    def _make_folder_item(self, folder: Path, root: Path) -> QTreeWidgetItem:
        item = QTreeWidgetItem([folder.name or str(folder)])
        item.setToolTip(0, str(folder))
        item.setData(0, Qt.ItemDataRole.UserRole, str(folder))
        item.setData(0, Qt.ItemDataRole.UserRole + 1, str(root))
        item.setData(0, Qt.ItemDataRole.UserRole + 2, False)
        return item

    def _add_placeholder_if_needed(self, item: QTreeWidgetItem, folder: Path) -> None:
        if self._has_subdirectories(folder):
            item.addChild(QTreeWidgetItem(["Loading..."]))

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
            folders = sorted(
                [path for path in folder.iterdir() if path.is_dir()],
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

    def _has_subdirectories(self, folder: Path) -> bool:
        try:
            return any(path.is_dir() for path in folder.iterdir())
        except OSError:
            return False

    def _find_tree_item(self, folder: Path) -> QTreeWidgetItem | None:
        for index in range(self.folder_tree.topLevelItemCount()):
            item = self.folder_tree.topLevelItem(index)
            if Path(item.data(0, Qt.ItemDataRole.UserRole)) == folder:
                return item
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
        item = QListWidgetItem()
        item.setText(image.name)
        item.setToolTip(str(image.path))
        item.setData(Qt.ItemDataRole.UserRole, image)
        item.setIcon(QIcon(self._make_thumbnail(image.path)))
        self.file_list.addItem(item)

    def _make_thumbnail(self, path: Path) -> QPixmap:
        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            placeholder = QPixmap(160, 120)
            placeholder.fill(Qt.GlobalColor.darkGray)
            return placeholder
        return pixmap.scaled(
            160,
            120,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

    def _on_current_file_changed(
        self, current: QListWidgetItem | None, _previous: QListWidgetItem | None
    ) -> None:
        if current is None:
            self.preview.set_image(None)
            self._set_info_rows([])
            return

        image = current.data(Qt.ItemDataRole.UserRole)
        if not isinstance(image, ImageFile):
            return
        self._show_image(image)

    def _show_image(self, image: ImageFile) -> None:
        self.preview.set_image(image.path)
        if self.use_external_preview:
            if self.preview_window is None:
                self.preview_window = PreviewWindow()
            self.preview_window.set_image(image.path)
            self.preview_window.show()
            self.preview_window.raise_()
        self._show_info(image.path, image.root)

    def _set_external_preview(self, enabled: bool) -> None:
        self.use_external_preview = enabled
        if not enabled and self.preview_window is not None:
            self.preview_window.close()
        current = self.file_list.currentItem()
        if enabled and current is not None:
            image = current.data(Qt.ItemDataRole.UserRole)
            if isinstance(image, ImageFile):
                self._show_image(image)

    def _show_info(self, path: Path, root: Path) -> None:
        rows: list[tuple[str, str]] = [
            ("File name", path.name),
            ("Full path", str(path)),
            ("Root folder", str(root)),
            ("Folder", str(path.parent)),
            ("Extension", path.suffix.lower()),
        ]

        try:
            stat = path.stat()
            rows.extend(
                [
                    ("File size", self._format_size(stat.st_size)),
                    (
                        "Modified",
                        datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                    ),
                ]
            )
        except OSError as exc:
            rows.append(("File status", f"Unavailable: {exc}"))

        reader = QImageReader(str(path))
        size = reader.size()
        if size.isValid():
            rows.append(("Dimensions", f"{size.width()} x {size.height()} px"))

        self._set_info_rows(rows)

    def _set_info_rows(self, rows: list[tuple[str, str]]) -> None:
        self.info_table.setRowCount(len(rows))
        for row, (key, value) in enumerate(rows):
            self.info_table.setItem(row, 0, QTableWidgetItem(key))
            self.info_table.setItem(row, 1, QTableWidgetItem(value))

    @staticmethod
    def _format_size(size: int) -> str:
        value = float(size)
        for unit in ("B", "KB", "MB", "GB"):
            if value < 1024 or unit == "GB":
                return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
            value /= 1024
        return f"{size} B"

    def closeEvent(self, event) -> None:  # noqa: N802
        if self.preview_window is not None:
            self.preview_window.close()
        super().closeEvent(event)
