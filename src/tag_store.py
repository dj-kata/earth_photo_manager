from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
from uuid import uuid4

from PySide6.QtCore import QSettings


TAG_DATA_VERSION = 1


@dataclass
class TagCategory:
    id: str
    name: str


@dataclass
class Tag:
    id: str
    name: str
    color: str
    category_id: str | None = None
    related_tag_ids_by_category: dict[str, str] = field(default_factory=dict)


class TagStore:
    def __init__(self, settings: QSettings) -> None:
        self._settings = settings
        self.categories: list[TagCategory] = []
        self.tags: list[Tag] = []
        self.image_tag_ids_by_path: dict[str, list[str]] = {}
        self.load()

    def load(self) -> None:
        raw = self._settings.value("tag_data", "", str)
        if not raw:
            return

        try:
            data = json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            return

        self.categories = [
            TagCategory(id=str(item["id"]), name=str(item["name"]))
            for item in data.get("categories", [])
            if item.get("id") and item.get("name")
        ]
        category_ids = {category.id for category in self.categories}

        self.tags = []
        for item in data.get("tags", []):
            tag_id = item.get("id")
            name = item.get("name")
            if not tag_id or not name:
                continue
            category_id = item.get("category_id") or None
            if category_id not in category_ids:
                category_id = None
            related = {
                str(category_id): str(related_tag_id)
                for category_id, related_tag_id in item.get(
                    "related_tag_ids_by_category", {}
                ).items()
                if category_id in category_ids and related_tag_id
            }
            self.tags.append(
                Tag(
                    id=str(tag_id),
                    name=str(name),
                    color=str(item.get("color") or "#3b82f6"),
                    category_id=category_id,
                    related_tag_ids_by_category=related,
                )
            )

        tag_ids = {tag.id for tag in self.tags}
        self.image_tag_ids_by_path = {}
        for path, assigned_ids in data.get("image_tag_ids_by_path", {}).items():
            ids = [str(tag_id) for tag_id in assigned_ids if str(tag_id) in tag_ids]
            if ids:
                self.image_tag_ids_by_path[str(path)] = self._deduplicated(ids)

    def save(self) -> None:
        data = {
            "version": TAG_DATA_VERSION,
            "categories": [
                {"id": category.id, "name": category.name}
                for category in self.categories
            ],
            "tags": [
                {
                    "id": tag.id,
                    "name": tag.name,
                    "color": tag.color,
                    "category_id": tag.category_id,
                    "related_tag_ids_by_category": tag.related_tag_ids_by_category,
                }
                for tag in self.tags
            ],
            "image_tag_ids_by_path": self.image_tag_ids_by_path,
        }
        self._settings.setValue(
            "tag_data", json.dumps(data, ensure_ascii=False, separators=(",", ":"))
        )

    def create_category(self, name: str) -> TagCategory:
        category = TagCategory(id=self._new_id(), name=name)
        self.categories.append(category)
        self.save()
        return category

    def update_category(self, category_id: str, name: str) -> None:
        category = self.category_by_id(category_id)
        if category is None:
            return
        category.name = name
        self.save()

    def delete_category(self, category_id: str) -> None:
        self.categories = [
            category for category in self.categories if category.id != category_id
        ]
        for tag in self.tags:
            if tag.category_id == category_id:
                tag.category_id = None
            tag.related_tag_ids_by_category.pop(category_id, None)
        self.save()

    def create_tag(
        self,
        name: str,
        color: str,
        category_id: str | None,
        related_tag_ids_by_category: dict[str, str],
    ) -> Tag:
        tag = Tag(
            id=self._new_id(),
            name=name,
            color=color,
            category_id=category_id,
            related_tag_ids_by_category=related_tag_ids_by_category,
        )
        self.tags.append(tag)
        self.save()
        return tag

    def update_tag(
        self,
        tag_id: str,
        name: str,
        color: str,
        category_id: str | None,
        related_tag_ids_by_category: dict[str, str],
    ) -> None:
        tag = self.tag_by_id(tag_id)
        if tag is None:
            return
        tag.name = name
        tag.color = color
        tag.category_id = category_id
        tag.related_tag_ids_by_category = related_tag_ids_by_category
        self.save()

    def delete_tag(self, tag_id: str) -> None:
        self.tags = [tag for tag in self.tags if tag.id != tag_id]
        for tag in self.tags:
            tag.related_tag_ids_by_category = {
                category_id: related_id
                for category_id, related_id in tag.related_tag_ids_by_category.items()
                if related_id != tag_id
            }
        for path, tag_ids in list(self.image_tag_ids_by_path.items()):
            remaining = [assigned_id for assigned_id in tag_ids if assigned_id != tag_id]
            if remaining:
                self.image_tag_ids_by_path[path] = remaining
            else:
                self.image_tag_ids_by_path.pop(path, None)
        self.save()

    def image_tag_ids(self, path: Path) -> list[str]:
        return list(self.image_tag_ids_by_path.get(str(path), []))

    def set_image_tag_ids(self, path: Path, tag_ids: list[str]) -> None:
        valid_tag_ids = {tag.id for tag in self.tags}
        clean_ids = self._deduplicated(
            [tag_id for tag_id in tag_ids if tag_id in valid_tag_ids]
        )
        key = str(path)
        if clean_ids:
            self.image_tag_ids_by_path[key] = clean_ids
        else:
            self.image_tag_ids_by_path.pop(key, None)
        self.save()

    def tag_by_id(self, tag_id: str | None) -> Tag | None:
        if tag_id is None:
            return None
        return next((tag for tag in self.tags if tag.id == tag_id), None)

    def category_by_id(self, category_id: str | None) -> TagCategory | None:
        if category_id is None:
            return None
        return next(
            (category for category in self.categories if category.id == category_id),
            None,
        )

    def related_tag_ids_for(self, tag: Tag) -> list[str]:
        return [
            tag_id
            for tag_id in tag.related_tag_ids_by_category.values()
            if self.tag_by_id(tag_id) is not None
        ]

    def tags_for_category(self, category_id: str) -> list[Tag]:
        return [tag for tag in self.tags if tag.category_id == category_id]

    @staticmethod
    def _deduplicated(values: list[str]) -> list[str]:
        clean: list[str] = []
        seen: set[str] = set()
        for value in values:
            if value in seen:
                continue
            seen.add(value)
            clean.append(value)
        return clean

    @staticmethod
    def _new_id() -> str:
        return uuid4().hex
