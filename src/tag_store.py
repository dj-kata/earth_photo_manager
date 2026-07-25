from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path
import random
import sqlite3
from uuid import uuid4


TAG_DB_SCHEMA_VERSION = 1
TAG_CSV_FIELDNAMES = ["category", "tag", "color", "related_tags"]
TAG_CSV_RELATION_SEPARATOR = ";"
TAG_CSV_RELATION_ASSIGNMENT = "="


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


class DuplicateCategoryError(ValueError):
    pass


class DuplicateTagError(ValueError):
    pass


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

    def export_csv(self, csv_path: Path) -> None:
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        with csv_path.open("w", newline="", encoding="utf-8-sig") as file:
            writer = csv.DictWriter(file, fieldnames=TAG_CSV_FIELDNAMES)
            writer.writeheader()
            categorized_ids: set[str] = set()
            for category in self.categories:
                category_tags = self.tags_for_category(category.id)
                if not category_tags:
                    writer.writerow(
                        {
                            "category": category.name,
                            "tag": "",
                            "color": "",
                            "related_tags": "",
                        }
                    )
                    continue
                for tag in category_tags:
                    categorized_ids.add(tag.id)
                    writer.writerow(self._tag_csv_row(tag))

            for tag in self.tags:
                if tag.id not in categorized_ids:
                    writer.writerow(self._tag_csv_row(tag))

    def csv_has_missing_tag_colors(self, csv_path: Path) -> bool:
        rows = self._read_tag_csv_rows(csv_path)
        return any(
            self._clean_csv_value(row.get("tag"))
            and not self._clean_csv_value(row.get("color"))
            for row in rows
        )

    def import_csv(
        self,
        csv_path: Path,
        randomize_missing_colors: bool = False,
    ) -> tuple[int, int]:
        rows = self._read_tag_csv_rows(csv_path)
        cleaned_rows = [
            {
                "category": self._clean_csv_value(row.get("category")),
                "tag": self._clean_csv_value(row.get("tag")),
                "color": self._csv_tag_color(row, randomize_missing_colors),
                "related_tags": self._clean_csv_value(row.get("related_tags")),
            }
            for row in rows
        ]

        categories_by_name = {category.name: category for category in self.categories}
        tags_by_key = self._tags_by_import_key()
        anchor_tag_ids_by_key: dict[tuple[str, str], str] = {}
        finalized_anchor_keys: set[tuple[str, str]] = set()
        imported_category_ids: set[str] = set()
        imported_tag_ids: set[str] = set()

        try:
            with self._connection:
                for row in cleaned_rows:
                    category_name = row["category"]
                    if category_name:
                        category = categories_by_name.get(category_name)
                        if category is None:
                            category = TagCategory(id=self._new_id(), name=category_name)
                            self.categories.append(category)
                            categories_by_name[category.name] = category
                            self._connection.execute(
                                "INSERT INTO categories (id, name) VALUES (?, ?)",
                                (category.id, category.name),
                            )
                        imported_category_ids.add(category.id)

                for row in cleaned_rows:
                    category_name = row["category"]
                    tag_name = row["tag"]
                    if not tag_name:
                        continue

                    tag_key = self._tag_import_key(category_name, tag_name)
                    if tag_key in tags_by_key:
                        continue

                    tag = Tag(
                        id=self._new_id(),
                        name=tag_name,
                        color=row["color"],
                        category_id=self._category_id_by_name(
                            category_name,
                            categories_by_name,
                        ),
                    )
                    self.tags.append(tag)
                    tags_by_key[tag_key] = tag
                    anchor_tag_ids_by_key[tag_key] = tag.id
                    self._connection.execute(
                        """
                        INSERT INTO tags (id, name, color, category_id)
                        VALUES (?, ?, ?, ?)
                        """,
                        (tag.id, tag.name, tag.color, tag.category_id),
                    )

                for row in cleaned_rows:
                    category_name = row["category"]
                    tag_name = row["tag"]
                    if not tag_name:
                        continue

                    category_id = self._category_id_by_name(
                        category_name,
                        categories_by_name,
                    )
                    tag_key = self._tag_import_key(category_name, tag_name)
                    related = self._related_ids_from_csv(
                        row["related_tags"],
                        categories_by_name,
                        tags_by_key,
                    )
                    anchor_tag_id = anchor_tag_ids_by_key.get(tag_key)
                    if (
                        anchor_tag_id is not None
                        and tag_key not in finalized_anchor_keys
                    ):
                        tag = self.tag_by_id(anchor_tag_id)
                        finalized_anchor_keys.add(tag_key)
                    else:
                        tag = self._duplicate_tag_for(tag_name, category_id, related)

                    if tag is None:
                        tag = Tag(
                            id=self._new_id(),
                            name=tag_name,
                            color=row["color"],
                            category_id=category_id,
                            related_tag_ids_by_category=related,
                        )
                        self.tags.append(tag)
                        self._connection.execute(
                            """
                            INSERT INTO tags (id, name, color, category_id)
                            VALUES (?, ?, ?, ?)
                            """,
                            (tag.id, tag.name, tag.color, tag.category_id),
                        )
                    else:
                        tag.name = tag_name
                        tag.color = row["color"]
                        tag.category_id = category_id
                        tag.related_tag_ids_by_category = related
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
                    imported_tag_ids.add(tag.id)
        except Exception:
            self.load()
            raise

        return len(imported_category_ids), len(imported_tag_ids)

    def _read_tag_csv_rows(self, csv_path: Path) -> list[dict[str, str]]:
        with csv_path.open("r", newline="", encoding="utf-8-sig") as file:
            reader = csv.DictReader(file)
            if reader.fieldnames is None:
                raise ValueError("CSV header is missing.")
            missing = [
                field
                for field in TAG_CSV_FIELDNAMES
                if field not in reader.fieldnames
            ]
            if missing:
                raise ValueError(f"CSV columns are missing: {', '.join(missing)}")
            return [row for row in reader]

    def create_category(self, name: str) -> TagCategory:
        if self.category_by_name(name) is not None:
            raise DuplicateCategoryError(f"Duplicate category: {name}")
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
        duplicate = self.category_by_name(name)
        if duplicate is not None and duplicate.id != category_id:
            raise DuplicateCategoryError(f"Duplicate category: {name}")
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
        if self._duplicate_tag_for(name, clean_category_id, clean_related) is not None:
            raise DuplicateTagError(f"Duplicate tag: {name}")
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
        clean_category_id = self._valid_category_id(category_id)
        clean_related = self._valid_related_tag_ids(related_tag_ids_by_category)
        duplicate = self._duplicate_tag_for(
            name,
            clean_category_id,
            clean_related,
            exclude_tag_id=tag_id,
        )
        if duplicate is not None:
            raise DuplicateTagError(f"Duplicate tag: {name}")
        tag.name = name
        tag.color = color
        tag.category_id = clean_category_id
        tag.related_tag_ids_by_category = clean_related
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

    def category_by_name(self, name: str) -> TagCategory | None:
        return next(
            (category for category in self.categories if category.name == name),
            None,
        )

    def related_tag_ids_for(self, tag: Tag) -> list[str]:
        return [
            tag_id
            for tag_id in tag.related_tag_ids_by_category.values()
            if self.tag_by_id(tag_id) is not None
        ]

    def connected_tag_ids_for(self, tag: Tag) -> list[str]:
        connected_ids = set(self.related_tag_ids_for(tag))
        for candidate in self.tags:
            if tag.id in candidate.related_tag_ids_by_category.values():
                connected_ids.add(candidate.id)
        return [
            candidate.id
            for candidate in self.tags
            if candidate.id in connected_ids and candidate.id != tag.id
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

    def _tag_csv_row(self, tag: Tag) -> dict[str, str]:
        category = self.category_by_id(tag.category_id)
        return {
            "category": category.name if category else "",
            "tag": tag.name,
            "color": tag.color,
            "related_tags": self._related_tags_to_csv(tag),
        }

    def _related_tags_to_csv(self, tag: Tag) -> str:
        values: list[str] = []
        for category_id, related_tag_id in tag.related_tag_ids_by_category.items():
            category = self.category_by_id(category_id)
            related_tag = self.tag_by_id(related_tag_id)
            if category is None or related_tag is None:
                continue
            values.append(
                f"{category.name}{TAG_CSV_RELATION_ASSIGNMENT}{related_tag.name}"
            )
        return TAG_CSV_RELATION_SEPARATOR.join(values)

    def _related_ids_from_csv(
        self,
        value: str,
        categories_by_name: dict[str, TagCategory],
        tags_by_key: dict[tuple[str, str], Tag],
    ) -> dict[str, str]:
        related: dict[str, str] = {}
        if not value:
            return related
        for raw_entry in value.split(TAG_CSV_RELATION_SEPARATOR):
            entry = raw_entry.strip()
            if not entry:
                continue
            if TAG_CSV_RELATION_ASSIGNMENT not in entry:
                raise ValueError(f"Invalid related tag entry: {entry}")
            category_name, tag_name = [
                part.strip()
                for part in entry.split(TAG_CSV_RELATION_ASSIGNMENT, 1)
            ]
            category = categories_by_name.get(category_name)
            related_tag = tags_by_key.get(self._tag_import_key(category_name, tag_name))
            if category is None or related_tag is None:
                raise ValueError(f"Unknown related tag entry: {entry}")
            related[category.id] = related_tag.id
        return related

    def _category_name_for_tag(self, tag: Tag) -> str:
        category = self.category_by_id(tag.category_id)
        return category.name if category is not None else ""

    def _category_id_by_name(
        self,
        category_name: str,
        categories_by_name: dict[str, TagCategory],
    ) -> str | None:
        category = categories_by_name.get(category_name)
        return category.id if category is not None else None

    def _tags_by_import_key(self) -> dict[tuple[str, str], Tag]:
        tags_by_key: dict[tuple[str, str], Tag] = {}
        for tag in self.tags:
            tags_by_key.setdefault(
                self._tag_import_key(self._category_name_for_tag(tag), tag.name),
                tag,
            )
        return tags_by_key

    def _duplicate_tag_for(
        self,
        name: str,
        category_id: str | None,
        related_tag_ids_by_category: dict[str, str],
        exclude_tag_id: str | None = None,
    ) -> Tag | None:
        signature = self._tag_signature(name, category_id, related_tag_ids_by_category)
        return next(
            (
                tag
                for tag in self.tags
                if tag.id != exclude_tag_id
                and self._tag_signature(
                    tag.name,
                    tag.category_id,
                    tag.related_tag_ids_by_category,
                )
                == signature
            ),
            None,
        )

    @staticmethod
    def _tag_signature(
        name: str,
        category_id: str | None,
        related_tag_ids_by_category: dict[str, str],
    ) -> tuple[str, str | None, tuple[tuple[str, str], ...]]:
        return (
            name,
            category_id,
            tuple(sorted(related_tag_ids_by_category.items())),
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

    @staticmethod
    def _clean_csv_value(value: str | None) -> str:
        return value.strip() if value else ""

    def _csv_tag_color(
        self,
        row: dict[str, str],
        randomize_missing_colors: bool,
    ) -> str:
        color = self._clean_csv_value(row.get("color"))
        if color:
            return color
        if self._clean_csv_value(row.get("tag")) and randomize_missing_colors:
            return self._random_tag_color()
        return "#3b82f6"

    @staticmethod
    def _random_tag_color() -> str:
        return f"#{random.randint(0, 0xFFFFFF):06x}"

    @staticmethod
    def _tag_import_key(category_name: str, tag_name: str) -> tuple[str, str]:
        return category_name, tag_name
