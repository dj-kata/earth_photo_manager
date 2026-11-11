from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, field
import math
from pathlib import Path

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QImage,
    QImageReader,
    QPainter,
    QPen,
    QTextBlockFormat,
    QTextCharFormat,
    QTextCursor,
    QTextDocument,
    QTextOption,
)

from src.photo_editorial_model import (
    EditorialDocument,
    EditorialPhoto,
    MAGAZINE_FEATURE_TEMPLATE_ID,
    NEWSPAPER_ARTICLE_TEMPLATE_ID,
    PHOTO_ESSAY_TEMPLATE_ID,
    PROFILE_FEATURE_TEMPLATE_ID,
)


PAGE_WIDTH = 2480
PAGE_HEIGHT = 3508
PAGE_SIZE = QSize(PAGE_WIDTH, PAGE_HEIGHT)
OUTPUT_DOTS_PER_METER = round(300 / 0.0254)
PREVIEW_WIDTH = 820
PREVIEW_HEIGHT = round(PREVIEW_WIDTH * PAGE_HEIGHT / PAGE_WIDTH)


@dataclass(frozen=True)
class MagazineFeatureTemplate:
    page_size: QSize = field(default_factory=lambda: QSize(PAGE_SIZE))
    header_rect: QRectF = field(
        default_factory=lambda: QRectF(140.0, 110.0, 2200.0, 90.0)
    )
    title_rect: QRectF = field(
        default_factory=lambda: QRectF(140.0, 245.0, 2200.0, 290.0)
    )
    hero_rect: QRectF = field(
        default_factory=lambda: QRectF(140.0, 590.0, 1500.0, 1120.0)
    )
    hero_caption_rect: QRectF = field(
        default_factory=lambda: QRectF(140.0, 1725.0, 1500.0, 90.0)
    )
    body_rect: QRectF = field(
        default_factory=lambda: QRectF(140.0, 1870.0, 1500.0, 1450.0)
    )
    supporting_rect: QRectF = field(
        default_factory=lambda: QRectF(1710.0, 590.0, 630.0, 2500.0)
    )


MAGAZINE_FEATURE_TEMPLATE = MagazineFeatureTemplate()


@dataclass
class EditorialRenderResult:
    image: QImage
    missing_paths: list[Path]
    text_overflow: bool = False


class PhotoEditorialRenderer:
    def __init__(self) -> None:
        self._image_cache: OrderedDict[tuple[str, int, int], QImage] = OrderedDict()

    def render(
        self,
        document: EditorialDocument,
        output_size: QSize | None = None,
    ) -> EditorialRenderResult:
        document.validate()
        size = output_size or PAGE_SIZE
        if size.width() <= 0 or size.height() <= 0:
            raise ValueError("output size must be positive")

        image = QImage(size, QImage.Format.Format_ARGB32_Premultiplied)
        if size == PAGE_SIZE:
            image.setDotsPerMeterX(OUTPUT_DOTS_PER_METER)
            image.setDotsPerMeterY(OUTPUT_DOTS_PER_METER)
        image.fill(QColor("#ffffff"))
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        painter.scale(size.width() / PAGE_WIDTH, size.height() / PAGE_HEIGHT)

        try:
            draw_template = {
                MAGAZINE_FEATURE_TEMPLATE_ID: self._draw_magazine,
                NEWSPAPER_ARTICLE_TEMPLATE_ID: self._draw_newspaper,
                PHOTO_ESSAY_TEMPLATE_ID: self._draw_photo_essay,
                PROFILE_FEATURE_TEMPLATE_ID: self._draw_profile,
            }[document.template_id]
            missing_paths, text_overflow = draw_template(painter, document)
        finally:
            painter.end()
        return EditorialRenderResult(image, missing_paths, text_overflow)

    def _draw_magazine(
        self, painter: QPainter, document: EditorialDocument
    ) -> tuple[list[Path], bool]:
        template = MAGAZINE_FEATURE_TEMPLATE
        painter.fillRect(QRectF(0.0, 0.0, PAGE_WIDTH, PAGE_HEIGHT), QColor("#f8f5ee"))
        painter.fillRect(QRectF(0.0, 0.0, PAGE_WIDTH, 26.0), QColor("#b45309"))
        overflow = self._draw_text(
            painter,
            self._header_text("EARTH PHOTO JOURNAL  /  FEATURE", document),
            template.header_rect,
            point_size=26,
            weight=QFont.Weight.DemiBold,
            color="#92400e",
            letter_spacing=2.0,
        )
        painter.setPen(QPen(QColor("#b45309"), 3.0))
        painter.drawLine(140.0, 215.0, 2340.0, 215.0)
        overflow |= self._draw_text(
            painter,
            document.title,
            QRectF(template.title_rect.x(), template.title_rect.y(), 2200.0, 190.0),
            point_size=86,
            weight=QFont.Weight.Bold,
            color="#1f2937",
            line_height=1.05,
        )
        overflow |= self._draw_text(
            painter,
            document.subtitle,
            QRectF(140.0, 445.0, 2200.0, 90.0),
            point_size=36,
            color="#6b4f3a",
        )

        missing_paths: list[Path] = []
        hero = document.photos[0]
        if not self._draw_photo(painter, hero, template.hero_rect):
            missing_paths.append(hero.source_path)
        overflow |= self._draw_text(
            painter,
            hero.caption,
            template.hero_caption_rect,
            point_size=28,
            color="#4b5563",
        )
        body_y = template.body_rect.y()
        if document.lead:
            overflow |= self._draw_text(
                painter,
                document.lead,
                QRectF(140.0, body_y, 1500.0, 190.0),
                point_size=38,
                weight=QFont.Weight.DemiBold,
                color="#374151",
                line_height=1.35,
            )
            body_y += 220.0
        if document.pull_quote:
            overflow |= self._draw_quote(
                painter, document.pull_quote, QRectF(140.0, body_y, 1500.0, 160.0), "#b45309"
            )
            body_y += 185.0
        overflow |= self._draw_sections(
            painter,
            document,
            QRectF(140.0, body_y, 1500.0, 3320.0 - body_y),
            heading_size=34.0,
            body_size=31.0,
            color="#1f2937",
        )
        grid_missing, grid_overflow = self._draw_photo_grid(
            painter,
            document.photos[1:],
            template.supporting_rect,
            columns=1,
            gap=34.0,
            caption_height=74.0,
            caption_size=23.0,
        )
        missing_paths.extend(grid_missing)
        overflow |= grid_overflow
        self._draw_footer(painter, "EARTH PHOTO MANAGER", "#9ca3af")
        return missing_paths, overflow

    def _draw_newspaper(
        self, painter: QPainter, document: EditorialDocument
    ) -> tuple[list[Path], bool]:
        painter.fillRect(QRectF(0.0, 0.0, PAGE_WIDTH, PAGE_HEIGHT), QColor("#f3f0e8"))
        painter.setPen(QPen(QColor("#202020"), 5.0))
        painter.drawLine(120.0, 245.0, 2360.0, 245.0)
        painter.drawLine(120.0, 265.0, 2360.0, 265.0)
        overflow = self._draw_text(
            painter,
            "THE EARTH OBSERVER",
            QRectF(120.0, 70.0, 2240.0, 150.0),
            point_size=62,
            weight=QFont.Weight.Bold,
            color="#181818",
            alignment=Qt.AlignmentFlag.AlignCenter,
            letter_spacing=3.0,
        )
        overflow |= self._draw_text(
            painter,
            document.title,
            QRectF(120.0, 340.0, 2240.0, 270.0),
            point_size=78,
            weight=QFont.Weight.Bold,
            color="#111111",
            line_height=1.05,
        )
        overflow |= self._draw_text(
            painter,
            self._metadata_text(document),
            QRectF(120.0, 285.0, 2240.0, 50.0),
            point_size=21,
            color="#444444",
            alignment=Qt.AlignmentFlag.AlignRight,
        )
        overflow |= self._draw_text(
            painter,
            document.subtitle,
            QRectF(120.0, 620.0, 2240.0, 80.0),
            point_size=31,
            color="#333333",
        )

        missing_paths: list[Path] = []
        hero = document.photos[0]
        hero_rect = QRectF(120.0, 730.0, 1120.0, 1030.0)
        if not self._draw_photo(painter, hero, hero_rect):
            missing_paths.append(hero.source_path)
        overflow |= self._draw_text(
            painter,
            hero.caption,
            QRectF(120.0, 1775.0, 1120.0, 85.0),
            point_size=24,
            color="#333333",
        )
        painter.setPen(QPen(QColor("#5f5f5f"), 2.0))
        painter.drawLine(1290.0, 730.0, 1290.0, 1850.0)
        article_y = 730.0
        if document.lead:
            overflow |= self._draw_text(
                painter,
                document.lead,
                QRectF(1350.0, article_y, 1010.0, 210.0),
                point_size=33,
                weight=QFont.Weight.DemiBold,
                color="#181818",
                line_height=1.35,
            )
            article_y += 235.0
        overflow |= self._draw_sections(
            painter,
            document,
            QRectF(1350.0, article_y, 1010.0, 1855.0 - article_y),
            heading_size=29.0,
            body_size=27.0,
            color="#181818",
        )
        painter.setPen(QPen(QColor("#202020"), 3.0))
        painter.drawLine(120.0, 1920.0, 2360.0, 1920.0)
        grid_missing, grid_overflow = self._draw_photo_grid(
            painter,
            document.photos[1:],
            QRectF(120.0, 1990.0, 2240.0, 1290.0),
            columns=3,
            gap=38.0,
            caption_height=84.0,
            caption_size=23.0,
        )
        missing_paths.extend(grid_missing)
        overflow |= grid_overflow
        self._draw_footer(painter, "THE EARTH OBSERVER  •  PHOTO EDITION", "#444444")
        return missing_paths, overflow

    def _draw_photo_essay(
        self, painter: QPainter, document: EditorialDocument
    ) -> tuple[list[Path], bool]:
        painter.fillRect(QRectF(0.0, 0.0, PAGE_WIDTH, PAGE_HEIGHT), QColor("#fcfcfa"))
        overflow = self._draw_text(
            painter,
            self._header_text("PHOTO ESSAY", document),
            QRectF(150.0, 95.0, 2180.0, 70.0),
            point_size=22,
            weight=QFont.Weight.DemiBold,
            color="#6b7280",
            letter_spacing=5.0,
        )
        overflow |= self._draw_text(
            painter,
            document.title,
            QRectF(150.0, 205.0, 2180.0, 190.0),
            point_size=76,
            weight=QFont.Weight.Light,
            color="#111827",
            line_height=1.05,
        )
        overflow |= self._draw_text(
            painter,
            document.subtitle,
            QRectF(150.0, 405.0, 2180.0, 80.0),
            point_size=31,
            color="#374151",
        )
        overflow |= self._draw_text(
            painter,
            document.lead,
            QRectF(150.0, 500.0, 2180.0, 190.0),
            point_size=28,
            color="#4b5563",
            line_height=1.4,
        )

        missing_paths: list[Path] = []
        hero = document.photos[0]
        hero_rect = QRectF(150.0, 720.0, 2180.0, 1320.0)
        if not self._draw_photo(painter, hero, hero_rect):
            missing_paths.append(hero.source_path)
        overflow |= self._draw_text(
            painter,
            hero.caption,
            QRectF(150.0, 2060.0, 2180.0, 80.0),
            point_size=24,
            color="#6b7280",
            alignment=Qt.AlignmentFlag.AlignRight,
        )
        grid_missing, grid_overflow = self._draw_photo_grid(
            painter,
            document.photos[1:],
            QRectF(150.0, 2170.0, 2180.0, 620.0),
            columns=3,
            gap=44.0,
            caption_height=72.0,
            caption_size=21.0,
        )
        missing_paths.extend(grid_missing)
        overflow |= grid_overflow
        section_y = 2840.0
        if document.pull_quote:
            overflow |= self._draw_quote(
                painter,
                document.pull_quote,
                QRectF(150.0, section_y, 2180.0, 130.0),
                "#6b7280",
            )
            section_y += 150.0
        overflow |= self._draw_sections(
            painter,
            document,
            QRectF(150.0, section_y, 2180.0, 3315.0 - section_y),
            heading_size=26.0,
            body_size=23.0,
            color="#374151",
            columns=2,
        )
        self._draw_footer(painter, "EARTH PHOTO ESSAY", "#c1c5cb")
        return missing_paths, overflow

    def _draw_profile(
        self, painter: QPainter, document: EditorialDocument
    ) -> tuple[list[Path], bool]:
        painter.fillRect(QRectF(0.0, 0.0, PAGE_WIDTH, PAGE_HEIGHT), QColor("#eee5d8"))
        painter.fillRect(QRectF(0.0, 0.0, 78.0, PAGE_HEIGHT), QColor("#315b52"))
        overflow = self._draw_text(
            painter,
            self._header_text("PORTRAIT  /  PROFILE", document),
            QRectF(150.0, 100.0, 2180.0, 80.0),
            point_size=25,
            weight=QFont.Weight.DemiBold,
            color="#315b52",
            letter_spacing=3.0,
        )
        overflow |= self._draw_text(
            painter,
            document.title,
            QRectF(1210.0, 270.0, 1120.0, 230.0),
            point_size=76,
            weight=QFont.Weight.Bold,
            color="#17332d",
            line_height=1.05,
        )
        overflow |= self._draw_text(
            painter,
            document.subtitle,
            QRectF(1210.0, 515.0, 1120.0, 110.0),
            point_size=32,
            color="#52635f",
        )

        missing_paths: list[Path] = []
        hero = document.photos[0]
        hero_rect = QRectF(150.0, 300.0, 960.0, 2050.0)
        if not self._draw_photo(painter, hero, hero_rect):
            missing_paths.append(hero.source_path)
        overflow |= self._draw_text(
            painter,
            hero.caption,
            QRectF(150.0, 2370.0, 960.0, 100.0),
            point_size=25,
            color="#52635f",
        )
        painter.fillRect(QRectF(1210.0, 650.0, 1120.0, 8.0), QColor("#c27649"))
        content_y = 700.0
        profile_height, profile_overflow = self._draw_profile_fields(
            painter,
            document,
            QRectF(1210.0, content_y, 1120.0, 650.0),
        )
        overflow |= profile_overflow
        content_y += profile_height
        if document.lead:
            overflow |= self._draw_text(
                painter,
                document.lead,
                QRectF(1210.0, content_y, 1120.0, 190.0),
                point_size=31,
                weight=QFont.Weight.DemiBold,
                color="#263c37",
                line_height=1.35,
            )
            content_y += 215.0
        if document.pull_quote:
            overflow |= self._draw_quote(
                painter,
                document.pull_quote,
                QRectF(1210.0, content_y, 1120.0, 145.0),
                "#c27649",
            )
            content_y += 170.0
        overflow |= self._draw_sections(
            painter,
            document,
            QRectF(1210.0, content_y, 1120.0, max(100.0, 1840.0 - content_y)),
            heading_size=29.0,
            body_size=25.0,
            color="#263c37",
        )
        grid_missing, grid_overflow = self._draw_photo_grid(
            painter,
            document.photos[1:],
            QRectF(1210.0, 1860.0, 1120.0, 1190.0),
            columns=2,
            gap=34.0,
            caption_height=68.0,
            caption_size=20.0,
        )
        missing_paths.extend(grid_missing)
        overflow |= grid_overflow
        self._draw_footer(painter, "EARTH PHOTO  •  PROFILE", "#71847f")
        return missing_paths, overflow

    def _header_text(self, base: str, document: EditorialDocument) -> str:
        metadata = self._metadata_text(document)
        return f"{base}  /  {metadata}" if metadata else base

    @staticmethod
    def _metadata_text(document: EditorialDocument) -> str:
        return "  /  ".join(
            value.strip()
            for value in (
                document.metadata.category,
                document.metadata.date,
                document.metadata.author,
            )
            if value.strip()
        )

    def _draw_profile_fields(
        self,
        painter: QPainter,
        document: EditorialDocument,
        rect: QRectF,
    ) -> tuple[float, bool]:
        fields = [
            profile_field
            for profile_field in document.profile_fields
            if profile_field.label.strip() or profile_field.value.strip()
        ]
        if not fields:
            return 0.0, False
        row_height = 88.0
        needed_height = row_height * len(fields)
        available_rows = max(0, int(rect.height() // row_height))
        overflow = len(fields) > available_rows
        label_width = rect.width() * 0.34
        for index, profile_field in enumerate(fields[:available_rows]):
            y = rect.y() + index * row_height
            label_rect = QRectF(rect.x(), y, label_width, row_height - 5.0)
            value_rect = QRectF(
                label_rect.right(), y, rect.width() - label_width, row_height - 5.0
            )
            painter.fillRect(label_rect, QColor("#315b52"))
            painter.fillRect(value_rect, QColor("#f7f2ea"))
            overflow |= self._draw_text(
                painter,
                profile_field.label,
                label_rect.adjusted(18.0, 12.0, -12.0, -8.0),
                point_size=23,
                weight=QFont.Weight.DemiBold,
                color="#ffffff",
            )
            overflow |= self._draw_text(
                painter,
                profile_field.value,
                value_rect.adjusted(20.0, 12.0, -12.0, -8.0),
                point_size=24,
                color="#263c37",
            )
        used_height = min(needed_height, rect.height()) + 28.0
        return used_height, overflow

    def _draw_sections(
        self,
        painter: QPainter,
        document: EditorialDocument,
        rect: QRectF,
        *,
        heading_size: float,
        body_size: float,
        color: str,
        columns: int = 1,
    ) -> bool:
        sections = [
            section
            for section in document.effective_sections()
            if section.heading.strip() or section.body.strip()
        ]
        if not sections:
            return False
        columns = max(1, min(columns, len(sections)))
        rows = math.ceil(len(sections) / columns)
        gap_x = 55.0 if columns > 1 else 0.0
        gap_y = 32.0
        cell_width = (rect.width() - gap_x * (columns - 1)) / columns
        cell_height = (rect.height() - gap_y * (rows - 1)) / rows
        if cell_height <= 0:
            return True
        overflow = False
        for index, section in enumerate(sections):
            row, column = divmod(index, columns)
            x = rect.x() + column * (cell_width + gap_x)
            y = rect.y() + row * (cell_height + gap_y)
            heading_height = max(65.0, heading_size * 2.25) if section.heading else 0.0
            if section.heading:
                overflow |= self._draw_text(
                    painter,
                    section.heading,
                    QRectF(x, y, cell_width, heading_height),
                    point_size=heading_size,
                    weight=QFont.Weight.Bold,
                    color=color,
                    line_height=1.1,
                )
                painter.setPen(QPen(QColor(color), 2.0))
                painter.drawLine(x, y + heading_height - 7.0, x + cell_width, y + heading_height - 7.0)
            body_height = cell_height - heading_height
            if body_height <= 0 and section.body:
                overflow = True
                continue
            overflow |= self._draw_text(
                painter,
                section.body,
                QRectF(x, y + heading_height + 10.0, cell_width, max(0.0, body_height - 10.0)),
                point_size=body_size,
                color=color,
                line_height=1.45,
            )
        return overflow

    def _draw_quote(
        self,
        painter: QPainter,
        text: str,
        rect: QRectF,
        accent_color: str,
    ) -> bool:
        if not text:
            return False
        painter.fillRect(QRectF(rect.x(), rect.y(), 8.0, rect.height()), QColor(accent_color))
        return self._draw_text(
            painter,
            f"“ {text} ”",
            rect.adjusted(30.0, 8.0, -10.0, -8.0),
            point_size=30,
            weight=QFont.Weight.DemiBold,
            color=accent_color,
            line_height=1.2,
        )

    def _draw_photo_grid(
        self,
        painter: QPainter,
        photos: list[EditorialPhoto],
        container: QRectF,
        *,
        columns: int,
        gap: float,
        caption_height: float,
        caption_size: float,
    ) -> tuple[list[Path], bool]:
        if not photos:
            return [], False
        columns = max(1, min(columns, len(photos)))
        rows = math.ceil(len(photos) / columns)
        cell_width = (container.width() - gap * (columns - 1)) / columns
        cell_height = (container.height() - gap * (rows - 1)) / rows
        photo_height = max(90.0, cell_height - caption_height)
        missing_paths: list[Path] = []
        overflow = False
        for index, photo in enumerate(photos):
            row, column = divmod(index, columns)
            x = container.x() + column * (cell_width + gap)
            y = container.y() + row * (cell_height + gap)
            photo_rect = QRectF(x, y, cell_width, photo_height)
            caption_rect = QRectF(
                x, photo_rect.bottom() + 9.0, cell_width, caption_height - 9.0
            )
            if not self._draw_photo(painter, photo, photo_rect):
                missing_paths.append(photo.source_path)
            overflow |= self._draw_text(
                painter,
                photo.caption,
                caption_rect,
                point_size=caption_size,
                color="#4b5563",
                line_height=1.15,
            )
        return missing_paths, overflow

    def _draw_footer(self, painter: QPainter, label: str, color: str) -> None:
        painter.setPen(QPen(QColor(color), 2.0))
        painter.drawLine(140.0, 3345.0, 2340.0, 3345.0)
        self._draw_text(
            painter,
            label,
            QRectF(140.0, 3360.0, 2200.0, 60.0),
            point_size=20,
            color=color,
            alignment=Qt.AlignmentFlag.AlignRight,
        )

    def _draw_photo(
        self, painter: QPainter, photo: EditorialPhoto, target_rect: QRectF
    ) -> bool:
        scale_x = painter.transform().m11()
        scale_y = painter.transform().m22()
        target_width = max(1, round(target_rect.width() * scale_x))
        target_height = max(1, round(target_rect.height() * scale_y))
        source = self._load_image(photo.source_path, target_width, target_height)
        if source.isNull():
            painter.fillRect(target_rect, QColor("#e5e7eb"))
            painter.setPen(QPen(QColor("#9ca3af"), 3.0))
            painter.drawRect(target_rect)
            self._draw_text(
                painter,
                photo.source_path.name,
                target_rect.adjusted(24.0, 24.0, -24.0, -24.0),
                point_size=24,
                color="#6b7280",
                alignment=Qt.AlignmentFlag.AlignCenter,
            )
            return False

        scaled = source.scaled(
            target_width,
            target_height,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        overflow_x = max(0, scaled.width() - target_width)
        overflow_y = max(0, scaled.height() - target_height)
        source_x = round(overflow_x * photo.focus_x)
        source_y = round(overflow_y * photo.focus_y)
        source_rect = QRectF(source_x, source_y, target_width, target_height)
        painter.drawImage(target_rect, scaled, source_rect)
        return True

    def _load_image(self, path: Path, width: int, height: int) -> QImage:
        key = (str(path), width, height)
        cached = self._image_cache.get(key)
        if cached is not None:
            self._image_cache.move_to_end(key)
            return cached

        reader = QImageReader(str(path))
        reader.setAutoTransform(True)
        source_size = reader.size()
        if source_size.isValid() and source_size.width() > 0 and source_size.height() > 0:
            requested = source_size.scaled(
                QSize(width, height), Qt.AspectRatioMode.KeepAspectRatioByExpanding
            )
            if (
                requested.width() < source_size.width()
                or requested.height() < source_size.height()
            ):
                reader.setScaledSize(requested)
        loaded = reader.read()
        self._image_cache[key] = loaded
        self._image_cache.move_to_end(key)
        while len(self._image_cache) > 32:
            self._image_cache.popitem(last=False)
        return loaded

    def _draw_text(
        self,
        painter: QPainter,
        text: str,
        rect: QRectF,
        *,
        point_size: float,
        weight: QFont.Weight = QFont.Weight.Normal,
        color: str = "#1f2937",
        line_height: float = 1.3,
        letter_spacing: float = 0.0,
        alignment: Qt.AlignmentFlag = Qt.AlignmentFlag.AlignLeft,
    ) -> bool:
        if not text:
            return False
        document = QTextDocument()
        document.setDocumentMargin(0.0)
        font = QFont()
        font.setPointSizeF(point_size)
        font.setWeight(weight)
        if letter_spacing:
            font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, letter_spacing)
        document.setDefaultFont(font)
        option = QTextOption()
        option.setWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        option.setAlignment(alignment)
        document.setDefaultTextOption(option)
        document.setPlainText(text)
        cursor = QTextCursor(document)
        cursor.select(QTextCursor.SelectionType.Document)
        block_format = QTextBlockFormat()
        block_format.setLineHeight(
            line_height * 100.0,
            QTextBlockFormat.LineHeightTypes.ProportionalHeight.value,
        )
        cursor.mergeBlockFormat(block_format)
        character_format = QTextCharFormat()
        character_format.setForeground(QColor(color))
        cursor.mergeCharFormat(character_format)
        document.setTextWidth(rect.width())
        overflow = document.size().height() > rect.height() + 0.5

        painter.save()
        painter.setClipRect(rect)
        painter.translate(rect.topLeft())
        document.drawContents(painter, QRectF(0.0, 0.0, rect.width(), rect.height()))
        painter.restore()
        return overflow
