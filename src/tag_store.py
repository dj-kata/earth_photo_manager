from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import sqlite3
from uuid import uuid4


TAG_DB_SCHEMA_VERSION = 1


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
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(str(self.database_path))
        self._connection.execute("PRAGMA foreign_keys = ON")
        self._connection.execute("PRAGMA journal_mode = WAL")
        self.categories: list[TagCategory] = []
        self.tags: list[Tag] = []
        self.image_tag_ids_by_path: dict[str, list[str]] = {}
        self._initialize_schema()
        self.load()

    def _initialize_schema(self) -> None:
        self._connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS categories (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS tags (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                color TEXT NOT NULL,
                category_id TEXT REFERENCES categories(id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS tag_relations (
                tag_id TEXT NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
                category_id TEXT NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
                related_tag_id TEXT NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
                PRIMARY KEY (tag_id, category_id)
            );

            CREATE TABLE IF NOT EXISTS image_tags (
                path TEXT NOT NULL,
                tag_id TEXT NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
                position INTEGER NOT NULL,
                PRIMARY KEY (path, tag_id)
            );

            CREATE INDEX IF NOT EXISTS idx_image_tags_tag_id
                ON image_tags(tag_id);
            """
        )
        self._connection.execute(
            """
            INSERT OR REPLACE INTO metadata (key, value)
            VALUES ('schema_version', ?)
            """,
            (str(TAG_DB_SCHEMA_VERSION),),
        )
        self._connection.commit()

    def load(self) -> None:
        self.categories = [
            TagCategory(id=row["id"], name=row["name"])
            for row in self._fetch_all("SELECT id, name FROM categories ORDER BY rowid")
        ]

        related_by_tag_id: dict[str, dict[str, str]] = {}
        for row in self._fetch_all(
            """
            SELECT tag_id, category_id, related_tag_id
            FROM tag_relations
            ORDER BY rowid
            """
        ):
            related_by_tag_id.setdefault(row["tag_id"], {})[
                row["category_id"]
            ] = row["related_tag_id"]

        self.tags = [
            Tag(
                id=row["id"],
                name=row["name"],
                color=row["color"],
                category_id=row["category_id"],
                related_tag_ids_by_category=related_by_tag_id.get(row["id"], {}),
            )
            for row in self._fetch_all(
                "SELECT id, name, color, category_id FROM tags ORDER BY rowid"
            )
        ]

        self.image_tag_ids_by_path = {}
        for row in self._fetch_all(
            "SELECT path, tag_id FROM image_tags ORDER BY path, position"
        ):
            self.image_tag_ids_by_path.setdefault(row["path"], []).append(row["tag_id"])

    def save(self) -> None:
        with self._connection:
            self._connection.execute("DELETE FROM image_tags")
            self._connection.execute("DELETE FROM tag_relations")
            self._connection.execute("DELETE FROM tags")
            self._connection.execute("DELETE FROM categories")
            self._connection.executemany(
                "INSERT INTO categories (id, name) VALUES (?, ?)",
                [(category.id, category.name) for category in self.categories],
            )
            self._connection.executemany(
                """
                INSERT INTO tags (id, name, color, category_id)
                VALUES (?, ?, ?, ?)
                """,
                [
                    (tag.id, tag.name, tag.color, tag.category_id)
                    for tag in self.tags
                ],
            )
            self._connection.executemany(
                """
                INSERT INTO tag_relations (tag_id, category_id, related_tag_id)
                VALUES (?, ?, ?)
                """,
                [
                    (tag.id, category_id, related_tag_id)
                    for tag in self.tags
                    for category_id, related_tag_id
                    in tag.related_tag_ids_by_category.items()
                ],
            )
            self._connection.executemany(
                """
                INSERT INTO image_tags (path, tag_id, position)
                VALUES (?, ?, ?)
                """,
                [
                    (path, tag_id, index)
                    for path, tag_ids in self.image_tag_ids_by_path.items()
                    for index, tag_id in enumerate(tag_ids)
                ],
            )

    def create_category(self, name: str) -> TagCategory:
        category = TagCategory(id=self._new_id(), name=name)
        with self._connection:
            self._connection.execute(
                "INSERT INTO categories (id, name) VALUES (?, ?)",
                (category.id, category.name),
            )
        self.categories.append(category)
        return category

    def update_category(self, category_id: str, name: str) -> None:
        category = self.category_by_id(category_id)
        if category is None:
            return
        with self._connection:
            self._connection.execute(
                "UPDATE categories SET name = ? WHERE id = ?",
                (name, category_id),
            )
        category.name = name

    def delete_category(self, category_id: str) -> None:
        with self._connection:
            self._connection.execute("DELETE FROM categories WHERE id = ?", (category_id,))
        self.categories = [
            category for category in self.categories if category.id != category_id
        ]
        for tag in self.tags:
            if tag.category_id == category_id:
                tag.category_id = None
            tag.related_tag_ids_by_category.pop(category_id, None)

    def create_tag(
        self,
        name: str,
        color: str,
        category_id: str | None,
        related_tag_ids_by_category: dict[str, str],
    ) -> Tag:
        clean_category_id = self._valid_category_id(category_id)
        clean_related = self._valid_related_tag_ids(related_tag_ids_by_category)
        tag = Tag(
            id=self._new_id(),
            name=name,
            color=color,
            category_id=clean_category_id,
            related_tag_ids_by_category=clean_related,
        )
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO tags (id, name, color, category_id)
                VALUES (?, ?, ?, ?)
                """,
                (tag.id, tag.name, tag.color, tag.category_id),
            )
            self._write_tag_relations(tag)
        self.tags.append(tag)
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
        tag.category_id = self._valid_category_id(category_id)
        tag.related_tag_ids_by_category = self._valid_related_tag_ids(
            related_tag_ids_by_category
        )
        with self._connection:
            self._connection.execute(
                """
                UPDATE tags
                SET name = ?, color = ?, category_id = ?
                WHERE id = ?
                """,
                (tag.name, tag.color, tag.category_id, tag.id),
            )
            self._connection.execute(
                "DELETE FROM tag_relations WHERE tag_id = ?",
                (tag.id,),
            )
            self._write_tag_relations(tag)

    def delete_tag(self, tag_id: str) -> None:
        with self._connection:
            self._connection.execute("DELETE FROM tags WHERE id = ?", (tag_id,))
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

    def image_tag_ids(self, path: Path) -> list[str]:
        return list(self.image_tag_ids_by_path.get(str(path), []))

    def set_image_tag_ids(self, path: Path, tag_ids: list[str]) -> None:
        valid_tag_ids = {tag.id for tag in self.tags}
        clean_ids = self._deduplicated(
            [tag_id for tag_id in tag_ids if tag_id in valid_tag_ids]
        )
        key = str(path)
        with self._connection:
            self._connection.execute("DELETE FROM image_tags WHERE path = ?", (key,))
            self._connection.executemany(
                """
                INSERT INTO image_tags (path, tag_id, position)
                VALUES (?, ?, ?)
                """,
                [(key, tag_id, index) for index, tag_id in enumerate(clean_ids)],
            )
        if clean_ids:
            self.image_tag_ids_by_path[key] = clean_ids
        else:
            self.image_tag_ids_by_path.pop(key, None)

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

    def close(self) -> None:
        self._connection.close()

    def _write_tag_relations(self, tag: Tag) -> None:
        self._connection.executemany(
            """
            INSERT INTO tag_relations (tag_id, category_id, related_tag_id)
            VALUES (?, ?, ?)
            """,
            [
                (tag.id, category_id, related_tag_id)
                for category_id, related_tag_id
                in tag.related_tag_ids_by_category.items()
            ],
        )

    def _valid_category_id(self, category_id: str | None) -> str | None:
        return category_id if self.category_by_id(category_id) is not None else None

    def _valid_related_tag_ids(self, values: dict[str, str]) -> dict[str, str]:
        return {
            str(category_id): str(related_tag_id)
            for category_id, related_tag_id in values.items()
            if self.category_by_id(str(category_id)) is not None
            and self.tag_by_id(str(related_tag_id)) is not None
        }

    def _fetch_all(self, query: str) -> list[sqlite3.Row]:
        previous_factory = self._connection.row_factory
        self._connection.row_factory = sqlite3.Row
        try:
            cursor = self._connection.execute(query)
            return list(cursor.fetchall())
        finally:
            self._connection.row_factory = previous_factory

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
