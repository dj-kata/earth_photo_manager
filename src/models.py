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

RAW_EXTENSIONS = {
    ".arw",
    ".srf",
    ".sr2",
    ".cr2",
    ".cr3",
    ".crw",
    ".nef",
    ".nrw",
    ".raf",
    ".rw2",
    ".orf",
    ".dng",
}


def find_raw_file_for_image(path: Path, root: Path | None = None) -> Path | None:
    stem = path.stem.casefold()
    search_root = root if root is not None and root.exists() else path.parent

    for candidate in _raw_candidates_in_folder(path.parent, stem):
        return candidate

    try:
        candidates_by_path: dict[Path, Path] = {}
        for raw_stem in {path.stem, path.stem.lower(), path.stem.upper()}:
            for candidate in search_root.rglob(f"{raw_stem}.*"):
                if _is_matching_raw_candidate(candidate, stem):
                    candidates_by_path[candidate] = candidate
        candidates = sorted(
            candidates_by_path,
            key=lambda candidate: str(candidate).casefold(),
        )
    except OSError:
        return None

    return candidates[0] if candidates else None


def _raw_candidates_in_folder(folder: Path, stem: str) -> list[Path]:
    try:
        return sorted(
            (
                candidate
                for candidate in folder.iterdir()
                if _is_matching_raw_candidate(candidate, stem)
            ),
            key=lambda candidate: str(candidate).casefold(),
        )
    except OSError:
        return []


def _is_matching_raw_candidate(candidate: Path, stem: str) -> bool:
    return (
        candidate.is_file()
        and candidate.stem.casefold() == stem
        and candidate.suffix.casefold() in RAW_EXTENSIONS
    )


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
