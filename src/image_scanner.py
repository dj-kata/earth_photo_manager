from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, Signal, Slot

from src.models import IMAGE_EXTENSIONS, ImageFile


class FolderLoadSignals(QObject):
    file_found = Signal(object)
    finished = Signal(int)
    failed = Signal(str)


class FolderImageLoadWorker(QRunnable):
    """Load image files directly under one folder."""

    def __init__(self, folder: Path, root: Path) -> None:
        super().__init__()
        self.folder = folder
        self.root = root
        self.signals = FolderLoadSignals()
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    @Slot()
    def run(self) -> None:
        count = 0
        try:
            children = sorted(self.folder.iterdir(), key=lambda path: path.name.lower())
        except OSError as exc:
            self.signals.failed.emit(str(exc))
            return

        for path in children:
            if self._cancelled:
                break
            if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS:
                self.signals.file_found.emit(ImageFile(path=path, root=self.root))
                count += 1

        self.signals.finished.emit(count)
