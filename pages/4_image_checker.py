"""图片尺寸、DPI 与印刷清晰度检测页面。"""

from __future__ import annotations

import math
import os
from fractions import Fraction
from io import BytesIO
from typing import Any

import streamlit as st
from PIL import Image, UnidentifiedImageError

from services import image_service
from ui.components import page_header, section_title
from ui.theme import apply_theme


ALLOWED_FORMATS = {"PNG", "JPEG", "WEBP"}
USAGE_OPTIONS = ["自动判断", "朋友圈", "小红书", "手机端宣传", "高清印刷", "大型背景墙"]


def _file_size_label(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes / 1024 / 1024:.2f} MB"


def _number(value: Any, default: float = 0) -> float:
    if isinstance(value, (tuple, list)) and value:
        value = value[0]
    try:
        parsed = float(value)
        return default if math.isnan(parsed) else parsed
    except (TypeError, ValueError):
        return default


def _fallback_analysis(file_bytes: bytes) -> dict[str, Any]:
    """服务不可用时仍可完成基础检测，避免页面崩溃。"""
    with Image.open(BytesIO(file_bytes)) as image:
        image.load()
        width, height = image.size
        image_format = (image.format or "未知").upper()
        dpi_value = image.info.get("dpi", (72, 72))
        if isinstance(dpi_value, (int, float)):
            dpi_x = dpi_y = float(dpi_value)
        else:
            dpi_x = _number(dpi_value[0] if dpi_value else 72, 72)
            dpi_y = _number(dpi_value[1] if len(dpi_value) > 1 else dpi_x, dpi_x)
        has_alpha = image.mode in {"RGBA", "LA"} or (
            image.mode == "P" and "transparency" in image.info
        )

    ratio = Fraction(width, height).limit_denominator(30)
    ratio_value = width / height
    suitable: list[str] = []
    unsuitable: list[str] = []
    if width >= 1080 and height >= 1080:
        suitable.append("手机端宣传")
    if 0.68 <= ratio_value <= 0.86 and width >= 900:
        suitable.extend(["朋友圈竖版", "小红书"])
    if 0.95 <= ratio_value <= 1.05 and width >= 900:
        suitable.extend(["朋友圈方图", "社交媒体封面"])
    if width >= 2480 and height >= 3508:
        suitable.append("A4 高清印刷（需结合实际 DPI）")
    if min(width, height) < 1000:
        unsuitable.extend(["大型背景墙", "近距离高清印刷"])
    elif min(width, height) < 2000:
        unsuitable.append("超大尺寸近距离印刷")
    if not suitable:
        suitable.append("网页预览与小尺寸数字展示")

    return {
        "width": width,
        "height": height,
        "format": image_format,
        "file_size_bytes": len(file_bytes),
        "dpi_x": dpi_x,
        "dpi_y": dpi_y,
        "aspect_ratio": f"{ratio.numerator}:{ratio.denominator}",
        "has_alpha": has_alpha,
        "suitable_for": suitable,
        "not_suitable_for": unsuitable,
    }


def _analyze(file_bytes: bytes, usage: str) -> dict[str, Any]:
    """调用服务层，并把不同版本的返回值归一到页面所需结构。"""
    result: Any = None
    try:
        result = image_service.analyze_image(
            BytesIO(file_bytes), usage=None if usage == "自动判断" else usage
        )
    except TypeError:
        result = image_service.analyze_image(BytesIO(file_bytes))
    except Exception:
        result = None

    if not isinstance(result, dict):
        return _fallback_analysis(file_bytes)

    fallback = _fallback_analysis(file_bytes)
    dpi = result.get("dpi")
    dpi_x = result.get("dpi_x") or result.get("horizontal_dpi")
    dpi_y = result.get("dpi_y") or result.get("vertical_dpi")
    if dpi_x is None and isinstance(dpi, (tuple, list)) and dpi:
        dpi_x = dpi[0]
    if dpi_y is None and isinstance(dpi, (tuple, list)) and dpi:
        dpi_y = dpi[1] if len(dpi) > 1 else dpi[0]
    if dpi_x is None and isinstance(dpi, (int, float)):
        dpi_x = dpi
    if dpi_y is None and isinstance(dpi, (int, float)):
        dpi_y = dpi

    suitable = (
        result.get("suitable_for")
        or result.get("suitable_usages")
        or result.get("recommended_usages")
        or fallback["suitable_for"]
    )
    unsuitable = (
        result.get("not_suitable_for")
        or result.get("unsuitable_usages")
        or fallback["not_suitable_for"]
    )
    if isinstance(suitable, str):
        suitable = [suitable]
    if isinstance(unsuitable, str):
        unsuitable = [unsuitable]

    normalized = {
        "width": int(result.get("width") or fallback["width"]),
        "height": int(result.get("height") or fallback["height"]),
        "format": str(result.get("format") or fallback["format"]).upper(),
        "file_size_bytes": int(
            result.get("file_size_bytes")
            or result.get("file_size")
            or fallback["file_size_bytes"]
        ),
        "dpi_x": _number(dpi_x, fallback["dpi_x"]),
        "dpi_y": _number(dpi_y, fallback["dpi_y"]),
        "aspect_ratio": result.get("aspect_ratio") or fallback["aspect_ratio"],
        "has_alpha": bool(
            result.get(
                "has_alpha",
                result.get(
                    "has_alpha_channel",
                    result.get("has_transparency", fallback["has_alpha"]),
                ),
            )
        ),
        "suitable_for": list(suitable),
        "not_suitable_for": list(unsuitable),
        "warning": result.get("warning") or result.get("usage_warning"),
        "usage_assessment": result.get("usage_assessment"),
    }
    return normalized


def _fallback_print_quality(
    width_px: int,
    height_px: int,
    print_width_cm: float,
    print_height_cm: float,
) -> dict[str, Any]:
    dpi_x = width_px / (print_width_cm / 2.54)
    dpi_y = height_px / (print_height_cm / 2.54)
    effective_dpi = min(dpi_x, dpi_y)

    if effective_dpi >= 300:
        level = "高质量印刷"
        message = "清晰度充足，适合近距离观看的高质量印刷。"
        tone = "success"
    elif effective_dpi >= 150:
        level = "普通印刷"
        message = "适合常规印刷；精细文字和细节仍建议先打样。"
        tone = "success"
    elif effective_dpi >= 72:
        level = "远距离观看可接受"
        message = "近看可能偏软，用于背景墙等远距离场景通常可接受。"
        tone = "warning"
    else:
        level = "明显模糊风险"
        message = "该图片不适合近距离高清印刷，用于大型背景墙也可能出现模糊。"
        tone = "error"

    return {
        "dpi_x": dpi_x,
        "dpi_y": dpi_y,
        "effective_dpi": effective_dpi,
        "risk_level": level,
        "message": message,
        "tone": tone,
    }


def _calculate_print_quality(
    width_px: int,
    height_px: int,
    print_width_cm: float,
    print_height_cm: float,
) -> dict[str, Any]:
    try:
        result = image_service.calculate_print_quality(
            width_px,
            height_px,
            print_width_cm,
            print_height_cm,
        )
    except Exception:
        result = None

    fallback = _fallback_print_quality(
        width_px, height_px, print_width_cm, print_height_cm
    )
    if not isinstance(result, dict):
        return fallback

    effective_dpi = _number(
        result.get("effective_dpi")
        or result.get("print_dpi")
        or result.get("dpi"),
        fallback["effective_dpi"],
    )
    level = result.get("risk_level") or result.get("quality_level") or fallback["risk_level"]
    message = result.get("message") or result.get("recommendation") or fallback["message"]
    if effective_dpi >= 150:
        tone = "success"
    elif effective_dpi >= 72:
        tone = "warning"
    else:
        tone = "error"
    return {
        "dpi_x": _number(result.get("dpi_x") or result.get("horizontal_dpi"), fallback["dpi_x"]),
        "dpi_y": _number(result.get("dpi_y") or result.get("vertical_dpi"), fallback["dpi_y"]),
        "effective_dpi": effective_dpi,
        "risk_level": str(level),
        "message": str(message),
        "tone": tone,
    }


def _info_card(label: str, value: str, helper: str = "") -> None:
    with st.container(border=True):
        st.caption(label)
        st.markdown(f"### {value}")
        if helper:
            st.caption(helper)


apply_theme()
page_header("图片质量检测", "上传交付稿，快速核对尺寸、透明通道和实际印刷清晰度。")

section_title("上传设计稿")
control_col, upload_col = st.columns([1, 2])
with control_col:
    usage = st.selectbox("预期用途", USAGE_OPTIONS, help="选择用途后，系统会给出更有针对性的建议。")
    max_upload_mb = max(1, int(os.getenv("MAX_UPLOAD_MB", "20")))
    st.caption(f"支持 PNG、JPG、WEBP，单个文件不超过 {max_upload_mb}MB。")
with upload_col:
    uploaded_file = st.file_uploader(
        "选择图片",
        type=["png", "jpg", "jpeg", "webp"],
        label_visibility="collapsed",
    )

if uploaded_file is None:
    with st.container(border=True):
        st.markdown("#### 把待交付图片拖到这里")
        st.caption("上传后会立即显示像素、DPI、比例和适用场景，不会修改原文件。")
    st.stop()

file_bytes = uploaded_file.getvalue()
if len(file_bytes) > max_upload_mb * 1024 * 1024:
    st.error(f"文件超过 {max_upload_mb}MB，请压缩后重新上传。")
    st.stop()

try:
    with Image.open(BytesIO(file_bytes)) as source_image:
        source_format = (source_image.format or "").upper()
        source_image.verify()
except (UnidentifiedImageError, OSError, ValueError):
    st.error("无法读取这张图片，请确认文件未损坏且格式为 PNG、JPG 或 WEBP。")
    st.stop()

if source_format not in ALLOWED_FORMATS:
    st.error("暂不支持该图片格式，请转换为 PNG、JPG 或 WEBP 后重试。")
    st.stop()

try:
    analysis = _analyze(file_bytes, usage)
except Exception as exc:
    st.error("图片检测暂时不可用，请更换文件或稍后重试。")
    st.caption(f"错误摘要：{exc}")
    st.stop()

preview_col, result_col = st.columns([1, 1.35], vertical_alignment="top")
with preview_col:
    st.image(file_bytes, caption=uploaded_file.name, width="stretch")
with result_col:
    st.markdown("#### 文件概览")
    first_row = st.columns(2)
    with first_row[0]:
        _info_card("图片尺寸", f"{analysis['width']} × {analysis['height']} px")
    with first_row[1]:
        _info_card("文件格式", analysis["format"], _file_size_label(analysis["file_size_bytes"]))
    second_row = st.columns(2)
    with second_row[0]:
        _info_card("文件 DPI", f"{analysis['dpi_x']:.0f} × {analysis['dpi_y']:.0f}")
    with second_row[1]:
        transparency = "包含透明通道" if analysis["has_alpha"] else "无透明通道"
        _info_card("宽高比例", str(analysis["aspect_ratio"]), transparency)

st.write("")
section_title("使用建议")
suitable_col, unsuitable_col = st.columns(2)
with suitable_col:
    with st.container(border=True):
        st.markdown("#### 适合")
        for item in analysis["suitable_for"]:
            st.markdown(f"- {item}")
with unsuitable_col:
    with st.container(border=True):
        st.markdown("#### 需要谨慎")
        if analysis["not_suitable_for"]:
            for item in analysis["not_suitable_for"]:
                st.markdown(f"- {item}")
        else:
            st.caption("暂未发现明显的用途限制，印刷前仍建议按实际尺寸检查。")

if analysis.get("warning"):
    st.warning(str(analysis["warning"]))

usage_assessment = analysis.get("usage_assessment")
if isinstance(usage_assessment, dict) and usage != "自动判断":
    assessment_text = str(usage_assessment.get("reason") or "已完成所选用途检查。")
    if usage_assessment.get("suitable"):
        st.success(f"**{usage}：可用** · {assessment_text}")
    else:
        st.warning(f"**{usage}：建议谨慎** · {assessment_text}")

st.write("")
section_title("实际印刷风险")
st.caption("输入成品的实际厘米尺寸，系统会分别计算横向和纵向 DPI，并以较低值评估风险。")

size_col_1, size_col_2, spacer_col = st.columns([1, 1, 1.2])
with size_col_1:
    print_width_cm = st.number_input(
        "成品宽度（厘米）", min_value=0.1, max_value=5000.0, value=100.0, step=1.0
    )
with size_col_2:
    print_height_cm = st.number_input(
        "成品高度（厘米）", min_value=0.1, max_value=5000.0, value=50.0, step=1.0
    )

quality = _calculate_print_quality(
    analysis["width"],
    analysis["height"],
    print_width_cm,
    print_height_cm,
)

quality_cols = st.columns(3)
with quality_cols[0]:
    _info_card("横向打印 DPI", f"{quality['dpi_x']:.1f}")
with quality_cols[1]:
    _info_card("纵向打印 DPI", f"{quality['dpi_y']:.1f}")
with quality_cols[2]:
    _info_card("有效打印 DPI", f"{quality['effective_dpi']:.1f}", quality["risk_level"])

message = f"**{quality['risk_level']}**  ·  {quality['message']}"
if quality["tone"] == "success":
    st.success(message)
elif quality["tone"] == "warning":
    st.warning(message)
else:
    st.error(message)

with st.expander("查看 DPI 判断标准"):
    st.markdown(
        """
        - **300 DPI 以上：** 高质量印刷，适合近距离观看。
        - **150–299 DPI：** 普通印刷，精细内容建议打样。
        - **72–149 DPI：** 远距离观看通常可接受。
        - **72 DPI 以下：** 存在明显模糊风险。
        """
    )
