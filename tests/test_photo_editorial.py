from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSize, Qt
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
    NEWSPAPER_MOSAIC_TEMPLATE_ID,
    PROFILE_BANNER_TEMPLATE_ID,
    PROFILE_FEATURE_TEMPLATE_ID,
)
from src.photo_editorial_crop_dialog import CropPreviewWidget
from src.photo_editorial_layout import (
    FORMAT_MAGAZINE,
    FORMAT_NEWSPAPER,
    FORMAT_PHOTO_ESSAY,
    FORMAT_PROFILE,
    layouts_for_format,
    max_photos_for_template,
    select_layout,
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

    def test_all_eight_templates_render_the_same_document(self) -> None:
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

    def test_each_format_has_two_distinct_layouts(self) -> None:
        for format_id in (
            FORMAT_MAGAZINE,
            FORMAT_NEWSPAPER,
            FORMAT_PHOTO_ESSAY,
            FORMAT_PROFILE,
        ):
            with self.subTest(format_id=format_id):
                layouts = layouts_for_format(format_id)
                expected_count = 3 if format_id == FORMAT_NEWSPAPER else 2
                self.assertEqual(len(layouts), expected_count)
                self.assertEqual(
                    len({layout.template_id for layout in layouts}), expected_count
                )
        self.assertEqual(max_photos_for_template(PROFILE_FEATURE_TEMPLATE_ID), 5)
        self.assertEqual(max_photos_for_template(PROFILE_BANNER_TEMPLATE_ID), 7)

    def test_layout_selection_is_reproducible_and_can_exclude_current(self) -> None:
        selected = select_layout(
            FORMAT_MAGAZINE,
            photo_count=3,
            text_length=240,
            hero_aspect=1.5,
            seed=17,
        )
        repeated = select_layout(
            FORMAT_MAGAZINE,
            photo_count=3,
            text_length=240,
            hero_aspect=1.5,
            seed=17,
        )
        alternative = select_layout(
            FORMAT_MAGAZINE,
            photo_count=3,
            text_length=240,
            hero_aspect=1.5,
            seed=18,
            exclude_template_id=selected,
        )

        self.assertEqual(selected, repeated)
        self.assertNotEqual(selected, alternative)

    def test_long_japanese_title_renders_in_all_layouts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            source = self._make_photo(directory, "long-title.png", "#315b52")
            document = EditorialDocument(
                photos=[EditorialPhoto(source)],
                title="静かな森で暮らす動物たちの知られざる一日を写真でたどる特別な物語",
            )
            renderer = PhotoEditorialRenderer()

            for template_id in EDITORIAL_TEMPLATE_IDS:
                with self.subTest(template_id=template_id):
                    document.template_id = template_id
                    result = renderer.render(document, QSize(310, 439))
                    self.assertFalse(result.image.isNull())
                    self.assertFalse(result.text_overflow)

    def test_profile_layouts_accept_eight_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            source = self._make_photo(directory, "profile-eight.png", "#9a6b45")
            document = EditorialDocument(
                photos=[EditorialPhoto(source)],
                title="プロフィール",
                profile_fields=[
                    EditorialProfileField(f"項目{index + 1}", f"値{index + 1}")
                    for index in range(8)
                ],
                sections=[
                    EditorialSection("紹介", "プロフィールを紹介する文章です。"),
                    EditorialSection("最近の様子", "最近のエピソードを紹介します。"),
                ],
            )
            for template_id in (PROFILE_FEATURE_TEMPLATE_ID, PROFILE_BANNER_TEMPLATE_ID):
                with self.subTest(template_id=template_id):
                    document.template_id = template_id
                    result = PhotoEditorialRenderer().render(document, QSize(310, 439))
                    self.assertFalse(result.image.isNull())
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
            overflow_field = document.profile_fields[-1]
            self.assertIn(f"profile_value:{overflow_field.id}", result.overflow_fields)

    def test_profile_banner_fills_two_by_three_supporting_grid(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            source = self._make_photo(directory, "seven-profile.png", "#52796f")
            document = EditorialDocument(
                photos=[EditorialPhoto(source) for _index in range(7)],
                title="七枚のプロフィール",
                template_id=PROFILE_BANNER_TEMPLATE_ID,
            )

            result = PhotoEditorialRenderer().render(document, QSize(310, 439))

            self.assertFalse(result.image.isNull())
            self.assertEqual(result.missing_paths, [])

    def test_newspaper_mosaic_places_five_photos(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            source = self._make_photo(directory, "newspaper-mosaic.png", "#457b9d")
            document = EditorialDocument(
                photos=[EditorialPhoto(source) for _index in range(5)],
                title="交互配置の記事",
                subtitle="穏やかな午後の記録",
                sections=[
                    EditorialSection("右上の記事", "最初の記事本文です。"),
                    EditorialSection("左下の記事", "写真の後へ続く本文です。"),
                ],
                template_id=NEWSPAPER_MOSAIC_TEMPLATE_ID,
            )

            result = PhotoEditorialRenderer().render(document, QSize(310, 439))

            self.assertFalse(result.image.isNull())
            self.assertFalse(result.text_overflow)

    def test_editor_window_accepts_selected_image(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            source = self._make_photo(directory, "window-source.png", "#588157")
            window = PhotoEditorialWindow(
                [ImageFile(path=source, root=directory)],
                {},
                editor_font_size=14,
            )

            self.assertEqual(len(window.document.photos), 1)
            self.assertEqual(window.font().pointSize(), 14)
            self.assertEqual(window.title_edit.font().pointSize(), 14)
            self.assertEqual(window.document.photos[0].source_path, source)
            self.assertFalse(window.preview._image.isNull())
            window.header_text_edit.setText("カスタム特集")
            window.layout_combo.setCurrentIndex(1)
            self.assertNotEqual(window.header_text_edit.text(), "カスタム特集")
            window.layout_combo.setCurrentIndex(0)
            self.assertEqual(window.header_text_edit.text(), "カスタム特集")
            window.title_font_combo.setCurrentIndex(
                min(1, window.title_font_combo.count() - 1)
            )
            selected_title_font = window.title_font_combo.currentFont().family()
            window._sync_document_text()
            self.assertEqual(window.document.title_font_family, selected_title_font)
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
            previous_template = window.document.template_id
            previous_title = window.title_edit.text()
            window._choose_another_layout()
            self.assertNotEqual(window.document.template_id, previous_template)
            self.assertEqual(window.title_edit.text(), previous_title)
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

    def test_excluded_candidate_is_not_rendered(self) -> None:
        active = EditorialPhoto(Path("active-missing.png"))
        excluded = EditorialPhoto(Path("excluded-missing.png"), included=False)
        document = EditorialDocument(photos=[active, excluded])

        result = PhotoEditorialRenderer().render(document, QSize(310, 439))

        self.assertEqual(result.missing_paths, [active.source_path])
        self.assertEqual(excluded.role, "excluded")

    def test_crop_rectangle_changes_the_rendered_photo_area(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            source = directory / "split.png"
            image = QImage(800, 400, QImage.Format.Format_RGB32)
            image.fill(QColor("#cc2222"))
            for y in range(image.height()):
                for x in range(image.width() // 2, image.width()):
                    image.setPixelColor(x, y, QColor("#2255cc"))
            self.assertTrue(image.save(str(source), "PNG"))
            document = EditorialDocument(
                photos=[
                    EditorialPhoto(
                        source,
                        crop_x=0.5,
                        crop_y=0.0,
                        crop_width=0.5,
                        crop_height=1.0,
                    )
                ]
            )

            result = PhotoEditorialRenderer().render(document, QSize(310, 439))
            hero_center = result.image.pixelColor(110, 145)

            self.assertGreater(hero_center.blue(), hero_center.red())

    def test_document_json_data_round_trip(self) -> None:
        document = EditorialDocument(
            photos=[
                EditorialPhoto(
                    Path("候補写真.png"),
                    caption="キャプション",
                    included=False,
                    crop_x=0.2,
                    crop_y=0.1,
                    crop_width=0.6,
                    crop_height=0.7,
                )
            ],
            title="保存する記事",
            sections=[EditorialSection("見出し", "本文")],
            profile_fields=[EditorialProfileField("所属", "動物園")],
            layout_seed=42,
            font_family="Yu Mincho",
            title_font_family="Noto Serif JP",
            body_font_family="Yu Mincho",
            accent_font_family="BIZ UDGothic",
            publication_title="みどりの森新聞",
        )
        document.layout_photo_ids = {"saved-layout": [document.photos[0].id]}
        document.layout_text_overrides = {
            MAGAZINE_FEATURE_TEMPLATE_ID: {
                "header": "森の特集",
                "footer": "編集部",
            }
        }

        restored = EditorialDocument.from_dict(document.to_dict())

        self.assertEqual(restored.title, document.title)
        self.assertEqual(restored.layout_seed, 42)
        self.assertEqual(restored.font_family, "Yu Mincho")
        self.assertEqual(restored.title_font_family, "Noto Serif JP")
        self.assertEqual(restored.body_font_family, "Yu Mincho")
        self.assertEqual(restored.accent_font_family, "BIZ UDGothic")
        self.assertEqual(restored.publication_title, "みどりの森新聞")
        self.assertEqual(
            restored.layout_photo_ids["saved-layout"], [restored.photos[0].id]
        )
        self.assertEqual(
            restored.layout_text_overrides[MAGAZINE_FEATURE_TEMPLATE_ID]["header"],
            "森の特集",
        )
        self.assertEqual(restored.sections[0].heading, "見出し")
        self.assertEqual(restored.profile_fields[0].value, "動物園")
        self.assertFalse(restored.photos[0].included)
        self.assertAlmostEqual(restored.photos[0].crop_x, 0.2)
        self.assertAlmostEqual(restored.photos[0].crop_width, 0.6)

    def test_each_layout_restores_its_own_photo_selection(self) -> None:
        photos = [
            EditorialPhoto(Path(f"candidate-{index}.png"), included=index < 5)
            for index in range(9)
        ]
        document = EditorialDocument(
            photos=photos,
            template_id=PROFILE_FEATURE_TEMPLATE_ID,
        )
        document.save_layout_photo_selection()
        portrait_ids = [photo.id for photo in document.included_photos()]

        document.template_id = PROFILE_BANNER_TEMPLATE_ID
        document.restore_layout_photo_selection(PROFILE_BANNER_TEMPLATE_ID, 7)
        document.set_photo_included(5, True)
        document.set_photo_included(6, True)
        document.save_layout_photo_selection()
        banner_ids = [photo.id for photo in document.included_photos()]
        document.template_id = PROFILE_FEATURE_TEMPLATE_ID
        document.restore_layout_photo_selection(PROFILE_FEATURE_TEMPLATE_ID, 5)

        self.assertEqual([photo.id for photo in document.included_photos()], portrait_ids)
        document.template_id = PROFILE_BANNER_TEMPLATE_ID
        document.restore_layout_photo_selection(PROFILE_BANNER_TEMPLATE_ID, 7)
        self.assertEqual([photo.id for photo in document.included_photos()], banner_ids)

    def test_crop_preview_supports_four_times_zoom(self) -> None:
        image = QImage(800, 400, QImage.Format.Format_RGB32)
        preview = CropPreviewWidget(image, 1.0)

        preview.set_crop(0.75, 0.5, 4.0)
        crop = preview.crop_rect()

        self.assertAlmostEqual(crop.width(), 0.125)
        self.assertAlmostEqual(crop.height(), 0.25)
        self.assertAlmostEqual(crop.x() + crop.width() / 2.0, 0.75)

    def test_editor_uses_extra_selected_images_as_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            paths = [
                self._make_photo(directory, f"candidate-{index}.png", "#52796f")
                for index in range(25)
            ]
            window = PhotoEditorialWindow(
                [ImageFile(path=path, root=directory) for path in paths], {}
            )

            self.assertEqual(len(window.document.photos), 25)
            self.assertEqual(len(window.document.included_photos()), 6)
            self.assertEqual(window.photo_list.item(0).text(), "")
            window.photo_list.item(0).setCheckState(Qt.CheckState.Unchecked)
            window.photo_list.item(6).setCheckState(Qt.CheckState.Checked)
            self.assertEqual(len(window.document.included_photos()), 6)
            self.assertTrue(window.document.photos[6].included)
            excluded_path = window.document.photos[7].source_path
            window.photo_list.setCurrentRow(7)
            window._set_selected_photo_as_hero()
            self.assertEqual(len(window.document.included_photos()), 6)
            self.assertEqual(window.document.photos[0].source_path, excluded_path)
            window._apply_overflow_warnings({"title"})
            self.assertIn("#dc2626", window.title_edit.styleSheet())
            window.close()


if __name__ == "__main__":
    unittest.main()
