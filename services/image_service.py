"""Image metadata and physical-print quality checks."""

from __future__ import annotations

from io import BytesIO
from math import gcd, isfinite
from pathlib import Path
from typing import Any, BinaryIO

from PIL import Image, UnidentifiedImageError

from utils.constants import ALLOWED_IMAGE_FORMATS, MAX_UPLOAD_SIZE_MB


class ImageValidationError(ValueError):
    """Raised when an uploaded file cannot be safely analyzed as an image."""


def _read_source(source: str | Path | bytes | bytearray | BinaryIO) -> tuple[bytes, str]:
    if isinstance(source, (str, Path)):
        path = Path(source)
        try:
            return path.read_bytes(), path.name
        except OSError as exc:
            raise ImageValidationError("无法读取图片文件") from exc
    if isinstance(source, (bytes, bytearray)):
        return bytes(source), "uploaded-image"

    name = getattr(source, "name", "uploaded-image")
    try:
        if hasattr(source, "getvalue"):
            return bytes(source.getvalue()), str(name)
        position = source.tell() if hasattr(source, "tell") else None
        data = source.read()
        if position is not None and hasattr(source, "seek"):
            source.seek(position)
        return bytes(data), str(name)
    except (OSError, TypeError, ValueError) as exc:
        raise ImageValidationError("无法读取上传的图片") from exc


def _extract_dpi(info: dict[str, Any]) -> tuple[float, float]:
    raw = info.get("dpi", (72.0, 72.0))
    if isinstance(raw, (int, float)):
        x = y = float(raw)
    elif isinstance(raw, (tuple, list)) and raw:
        x = float(raw[0] or 72.0)
        y = float((raw[1] if len(raw) > 1 else raw[0]) or 72.0)
    else:
        x = y = 72.0
    if x <= 0:
        x = 72.0
    if y <= 0:
        y = 72.0
    return round(x, 2), round(y, 2)


def _usage_lists(width: int, height: int) -> tuple[list[str], list[str]]:
    suitable: list[str] = []
    unsuitable: list[str] = []
    shortest = min(width, height)
    longest = max(width, height)

    if shortest >= 720:
        suitable.append("手机端宣传")
    else:
        unsuitable.append("手机端高清宣传")
    if width >= 1080 and height >= 1080:
        suitable.append("朋友圈")
    else:
        unsuitable.append("朋友圈高清发布")
    ratio = width / height
    if width >= 1080 and height >= 1080 and 0.7 <= ratio <= 1.0:
        suitable.append("小红书")
    else:
        unsuitable.append("小红书竖版封面")
    if shortest >= 2400:
        suitable.append("中小尺寸印刷")
    else:
        unsuitable.append("近距离高清印刷")
    if shortest >= 5000 and longest >= 8000:
        suitable.append("大型背景墙（需结合实际尺寸复核）")
    else:
        unsuitable.extend(["大型背景墙", "10米喷绘"])
    return suitable, unsuitable


def assess_usage(width: int, height: int, usage: str | None) -> dict[str, Any] | None:
    """Provide a conservative pixel-dimension assessment for a named use."""

    if not usage:
        return None
    normalized = usage.strip()
    suitable, unsuitable = _usage_lists(width, height)
    matching_bad = [item for item in unsuitable if normalized in item or item in normalized]
    matching_good = [item for item in suitable if normalized in item or item in normalized]
    if matching_good:
        return {"usage": normalized, "suitable": True, "reason": f"像素尺寸可用于{matching_good[0]}"}
    if matching_bad:
        return {"usage": normalized, "suitable": False, "reason": f"像素尺寸不足以稳妥用于{matching_bad[0]}"}
    return {
        "usage": normalized,
        "suitable": min(width, height) >= 1080,
        "reason": "常规数字用途可接受；印刷仍需输入实际尺寸计算 DPI"
        if min(width, height) >= 1080
        else "短边低于 1080px，建议使用更高分辨率文件",
    }


def analyze_image(
    source: str | Path | bytes | bytearray | BinaryIO,
    usage: str | None = None,
    *,
    max_size_mb: int | float = MAX_UPLOAD_SIZE_MB,
) -> dict[str, Any]:
    """Read safe metadata from a PNG, JPEG, or WEBP image.

    The returned dictionary is deliberately Streamlit-friendly and does not
    retain an open file handle.
    """

    data, file_name = _read_source(source)
    max_bytes = int(float(max_size_mb) * 1024 * 1024)
    if not data:
        raise ImageValidationError("图片文件为空")
    if len(data) > max_bytes:
        raise ImageValidationError(f"图片不能超过 {max_size_mb:g}MB")

    try:
        with Image.open(BytesIO(data)) as image:
            image.verify()
        with Image.open(BytesIO(data)) as image:
            image_format = (image.format or "").upper()
            if image_format not in ALLOWED_IMAGE_FORMATS:
                raise ImageValidationError("仅支持 PNG、JPG 和 WEBP 图片")
            width, height = image.size
            if width <= 0 or height <= 0:
                raise ImageValidationError("图片尺寸无效")
            dpi_x, dpi_y = _extract_dpi(image.info)
            bands = image.getbands()
            has_alpha_channel = "A" in bands or "transparency" in image.info
            contains_transparent_pixels = False
            if "A" in bands:
                alpha_extrema = image.getchannel("A").getextrema()
                contains_transparent_pixels = bool(alpha_extrema and alpha_extrema[0] < 255)
            elif "transparency" in image.info:
                contains_transparent_pixels = True
    except ImageValidationError:
        raise
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError) as exc:
        raise ImageValidationError("图片无法打开或文件已损坏") from exc

    divisor = gcd(width, height)
    suitable, unsuitable = _usage_lists(width, height)
    result = {
        "file_name": file_name,
        "width": width,
        "height": height,
        "dimensions": f"{width}×{height}px",
        "format": "JPG" if image_format == "JPEG" else image_format,
        "file_size_bytes": len(data),
        "file_size_mb": round(len(data) / (1024 * 1024), 2),
        "dpi": round(min(dpi_x, dpi_y), 2),
        "dpi_x": dpi_x,
        "dpi_y": dpi_y,
        "aspect_ratio": f"{width // divisor}:{height // divisor}",
        "aspect_ratio_value": round(width / height, 4),
        "has_alpha_channel": has_alpha_channel,
        "has_alpha": has_alpha_channel,
        "has_transparency": has_alpha_channel,
        "contains_transparent_pixels": contains_transparent_pixels,
        "suitable_for": suitable,
        "not_suitable_for": unsuitable,
        "usage_assessment": assess_usage(width, height, usage),
    }
    return result


def classify_print_dpi(effective_dpi: float) -> dict[str, str]:
    """Map effective physical DPI to the four agreed risk levels."""

    if effective_dpi >= 300:
        return {"risk_level": "高质量印刷", "risk": "低", "message": "清晰度适合近距离高质量印刷。"}
    if effective_dpi >= 150:
        return {"risk_level": "普通印刷", "risk": "较低", "message": "清晰度适合常规印刷。"}
    if effective_dpi >= 72:
        return {
            "risk_level": "远距离观看可接受",
            "risk": "中",
            "message": "近看可能不够清晰，较适合远距离观看。",
        }
    return {
        "risk_level": "存在明显模糊风险",
        "risk": "高",
        "message": "该图片不适合近距离高清印刷，用于大型背景墙可能出现明显模糊。",
    }


def calculate_print_quality(
    width_px: int | float,
    height_px: int | float,
    print_width_cm: int | float,
    print_height_cm: int | float,
) -> dict[str, Any]:
    """Calculate physical DPI for both axes and report the limiting result."""

    try:
        width_px_value = float(width_px)
        height_px_value = float(height_px)
        width_cm_value = float(print_width_cm)
        height_cm_value = float(print_height_cm)
    except (TypeError, ValueError) as exc:
        raise ValueError("像素和印刷尺寸必须是有效数字") from exc
    if not all(isfinite(value) for value in (width_px_value, height_px_value, width_cm_value, height_cm_value)):
        raise ValueError("像素和印刷尺寸必须是有限数字")
    if min(width_px_value, height_px_value, width_cm_value, height_cm_value) <= 0:
        raise ValueError("像素和印刷尺寸必须大于 0")

    dpi_x = width_px_value / (width_cm_value / 2.54)
    dpi_y = height_px_value / (height_cm_value / 2.54)
    effective = min(dpi_x, dpi_y)
    result: dict[str, Any] = {
        "dpi_x": round(dpi_x, 2),
        "dpi_y": round(dpi_y, 2),
        "effective_dpi": round(effective, 2),
        "print_width_cm": width_cm_value,
        "print_height_cm": height_cm_value,
    }
    result.update(classify_print_dpi(effective))
    return result


def calculate_actual_print_dpi(
    width_px: int | float,
    height_px: int | float,
    print_width_cm: int | float,
    print_height_cm: int | float,
) -> dict[str, Any]:
    """Compatibility alias for :func:`calculate_print_quality`."""

    return calculate_print_quality(width_px, height_px, print_width_cm, print_height_cm)


def calculate_print_dpi(
    width_px: int | float,
    height_px: int | float,
    print_width_cm: int | float,
    print_height_cm: int | float,
) -> float:
    """Return only the limiting physical DPI for simple callers."""

    return float(
        calculate_print_quality(width_px, height_px, print_width_cm, print_height_cm)[
            "effective_dpi"
        ]
    )


inspect_image = analyze_image
get_image_info = analyze_image
