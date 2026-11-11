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
            "EARTH PHOTO JOURNAL  /  FEATURE",
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
            template.title_rect,
            point_size=86,
            weight=QFont.Weight.Bold,
            color="#1f2937",
            line_height=1.05,
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
        overflow |= self._draw_text(
            painter,
            document.body,
            template.body_rect,
            point_size=35,
            line_height=1.55,
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
            QRectF(120.0, 330.0, 2240.0, 330.0),
            point_size=78,
            weight=QFont.Weight.Bold,
            color="#111111",
            line_height=1.05,
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
        overflow |= self._draw_text(
            painter,
            document.body,
            QRectF(1350.0, 730.0, 1010.0, 1130.0),
            point_size=32,
            color="#181818",
            line_height=1.45,
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
            "PHOTO ESSAY",
            QRectF(150.0, 95.0, 2180.0, 70.0),
            point_size=22,
            weight=QFont.Weight.DemiBold,
            color="#6b7280",
            letter_spacing=5.0,
        )
        overflow |= self._draw_text(
            painter,
            document.title,
            QRectF(150.0, 210.0, 2180.0, 250.0),
            point_size=76,
            weight=QFont.Weight.Light,
            color="#111827",
            line_height=1.05,
        )
        overflow |= self._draw_text(
            painter,
            document.body,
            QRectF(150.0, 465.0, 2180.0, 250.0),
            point_size=29,
            color="#4b5563",
            line_height=1.4,
        )

        missing_paths: list[Path] = []
        hero = document.photos[0]
        hero_rect = QRectF(150.0, 760.0, 2180.0, 1440.0)
        if not self._draw_photo(painter, hero, hero_rect):
            missing_paths.append(hero.source_path)
        overflow |= self._draw_text(
            painter,
            hero.caption,
            QRectF(150.0, 2220.0, 2180.0, 80.0),
            point_size=24,
            color="#6b7280",
            alignment=Qt.AlignmentFlag.AlignRight,
        )
        grid_missing, grid_overflow = self._draw_photo_grid(
            painter,
            document.photos[1:],
            QRectF(150.0, 2370.0, 2180.0, 850.0),
            columns=3,
            gap=44.0,
            caption_height=72.0,
            caption_size=21.0,
        )
        missing_paths.extend(grid_missing)
        overflow |= grid_overflow
        self._draw_footer(painter, "EARTH PHOTO ESSAY", "#c1c5cb")
        return missing_paths, overflow

    def _draw_profile(
        self, painter: QPainter, document: EditorialDocument
    ) -> tuple[list[Path], bool]:
        painter.fillRect(QRectF(0.0, 0.0, PAGE_WIDTH, PAGE_HEIGHT), QColor("#eee5d8"))
        painter.fillRect(QRectF(0.0, 0.0, 78.0, PAGE_HEIGHT), QColor("#315b52"))
        overflow = self._draw_text(
            painter,
            "PORTRAIT  /  PROFILE",
            QRectF(150.0, 100.0, 2180.0, 80.0),
            point_size=25,
            weight=QFont.Weight.DemiBold,
            color="#315b52",
            letter_spacing=3.0,
        )
        overflow |= self._draw_text(
            painter,
            document.title,
            QRectF(1210.0, 300.0, 1120.0, 330.0),
            point_size=76,
            weight=QFont.Weight.Bold,
            color="#17332d",
            line_height=1.05,
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
        painter.fillRect(QRectF(1210.0, 680.0, 1120.0, 8.0), QColor("#c27649"))
        overflow |= self._draw_text(
            painter,
            document.body,
            QRectF(1210.0, 750.0, 1120.0, 1030.0),
            point_size=32,
            color="#263c37",
            line_height=1.5,
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
