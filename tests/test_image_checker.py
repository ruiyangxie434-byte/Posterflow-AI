from io import BytesIO

import pytest
from PIL import Image

from services.image_service import ImageValidationError, analyze_image, calculate_print_quality


def _image_bytes(mode="RGB", size=(1080, 1440), image_format="PNG", **save_kwargs):
    buffer = BytesIO()
    Image.new(mode, size, (255, 0, 0, 128) if mode == "RGBA" else "red").save(
        buffer, format=image_format, **save_kwargs
    )
    buffer.seek(0)
    buffer.name = f"test.{image_format.lower()}"
    return buffer


def test_analyze_png_metadata_ratio_and_transparency():
    result = analyze_image(_image_bytes(mode="RGBA"), usage="朋友圈")
    assert result["width"] == 1080
    assert result["height"] == 1440
    assert result["format"] == "PNG"
    assert result["aspect_ratio"] == "3:4"
    assert result["has_alpha_channel"] is True
    assert result["contains_transparent_pixels"] is True
    assert "朋友圈" in result["suitable_for"]


def test_analyze_jpeg_dpi():
    result = analyze_image(_image_bytes(image_format="JPEG", dpi=(300, 300)))
    assert result["format"] == "JPG"
    assert result["dpi"] == pytest.approx(300, abs=1)


def test_invalid_image_is_user_correctable_error():
    with pytest.raises(ImageValidationError, match="无法打开|损坏"):
        analyze_image(b"not an image")


@pytest.mark.parametrize(
    ("pixels", "cm", "level"),
    [
        (3000, 25.4, "高质量印刷"),
        (2000, 25.4, "普通印刷"),
        (1000, 25.4, "远距离观看可接受"),
        (600, 25.4, "存在明显模糊风险"),
    ],
)
def test_print_quality_four_levels(pixels, cm, level):
    result = calculate_print_quality(pixels, pixels, cm, cm)
    assert result["risk_level"] == level


def test_large_background_risk_uses_limiting_axis():
    result = calculate_print_quality(1080, 1440, 1000, 500)
    assert result["effective_dpi"] < 72
    assert result["risk"] == "高"
