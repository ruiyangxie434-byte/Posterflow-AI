from datetime import datetime, timezone

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database.db import Base
from database.models import Client, DesignVersion, Order, Payment, Quote, Revision, User


def _session_factory():
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(test_engine)
    return test_engine, sessionmaker(bind=test_engine, expire_on_commit=False, future=True)


def _order(client_id):
    return Order(
        client_id=client_id,
        title="测试海报",
        design_type="商业海报",
        original_requirement="黑红色健身海报",
        structured_requirement="{}",
        usage="朋友圈",
        size="1080×1440px",
        style="运动",
        main_color="黑红",
        status="待沟通",
        price=69,
        deadline=datetime.now(timezone.utc),
        source_file_required=False,
    )


def test_all_required_tables_and_relationships_round_trip():
    engine, Factory = _session_factory()
    with Factory.begin() as session:
        user = User(username="designer", password_hash="stored-hash")
        client = Client(name="张同学", contact="微信 zhang", source="同学介绍", notes="")
        session.add_all([user, client])
        session.flush()
        order = _order(client.id)
        session.add(order)
        session.flush()
        session.add_all(
            [
                Quote(order_id=order.id, base_price=69, final_price=69),
                Revision(
                    order_id=order.id,
                    customer_feedback="标题放大",
                    revision_type="排版修改",
                    is_free=True,
                    extra_fee=0,
                    status="待处理",
                ),
                DesignVersion(
                    order_id=order.id,
                    version_number="V1",
                    file_name="v1.png",
                    file_path="uploads/design_versions/v1.png",
                    description="初稿",
                ),
                Payment(
                    order_id=order.id,
                    payment_type="定金",
                    amount=30,
                    payment_method="微信",
                    payment_date=datetime.now(timezone.utc),
                ),
            ]
        )

    with Factory() as session:
        saved = session.scalar(select(Order).where(Order.title == "测试海报"))
        assert saved.client.name == "张同学"
        assert len(saved.quotes) == 1
        assert len(saved.revisions) == 1
        assert len(saved.design_versions) == 1
        assert len(saved.payments) == 1
        assert saved.source_file_required is False
    engine.dispose()


def test_deleting_client_cascades_all_order_children():
    engine, Factory = _session_factory()
    with Factory.begin() as session:
        client = Client(name="被删除客户", contact="", source="其他")
        session.add(client)
        session.flush()
        order = _order(client.id)
        session.add(order)
        session.flush()
        session.add_all(
            [
                Quote(order_id=order.id, base_price=69, final_price=69),
                Revision(order_id=order.id, customer_feedback="修改", revision_type="其他"),
                DesignVersion(
                    order_id=order.id,
                    version_number="V1",
                    file_name="x.png",
                    file_path="x.png",
                ),
                Payment(order_id=order.id, payment_type="定金", amount=20),
            ]
        )
    with Factory.begin() as session:
        client = session.scalar(select(Client).where(Client.name == "被删除客户"))
        session.delete(client)
    with Factory() as session:
        for model in (Order, Quote, Revision, DesignVersion, Payment):
            assert session.scalar(select(func.count()).select_from(model)) == 0
    engine.dispose()
