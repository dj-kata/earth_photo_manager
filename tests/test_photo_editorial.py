from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSize
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication

from src.models import ImageFile
from src.photo_editorial_model import (
    EDITORIAL_TEMPLATE_IDS,
    EditorialDocument,
    EditorialPhoto,
    EditorialProfileField,
    EditorialSection,
    MAGAZINE_FEATURE_TEMPLATE_ID,
    PROFILE_FEATURE_TEMPLATE_ID,
)
from src.photo_editorial_renderer import (
    OUTPUT_DOTS_PER_METER,
    PAGE_HEIGHT,
    PAGE_WIDTH,
    PhotoEditorialRenderer,
)
from src.photo_editorial_window import PhotoEditorialWindow


_application = QApplication.instance() or QApplication([])


class PhotoEditorialRendererTest(unittest.TestCase):
    def _make_photo(self, directory: Path, name: str, color: str) -> Path:
        path = directory / name
        image = QImage(640, 420, QImage.Format.Format_RGB32)
        image.fill(QColor(color))
        self.assertTrue(image.save(str(path), "PNG"))
        return path

    def test_renders_japanese_text_and_six_photos(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            photos = [
                EditorialPhoto(
                    self._make_photo(directory, f"photo_{index}.png", "#4f7cac"),
                    caption=f"写真{index}のキャプション",
                )
                for index in range(6)
            ]
            document = EditorialDocument(
                photos=photos,
                title="森で過ごす一日",
                body="日本語の本文です。\n写真とともに記録を残します。",
            )

            result = PhotoEditorialRenderer().render(document, QSize(620, 877))

            self.assertEqual(result.image.size(), QSize(620, 877))
            self.assertFalse(result.image.isNull())
            self.assertEqual(result.missing_paths, [])

    def test_full_size_png_export(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            source = self._make_photo(directory, "source.png", "#bc6c25")
            output = directory / "article.png"
            document = EditorialDocument(
                photos=[EditorialPhoto(source, caption="キャプション")],
                title="特集タイトル",
                body="本文",
            )

            result = PhotoEditorialRenderer().render(document)

            self.assertEqual(result.image.size(), QSize(PAGE_WIDTH, PAGE_HEIGHT))
            self.assertEqual(result.image.dotsPerMeterX(), OUTPUT_DOTS_PER_METER)
            self.assertEqual(result.image.dotsPerMeterY(), OUTPUT_DOTS_PER_METER)
            self.assertTrue(result.image.save(str(output), "PNG"))
            self.assertTrue(output.exists())

    def test_missing_photo_uses_placeholder(self) -> None:
        missing_path = Path("missing-photo-for-editorial-test.png")
        document = EditorialDocument(photos=[EditorialPhoto(missing_path)])

        result = PhotoEditorialRenderer().render(document, QSize(310, 439))

        self.assertEqual(result.missing_paths, [missing_path])
        self.assertFalse(result.image.isNull())

    def test_rejects_unsupported_photo_count(self) -> None:
        with self.assertRaises(ValueError):
            PhotoEditorialRenderer().render(EditorialDocument())

    def test_all_four_templates_render_the_same_document(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            source = self._make_photo(directory, "templates.png", "#457b9d")
            document = EditorialDocument(
                photos=[
                    EditorialPhoto(source, caption=f"写真{index}")
                    for index in range(3)
                ],
                title="四つの紙面",
                subtitle="共通データから作る記事",
                lead="入力した文章を保持したままフォーマットを切り替えます。",
                profile_fields=[
                    EditorialProfileField("所属", "○○動物園"),
                    EditorialProfileField("好物", "ユーカリ"),
                ],
                sections=[
                    EditorialSection("紹介", "一つ目の記事セクションです。"),
                    EditorialSection("近況", "二つ目の記事セクションです。"),
                ],
                pull_quote="お気に入りの一枚",
            )
            renderer = PhotoEditorialRenderer()

            for template_id in EDITORIAL_TEMPLATE_IDS:
                with self.subTest(template_id=template_id):
                    document.template_id = template_id
                    result = renderer.render(document, QSize(310, 439))
                    self.assertFalse(result.image.isNull())
                    self.assertEqual(result.missing_paths, [])
                    self.assertFalse(result.text_overflow)

    def test_profile_renders_fields_and_multiple_sections(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            source = self._make_photo(directory, "sachi.png", "#6a994e")
            document = EditorialDocument(
                photos=[EditorialPhoto(source, caption="木の上で休むさち")],
                title="さち",
                subtitle="のんびり過ごすコアラの一日",
                lead="この個体の魅力を紹介します。",
                profile_fields=[
                    EditorialProfileField("生年月日", "2018年生まれ"),
                    EditorialProfileField("性別", "メス"),
                    EditorialProfileField("所属", "○○動物園"),
                ],
                sections=[
                    EditorialSection("さちの紹介", "性格や特徴を紹介する文章。"),
                    EditorialSection("最近の様子", "撮影時のエピソード。"),
                ],
                template_id=PROFILE_FEATURE_TEMPLATE_ID,
            )

            result = PhotoEditorialRenderer().render(document, QSize(620, 877))

            self.assertFalse(result.image.isNull())
            self.assertEqual(result.missing_paths, [])
            self.assertFalse(result.text_overflow)

    def test_excess_profile_fields_report_overflow(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            source = self._make_photo(directory, "many-fields.png", "#a7c957")
            document = EditorialDocument(
                photos=[EditorialPhoto(source)],
                profile_fields=[
                    EditorialProfileField(f"項目{index}", f"値{index}")
                    for index in range(10)
                ],
                template_id=PROFILE_FEATURE_TEMPLATE_ID,
            )

            result = PhotoEditorialRenderer().render(document, QSize(310, 439))

            self.assertTrue(result.text_overflow)

    def test_editor_window_accepts_selected_image(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            source = self._make_photo(directory, "window-source.png", "#588157")
            window = PhotoEditorialWindow(
                [ImageFile(path=source, root=directory)],
                {},
            )

            self.assertEqual(len(window.document.photos), 1)
            self.assertEqual(window.document.photos[0].source_path, source)
            self.assertFalse(window.preview._image.isNull())
            window.title_edit.setText("保持するタイトル")
            profile_index = window.format_combo.findData(PROFILE_FEATURE_TEMPLATE_ID)
            window.format_combo.setCurrentIndex(profile_index)
            for label, value in (("生年月日", "2018年"), ("性別", "メス")):
                window._add_profile_field()
                row = window.profile_table.rowCount() - 1
                window.profile_table.item(row, 0).setText(label)
                window.profile_table.item(row, 1).setText(value)
            window._move_profile_field(-1)
            self.assertEqual(window.document.profile_fields[0].label, "性別")
            window._add_section()
            window.section_heading_edit.setText("最近の様子")
            window.section_body_edit.setPlainText("撮影時のエピソード")
            window._move_section(-1)
            self.assertEqual(window.document.sections[0].heading, "最近の様子")
            magazine_index = window.format_combo.findData(MAGAZINE_FEATURE_TEMPLATE_ID)
            window.format_combo.setCurrentIndex(magazine_index)
            window.format_combo.setCurrentIndex(profile_index)
            window._sync_document_text()
            self.assertEqual(window.document.template_id, PROFILE_FEATURE_TEMPLATE_ID)
            self.assertEqual(window.document.title, "保持するタイトル")
            self.assertEqual(len(window.document.profile_fields), 2)
            self.assertEqual(len(window.document.sections), 2)
            window._copy_to_clipboard()
            self.assertEqual(
                QApplication.clipboard().image().size(), QSize(PAGE_WIDTH, PAGE_HEIGHT)
            )
            window.close()

    def test_photo_main_role_and_order_follow_the_photo(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            paths = [
                self._make_photo(directory, f"order-{index}.png", "#386641")
                for index in range(3)
            ]
            document = EditorialDocument(
                photos=[
                    EditorialPhoto(path, caption=f"caption-{index}")
                    for index, path in enumerate(paths)
                ]
            )

            document.set_hero_photo(2)
            moved_index = document.move_photo(0, 1)

            self.assertEqual(moved_index, 1)
            self.assertEqual(document.photos[1].source_path, paths[2])
            self.assertEqual(document.photos[1].caption, "caption-2")
            self.assertEqual(document.photos[0].role, "hero")


if __name__ == "__main__":
    unittest.main()
