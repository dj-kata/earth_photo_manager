from __future__ import annotations

from collections import deque
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime
import os
from pathlib import Path

from PySide6.QtCore import QPoint, QSize, Qt, QTimer
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
    QSizePolicy,
)

from src.models import IMAGE_EXTENSIONS, ImageFile
from src.image_metadata import read_image_metadata
from src.preview_window import ImagePreviewLabel, PreviewWindow
from src.settings import AppSettings
from src.thumbnail_cache import (
    CACHE_DIR_NAME,
    ThumbnailCache,
    create_thumbnail_file_for_cache_dir,
)


def _thumbnail_worker_count() -> int:
    configured = os.environ.get("EPM_THUMBNAIL_WORKERS", "").strip()
    if configured:
        try:
            return max(1, int(configured))
        except ValueError:
            pass

    cpu_count = os.cpu_count() or 2
    return max(2, min(8, cpu_count - 2))


THUMBNAIL_WORKER_COUNT = _thumbnail_worker_count()
THUMBNAIL_POLL_INTERVAL_MS = 100
THUMBNAIL_UI_UPDATE_INTERVAL_MS = 50
THUMBNAIL_UI_UPDATES_PER_TICK = 12
THUMBNAIL_VISIBLE_PRIORITY_DELAY_MS = 80
STATUS_BAR_VERTICAL_PADDING = 6


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Earth Photo Manager")
        self.resize(1280, 820)

        self.settings = AppSettings()
        self.roots = self.settings.root_folders()
        self.thumbnail_executor = ThreadPoolExecutor(max_workers=THUMBNAIL_WORKER_COUNT)
        self.images: list[ImageFile] = []
        self.file_items_by_path: dict[str, QListWidgetItem] = {}
        self.current_folder: Path | None = None
        self.restore_selected_image_path = self.settings.selected_image_path()
        self.thumbnail_cache = ThumbnailCache(QSize(160, 120))
        self.thumbnail_queue: deque[Path] = deque()
        self.thumbnail_queued_paths: set[str] = set()
        self.thumbnail_futures: dict[Future, str] = {}
        self.thumbnail_paths_by_source: dict[str, str] = {}
        self.thumbnail_poll_timer = QTimer(self)
        self.thumbnail_poll_timer.setInterval(THUMBNAIL_POLL_INTERVAL_MS)
        self.thumbnail_poll_timer.timeout.connect(self._poll_thumbnail_futures)
        self.pending_thumbnail_updates: dict[str, str] = {}
        self.thumbnail_update_timer = QTimer(self)
        self.thumbnail_update_timer.setInterval(THUMBNAIL_UI_UPDATE_INTERVAL_MS)
        self.thumbnail_update_timer.timeout.connect(self._flush_thumbnail_updates)
        self.thumbnail_visible_priority_timer = QTimer(self)
        self.thumbnail_visible_priority_timer.setSingleShot(True)
        self.thumbnail_visible_priority_timer.setInterval(
            THUMBNAIL_VISIBLE_PRIORITY_DELAY_MS
        )
        self.thumbnail_visible_priority_timer.timeout.connect(
            self._prioritize_visible_thumbnails
        )
        self.preview_window: PreviewWindow | None = None
        self.use_external_preview = False
        self.placeholder_icon = QIcon(self._make_placeholder_thumbnail())

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
        self.file_list.setStyleSheet(
            """
            QListWidget {
                background: #ffffff;
                outline: 0;
            }
            QListWidget::item {
                border: 3px solid transparent;
                border-radius: 4px;
                padding: 6px;
                color: #1f2933;
            }
            QListWidget::item:selected {
                background: #d9ecff;
                border: 3px solid #0078d4;
                color: #001f33;
            }
            QListWidget::item:selected:active,
            QListWidget::item:selected:!active {
                background: #d9ecff;
                border: 3px solid #0078d4;
                color: #001f33;
            }
            QListWidget::item:hover {
                background: #eef6ff;
                border: 3px solid #8cc8ff;
            }
            """
        )
        self.file_list.currentItemChanged.connect(self._on_current_file_changed)
        self.file_list.verticalScrollBar().valueChanged.connect(
            self._schedule_visible_thumbnail_priority
        )

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
        self.status.setWordWrap(False)
        self.status.setMinimumWidth(0)
        self.status.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.status.setFixedHeight(
            self.status.fontMetrics().height() + STATUS_BAR_VERTICAL_PADDING
        )
        self.status.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)

        self._build_ui()
        self._refresh_folder_tree()
        self._resume_pending_thumbnails()

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

        self.center_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.center_splitter.addWidget(self.file_list)
        self.center_splitter.addWidget(right_panel)
        self.center_splitter.setSizes([720, 420])

        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.main_splitter.addWidget(left_panel)
        self.main_splitter.addWidget(self.center_splitter)
        self.main_splitter.setSizes([260, 1000])

        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.main_splitter)
        layout.addWidget(self.status)
        self.setCentralWidget(root)
        self._restore_window_layout()

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
        self.file_items_by_path.clear()
        self.preview.set_image(None)
        self._set_info_rows([])
        self.current_folder = folder

        if folder is None:
            self.status.setText("Add a root folder to begin.")
            self.settings.set_selected_folder_path(None)
            self.settings.set_selected_image_path(None)
            return

        self.settings.set_selected_folder_path(folder)
        root = self._root_for_folder(folder)
        try:
            image_paths = self._image_paths_in_folder(folder)
        except OSError as exc:
            self.status.setText(f"Cannot open folder: {exc}")
            return

        self.file_list.setUpdatesEnabled(False)
        try:
            for path in image_paths:
                self._add_image_item(ImageFile(path=path, root=root))
        finally:
            self.file_list.setUpdatesEnabled(True)

        count = len(image_paths)
        self.status.setText(f"{count} image(s) in {folder}")
        self._restore_or_clear_selected_image(folder)
        self._scroll_file_list_to_top()
        self._start_thumbnail_loading(image_paths, prioritize=True)
        self._schedule_visible_thumbnail_priority()

    def _image_paths_in_folder(self, folder: Path) -> list[Path]:
        image_paths: list[Path] = []
        with os.scandir(folder) as entries:
            for entry in entries:
                if not entry.is_file():
                    continue
                path = Path(entry.path)
                if path.suffix.lower() in IMAGE_EXTENSIONS:
                    image_paths.append(path)
        image_paths.sort(key=lambda path: path.name.lower())
        return image_paths

    def _refresh_folder_tree(self, select_path: Path | None = None) -> None:
        self.folder_tree.clear()
        for root in self.roots:
            item = self._make_folder_item(root, root)
            self.folder_tree.addTopLevelItem(item)
            self._add_placeholder_if_needed(item, root)

        target = select_path or self.settings.selected_folder_path()
        if target is None and self.restore_selected_image_path is not None:
            target = self.restore_selected_image_path.parent
        if target is None:
            target = self.roots[0] if self.roots else None
        if target is None:
            self.load_folder_images(None)
            return

        found = self._select_folder_path(target)
        if found is not None:
            self.folder_tree.setCurrentItem(found)
        else:
            fallback = self.roots[0] if self.roots else None
            self.load_folder_images(fallback)

    def _make_folder_item(self, folder: Path, root: Path) -> QTreeWidgetItem:
        item = QTreeWidgetItem([folder.name or str(folder)])
        item.setToolTip(0, str(folder))
        item.setData(0, Qt.ItemDataRole.UserRole, str(folder))
        item.setData(0, Qt.ItemDataRole.UserRole + 1, str(root))
        item.setData(0, Qt.ItemDataRole.UserRole + 2, False)
        return item

    def _add_placeholder_if_needed(self, item: QTreeWidgetItem, _folder: Path) -> None:
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
                [
                    path
                    for path in folder.iterdir()
                    if path.is_dir() and path.name != CACHE_DIR_NAME
                ],
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

    def _find_tree_item(self, folder: Path) -> QTreeWidgetItem | None:
        for index in range(self.folder_tree.topLevelItemCount()):
            item = self.folder_tree.topLevelItem(index)
            if Path(item.data(0, Qt.ItemDataRole.UserRole)) == folder:
                return item
        return None

    def _select_folder_path(self, folder: Path) -> QTreeWidgetItem | None:
        root_item: QTreeWidgetItem | None = None
        root_path: Path | None = None
        for index in range(self.folder_tree.topLevelItemCount()):
            item = self.folder_tree.topLevelItem(index)
            candidate = Path(item.data(0, Qt.ItemDataRole.UserRole))
            try:
                folder.relative_to(candidate)
            except ValueError:
                continue
            root_item = item
            root_path = candidate
            break

        if root_item is None or root_path is None:
            return None

        current_item = root_item
        current_path = root_path
        if current_path == folder:
            return current_item

        try:
            relative_parts = folder.relative_to(root_path).parts
        except ValueError:
            return None

        for part in relative_parts:
            self._load_tree_item_children(current_item)
            next_item = self._find_child_folder_item(current_item, current_path / part)
            if next_item is None:
                return None
            current_item.setExpanded(True)
            current_item = next_item
            current_path = current_path / part
        return current_item

    def _find_child_folder_item(
        self, parent: QTreeWidgetItem, folder: Path
    ) -> QTreeWidgetItem | None:
        for index in range(parent.childCount()):
            child = parent.child(index)
            child_path = child.data(0, Qt.ItemDataRole.UserRole)
            if child_path and Path(child_path) == folder:
                return child
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
        item.setTextAlignment(Qt.AlignmentFlag.AlignHCenter)
        item.setToolTip(str(image.path))
        item.setData(Qt.ItemDataRole.UserRole, image)
        thumbnail_path = self._known_thumbnail_path_for(image.path)
        if thumbnail_path:
            item.setIcon(QIcon(thumbnail_path))
        else:
            item.setIcon(self.placeholder_icon)
        self.file_list.addItem(item)
        self.file_items_by_path[str(image.path)] = item

    def _known_thumbnail_path_for(self, source_path: Path) -> str | None:
        source_key = str(source_path)
        thumbnail_path = self.thumbnail_paths_by_source.get(source_key)
        if thumbnail_path and Path(thumbnail_path).exists():
            return thumbnail_path
        if thumbnail_path:
            self.thumbnail_paths_by_source.pop(source_key, None)

        cache_path = self.thumbnail_cache.cached_path_for(source_path)
        if cache_path is not None:
            thumbnail_path = str(cache_path)
            self.thumbnail_paths_by_source[source_key] = thumbnail_path
            return thumbnail_path
        return None

    def _scroll_file_list_to_top(self) -> None:
        self.file_list.scrollToTop()
        self.file_list.verticalScrollBar().setValue(0)

    def _start_thumbnail_loading(
        self, image_paths: list[Path], prioritize: bool = False
    ) -> None:
        if not image_paths:
            return

        priority_paths: list[Path] = []
        active_paths = set(self.thumbnail_futures.values())
        for path in image_paths:
            key = str(path)
            if self._known_thumbnail_path_for(path):
                continue
            if key in active_paths:
                continue
            if key in self.thumbnail_queued_paths:
                if prioritize:
                    try:
                        self.thumbnail_queue.remove(path)
                    except ValueError:
                        continue
                    priority_paths.append(path)
                continue
            if prioritize:
                priority_paths.append(path)
            else:
                self.thumbnail_queue.append(path)
            self.thumbnail_queued_paths.add(key)

        if priority_paths:
            self.thumbnail_queue.extendleft(reversed(priority_paths))

        self._start_next_thumbnail_job()

    def _schedule_visible_thumbnail_priority(self, *_args: object) -> None:
        if self.file_list.count() and self.thumbnail_queue:
            self.thumbnail_visible_priority_timer.start()

    def _prioritize_visible_thumbnails(self) -> None:
        visible_paths = self._visible_image_paths()
        if not visible_paths or not self.thumbnail_queue:
            return

        queued_paths = set(self.thumbnail_queue)
        priority_paths = [path for path in visible_paths if path in queued_paths]
        if not priority_paths:
            return

        priority_set = set(priority_paths)
        self.thumbnail_queue = deque(
            [
                *priority_paths,
                *[path for path in self.thumbnail_queue if path not in priority_set],
            ]
        )
        self._start_next_thumbnail_job()

    def _visible_image_paths(self) -> list[Path]:
        viewport_rect = self.file_list.viewport().rect()
        grid_size = self.file_list.gridSize()
        step_x = max(1, grid_size.width() // 2)
        step_y = max(1, grid_size.height() // 2)
        x_values = list(range(viewport_rect.left(), viewport_rect.right() + 1, step_x))
        y_values = list(range(viewport_rect.top(), viewport_rect.bottom() + 1, step_y))
        if not x_values or x_values[-1] != viewport_rect.right():
            x_values.append(viewport_rect.right())
        if not y_values or y_values[-1] != viewport_rect.bottom():
            y_values.append(viewport_rect.bottom())

        visible_paths: list[Path] = []
        seen_paths: set[Path] = set()
        for y in y_values:
            for x in x_values:
                item = self.file_list.itemAt(QPoint(x, y))
                if item is None:
                    continue
                image = item.data(Qt.ItemDataRole.UserRole)
                if isinstance(image, ImageFile) and image.path not in seen_paths:
                    seen_paths.add(image.path)
                    visible_paths.append(image.path)
        return visible_paths

    def _start_next_thumbnail_job(self) -> None:
        while self.thumbnail_queue and len(self.thumbnail_futures) < THUMBNAIL_WORKER_COUNT:
            image_path = self.thumbnail_queue.popleft()
            source_key = str(image_path)
            if self._known_thumbnail_path_for(image_path):
                self.thumbnail_queued_paths.discard(source_key)
                continue
            future = self.thumbnail_executor.submit(
                create_thumbnail_file_for_cache_dir,
                str(image_path),
                str(self.thumbnail_cache.cache_dir),
                self.thumbnail_cache.thumbnail_size.width(),
                self.thumbnail_cache.thumbnail_size.height(),
            )
            self.thumbnail_futures[future] = str(image_path)

        if self.thumbnail_futures and not self.thumbnail_poll_timer.isActive():
            self.thumbnail_poll_timer.start()

        self._update_thumbnail_status()

    def _cancel_thumbnail_worker(self, clear_saved_queue: bool = True) -> None:
        for future in self.thumbnail_futures:
            future.cancel()
        self.thumbnail_futures.clear()
        self.thumbnail_queue.clear()
        self.thumbnail_queued_paths.clear()
        self.pending_thumbnail_updates.clear()
        self.thumbnail_poll_timer.stop()
        self.thumbnail_update_timer.stop()
        self.thumbnail_visible_priority_timer.stop()
        if clear_saved_queue:
            self._save_pending_thumbnails()

    def _poll_thumbnail_futures(self) -> None:
        if not self.thumbnail_futures:
            self.thumbnail_poll_timer.stop()
            self._save_pending_thumbnails()
            return

        done_futures = [future for future in self.thumbnail_futures if future.done()]
        had_finished_work = bool(done_futures)
        for future in done_futures:
            source_path = self.thumbnail_futures.pop(future)
            self.thumbnail_queued_paths.discard(source_path)
            try:
                completed_source, thumbnail_path = future.result()
            except Exception:
                continue
            if thumbnail_path:
                self.thumbnail_paths_by_source[completed_source] = thumbnail_path
                self._queue_thumbnail_update(completed_source, thumbnail_path)

        self._start_next_thumbnail_job()
        if had_finished_work:
            self._save_pending_thumbnails()

    def _queue_thumbnail_update(self, source_path: str, thumbnail_path: str) -> None:
        self.pending_thumbnail_updates[source_path] = thumbnail_path
        if not self.thumbnail_update_timer.isActive():
            self.thumbnail_update_timer.start()

    def _flush_thumbnail_updates(self) -> None:
        if not self.pending_thumbnail_updates:
            self.thumbnail_update_timer.stop()
            return

        self.file_list.setUpdatesEnabled(False)
        try:
            for source_path in list(self.pending_thumbnail_updates)[
                :THUMBNAIL_UI_UPDATES_PER_TICK
            ]:
                thumbnail_path = self.pending_thumbnail_updates.pop(source_path)
                item = self.file_items_by_path.get(source_path)
                if item is not None:
                    item.setIcon(QIcon(thumbnail_path))
        finally:
            self.file_list.setUpdatesEnabled(True)

    def _update_thumbnail_status(self) -> None:
        if self.current_folder is None:
            return

        remaining = len(self.thumbnail_queue) + len(self.thumbnail_futures)
        if remaining:
            self.status.setText(
                f"{self.file_list.count()} image(s) in {self.current_folder} "
                f"- thumbnail queue: {remaining}"
            )
        else:
            self.status.setText(
                f"{self.file_list.count()} image(s) in {self.current_folder}"
            )

    def _resume_pending_thumbnails(self) -> None:
        pending_paths = [
            path
            for path in self.settings.pending_thumbnail_paths()
            if path.exists() and self.thumbnail_cache.cached_path_for(path) is None
        ]
        if pending_paths:
            self._start_thumbnail_loading(pending_paths)
        else:
            self.settings.set_pending_thumbnail_paths([])

    def _save_pending_thumbnails(self) -> None:
        pending_paths = list(self.thumbnail_queue)
        pending_paths.extend(Path(path) for path in self.thumbnail_futures.values())
        self.settings.set_pending_thumbnail_paths(pending_paths)

    def _make_placeholder_thumbnail(self) -> QPixmap:
        placeholder = QPixmap(160, 120)
        placeholder.fill(Qt.GlobalColor.darkGray)
        return placeholder

    def _on_current_file_changed(
        self, current: QListWidgetItem | None, _previous: QListWidgetItem | None
    ) -> None:
        if current is None:
            self.preview.set_image(None)
            self._set_info_rows([])
            self.settings.set_selected_image_path(None)
            return

        image = current.data(Qt.ItemDataRole.UserRole)
        if not isinstance(image, ImageFile):
            return
        self.settings.set_selected_image_path(image.path)
        self._show_image(image)

    def _restore_or_clear_selected_image(self, folder: Path) -> None:
        selected_path = self.restore_selected_image_path or self.settings.selected_image_path()
        if selected_path is None or selected_path.parent != folder:
            self.settings.set_selected_image_path(None)
            self.restore_selected_image_path = None
            return

        item = self.file_items_by_path.get(str(selected_path))
        if item is None:
            self.settings.set_selected_image_path(None)
            self.restore_selected_image_path = None
            return

        self.file_list.setCurrentItem(item)
        self.file_list.scrollToItem(item, QAbstractItemView.ScrollHint.PositionAtCenter)
        self.restore_selected_image_path = None

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
        metadata = read_image_metadata(path)
        rows: list[tuple[str, str]] = [
            ("File name", path.name),
            ("Full path", str(path)),
            ("Root folder", str(root)),
            ("Folder", str(path.parent)),
            ("Extension", path.suffix.lower()),
        ]

        try:
            stat = path.stat()
            captured_rows = [
                row for row in metadata.rows if row[0] == "撮影日時"
            ]
            rows.extend(
                [
                    ("File size", self._format_size(stat.st_size)),
                    *captured_rows,
                    (
                        "更新日時",
                        datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                    ),
                ]
            )
        except OSError as exc:
            rows.append(("File status", f"Unavailable: {exc}"))

        reader = QImageReader(str(path))
        size = reader.size()
        if size.isValid() and metadata.width is None and metadata.height is None:
            rows.append(("大きさ", f"{size.width()} x {size.height()}"))

        rows.extend(row for row in metadata.rows if row[0] != "撮影日時")

        self._set_info_rows(rows)

    def _set_info_rows(self, rows: list[tuple[str, str]]) -> None:
        self.info_table.setRowCount(len(rows))
        for row, (key, value) in enumerate(rows):
            self.info_table.setItem(row, 0, QTableWidgetItem(key))
            self.info_table.setItem(row, 1, QTableWidgetItem(value))

    def _restore_window_layout(self) -> None:
        geometry = self.settings.window_geometry()
        if geometry is not None:
            self.restoreGeometry(geometry)

        main_splitter_state = self.settings.main_splitter_state()
        if main_splitter_state is not None:
            self.main_splitter.restoreState(main_splitter_state)

        center_splitter_state = self.settings.center_splitter_state()
        if center_splitter_state is not None:
            self.center_splitter.restoreState(center_splitter_state)

    def _save_window_layout(self) -> None:
        self.settings.set_window_geometry(self.saveGeometry())
        self.settings.set_main_splitter_state(self.main_splitter.saveState())
        self.settings.set_center_splitter_state(self.center_splitter.saveState())

    @staticmethod
    def _format_size(size: int) -> str:
        value = float(size)
        for unit in ("B", "KB", "MB", "GB"):
            if value < 1024 or unit == "GB":
                return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
            value /= 1024
        return f"{size} B"

    def closeEvent(self, event) -> None:  # noqa: N802
        self._save_window_layout()
        self._save_pending_thumbnails()
        self._cancel_thumbnail_worker(clear_saved_queue=False)
        self.thumbnail_executor.shutdown(wait=False, cancel_futures=True)
        if self.preview_window is not None:
            self.preview_window.close()
        super().closeEvent(event)
