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
                body="入力した文章を保持したままフォーマットを切り替えます。",
            )
            renderer = PhotoEditorialRenderer()

            for template_id in EDITORIAL_TEMPLATE_IDS:
                with self.subTest(template_id=template_id):
                    document.template_id = template_id
                    result = renderer.render(document, QSize(310, 439))
                    self.assertFalse(result.image.isNull())
                    self.assertEqual(result.missing_paths, [])

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
            window._sync_document_text()
            self.assertEqual(window.document.template_id, PROFILE_FEATURE_TEMPLATE_ID)
            self.assertEqual(window.document.title, "保持するタイトル")
            window._copy_to_clipboard()
            self.assertEqual(
                QApplication.clipboard().image().size(), QSize(PAGE_WIDTH, PAGE_HEIGHT)
            )
            window.close()


if __name__ == "__main__":
    unittest.main()
