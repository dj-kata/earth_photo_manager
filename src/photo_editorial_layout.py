from __future__ import annotations

from dataclasses import dataclass
import random

from src.photo_editorial_model import (
    MAGAZINE_FEATURE_TEMPLATE_ID,
    MAGAZINE_HERO_OVERLAY_TEMPLATE_ID,
    NEWSPAPER_ARTICLE_TEMPLATE_ID,
    NEWSPAPER_COLUMNS_TEMPLATE_ID,
    PHOTO_ESSAY_ASYMMETRIC_TEMPLATE_ID,
    PHOTO_ESSAY_TEMPLATE_ID,
    PROFILE_BANNER_TEMPLATE_ID,
    PROFILE_FEATURE_TEMPLATE_ID,
)


FORMAT_MAGAZINE = "magazine"
FORMAT_NEWSPAPER = "newspaper"
FORMAT_PHOTO_ESSAY = "photo_essay"
FORMAT_PROFILE = "profile"


@dataclass(frozen=True)
class DesignTokens:
    page_margin: float = 140.0
    gutter: float = 40.0
    title_max_size: float = 112.0
    title_min_size: float = 54.0
    body_size: float = 27.0
    sans_families: tuple[str, ...] = (
        "Noto Sans JP",
        "Yu Gothic UI",
        "Meiryo",
        "sans-serif",
    )
    serif_families: tuple[str, ...] = (
        "Noto Serif JP",
        "Yu Mincho",
        "MS Mincho",
        "serif",
    )


TOKENS = DesignTokens()


@dataclass(frozen=True)
class LayoutSpec:
    template_id: str
    format_id: str
    label_key: str
    preferred_density: str
    max_photos: int
    preferred_orientation: str = "any"


LAYOUT_SPECS = (
    LayoutSpec(
        MAGAZINE_FEATURE_TEMPLATE_ID,
        FORMAT_MAGAZINE,
        "layout_magazine_asymmetric",
        "standard",
        6,
    ),
    LayoutSpec(
        MAGAZINE_HERO_OVERLAY_TEMPLATE_ID,
        FORMAT_MAGAZINE,
        "layout_magazine_overlay",
        "short",
        7,
        "landscape",
    ),
    LayoutSpec(
        NEWSPAPER_ARTICLE_TEMPLATE_ID,
        FORMAT_NEWSPAPER,
        "layout_newspaper_photo_news",
        "short",
        7,
    ),
    LayoutSpec(
        NEWSPAPER_COLUMNS_TEMPLATE_ID,
        FORMAT_NEWSPAPER,
        "layout_newspaper_columns",
        "long",
        4,
    ),
    LayoutSpec(
        PHOTO_ESSAY_TEMPLATE_ID,
        FORMAT_PHOTO_ESSAY,
        "layout_essay_hero",
        "short",
        4,
        "landscape",
    ),
    LayoutSpec(
        PHOTO_ESSAY_ASYMMETRIC_TEMPLATE_ID,
        FORMAT_PHOTO_ESSAY,
        "layout_essay_gallery",
        "standard",
        7,
    ),
    LayoutSpec(
        PROFILE_FEATURE_TEMPLATE_ID,
        FORMAT_PROFILE,
        "layout_profile_portrait",
        "standard",
        5,
        "portrait",
    ),
    LayoutSpec(
        PROFILE_BANNER_TEMPLATE_ID,
        FORMAT_PROFILE,
        "layout_profile_banner",
        "long",
        7,
    ),
)

_SPEC_BY_ID = {spec.template_id: spec for spec in LAYOUT_SPECS}


def format_for_template(template_id: str) -> str:
    return _SPEC_BY_ID[template_id].format_id


def layouts_for_format(format_id: str) -> tuple[LayoutSpec, ...]:
    return tuple(spec for spec in LAYOUT_SPECS if spec.format_id == format_id)


def max_photos_for_template(template_id: str) -> int:
    return _SPEC_BY_ID[template_id].max_photos


def content_density(text_length: int) -> str:
    if text_length < 180:
        return "short"
    if text_length > 700:
        return "long"
    return "standard"


def select_layout(
    format_id: str,
    *,
    photo_count: int,
    text_length: int,
    hero_aspect: float,
    seed: int,
    exclude_template_id: str | None = None,
) -> str:
    """入力の密度に合う構図を、同じseedなら同じ結果になるよう選ぶ。"""

    candidates = list(layouts_for_format(format_id))
    if exclude_template_id and len(candidates) > 1:
        candidates = [
            spec for spec in candidates if spec.template_id != exclude_template_id
        ]
    density = content_density(text_length)
    scored: list[tuple[int, LayoutSpec]] = []
    for spec in candidates:
        score = 3 if spec.preferred_density == density else 0
        if spec.preferred_density == "standard":
            score += 1
        if spec.preferred_orientation == "landscape" and hero_aspect >= 1.15:
            score += 2
        if spec.preferred_orientation == "portrait" and hero_aspect <= 0.9:
            score += 2
        if "gallery" in spec.template_id and photo_count >= 3:
            score += 2
        if "columns" in spec.template_id and text_length >= 400:
            score += 2
        scored.append((score, spec))
    best_score = max(score for score, _spec in scored)
    best = [spec for score, spec in scored if score == best_score]
    return random.Random(seed).choice(best).template_id
