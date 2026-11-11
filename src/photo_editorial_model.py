from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


MAGAZINE_FEATURE_TEMPLATE_ID = "magazine_feature_01"
NEWSPAPER_ARTICLE_TEMPLATE_ID = "newspaper_article_01"
PHOTO_ESSAY_TEMPLATE_ID = "photo_essay_01"
PROFILE_FEATURE_TEMPLATE_ID = "profile_feature_01"
EDITORIAL_TEMPLATE_IDS = (
    MAGAZINE_FEATURE_TEMPLATE_ID,
    NEWSPAPER_ARTICLE_TEMPLATE_ID,
    PHOTO_ESSAY_TEMPLATE_ID,
    PROFILE_FEATURE_TEMPLATE_ID,
)
MIN_EDITORIAL_PHOTOS = 1
MAX_EDITORIAL_PHOTOS = 6


@dataclass
class EditorialPhoto:
    source_path: Path
    source_id: str | None = None
    caption: str = ""
    role: str = "photo"
    focus_x: float = 0.5
    focus_y: float = 0.5

    def __post_init__(self) -> None:
        self.source_path = Path(self.source_path)
        self.focus_x = min(1.0, max(0.0, float(self.focus_x)))
        self.focus_y = min(1.0, max(0.0, float(self.focus_y)))


@dataclass
class EditorialDocument:
    photos: list[EditorialPhoto] = field(default_factory=list)
    title: str = ""
    body: str = ""
    template_id: str = MAGAZINE_FEATURE_TEMPLATE_ID

    def __post_init__(self) -> None:
        self._update_photo_roles()

    def validate(self) -> None:
        photo_count = len(self.photos)
        if not MIN_EDITORIAL_PHOTOS <= photo_count <= MAX_EDITORIAL_PHOTOS:
            raise ValueError(
                f"photo count must be between {MIN_EDITORIAL_PHOTOS} "
                f"and {MAX_EDITORIAL_PHOTOS}"
            )
        if self.template_id not in EDITORIAL_TEMPLATE_IDS:
            raise ValueError(f"unsupported template: {self.template_id}")

    def _update_photo_roles(self) -> None:
        for index, photo in enumerate(self.photos):
            photo.role = "hero" if index == 0 else "supporting"
