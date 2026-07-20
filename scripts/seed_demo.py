"""Insert ten realistic Chinese demo orders without creating duplicates."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import select


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from database.db import get_session, init_db  # noqa: E402
from database.models import Client, Order, Payment, Quote, Revision  # noqa: E402
from services.quote_service import calculate_quote  # noqa: E402


DEMO_ORDERS = [
    {
        "client": ("林悦", "微信 demo_linyue", "微信"),
        "title": "[演示] 健身房暑期招生海报",
        "design_type": "商业海报",
        "requirement": "黑红色、力量感，朋友圈暑期招生宣传，突出限时优惠。",
        "usage": "朋友圈",
        "size": "1080×1440px",
        "style": "酷炫、运动、力量感",
        "color": "黑红",
        "status": "设计中",
        "days": 2,
        "urgent_hours": 24,
        "print_required": False,
        "paid_ratio": 0.5,
        "revisions": [("价格信息改为 699 元", "文字修改", True, 0, "已完成")],
    },
    {
        "client": ("陈一鸣", "小红书 @一鸣咖啡", "小红书"),
        "title": "[演示] 新品咖啡小红书封面",
        "design_type": "小红书封面",
        "requirement": "暖棕色，突出桂花拿铁新品和到店折扣。",
        "usage": "小红书",
        "size": "1080×1440px",
        "style": "温暖、生活方式",
        "color": "咖啡棕、奶油白",
        "status": "已完成",
        "days": -18,
        "paid_ratio": 1,
        "revisions": [],
    },
    {
        "client": ("周老师", "13800000003", "同学介绍"),
        "title": "[演示] 校园社团招新海报",
        "design_type": "校园海报",
        "requirement": "面向新生，活泼年轻，保留二维码和招新时间。",
        "usage": "校园公众号",
        "size": "1080×1920px",
        "style": "青春、明快",
        "color": "蓝黄",
        "status": "待客户确认",
        "days": 5,
        "paid_ratio": 0.5,
        "revisions": [("标题再大一些", "排版修改", True, 0, "已完成")],
    },
    {
        "client": ("王倩", "闲鱼用户 qian88", "闲鱼"),
        "title": "[演示] 美甲店开业宣传",
        "design_type": "门店宣传",
        "requirement": "轻奢风，开业首周八折，需要 A3 打印文件。",
        "usage": "门店印刷",
        "size": "A3",
        "style": "轻奢、女性化",
        "color": "裸粉、金色",
        "status": "修改中",
        "days": 3,
        "print_required": True,
        "paid_ratio": 0.5,
        "revisions": [
            ("模特图片换成手部特写", "图片替换", True, 0, "已完成"),
            ("折扣文字改成全场八折", "文字修改", False, 10, "处理中"),
        ],
    },
    {
        "client": ("赵宁", "微信 zhaoning_art", "朋友圈"),
        "title": "[演示] 音乐节活动主视觉",
        "design_type": "活动海报",
        "requirement": "电子音乐节，霓虹未来感，突出阵容与购票二维码。",
        "usage": "朋友圈",
        "size": "1242×1660px",
        "style": "未来、霓虹",
        "color": "紫蓝",
        "status": "待尾款",
        "days": 1,
        "urgent_hours": 12,
        "paid_ratio": 0.6,
        "revisions": [("调整艺人排序", "排版修改", True, 0, "已完成")],
    },
    {
        "client": ("许店长", "13900000006", "老客户"),
        "title": "[演示] 火锅店周年庆海报",
        "design_type": "商业海报",
        "requirement": "热闹红金风格，周年套餐优惠，需印刷和朋友圈两版。",
        "usage": "门店及朋友圈",
        "size": "A2 / 1080×1440px",
        "style": "热闹、传统节庆",
        "color": "红金",
        "status": "已完成",
        "days": -32,
        "print_required": True,
        "paid_ratio": 1,
        "revisions": [
            ("套餐价格更正", "文字修改", True, 0, "已完成"),
            ("整体改成国潮方向", "整体方案重做", False, 30, "已完成"),
        ],
    },
    {
        "client": ("孙同学", "微信 sun2026", "同学介绍"),
        "title": "[演示] 毕业答辩PPT美化",
        "design_type": "PPT美化",
        "requirement": "学术简洁风，先完成封面和目录两页。",
        "usage": "答辩投影",
        "size": "16:9",
        "style": "学术、简洁",
        "color": "深蓝、白",
        "status": "待付款",
        "days": 7,
        "paid_ratio": 0,
        "revisions": [],
    },
    {
        "client": ("高经理", "企业微信 gaom", "微信"),
        "title": "[演示] 商场五一大型背景墙",
        "design_type": "大型背景墙",
        "requirement": "10米主背景墙，家庭购物节主题，需要印刷文件处理。",
        "usage": "大型喷绘",
        "size": "1000×500cm",
        "style": "明亮、节日氛围",
        "color": "橙红、蓝",
        "status": "待报价",
        "days": 14,
        "print_required": True,
        "oversized": True,
        "paid_ratio": 0,
        "revisions": [],
    },
    {
        "client": ("何女士", "小红书 @禾木瑜伽", "小红书"),
        "title": "[演示] 瑜伽体验课朋友圈配图",
        "design_type": "朋友圈配图",
        "requirement": "清新安静，女性瑜伽体验课，预约方式醒目。",
        "usage": "朋友圈",
        "size": "1080×1440px",
        "style": "自然、呼吸感",
        "color": "鼠尾草绿、米白",
        "status": "待沟通",
        "days": 10,
        "paid_ratio": 0,
        "revisions": [],
    },
    {
        "client": ("吴老板", "闲鱼用户 wu-store", "闲鱼"),
        "title": "[演示] 夏季清仓促销海报",
        "design_type": "商业海报",
        "requirement": "服装店夏季清仓，全场五折起，画面冲击力强。",
        "usage": "朋友圈",
        "size": "1080×1440px",
        "style": "强促销、醒目",
        "color": "黄黑",
        "status": "已取消",
        "days": -5,
        "paid_ratio": 0,
        "revisions": [],
    },
]


def seed_demo() -> int:
    init_db()
    inserted = 0
    now = datetime.now(timezone.utc)
    with get_session() as session:
        for item in DEMO_ORDERS:
            if session.scalar(select(Order.id).where(Order.title == item["title"])) is not None:
                continue
            client_name, contact, source = item["client"]
            client = session.scalar(select(Client).where(Client.contact == contact))
            if client is None:
                client = Client(name=client_name, contact=contact, source=source, notes="演示客户")
                session.add(client)
                session.flush()

            quote = calculate_quote(
                item["design_type"],
                hours_until_deadline=item.get("urgent_hours"),
                print_required=item.get("print_required", False),
                oversized=item.get("oversized", False),
            )
            deadline = now + timedelta(days=item["days"])
            order = Order(
                client_id=client.id,
                title=item["title"],
                design_type=item["design_type"],
                original_requirement=item["requirement"],
                structured_requirement=json.dumps(
                    {"style": item["style"], "main_color": item["color"], "usage": item["usage"]},
                    ensure_ascii=False,
                ),
                usage=item["usage"],
                size=item["size"],
                style=item["style"],
                main_color=item["color"],
                status=item["status"],
                price=quote["final_price"],
                deadline=deadline,
                urgent=item.get("urgent_hours") is not None,
                source_file_required=False,
                print_required=item.get("print_required", False),
                revision_limit=1,
                revision_used=len(item["revisions"]),
                payment_status="未付款",
                notes="由 scripts/seed_demo.py 创建",
                created_at=deadline - timedelta(days=12),
            )
            session.add(order)
            session.flush()
            session.add(Quote(order_id=order.id, **quote))

            for feedback, revision_type, is_free, extra_fee, status in item["revisions"]:
                session.add(
                    Revision(
                        order_id=order.id,
                        customer_feedback=feedback,
                        revision_type=revision_type,
                        is_free=is_free,
                        extra_fee=extra_fee,
                        status=status,
                        notes="演示修改记录",
                    )
                )

            paid_ratio = item["paid_ratio"]
            if paid_ratio > 0:
                paid_amount = round(float(quote["final_price"]) * paid_ratio, 2)
                payment_type = "全款" if paid_ratio == 1 else "定金"
                order.payment_status = "已付清" if paid_ratio == 1 else "已付定金"
                session.add(
                    Payment(
                        order_id=order.id,
                        payment_type=payment_type,
                        amount=paid_amount,
                        payment_method="微信",
                        payment_date=min(now, deadline),
                        notes="演示收款记录",
                    )
                )
            inserted += 1
    return inserted


if __name__ == "__main__":
    count = seed_demo()
    print(f"演示数据准备完成，本次新增 {count} 条订单。")
