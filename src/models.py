from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


IMAGE_EXTENSIONS = {
    ".bmp",
    ".gif",
    ".jpeg",
    ".jpg",
    ".png",
    ".tif",
    ".tiff",
    ".webp",
}


@dataclass(frozen=True)
class ImageFile:
    path: Path
    root: Path

    @property
    def name(self) -> str:
        return self.path.name

    @property
    def folder(self) -> Path:
        return self.path.parent

    @property
    def relative_folder(self) -> str:
        try:
            return str(self.path.parent.relative_to(self.root))
        except ValueError:
            return str(self.path.parent)
