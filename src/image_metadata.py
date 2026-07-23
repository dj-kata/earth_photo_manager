from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from fractions import Fraction
from pathlib import Path
import struct


TIFF_TYPES = {
    1: (1, "B"),
    2: (1, "s"),
    3: (2, "H"),
    4: (4, "I"),
    5: (8, "II"),
    7: (1, "B"),
    9: (4, "i"),
    10: (8, "ii"),
}

EXIF_TAG = 0x8769
IFD_TAGS = {
    0x0102: "BitsPerSample",
    0x0103: "Compression",
    0x010F: "Make",
    0x0110: "Model",
    0x011A: "XResolution",
    0x011B: "YResolution",
    0x0128: "ResolutionUnit",
    0x0131: "Software",
    0x0132: "DateTime",
    0x0115: "SamplesPerPixel",
}
EXIF_TAGS = {
    0x829A: "ExposureTime",
    0x829D: "FNumber",
    0x8822: "ExposureProgram",
    0x8827: "ISOSpeedRatings",
    0x8833: "PhotographicSensitivity",
    0x9000: "ExifVersion",
    0x9003: "DateTimeOriginal",
    0x9203: "BrightnessValue",
    0x9204: "ExposureBiasValue",
    0x9205: "MaxApertureValue",
    0x9206: "SubjectDistance",
    0x9207: "MeteringMode",
    0x9208: "LightSource",
    0x9209: "Flash",
    0x920A: "FocalLength",
    0xA001: "ColorSpace",
    0xA002: "PixelXDimension",
    0xA003: "PixelYDimension",
    0xA403: "WhiteBalance",
    0xA404: "DigitalZoomRatio",
    0xA405: "FocalLengthIn35mmFilm",
    0xA408: "Contrast",
    0xA409: "Saturation",
    0xA40A: "Sharpness",
    0xA433: "LensMake",
    0xA434: "LensModel",
}

EXPOSURE_PROGRAM = {
    0: "未定義",
    1: "マニュアル",
    2: "標準",
    3: "絞り優先",
    4: "シャッター優先",
    5: "クリエイティブ",
    6: "アクション",
    7: "ポートレート",
    8: "風景",
}
METERING_MODE = {
    0: "不明",
    1: "平均",
    2: "中央重点",
    3: "スポット",
    4: "マルチスポット",
    5: "パターン",
    6: "部分",
}
LIGHT_SOURCE = {
    0: "不明",
    1: "昼光",
    2: "蛍光灯",
    3: "タングステン",
    4: "フラッシュ",
    9: "晴天",
    10: "曇天",
    11: "日陰",
}
NORMAL_SOFT_HARD = {0: "標準", 1: "ソフト", 2: "ハード"}
NORMAL_LOW_HIGH = {0: "標準", 1: "低", 2: "高"}
WHITE_BALANCE = {0: "自動", 1: "マニュアル"}
RESOLUTION_UNIT = {2: "dpi", 3: "dpcm"}
COLOR_SPACE = {1: "sRGB", 0xFFFF: "未較正"}
COMPRESSION = {
    1: "非圧縮",
    6: "JPEG",
}


@dataclass(frozen=True)
class ImageMetadata:
    rows: list[tuple[str, str]] = field(default_factory=list)
    width: int | None = None
    height: int | None = None
    bit_depth: int | None = None
    color_representation: str | None = None
    compression: str | None = None


def read_image_metadata(path: Path) -> ImageMetadata:
    try:
        data = path.read_bytes()
    except OSError:
        return ImageMetadata()

    suffix = path.suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        header = _read_jpeg_header(data)
        exif = _read_jpeg_exif(data)
        return _metadata_from_tags(exif, header)
    if suffix in {".tif", ".tiff"}:
        exif = _read_tiff_tags(data)
        return _metadata_from_tags(exif, ImageMetadata())
    if suffix == ".png":
        return _read_png_metadata(data)
    if suffix == ".gif":
        return _read_gif_metadata(data)
    if suffix == ".bmp":
        return _read_bmp_metadata(data)

    return ImageMetadata()


def _read_jpeg_header(data: bytes) -> ImageMetadata:
    if not data.startswith(b"\xff\xd8"):
        return ImageMetadata()

    offset = 2
    while offset + 4 <= len(data):
        if data[offset] != 0xFF:
            break
        while offset < len(data) and data[offset] == 0xFF:
            offset += 1
        if offset >= len(data):
            break
        marker = data[offset]
        offset += 1
        if marker in {0xD8, 0xD9}:
            continue
        if marker == 0xDA or offset + 2 > len(data):
            break
        length = int.from_bytes(data[offset : offset + 2], "big")
        payload_start = offset + 2
        payload_end = offset + length
        if payload_end > len(data) or length < 2:
            break

        if marker in {
            0xC0,
            0xC1,
            0xC2,
            0xC3,
            0xC5,
            0xC6,
            0xC7,
            0xC9,
            0xCA,
            0xCB,
            0xCD,
            0xCE,
            0xCF,
        }:
            payload = data[payload_start:payload_end]
            if len(payload) >= 6:
                bit_depth = payload[0]
                height = int.from_bytes(payload[1:3], "big")
                width = int.from_bytes(payload[3:5], "big")
                components = payload[5]
                color = {1: "グレースケール", 3: "YCbCr", 4: "CMYK"}.get(
                    components, f"{components} components"
                )
                return ImageMetadata(
                    width=width,
                    height=height,
                    bit_depth=bit_depth * components,
                    color_representation=color,
                    compression="JPEG",
                )
        offset = payload_end

    return ImageMetadata()


def _read_jpeg_exif(data: bytes) -> dict[str, object]:
    if not data.startswith(b"\xff\xd8"):
        return {}

    offset = 2
    while offset + 4 <= len(data):
        if data[offset] != 0xFF:
            break
        while offset < len(data) and data[offset] == 0xFF:
            offset += 1
        if offset >= len(data):
            break
        marker = data[offset]
        offset += 1
        if marker == 0xDA or offset + 2 > len(data):
            break
        length = int.from_bytes(data[offset : offset + 2], "big")
        payload_start = offset + 2
        payload_end = offset + length
        if payload_end > len(data) or length < 2:
            break
        payload = data[payload_start:payload_end]
        if marker == 0xE1 and payload.startswith(b"Exif\x00\x00"):
            return _read_tiff_tags(payload[6:])
        offset = payload_end
    return {}


def _read_tiff_tags(data: bytes) -> dict[str, object]:
    if len(data) < 8:
        return {}
    endian = data[:2]
    if endian == b"II":
        prefix = "<"
    elif endian == b"MM":
        prefix = ">"
    else:
        return {}
    if _unpack(data, prefix, "H", 2) != 42:
        return {}

    first_ifd = _unpack(data, prefix, "I", 4)
    tags: dict[str, object] = {}
    exif_offset = _read_ifd(data, prefix, first_ifd, IFD_TAGS, tags)
    if isinstance(exif_offset, int):
        _read_ifd(data, prefix, exif_offset, EXIF_TAGS, tags)
    return tags


def _read_ifd(
    data: bytes,
    prefix: str,
    offset: int,
    tag_names: dict[int, str],
    tags: dict[str, object],
) -> int | None:
    if offset < 0 or offset + 2 > len(data):
        return None
    count = _unpack(data, prefix, "H", offset)
    entry_start = offset + 2
    exif_offset: int | None = None
    for index in range(count):
        entry = entry_start + index * 12
        if entry + 12 > len(data):
            break
        tag, value_type, value_count = struct.unpack(
            f"{prefix}HHI", data[entry : entry + 8]
        )
        value = _read_tiff_value(data, prefix, entry + 8, value_type, value_count)
        if tag == EXIF_TAG and isinstance(value, int):
            exif_offset = value
        elif tag in tag_names:
            tags[tag_names[tag]] = value
    return exif_offset


def _read_tiff_value(
    data: bytes, prefix: str, value_offset: int, value_type: int, count: int
) -> object | None:
    type_info = TIFF_TYPES.get(value_type)
    if type_info is None or count < 0:
        return None
    unit_size, fmt = type_info
    size = unit_size * count
    raw = data[value_offset : value_offset + 4]
    if size > 4:
        target = _unpack(data, prefix, "I", value_offset)
        if target < 0 or target + size > len(data):
            return None
        raw = data[target : target + size]

    if value_type == 2:
        return raw.rstrip(b"\x00").decode("utf-8", errors="replace").strip()
    if value_type == 7:
        return bytes(raw[:size])

    values = []
    cursor = 0
    for _ in range(count):
        chunk = raw[cursor : cursor + unit_size]
        cursor += unit_size
        if len(chunk) < unit_size:
            break
        if value_type in {5, 10}:
            numerator, denominator = struct.unpack(f"{prefix}{fmt}", chunk)
            values.append(_fraction_or_none(numerator, denominator))
        else:
            values.append(struct.unpack(f"{prefix}{fmt}", chunk)[0])

    if len(values) == 1:
        return values[0]
    return tuple(values)


def _metadata_from_tags(tags: dict[str, object], header: ImageMetadata) -> ImageMetadata:
    rows: list[tuple[str, str]] = []
    add = _row_adder(rows)

    add("撮影日時", _format_datetime(tags.get("DateTimeOriginal")))
    add("プログラム名", _format_plain(tags.get("Software")))
    add("カメラの製造元", _format_plain(tags.get("Make")))
    add("カメラのモデル", _format_plain(tags.get("Model")))
    add("絞り値", _format_f_number(tags.get("FNumber")))
    add("露出時間", _format_exposure_time(tags.get("ExposureTime")))
    add("ISO 速度", _format_iso(tags))
    add("露出補正", _format_signed_fraction(tags.get("ExposureBiasValue"), " ステップ"))
    add("焦点距離", _format_fraction(tags.get("FocalLength"), " mm"))
    add("最大絞り", _format_fraction(tags.get("MaxApertureValue")))
    add("測光モード", _format_choice(tags.get("MeteringMode"), METERING_MODE))
    add("対象の距離", _format_fraction(tags.get("SubjectDistance"), " m"))
    add("フラッシュ モード", _format_flash(tags.get("Flash")))
    add("35mm 焦点距離", _format_plain(tags.get("FocalLengthIn35mmFilm")))
    add("レンズ メーカー", _format_plain(tags.get("LensMake")))
    add("レンズ モデル", _format_plain(tags.get("LensModel")))
    add("コントラスト", _format_choice(tags.get("Contrast"), NORMAL_SOFT_HARD))
    add("明るさ", _format_fraction(tags.get("BrightnessValue")))
    add("光源", _format_choice(tags.get("LightSource"), LIGHT_SOURCE))
    add("露出プログラム", _format_choice(tags.get("ExposureProgram"), EXPOSURE_PROGRAM))
    add("彩度", _format_choice(tags.get("Saturation"), NORMAL_LOW_HIGH))
    add("鮮明度", _format_choice(tags.get("Sharpness"), NORMAL_SOFT_HARD))
    add("ホワイト バランス", _format_choice(tags.get("WhiteBalance"), WHITE_BALANCE))
    add("デジタル ズーム", _format_fraction(tags.get("DigitalZoomRatio")))
    add("EXIF バージョン", _format_exif_version(tags.get("ExifVersion")))

    width = _int_or_none(tags.get("PixelXDimension")) or header.width
    height = _int_or_none(tags.get("PixelYDimension")) or header.height
    bit_depth = _bit_depth(tags.get("BitsPerSample"), header.bit_depth)
    compression = _format_choice(tags.get("Compression"), COMPRESSION) or header.compression
    color = _format_choice(tags.get("ColorSpace"), COLOR_SPACE) or header.color_representation

    add("大きさ", _format_dimensions(width, height))
    add("幅", f"{width} ピクセル" if width else None)
    add("高さ", f"{height} ピクセル" if height else None)
    add("水平方向の解像度", _format_resolution(tags.get("XResolution"), tags.get("ResolutionUnit")))
    add("垂直方向の解像度", _format_resolution(tags.get("YResolution"), tags.get("ResolutionUnit")))
    add("ビットの深さ", str(bit_depth) if bit_depth else None)
    add("圧縮", compression)
    add("解像度の単位", _format_plain(tags.get("ResolutionUnit")))
    add("色の表現", color)
    add("圧縮ビット/ピクセル", _format_plain(tags.get("SamplesPerPixel")))

    return ImageMetadata(
        rows=rows,
        width=width,
        height=height,
        bit_depth=bit_depth,
        color_representation=color,
        compression=compression,
    )


def _read_png_metadata(data: bytes) -> ImageMetadata:
    if len(data) < 33 or not data.startswith(b"\x89PNG\r\n\x1a\n"):
        return ImageMetadata()
    if data[12:16] != b"IHDR":
        return ImageMetadata()
    width = int.from_bytes(data[16:20], "big")
    height = int.from_bytes(data[20:24], "big")
    bit_depth = data[24]
    color_type = data[25]
    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}.get(color_type, 1)
    color = {
        0: "グレースケール",
        2: "RGB",
        3: "インデックスカラー",
        4: "グレースケール + アルファ",
        6: "RGBA",
    }.get(color_type)
    return _metadata_from_tags(
        {},
        ImageMetadata(
            width=width,
            height=height,
            bit_depth=bit_depth * channels,
            color_representation=color,
            compression="PNG",
        ),
    )


def _read_gif_metadata(data: bytes) -> ImageMetadata:
    if len(data) < 10 or data[:6] not in {b"GIF87a", b"GIF89a"}:
        return ImageMetadata()
    width = int.from_bytes(data[6:8], "little")
    height = int.from_bytes(data[8:10], "little")
    palette_depth = ((data[10] & 0b00000111) + 1) if len(data) > 10 else 8
    return _metadata_from_tags(
        {},
        ImageMetadata(
            width=width,
            height=height,
            bit_depth=palette_depth,
            color_representation="インデックスカラー",
            compression="LZW",
        ),
    )


def _read_bmp_metadata(data: bytes) -> ImageMetadata:
    if len(data) < 30 or not data.startswith(b"BM"):
        return ImageMetadata()
    dib_size = int.from_bytes(data[14:18], "little")
    if dib_size < 12 or 14 + dib_size > len(data):
        return ImageMetadata()
    if dib_size == 12:
        width = int.from_bytes(data[18:20], "little")
        height = int.from_bytes(data[20:22], "little")
        bit_depth = int.from_bytes(data[24:26], "little")
    else:
        width = int.from_bytes(data[18:22], "little", signed=True)
        height = abs(int.from_bytes(data[22:26], "little", signed=True))
        bit_depth = int.from_bytes(data[28:30], "little")
    color = "RGB" if bit_depth >= 24 else "インデックスカラー"
    return _metadata_from_tags(
        {},
        ImageMetadata(
            width=width,
            height=height,
            bit_depth=bit_depth,
            color_representation=color,
            compression="BMP",
        ),
    )


def _unpack(data: bytes, prefix: str, fmt: str, offset: int) -> int:
    size = struct.calcsize(fmt)
    if offset + size > len(data):
        return 0
    return struct.unpack(f"{prefix}{fmt}", data[offset : offset + size])[0]


def _fraction_or_none(numerator: int, denominator: int) -> Fraction | None:
    if denominator == 0:
        return None
    return Fraction(numerator, denominator)


def _row_adder(rows: list[tuple[str, str]]):
    def add(label: str, value: str | None) -> None:
        if value:
            rows.append((label, value))

    return add


def _format_plain(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, bytes):
        return value.split(b"\x00", 1)[0].decode("utf-8", errors="replace").strip() or None
    if isinstance(value, tuple):
        return ", ".join(_format_plain(item) or "" for item in value).strip(", ") or None
    return str(value).split("\x00", 1)[0].strip() or None


def _format_datetime(value: object) -> str | None:
    text = _format_plain(value)
    if not text:
        return None
    try:
        return datetime.strptime(text, "%Y:%m:%d %H:%M:%S").strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        return text


def _format_fraction(value: object, suffix: str = "") -> str | None:
    if isinstance(value, Fraction):
        as_float = float(value)
        if value.denominator == 1:
            text = str(value.numerator)
        else:
            text = f"{as_float:.6g}"
        return f"{text}{suffix}"
    return _format_plain(value)


def _format_signed_fraction(value: object, suffix: str = "") -> str | None:
    text = _format_fraction(value)
    if text is None:
        return None
    if not text.startswith("-") and text != "0":
        text = f"+{text}"
    return f"{text}{suffix}"


def _format_exposure_time(value: object) -> str | None:
    if not isinstance(value, Fraction):
        return _format_plain(value)
    if value.numerator == 1:
        return f"1/{value.denominator} 秒"
    seconds = float(value)
    if seconds < 1:
        reciprocal = round(1 / seconds)
        return f"1/{reciprocal} 秒"
    return f"{seconds:.6g} 秒"


def _format_f_number(value: object) -> str | None:
    if not isinstance(value, Fraction):
        return _format_plain(value)
    return f"f/{float(value):.3g}"


def _format_iso(tags: dict[str, object]) -> str | None:
    value = tags.get("ISOSpeedRatings") or tags.get("PhotographicSensitivity")
    if isinstance(value, tuple):
        value = value[0] if value else None
    if value is None:
        return None
    return f"ISO-{value}"


def _format_choice(value: object, choices: dict[int, str]) -> str | None:
    if isinstance(value, tuple):
        value = value[0] if value else None
    if not isinstance(value, int):
        return _format_plain(value)
    return choices.get(value, str(value))


def _format_flash(value: object) -> str | None:
    if not isinstance(value, int):
        return _format_plain(value)
    fired = bool(value & 1)
    mode_bits = (value >> 3) & 0b11
    if not fired:
        return "フラッシュなし"
    if mode_bits == 3:
        return "フラッシュあり (自動)"
    if mode_bits == 2:
        return "フラッシュあり (強制)"
    return "フラッシュあり"


def _format_exif_version(value: object) -> str | None:
    if isinstance(value, bytes):
        return value.decode("ascii", errors="replace").rstrip("\x00")
    return _format_plain(value)


def _format_dimensions(width: int | None, height: int | None) -> str | None:
    if width is None or height is None:
        return None
    return f"{width} x {height}"


def _format_resolution(value: object, unit_value: object) -> str | None:
    number = _format_fraction(value)
    if number is None:
        return None
    unit = _format_choice(unit_value, RESOLUTION_UNIT) or "dpi"
    return f"{number} {unit}"


def _int_or_none(value: object) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, Fraction) and value.denominator == 1:
        return value.numerator
    return None


def _bit_depth(value: object, fallback: int | None) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, tuple) and all(isinstance(item, int) for item in value):
        return sum(value)
    return fallback
