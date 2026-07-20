"""Input validation shared by forms and services."""

from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from .constants import ALLOWED_IMAGE_EXTENSIONS, CLIENT_SOURCES, DESIGN_TYPES, ORDER_STATUSES


class ValidationError(ValueError):
    """A user-correctable validation error."""


def require_text(value: Any, label: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValidationError(f"{label}不能为空")
    return text


def validate_non_negative(value: Any, label: str = "数值") -> Decimal:
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValidationError(f"{label}必须是有效数字") from exc
    if not number.is_finite():
        raise ValidationError(f"{label}必须是有限数字")
    if number < 0:
        raise ValidationError(f"{label}不能小于 0")
    return number


def validate_non_negative_int(value: Any, label: str = "次数") -> int:
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"{label}必须是整数") from exc
    if number < 0:
        raise ValidationError(f"{label}不能小于 0")
    return number


def parse_deadline(value: Any) -> datetime:
    """Normalize form date, datetime, or ISO text to a datetime."""

    if value is None or value == "":
        raise ValidationError("截止日期不能为空")
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, time(hour=23, minute=59, second=59))
    if isinstance(value, str):
        candidate = value.strip()
        if not candidate:
            raise ValidationError("截止日期不能为空")
        try:
            return datetime.fromisoformat(candidate.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValidationError("截止日期格式不正确") from exc
    raise ValidationError("截止日期格式不正确")


def validate_image_filename(file_name: str) -> str:
    clean_name = Path(file_name or "").name
    if not clean_name:
        raise ValidationError("文件名不能为空")
    if Path(clean_name).suffix.lower() not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValidationError("图片格式必须是 PNG、JPG 或 WEBP")
    return clean_name


def validate_upload_size(size_bytes: int, max_size_mb: int | float = 20) -> None:
    if size_bytes < 0:
        raise ValidationError("文件大小无效")
    if size_bytes > float(max_size_mb) * 1024 * 1024:
        raise ValidationError(f"上传文件不能超过 {max_size_mb:g}MB")


def validate_client_data(data: dict[str, Any]) -> dict[str, Any]:
    cleaned = dict(data)
    cleaned["name"] = require_text(data.get("name"), "客户姓名")
    cleaned["contact"] = str(data.get("contact") or "").strip()
    source = str(data.get("source") or "其他").strip()
    cleaned["source"] = source if source in CLIENT_SOURCES else "其他"
    cleaned["notes"] = str(data.get("notes") or "").strip()
    return cleaned


def validate_order_data(data: dict[str, Any]) -> dict[str, Any]:
    """Validate and normalize the minimum order payload."""

    cleaned = dict(data)
    cleaned["title"] = require_text(data.get("title"), "订单标题")
    design_type = str(data.get("design_type") or "其他").strip()
    cleaned["design_type"] = design_type if design_type in DESIGN_TYPES else "其他"
    status = str(data.get("status") or "待沟通").strip()
    if status not in ORDER_STATUSES:
        raise ValidationError("订单状态无效")
    cleaned["status"] = status
    cleaned["deadline"] = parse_deadline(data.get("deadline"))
    cleaned["price"] = validate_non_negative(data.get("price", 0), "价格")
    cleaned["revision_limit"] = validate_non_negative_int(data.get("revision_limit", 1), "免费修改次数")
    cleaned["revision_used"] = validate_non_negative_int(data.get("revision_used", 0), "已用修改次数")
    return cleaned
