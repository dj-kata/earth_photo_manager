from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import uuid4


MAGAZINE_FEATURE_TEMPLATE_ID = "magazine_feature_01"
MAGAZINE_HERO_OVERLAY_TEMPLATE_ID = "magazine_hero_overlay_02"
NEWSPAPER_ARTICLE_TEMPLATE_ID = "newspaper_article_01"
NEWSPAPER_COLUMNS_TEMPLATE_ID = "newspaper_columns_02"
PHOTO_ESSAY_TEMPLATE_ID = "photo_essay_01"
PHOTO_ESSAY_ASYMMETRIC_TEMPLATE_ID = "photo_essay_asymmetric_02"
PROFILE_FEATURE_TEMPLATE_ID = "profile_feature_01"
PROFILE_BANNER_TEMPLATE_ID = "profile_banner_02"
EDITORIAL_TEMPLATE_IDS = (
    MAGAZINE_FEATURE_TEMPLATE_ID,
    MAGAZINE_HERO_OVERLAY_TEMPLATE_ID,
    NEWSPAPER_ARTICLE_TEMPLATE_ID,
    NEWSPAPER_COLUMNS_TEMPLATE_ID,
    PHOTO_ESSAY_TEMPLATE_ID,
    PHOTO_ESSAY_ASYMMETRIC_TEMPLATE_ID,
    PROFILE_FEATURE_TEMPLATE_ID,
    PROFILE_BANNER_TEMPLATE_ID,
)
MIN_EDITORIAL_PHOTOS = 1


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
    included: bool = True
    crop_x: float = 0.0
    crop_y: float = 0.0
    crop_width: float = 1.0
    crop_height: float = 1.0

    def __post_init__(self) -> None:
        self.source_path = Path(self.source_path)
        self.focus_x = min(1.0, max(0.0, float(self.focus_x)))
        self.focus_y = min(1.0, max(0.0, float(self.focus_y)))
        self.crop_width = min(1.0, max(0.02, float(self.crop_width)))
        self.crop_height = min(1.0, max(0.02, float(self.crop_height)))
        self.crop_x = min(1.0 - self.crop_width, max(0.0, float(self.crop_x)))
        self.crop_y = min(1.0 - self.crop_height, max(0.0, float(self.crop_y)))


@dataclass
class EditorialDocument:
    schema_version: int = 4
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
    layout_seed: int = 0
    font_family: str = "Noto Sans JP"
    publication_title: str = "THE EARTH OBSERVER"

    def __post_init__(self) -> None:
        self._update_photo_roles()

    def validate(self, max_photos: int | None = None) -> None:
        photo_count = len(self.included_photos())
        if photo_count < MIN_EDITORIAL_PHOTOS or (
            max_photos is not None and photo_count > max_photos
        ):
            raise ValueError(
                f"photo count must be between {MIN_EDITORIAL_PHOTOS} and "
                f"{max_photos if max_photos is not None else 'unlimited'}"
            )
        if self.template_id not in EDITORIAL_TEMPLATE_IDS:
            raise ValueError(f"unsupported template: {self.template_id}")

    def _update_photo_roles(self) -> None:
        included_index = 0
        for photo in self.photos:
            if not photo.included:
                photo.role = "excluded"
                continue
            photo.role = "hero" if included_index == 0 else "supporting"
            included_index += 1

    def included_photos(self) -> list[EditorialPhoto]:
        return [photo for photo in self.photos if photo.included]

    def set_photo_included(self, index: int, included: bool) -> None:
        if not 0 <= index < len(self.photos):
            raise IndexError(index)
        self.photos[index].included = included
        self._update_photo_roles()

    def effective_sections(self) -> list[EditorialSection]:
        if self.sections:
            return self.sections
        if self.body:
            return [EditorialSection(body=self.body, id="legacy-body")]
        return []

    def set_hero_photo(self, index: int, max_photos: int | None = None) -> None:
        if not 0 <= index < len(self.photos):
            raise IndexError(index)
        selected = self.photos[index]
        if not selected.included:
            included = self.included_photos()
            if max_photos is not None and len(included) >= max_photos:
                included[0].included = False
            selected.included = True
            index = self.photos.index(selected)
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

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "template_id": self.template_id,
            "layout_seed": self.layout_seed,
            "font_family": self.font_family,
            "publication_title": self.publication_title,
            "title": self.title,
            "subtitle": self.subtitle,
            "lead": self.lead,
            "body": self.body,
            "pull_quote": self.pull_quote,
            "metadata": {
                "category": self.metadata.category,
                "author": self.metadata.author,
                "date": self.metadata.date,
            },
            "sections": [
                {"id": section.id, "heading": section.heading, "body": section.body}
                for section in self.sections
            ],
            "profile_fields": [
                {"id": field.id, "label": field.label, "value": field.value}
                for field in self.profile_fields
            ],
            "photos": [
                {
                    "source_path": str(photo.source_path),
                    "source_id": photo.source_id,
                    "caption": photo.caption,
                    "included": photo.included,
                    "focus_x": photo.focus_x,
                    "focus_y": photo.focus_y,
                    "crop_x": photo.crop_x,
                    "crop_y": photo.crop_y,
                    "crop_width": photo.crop_width,
                    "crop_height": photo.crop_height,
                }
                for photo in self.photos
            ],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EditorialDocument:
        metadata_data = data.get("metadata") or {}
        photos = [
            EditorialPhoto(
                source_path=Path(str(photo["source_path"])),
                source_id=photo.get("source_id"),
                caption=str(photo.get("caption", "")),
                included=bool(photo.get("included", True)),
                focus_x=float(photo.get("focus_x", 0.5)),
                focus_y=float(photo.get("focus_y", 0.5)),
                crop_x=float(photo.get("crop_x", 0.0)),
                crop_y=float(photo.get("crop_y", 0.0)),
                crop_width=float(photo.get("crop_width", 1.0)),
                crop_height=float(photo.get("crop_height", 1.0)),
            )
            for photo in data.get("photos", [])
            if isinstance(photo, dict) and photo.get("source_path")
        ]
        document = cls(
            schema_version=max(4, int(data.get("schema_version", 1))),
            photos=photos,
            title=str(data.get("title", "")),
            subtitle=str(data.get("subtitle", "")),
            lead=str(data.get("lead", "")),
            body=str(data.get("body", "")),
            metadata=EditorialMetadata(
                category=str(metadata_data.get("category", "")),
                author=str(metadata_data.get("author", "")),
                date=str(metadata_data.get("date", "")),
            ),
            sections=[
                EditorialSection(
                    heading=str(section.get("heading", "")),
                    body=str(section.get("body", "")),
                    id=str(section.get("id") or _new_item_id()),
                )
                for section in data.get("sections", [])
                if isinstance(section, dict)
            ],
            profile_fields=[
                EditorialProfileField(
                    label=str(profile.get("label", "")),
                    value=str(profile.get("value", "")),
                    id=str(profile.get("id") or _new_item_id()),
                )
                for profile in data.get("profile_fields", [])
                if isinstance(profile, dict)
            ],
            pull_quote=str(data.get("pull_quote", "")),
            template_id=str(data.get("template_id", MAGAZINE_FEATURE_TEMPLATE_ID)),
            layout_seed=int(data.get("layout_seed", 0)),
            font_family=str(data.get("font_family", "Noto Sans JP")),
            publication_title=str(
                data.get("publication_title", "THE EARTH OBSERVER")
            ),
        )
        if document.template_id not in EDITORIAL_TEMPLATE_IDS:
            document.template_id = MAGAZINE_FEATURE_TEMPLATE_ID
        document._update_photo_roles()
        return document
