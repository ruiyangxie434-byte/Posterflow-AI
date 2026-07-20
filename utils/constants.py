"""Central business constants for forms, validation, and calculations."""

APP_VERSION = "1.0.0"

DESIGN_TYPES = [
    "商业海报",
    "活动海报",
    "校园海报",
    "小红书封面",
    "朋友圈配图",
    "门店宣传",
    "大型背景墙",
    "PPT美化",
    "其他",
]

ORDER_STATUSES = [
    "待沟通",
    "待报价",
    "待付款",
    "设计中",
    "待客户确认",
    "修改中",
    "待尾款",
    "已完成",
    "已取消",
]

CLIENT_SOURCES = ["小红书", "闲鱼", "微信", "朋友圈", "同学介绍", "老客户", "其他"]

USAGE_SCENARIOS = [
    "朋友圈宣传",
    "小红书发布",
    "线上活动",
    "线下活动",
    "门店展示",
    "印刷宣传",
    "大型背景墙",
    "其他",
]

REVISION_TYPES = ["文字修改", "颜色修改", "排版修改", "图片替换", "尺寸调整", "整体方案重做", "其他"]
REVISION_STATUSES = ["待处理", "处理中", "已完成", "已取消"]

PAYMENT_TYPES = ["定金", "尾款", "全款", "修改费", "退款"]
PAYMENT_STATUSES = ["未付款", "已付定金", "部分付款", "已付清", "已退款"]
PAYMENT_STATUS = PAYMENT_STATUSES  # Backwards-compatible singular alias.
PAYMENT_METHODS = ["微信", "支付宝", "银行卡", "现金", "其他"]

BASE_PRICES = {
    "普通社交媒体海报": 49,
    "商业宣传海报": 69,
    "大型印刷设计": 99,
    "小红书封面": 39,
    "PPT单页美化": 20,
    "商业海报": 69,
    "活动海报": 69,
    "校园海报": 49,
    "朋友圈配图": 49,
    "门店宣传": 69,
    "大型背景墙": 99,
    "PPT美化": 20,
    "其他": 49,
}

QUOTE_FEES = {
    "urgent_24h": 20,
    "urgent_12h": 40,
    "source_file": 30,
    "print_processing": 20,
    "complex_cutout": 20,
    "overall_redesign": 30,
    "extra_revision": 10,
    "oversized": 30,
}

ALLOWED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
ALLOWED_IMAGE_FORMATS = {"PNG", "JPEG", "WEBP"}
MAX_UPLOAD_SIZE_MB = 20
