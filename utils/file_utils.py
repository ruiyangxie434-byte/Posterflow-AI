"""Safe file-name generation and upload persistence."""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import BinaryIO, Iterable
from uuid import uuid4

from .constants import ALLOWED_IMAGE_EXTENSIONS, MAX_UPLOAD_SIZE_MB
from .validators import ValidationError, validate_upload_size


def sanitize_filename(file_name: str, default_stem: str = "file") -> str:
    """Remove path components and characters unsafe on common filesystems."""

    name = Path(str(file_name or "")).name
    normalized = unicodedata.normalize("NFKC", name)
    suffix = Path(normalized).suffix.lower()
    stem = Path(normalized).stem
    stem = re.sub(r"[^\w\u4e00-\u9fff-]+", "-", stem, flags=re.UNICODE).strip("-_.")
    if not stem:
        stem = default_stem
    return f"{stem[:100]}{suffix}"


def unique_filename(file_name: str, prefix: str | None = None) -> str:
    clean = sanitize_filename(file_name)
    suffix = Path(clean).suffix.lower()
    stem = Path(clean).stem
    safe_prefix = sanitize_filename(prefix, "") if prefix else ""
    safe_prefix = Path(safe_prefix).stem.strip("-_")
    beginning = f"{safe_prefix}-" if safe_prefix else ""
    return f"{beginning}{stem}-{uuid4().hex[:12]}{suffix}"


def _read_upload(uploaded_file: bytes | bytearray | BinaryIO) -> bytes:
    if isinstance(uploaded_file, (bytes, bytearray)):
        return bytes(uploaded_file)
    if hasattr(uploaded_file, "getvalue"):
        return bytes(uploaded_file.getvalue())
    position = uploaded_file.tell() if hasattr(uploaded_file, "tell") else None
    data = uploaded_file.read()
    if position is not None and hasattr(uploaded_file, "seek"):
        uploaded_file.seek(position)
    return bytes(data)


def save_uploaded_file(
    uploaded_file: bytes | bytearray | BinaryIO,
    destination_dir: str | Path,
    *,
    file_name: str | None = None,
    allowed_extensions: Iterable[str] = ALLOWED_IMAGE_EXTENSIONS,
    max_size_mb: int | float = MAX_UPLOAD_SIZE_MB,
    prefix: str | None = None,
) -> Path:
    """Validate and save an uploaded file under a collision-proof name."""

    original_name = file_name or getattr(uploaded_file, "name", "upload")
    clean_name = sanitize_filename(str(original_name))
    suffix = Path(clean_name).suffix.lower()
    normalized_allowed = {ext.lower() if ext.startswith(".") else f".{ext.lower()}" for ext in allowed_extensions}
    if suffix not in normalized_allowed:
        raise ValidationError("不支持该文件格式")
    data = _read_upload(uploaded_file)
    validate_upload_size(len(data), max_size_mb)
    if not data:
        raise ValidationError("上传文件为空")

    target_dir = Path(destination_dir).resolve()
    target_dir.mkdir(parents=True, exist_ok=True)
    target = (target_dir / unique_filename(clean_name, prefix)).resolve()
    if target_dir not in target.parents:
        raise ValidationError("文件路径无效")
    target.write_bytes(data)
    return target


def delete_uploaded_file(file_path: str | Path, allowed_root: str | Path) -> bool:
    """Delete one known upload while preventing traversal outside its root."""

    root = Path(allowed_root).resolve()
    target = Path(file_path).resolve()
    if root != target and root not in target.parents:
        raise ValidationError("文件路径无效")
    if not target.exists():
        return False
    if not target.is_file():
        raise ValidationError("目标不是文件")
    target.unlink()
    return True
