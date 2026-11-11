from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, field, replace
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
    EditorialSection,
    MAGAZINE_FEATURE_TEMPLATE_ID,
    MAGAZINE_HERO_OVERLAY_TEMPLATE_ID,
    NEWSPAPER_ARTICLE_TEMPLATE_ID,
    NEWSPAPER_COLUMNS_TEMPLATE_ID,
    NEWSPAPER_MOSAIC_TEMPLATE_ID,
    PHOTO_ESSAY_ASYMMETRIC_TEMPLATE_ID,
    PHOTO_ESSAY_TEMPLATE_ID,
    PROFILE_BANNER_TEMPLATE_ID,
    PROFILE_FEATURE_TEMPLATE_ID,
)
from src.photo_editorial_layout import (
    TOKENS,
    default_layout_text,
    max_photos_for_template,
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
    overflow_fields: frozenset[str] = frozenset()


class PhotoEditorialRenderer:
    def __init__(self) -> None:
        self._image_cache: OrderedDict[tuple[str, int, int], QImage] = OrderedDict()

    def render(
        self,
        document: EditorialDocument,
        output_size: QSize | None = None,
    ) -> EditorialRenderResult:
        document.validate(max_photos_for_template(document.template_id))
        render_document = replace(document, photos=document.included_photos())
        self._title_font_family = document.title_font_family.strip()
        self._body_font_family = document.body_font_family.strip()
        self._accent_font_family = document.accent_font_family.strip()
        self._title_texts = {
            text for text in (document.title, document.subtitle, document.publication_title) if text
        }
        self._body_texts = {
            text
            for text in (
                document.lead,
                document.pull_quote,
                *(section.body for section in document.effective_sections()),
                *(field.value for field in document.profile_fields),
                *(photo.caption for photo in render_document.photos),
            )
            if text
        }
        self._accent_texts = {
            text
            for text in (
                *(section.heading for section in document.effective_sections()),
                *(field.label for field in document.profile_fields),
            )
            if text
        }
        self._overflow_fields: set[str] = set()
        self._text_field_keys = self._build_text_field_keys(render_document)
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
                MAGAZINE_HERO_OVERLAY_TEMPLATE_ID: self._draw_magazine_overlay,
                NEWSPAPER_ARTICLE_TEMPLATE_ID: self._draw_newspaper,
                NEWSPAPER_COLUMNS_TEMPLATE_ID: self._draw_newspaper_columns,
                NEWSPAPER_MOSAIC_TEMPLATE_ID: self._draw_newspaper_mosaic,
                PHOTO_ESSAY_TEMPLATE_ID: self._draw_photo_essay,
                PHOTO_ESSAY_ASYMMETRIC_TEMPLATE_ID: self._draw_photo_essay_asymmetric,
                PROFILE_FEATURE_TEMPLATE_ID: self._draw_profile,
                PROFILE_BANNER_TEMPLATE_ID: self._draw_profile_banner,
            }[render_document.template_id]
            missing_paths, text_overflow = draw_template(painter, render_document)
        finally:
            painter.end()
        return EditorialRenderResult(
            image, missing_paths, text_overflow, frozenset(self._overflow_fields)
        )

    @staticmethod
    def _build_text_field_keys(document: EditorialDocument) -> dict[str, set[str]]:
        fields: dict[str, set[str]] = {}

        def register(text: str, key: str) -> None:
            if text:
                fields.setdefault(text, set()).add(key)

        register(document.title, "title")
        register(document.subtitle, "subtitle")
        register(document.lead, "lead")
        register(document.pull_quote, "pull_quote")
        register(f"“ {document.pull_quote} ”", "pull_quote")
        register(document.publication_title, "publication_title")
        for section in document.effective_sections():
            register(section.heading, f"section_heading:{section.id}")
            register(section.body, f"section_body:{section.id}")
        for field in document.profile_fields:
            register(field.label, f"profile_label:{field.id}")
            register(field.value, f"profile_value:{field.id}")
        for photo in document.photos:
            register(photo.caption, f"caption:{photo.source_path}")
        return fields

    def _draw_magazine(
        self, painter: QPainter, document: EditorialDocument
    ) -> tuple[list[Path], bool]:
        template = MAGAZINE_FEATURE_TEMPLATE
        painter.fillRect(QRectF(0.0, 0.0, PAGE_WIDTH, PAGE_HEIGHT), QColor("#f8f5ee"))
        painter.fillRect(QRectF(0.0, 0.0, PAGE_WIDTH, 26.0), QColor("#b45309"))
        overflow = self._draw_text(
            painter,
            self._header_text(self._layout_text(document, "header"), document),
            template.header_rect,
            point_size=26,
            weight=QFont.Weight.DemiBold,
            color="#92400e",
            letter_spacing=2.0,
            font_role="accent",
            field_key="header_text",
        )
        painter.setPen(QPen(QColor("#b45309"), 3.0))
        painter.drawLine(140.0, 215.0, 2340.0, 215.0)
        overflow |= self._draw_fitted_text(
            painter,
            document.title,
            QRectF(template.title_rect.x(), template.title_rect.y(), 2200.0, 190.0),
            max_size=96.0,
            min_size=54.0,
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
        self._draw_footer(painter, self._layout_text(document, "footer"), "#9ca3af")
        return missing_paths, overflow

    def _draw_newspaper(
        self, painter: QPainter, document: EditorialDocument
    ) -> tuple[list[Path], bool]:
        painter.fillRect(QRectF(0.0, 0.0, PAGE_WIDTH, PAGE_HEIGHT), QColor("#f3f0e8"))
        painter.setPen(QPen(QColor("#202020"), 5.0))
        painter.drawLine(120.0, 225.0, 2360.0, 225.0)
        overflow = self._draw_fitted_text(
            painter,
            document.publication_title or "THE EARTH OBSERVER",
            QRectF(120.0, 62.0, 1580.0, 135.0),
            max_size=68.0,
            min_size=36.0,
            weight=QFont.Weight.Bold,
            color="#111111",
            alignment=Qt.AlignmentFlag.AlignCenter,
            families=TOKENS.serif_families,
        )
        overflow |= self._draw_text(
            painter,
            self._metadata_text(document),
            QRectF(1740.0, 78.0, 620.0, 100.0),
            point_size=21,
            weight=QFont.Weight.DemiBold,
            color="#222222",
            alignment=Qt.AlignmentFlag.AlignRight,
        )
        overflow |= self._draw_text(
            painter,
            self._layout_text(document, "header"),
            QRectF(120.0, 235.0, 2240.0, 65.0),
            point_size=20,
            weight=QFont.Weight.DemiBold,
            color="#555555",
            alignment=Qt.AlignmentFlag.AlignRight,
            font_role="accent",
            field_key="header_text",
        )
        painter.fillRect(QRectF(120.0, 305.0, 2240.0, 285.0), QColor("#151515"))
        overflow |= self._draw_fitted_text(
            painter,
            document.title,
            QRectF(165.0, 340.0, 2150.0, 215.0),
            max_size=94.0,
            min_size=54.0,
            weight=QFont.Weight.Bold,
            color="#ffffff",
            line_height=1.05,
            families=TOKENS.serif_families,
            alignment=Qt.AlignmentFlag.AlignCenter,
            vertical_center=True,
        )
        overflow |= self._draw_text(
            painter,
            document.subtitle,
            QRectF(120.0, 615.0, 2240.0, 95.0),
            point_size=34,
            weight=QFont.Weight.DemiBold,
            color="#222222",
            families=TOKENS.serif_families,
        )

        missing_paths: list[Path] = []
        hero = document.photos[0]
        hero_rect = QRectF(120.0, 740.0, 1120.0, 1020.0)
        if not self._draw_photo(painter, hero, hero_rect):
            missing_paths.append(hero.source_path)
        overflow |= self._draw_text(
            painter,
            hero.caption,
            QRectF(120.0, 1775.0, 1120.0, 75.0),
            point_size=24,
            color="#333333",
        )
        painter.setPen(QPen(QColor("#5f5f5f"), 2.0))
        painter.drawLine(1290.0, 740.0, 1290.0, 1850.0)
        article_y = 740.0
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
        self._draw_footer(
            painter,
            f"{document.publication_title or 'THE EARTH OBSERVER'}  •  {self._layout_text(document, 'footer')}",
            "#444444",
        )
        return missing_paths, overflow

    def _draw_photo_essay(
        self, painter: QPainter, document: EditorialDocument
    ) -> tuple[list[Path], bool]:
        painter.fillRect(QRectF(0.0, 0.0, PAGE_WIDTH, PAGE_HEIGHT), QColor("#fcfcfa"))
        overflow = self._draw_text(
            painter,
            self._header_text(self._layout_text(document, "header"), document),
            QRectF(150.0, 95.0, 2180.0, 70.0),
            point_size=22,
            weight=QFont.Weight.DemiBold,
            color="#6b7280",
            letter_spacing=5.0,
            font_role="accent",
            field_key="header_text",
        )
        overflow |= self._draw_fitted_text(
            painter,
            document.title,
            QRectF(150.0, 205.0, 2180.0, 190.0),
            max_size=92.0,
            min_size=52.0,
            weight=QFont.Weight.DemiBold,
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
        self._draw_footer(painter, self._layout_text(document, "footer"), "#c1c5cb")
        return missing_paths, overflow

    def _draw_profile(
        self, painter: QPainter, document: EditorialDocument
    ) -> tuple[list[Path], bool]:
        painter.fillRect(QRectF(0.0, 0.0, PAGE_WIDTH, PAGE_HEIGHT), QColor("#eee5d8"))
        painter.fillRect(QRectF(0.0, 0.0, 78.0, PAGE_HEIGHT), QColor("#315b52"))
        overflow = self._draw_text(
            painter,
            self._header_text(self._layout_text(document, "header"), document),
            QRectF(150.0, 100.0, 2180.0, 80.0),
            point_size=25,
            weight=QFont.Weight.DemiBold,
            color="#315b52",
            letter_spacing=3.0,
            font_role="accent",
            field_key="header_text",
        )
        overflow |= self._draw_fitted_text(
            painter,
            document.title,
            QRectF(1210.0, 270.0, 1120.0, 230.0),
            max_size=98.0,
            min_size=52.0,
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

        section_items = [
            section
            for section in document.effective_sections()
            if section.heading.strip() or section.body.strip()
        ]
        has_lower_sections = len(section_items) > 1
        missing_paths: list[Path] = []
        hero = document.photos[0]
        hero_bottom = 2000.0 if has_lower_sections else 3200.0
        hero_rect = QRectF(150.0, 300.0, 960.0, hero_bottom - 300.0)
        if not self._draw_photo(painter, hero, hero_rect):
            missing_paths.append(hero.source_path)
        if hero.caption:
            if has_lower_sections:
                caption_rect = QRectF(150.0, 2010.0, 960.0, 80.0)
                caption_color = "#52635f"
            else:
                painter.fillRect(
                    QRectF(150.0, 3090.0, 960.0, 110.0), QColor(23, 51, 45, 190)
                )
                caption_rect = QRectF(175.0, 3110.0, 910.0, 70.0)
                caption_color = "#ffffff"
            overflow |= self._draw_text(
                painter,
                hero.caption,
                caption_rect,
                point_size=25,
                color=caption_color,
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
        if section_items:
            upper_height = self._section_stack_height(
                section_items[:1], 1120.0, 31.0, 26.0, max(100.0, 2280.0 - content_y)
            )
            overflow |= self._draw_sections(
                painter,
                document,
                QRectF(1210.0, content_y, 1120.0, upper_height),
                heading_size=31.0,
                body_size=26.0,
                color="#263c37",
                card_background="#f8f4ec",
                section_items=section_items[:1],
            )
        else:
            upper_height = 0.0
        if has_lower_sections:
            lower_height = self._section_stack_height(
                section_items[1:], 960.0, 29.0, 25.0, 1060.0
            )
            overflow |= self._draw_sections(
                painter,
                document,
                QRectF(150.0, 2140.0, 960.0, lower_height),
                heading_size=29.0,
                body_size=25.0,
                color="#263c37",
                card_background="#f8f4ec",
                section_items=section_items[1:],
            )
        photo_grid_y = min(2370.0, max(1550.0, content_y + upper_height + 70.0))
        grid_missing, grid_overflow = self._draw_photo_grid(
            painter,
            document.photos[1:],
            QRectF(1210.0, photo_grid_y, 1120.0, 3200.0 - photo_grid_y),
            columns=2,
            gap=28.0,
            caption_height=55.0,
            caption_size=18.0,
        )
        missing_paths.extend(grid_missing)
        overflow |= grid_overflow
        self._draw_footer(painter, self._layout_text(document, "footer"), "#71847f")
        return missing_paths, overflow

    def _draw_magazine_overlay(
        self, painter: QPainter, document: EditorialDocument
    ) -> tuple[list[Path], bool]:
        painter.fillRect(QRectF(0.0, 0.0, PAGE_WIDTH, PAGE_HEIGHT), QColor("#f4efe6"))
        missing_paths: list[Path] = []
        hero_rect = QRectF(0.0, 0.0, PAGE_WIDTH, 1900.0)
        if not self._draw_photo(painter, document.photos[0], hero_rect):
            missing_paths.append(document.photos[0].source_path)
        painter.fillRect(QRectF(0.0, 0.0, PAGE_WIDTH, 175.0), QColor(15, 23, 42, 178))
        painter.fillRect(QRectF(105.0, 1040.0, 2150.0, 720.0), QColor(15, 23, 42, 196))
        overflow = self._draw_text(
            painter,
            self._header_text(self._layout_text(document, "header"), document),
            QRectF(140.0, 62.0, 2200.0, 80.0),
            point_size=25,
            weight=QFont.Weight.DemiBold,
            color="#ffffff",
            letter_spacing=3.0,
            font_role="accent",
            field_key="header_text",
        )
        overflow |= self._draw_fitted_text(
            painter,
            document.title,
            QRectF(155.0, 1100.0, 2020.0, 365.0),
            max_size=122.0,
            min_size=62.0,
            weight=QFont.Weight.Bold,
            color="#ffffff",
            line_height=1.0,
        )
        overflow |= self._draw_text(
            painter,
            document.subtitle,
            QRectF(160.0, 1490.0, 1960.0, 105.0),
            point_size=38,
            color="#f3e8d4",
        )
        overflow |= self._draw_text(
            painter,
            document.photos[0].caption,
            QRectF(145.0, 1815.0, 2190.0, 60.0),
            point_size=22,
            color="#ffffff",
            alignment=Qt.AlignmentFlag.AlignRight,
        )
        content_y = 1980.0
        if document.lead:
            overflow |= self._draw_text(
                painter,
                document.lead,
                QRectF(145.0, content_y, 2190.0, 185.0),
                point_size=37,
                weight=QFont.Weight.DemiBold,
                color="#292524",
                line_height=1.25,
            )
            content_y += 210.0
        grid_missing, grid_overflow = self._draw_photo_grid(
            painter,
            document.photos[1:],
            QRectF(145.0, content_y, 820.0, 1050.0),
            columns=2,
            gap=30.0,
            caption_height=65.0,
            caption_size=20.0,
        )
        missing_paths.extend(grid_missing)
        overflow |= grid_overflow
        overflow |= self._draw_sections(
            painter,
            document,
            QRectF(1040.0, content_y, 1295.0, 3250.0 - content_y),
            heading_size=31.0,
            body_size=26.0,
            color="#292524",
        )
        self._draw_footer(painter, self._layout_text(document, "footer"), "#9a3412")
        return missing_paths, overflow

    def _draw_newspaper_columns(
        self, painter: QPainter, document: EditorialDocument
    ) -> tuple[list[Path], bool]:
        painter.fillRect(QRectF(0.0, 0.0, PAGE_WIDTH, PAGE_HEIGHT), QColor("#f7f3e8"))
        painter.fillRect(QRectF(0.0, 0.0, PAGE_WIDTH, 38.0), QColor("#191919"))
        overflow = self._draw_fitted_text(
            painter,
            document.publication_title or "地球写真新聞",
            QRectF(125.0, 80.0, 2230.0, 100.0),
            max_size=48.0,
            min_size=28.0,
            weight=QFont.Weight.Bold,
            color="#181818",
            families=TOKENS.serif_families,
        )
        painter.setPen(QPen(QColor("#181818"), 4.0))
        painter.drawLine(125.0, 205.0, 2355.0, 205.0)
        overflow |= self._draw_fitted_text(
            painter,
            document.title,
            QRectF(125.0, 255.0, 2230.0, 390.0),
            max_size=112.0,
            min_size=58.0,
            weight=QFont.Weight.Bold,
            color="#111111",
            line_height=1.0,
            families=TOKENS.serif_families,
        )
        overflow |= self._draw_text(
            painter,
            document.subtitle,
            QRectF(125.0, 670.0, 2230.0, 95.0),
            point_size=34,
            color="#3f3f3f",
            families=TOKENS.serif_families,
        )
        overflow |= self._draw_text(
            painter,
            self._metadata_text(document),
            QRectF(125.0, 775.0, 2230.0, 55.0),
            point_size=21,
            color="#555555",
            alignment=Qt.AlignmentFlag.AlignRight,
        )
        missing_paths: list[Path] = []
        hero_rect = QRectF(125.0, 865.0, 1050.0, 900.0)
        if not self._draw_photo(painter, document.photos[0], hero_rect):
            missing_paths.append(document.photos[0].source_path)
        overflow |= self._draw_text(
            painter,
            document.photos[0].caption,
            QRectF(125.0, 1780.0, 1050.0, 70.0),
            point_size=22,
            color="#444444",
        )
        if document.lead:
            overflow |= self._draw_text(
                painter,
                document.lead,
                QRectF(1235.0, 865.0, 1120.0, 300.0),
                point_size=34,
                weight=QFont.Weight.DemiBold,
                color="#181818",
                line_height=1.35,
                families=TOKENS.serif_families,
            )
        if document.pull_quote:
            overflow |= self._draw_quote(
                painter,
                document.pull_quote,
                QRectF(1235.0, 1200.0, 1120.0, 180.0),
                "#8b1e1e",
            )
        painter.setPen(QPen(QColor("#181818"), 3.0))
        painter.drawLine(125.0, 1910.0, 2355.0, 1910.0)
        overflow |= self._draw_sections(
            painter,
            document,
            QRectF(125.0, 1980.0, 1450.0, 1310.0),
            heading_size=30.0,
            body_size=25.0,
            color="#181818",
            columns=3,
        )
        grid_missing, grid_overflow = self._draw_photo_grid(
            painter,
            document.photos[1:],
            QRectF(1640.0, 1980.0, 715.0, 1310.0),
            columns=1,
            gap=28.0,
            caption_height=62.0,
            caption_size=19.0,
        )
        missing_paths.extend(grid_missing)
        overflow |= grid_overflow
        self._draw_footer(
            painter,
            f"{document.publication_title or 'THE EARTH OBSERVER'} / {self._layout_text(document, 'footer')}",
            "#333333",
        )
        return missing_paths, overflow

    def _draw_newspaper_mosaic(
        self, painter: QPainter, document: EditorialDocument
    ) -> tuple[list[Path], bool]:
        painter.fillRect(QRectF(0.0, 0.0, PAGE_WIDTH, PAGE_HEIGHT), QColor("#f4f0e7"))
        overflow = self._draw_fitted_text(
            painter,
            document.publication_title or "THE EARTH OBSERVER",
            QRectF(120.0, 62.0, 1580.0, 135.0),
            max_size=68.0,
            min_size=32.0,
            weight=QFont.Weight.Bold,
            color="#111111",
            alignment=Qt.AlignmentFlag.AlignCenter,
            families=TOKENS.serif_families,
        )
        overflow |= self._draw_text(
            painter,
            self._metadata_text(document),
            QRectF(1740.0, 78.0, 620.0, 100.0),
            point_size=21,
            weight=QFont.Weight.DemiBold,
            color="#222222",
            alignment=Qt.AlignmentFlag.AlignRight,
        )
        painter.setPen(QPen(QColor("#202020"), 5.0))
        painter.drawLine(120.0, 225.0, 2360.0, 225.0)
        overflow |= self._draw_text(
            painter,
            self._layout_text(document, "header"),
            QRectF(120.0, 235.0, 2240.0, 65.0),
            point_size=20,
            weight=QFont.Weight.DemiBold,
            color="#555555",
            alignment=Qt.AlignmentFlag.AlignRight,
            font_role="accent",
            field_key="header_text",
        )
        painter.fillRect(QRectF(120.0, 305.0, 2240.0, 285.0), QColor("#151515"))
        overflow |= self._draw_fitted_text(
            painter,
            document.title,
            QRectF(165.0, 340.0, 2150.0, 215.0),
            max_size=92.0,
            min_size=50.0,
            weight=QFont.Weight.Bold,
            color="#ffffff",
            line_height=1.0,
            families=TOKENS.serif_families,
            alignment=Qt.AlignmentFlag.AlignCenter,
            vertical_center=True,
        )
        overflow |= self._draw_text(
            painter,
            document.subtitle,
            QRectF(120.0, 615.0, 2240.0, 95.0),
            point_size=32,
            weight=QFont.Weight.DemiBold,
            color="#333333",
            families=TOKENS.serif_families,
        )
        painter.setPen(QPen(QColor("#222222"), 3.0))
        painter.drawLine(120.0, 720.0, 2360.0, 720.0)

        missing_paths: list[Path] = []
        hero = document.photos[0]
        hero_rect = QRectF(120.0, 770.0, 1040.0, 1070.0)
        if not self._draw_photo(painter, hero, hero_rect):
            missing_paths.append(hero.source_path)
        overflow |= self._draw_text(
            painter,
            hero.caption,
            QRectF(120.0, 1855.0, 1040.0, 65.0),
            point_size=21,
            color="#444444",
        )

        section_items = [
            section
            for section in document.effective_sections()
            if section.heading.strip() or section.body.strip()
        ]
        section_y = 770.0
        if document.lead:
            overflow |= self._draw_text(
                painter,
                document.lead,
                QRectF(1240.0, section_y, 1120.0, 190.0),
                point_size=31,
                weight=QFont.Weight.DemiBold,
                color="#181818",
                line_height=1.35,
                families=TOKENS.serif_families,
            )
            section_y += 220.0
        if section_items:
            first_height = self._section_stack_height(
                section_items[:1], 1120.0, 30.0, 25.0, 1920.0 - section_y
            )
            overflow |= self._draw_sections(
                painter,
                document,
                QRectF(1240.0, section_y, 1120.0, first_height),
                heading_size=30.0,
                body_size=25.0,
                color="#181818",
                card_background="#ffffff",
                section_items=section_items[:1],
            )
        if len(section_items) > 1:
            lower_height = self._section_stack_height(
                section_items[1:], 1040.0, 28.0, 24.0, 1160.0
            )
            overflow |= self._draw_sections(
                painter,
                document,
                QRectF(120.0, 2030.0, 1040.0, lower_height),
                heading_size=28.0,
                body_size=24.0,
                color="#181818",
                card_background="#ffffff",
                section_items=section_items[1:],
            )
        grid_missing, grid_overflow = self._draw_photo_grid(
            painter,
            document.photos[1:],
            QRectF(1240.0, 2030.0, 1120.0, 1170.0),
            columns=2,
            gap=32.0,
            caption_height=62.0,
            caption_size=19.0,
        )
        missing_paths.extend(grid_missing)
        overflow |= grid_overflow
        self._draw_footer(
            painter,
            f"{document.publication_title or 'THE EARTH OBSERVER'} / {self._layout_text(document, 'footer')}",
            "#444444",
        )
        return missing_paths, overflow

    def _draw_photo_essay_asymmetric(
        self, painter: QPainter, document: EditorialDocument
    ) -> tuple[list[Path], bool]:
        painter.fillRect(QRectF(0.0, 0.0, PAGE_WIDTH, PAGE_HEIGHT), QColor("#111827"))
        missing_paths: list[Path] = []
        hero_rect = QRectF(0.0, 0.0, 1480.0, 2210.0)
        if not self._draw_photo(painter, document.photos[0], hero_rect):
            missing_paths.append(document.photos[0].source_path)
        painter.fillRect(QRectF(1480.0, 0.0, 1000.0, 2210.0), QColor("#efe9de"))
        overflow = self._draw_text(
            painter,
            self._header_text(self._layout_text(document, "header"), document),
            QRectF(1570.0, 120.0, 810.0, 75.0),
            point_size=22,
            weight=QFont.Weight.DemiBold,
            color="#9a3412",
            letter_spacing=3.0,
            font_role="accent",
            field_key="header_text",
        )
        overflow |= self._draw_fitted_text(
            painter,
            document.title,
            QRectF(1570.0, 280.0, 810.0, 610.0),
            max_size=104.0,
            min_size=56.0,
            weight=QFont.Weight.Bold,
            color="#111827",
            line_height=1.05,
        )
        overflow |= self._draw_text(
            painter,
            document.subtitle,
            QRectF(1570.0, 930.0, 810.0, 140.0),
            point_size=32,
            color="#7c2d12",
        )
        overflow |= self._draw_text(
            painter,
            document.lead,
            QRectF(1570.0, 1140.0, 810.0, 480.0),
            point_size=29,
            color="#374151",
            line_height=1.45,
        )
        overflow |= self._draw_text(
            painter,
            document.photos[0].caption,
            QRectF(70.0, 2120.0, 1320.0, 55.0),
            point_size=20,
            color="#ffffff",
            alignment=Qt.AlignmentFlag.AlignRight,
        )
        grid_missing, grid_overflow = self._draw_photo_grid(
            painter,
            document.photos[1:],
            QRectF(100.0, 2300.0, 1360.0, 930.0),
            columns=2,
            gap=34.0,
            caption_height=64.0,
            caption_size=19.0,
        )
        missing_paths.extend(grid_missing)
        overflow |= grid_overflow
        overflow |= self._draw_sections(
            painter,
            document,
            QRectF(1540.0, 2300.0, 840.0, 930.0),
            heading_size=28.0,
            body_size=23.0,
            color="#f3f4f6",
        )
        self._draw_footer(painter, self._layout_text(document, "footer"), "#6b7280")
        return missing_paths, overflow

    def _draw_profile_banner(
        self, painter: QPainter, document: EditorialDocument
    ) -> tuple[list[Path], bool]:
        painter.fillRect(QRectF(0.0, 0.0, PAGE_WIDTH, PAGE_HEIGHT), QColor("#f5efe5"))
        painter.fillRect(QRectF(0.0, 0.0, PAGE_WIDTH, 760.0), QColor("#173b36"))
        painter.fillRect(QRectF(0.0, 720.0, PAGE_WIDTH, 40.0), QColor("#e8793e"))
        overflow = self._draw_text(
            painter,
            self._header_text(self._layout_text(document, "header"), document),
            QRectF(140.0, 80.0, 2200.0, 70.0),
            point_size=25,
            weight=QFont.Weight.DemiBold,
            color="#b7d2c8",
            letter_spacing=4.0,
            font_role="accent",
            field_key="header_text",
        )
        overflow |= self._draw_fitted_text(
            painter,
            document.title,
            QRectF(140.0, 190.0, 2200.0, 330.0),
            max_size=148.0,
            min_size=72.0,
            weight=QFont.Weight.Bold,
            color="#ffffff",
            line_height=1.0,
        )
        overflow |= self._draw_text(
            painter,
            document.subtitle,
            QRectF(145.0, 555.0, 2190.0, 105.0),
            point_size=39,
            weight=QFont.Weight.DemiBold,
            color="#f5c3a8",
        )

        missing_paths: list[Path] = []
        hero_rect = QRectF(140.0, 850.0, 1120.0, 1320.0)
        if not self._draw_photo(painter, document.photos[0], hero_rect):
            missing_paths.append(document.photos[0].source_path)
        overflow |= self._draw_text(
            painter,
            document.photos[0].caption,
            QRectF(140.0, 2185.0, 1120.0, 65.0),
            point_size=23,
            color="#52635f",
        )
        overflow |= self._draw_profile_band(
            painter,
            document,
            QRectF(1340.0, 850.0, 1000.0, 1400.0),
        )
        content_y = 2320.0
        if document.lead:
            painter.fillRect(QRectF(140.0, content_y, 2200.0, 190.0), QColor("#e3d7c5"))
            overflow |= self._draw_text(
                painter,
                document.lead,
                QRectF(180.0, content_y + 25.0, 2120.0, 140.0),
                point_size=35,
                weight=QFont.Weight.DemiBold,
                color="#173b36",
                line_height=1.25,
            )
            content_y += 235.0
        overflow |= self._draw_sections(
            painter,
            document,
            QRectF(140.0, content_y, 1320.0, 3280.0 - content_y),
            heading_size=34.0,
            body_size=27.0,
            color="#263c37",
            columns=2,
            card_background="#ffffff",
        )
        grid_missing, grid_overflow = self._draw_photo_grid(
            painter,
            document.photos[1:],
            QRectF(1530.0, content_y, 810.0, 3280.0 - content_y),
            columns=2,
            gap=24.0,
            caption_height=54.0,
            caption_size=17.0,
        )
        missing_paths.extend(grid_missing)
        overflow |= grid_overflow
        self._draw_footer(painter, self._layout_text(document, "footer"), "#71847f")
        return missing_paths, overflow

    def _draw_profile_band(
        self, painter: QPainter, document: EditorialDocument, rect: QRectF
    ) -> bool:
        fields = [
            field
            for field in document.profile_fields
            if field.label.strip() or field.value.strip()
        ]
        if not fields:
            return False
        columns = min(2, len(fields))
        rows = math.ceil(len(fields) / columns)
        gap = 22.0
        row_height = (rect.height() - gap * 3.0) / 4.0
        overflow = rows > 4
        if overflow:
            for field in fields[8:]:
                self._overflow_fields.add(f"profile_label:{field.id}")
                self._overflow_fields.add(f"profile_value:{field.id}")
        cell_width = (rect.width() - gap * (columns - 1)) / columns
        for index, field in enumerate(fields[: columns * 4]):
            row, column = divmod(index, columns)
            cell = QRectF(
                rect.x() + column * (cell_width + gap),
                rect.y() + row * (row_height + gap),
                cell_width,
                row_height,
            )
            painter.fillRect(cell, QColor("#ffffff"))
            painter.fillRect(
                QRectF(cell.x(), cell.y(), cell.width(), 88.0), QColor("#e8793e")
            )
            overflow |= self._draw_text(
                painter,
                field.label,
                QRectF(cell.x() + 20.0, cell.y() + 12.0, cell.width() - 40.0, 66.0),
                point_size=28,
                weight=QFont.Weight.Bold,
                color="#ffffff",
            )
            overflow |= self._draw_fitted_text(
                painter,
                field.value,
                QRectF(
                    cell.x() + 22.0,
                    cell.y() + 94.0,
                    cell.width() - 44.0,
                    cell.height() - 112.0,
                ),
                max_size=42.0,
                min_size=28.0,
                weight=QFont.Weight.DemiBold,
                color="#173b36",
                line_height=1.15,
            )
        return overflow

    @staticmethod
    def _section_stack_height(
        sections: list[EditorialSection],
        width: float,
        heading_size: float,
        body_size: float,
        maximum: float,
    ) -> float:
        if not sections:
            return 0.0
        usable_width = max(100.0, width - 48.0)
        characters_per_line = max(8, int(usable_width / (body_size * 0.95)))
        needed = 0.0
        for section in sections:
            heading_height = heading_size * 2.4 if section.heading else 0.0
            body_lines = max(1, math.ceil(len(section.body) / characters_per_line))
            needed += 55.0 + heading_height + body_lines * body_size * 1.65
        needed += max(0, len(sections) - 1) * 32.0
        return min(max(100.0, maximum), max(320.0, needed))

    def _header_text(self, base: str, document: EditorialDocument) -> str:
        metadata = self._metadata_text(document)
        if base and metadata:
            return f"{base}  /  {metadata}"
        return base or metadata

    @staticmethod
    def _layout_text(document: EditorialDocument, key: str) -> str:
        return document.layout_text_overrides.get(document.template_id, {}).get(
            key, default_layout_text(document.template_id, key)
        )

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
        target_rows = min(8, len(fields))
        row_height = min(88.0, rect.height() / target_rows)
        needed_height = row_height * len(fields)
        available_rows = max(0, int(rect.height() // row_height))
        overflow = len(fields) > available_rows
        if overflow:
            for field in fields[available_rows:]:
                self._overflow_fields.add(f"profile_label:{field.id}")
                self._overflow_fields.add(f"profile_value:{field.id}")
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
        card_background: str | None = None,
        section_items: list[EditorialSection] | None = None,
    ) -> bool:
        sections = (
            section_items
            if section_items is not None
            else [
                section
                for section in document.effective_sections()
                if section.heading.strip() or section.body.strip()
            ]
        )
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
            current_width = cell_width
            current_height = cell_height
            if card_background:
                painter.fillRect(
                    QRectF(x, y, cell_width, cell_height), QColor(card_background)
                )
                x += 24.0
                y += 20.0
                current_width -= 48.0
                current_height -= 40.0
            heading_height = max(65.0, heading_size * 2.25) if section.heading else 0.0
            if section.heading:
                overflow |= self._draw_text(
                    painter,
                    section.heading,
                    QRectF(x, y, current_width, heading_height),
                    point_size=heading_size,
                    weight=QFont.Weight.Bold,
                    color=color,
                    line_height=1.1,
                )
                painter.setPen(QPen(QColor(color), 2.0))
                painter.drawLine(x, y + heading_height - 7.0, x + current_width, y + heading_height - 7.0)
            body_height = current_height - heading_height
            if body_height <= 0 and section.body:
                overflow = True
                self._overflow_fields.add(f"section_body:{section.id}")
                continue
            overflow |= self._draw_text(
                painter,
                section.body,
                QRectF(x, y + heading_height + 10.0, current_width, max(0.0, body_height - 10.0)),
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
            QRectF(140.0, 3350.0, 2200.0, 85.0),
            point_size=20,
            color=color,
            alignment=Qt.AlignmentFlag.AlignRight,
            font_role="accent",
            field_key="footer_text",
        )

    def _draw_photo(
        self, painter: QPainter, photo: EditorialPhoto, target_rect: QRectF
    ) -> bool:
        scale_x = painter.transform().m11()
        scale_y = painter.transform().m22()
        target_width = max(1, round(target_rect.width() * scale_x))
        target_height = max(1, round(target_rect.height() * scale_y))
        load_width = round(target_width / photo.crop_width)
        load_height = round(target_height / photo.crop_height)
        source = self._load_image(photo.source_path, load_width, load_height)
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

        crop_x = round(source.width() * photo.crop_x)
        crop_y = round(source.height() * photo.crop_y)
        crop_width = max(1, round(source.width() * photo.crop_width))
        crop_height = max(1, round(source.height() * photo.crop_height))
        crop_width = min(crop_width, source.width() - crop_x)
        crop_height = min(crop_height, source.height() - crop_y)
        cropped = source.copy(crop_x, crop_y, crop_width, crop_height)
        scaled = cropped.scaled(
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
        families: tuple[str, ...] = TOKENS.sans_families,
        font_role: str | None = None,
        vertical_center: bool = False,
        vertical_scale: float = 1.0,
        field_key: str | None = None,
    ) -> bool:
        if not text:
            return False
        document = QTextDocument()
        document.setDocumentMargin(0.0)
        font = QFont()
        font.setFamily(self._font_family_for(text, font_role, families))
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
        vertical_scale = max(0.5, vertical_scale)
        document.setTextWidth(rect.width())
        content_height = document.size().height()
        scaled_content_height = content_height * vertical_scale
        overflow = scaled_content_height > rect.height() + 0.5
        if overflow:
            self._overflow_fields.update(self._text_field_keys.get(text, ()))
            if field_key:
                self._overflow_fields.add(field_key)

        painter.save()
        painter.setClipRect(rect)
        y_offset = (
            max(0.0, (rect.height() - scaled_content_height) / 2.0)
            if vertical_center
            else 0.0
        )
        painter.translate(rect.x(), rect.y() + y_offset)
        painter.scale(1.0, vertical_scale)
        document.drawContents(
            painter,
            QRectF(0.0, 0.0, rect.width(), rect.height() / vertical_scale),
        )
        painter.restore()
        return overflow

    def _draw_fitted_text(
        self,
        painter: QPainter,
        text: str,
        rect: QRectF,
        *,
        max_size: float,
        min_size: float,
        weight: QFont.Weight,
        color: str,
        line_height: float = 1.05,
        families: tuple[str, ...] = TOKENS.sans_families,
        alignment: Qt.AlignmentFlag = Qt.AlignmentFlag.AlignLeft,
        font_role: str | None = None,
        vertical_center: bool = False,
        vertical_scale: float = 1.0,
        field_key: str | None = None,
    ) -> bool:
        """タイトルを測定し、領域に収まる最大サイズで描画する。"""

        if not text:
            return False
        selected_size = min_size
        for point_size in range(round(max_size), round(min_size) - 1, -2):
            document = QTextDocument()
            document.setDocumentMargin(0.0)
            font = QFont()
            font.setFamily(self._font_family_for(text, font_role, families))
            font.setPointSizeF(float(point_size))
            font.setWeight(weight)
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
            document.setTextWidth(rect.width())
            if document.size().height() * vertical_scale <= rect.height() + 0.5:
                selected_size = float(point_size)
                break
        return self._draw_text(
            painter,
            text,
            rect,
            point_size=selected_size,
            weight=weight,
            color=color,
            line_height=line_height,
            families=families,
            alignment=alignment,
            font_role=font_role,
            vertical_center=vertical_center,
            vertical_scale=vertical_scale,
            field_key=field_key,
        )

    def _font_family_for(
        self,
        text: str,
        font_role: str | None,
        fallback: tuple[str, ...],
    ) -> str:
        if font_role == "title" or text in self._title_texts:
            return self._title_font_family or fallback[0]
        if font_role == "accent" or text in self._accent_texts:
            return self._accent_font_family or fallback[0]
        return self._body_font_family or fallback[0]
