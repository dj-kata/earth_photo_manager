from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from uuid import uuid4


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


def _new_item_id() -> str:
    return uuid4().hex


@dataclass
class EditorialMetadata:
    category: str = ""
    author: str = ""
    date: str = ""


@dataclass
class EditorialSection:
    heading: str = ""
    body: str = ""
    id: str = field(default_factory=_new_item_id)


@dataclass
class EditorialProfileField:
    label: str = ""
    value: str = ""
    id: str = field(default_factory=_new_item_id)


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
    schema_version: int = 2
    photos: list[EditorialPhoto] = field(default_factory=list)
    title: str = ""
    subtitle: str = ""
    lead: str = ""
    body: str = ""
    metadata: EditorialMetadata = field(default_factory=EditorialMetadata)
    sections: list[EditorialSection] = field(default_factory=list)
    profile_fields: list[EditorialProfileField] = field(default_factory=list)
    pull_quote: str = ""
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

    def effective_sections(self) -> list[EditorialSection]:
        if self.sections:
            return self.sections
        if self.body:
            return [EditorialSection(body=self.body, id="legacy-body")]
        return []

    def set_hero_photo(self, index: int) -> None:
        if not 0 <= index < len(self.photos):
            raise IndexError(index)
        if index:
            self.photos.insert(0, self.photos.pop(index))
        self._update_photo_roles()

    def move_photo(self, index: int, offset: int) -> int:
        target = index + offset
        if not 0 <= index < len(self.photos) or not 0 <= target < len(self.photos):
            return index
        self.photos[index], self.photos[target] = self.photos[target], self.photos[index]
        self._update_photo_roles()
        return target
