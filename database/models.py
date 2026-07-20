"""Relational models used by PosterFlow AI."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.orm import relationship

from .db import Base


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""

    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String(80), nullable=False, unique=True, index=True)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)


class Client(Base):
    __tablename__ = "clients"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, index=True)
    contact = Column(String(200), nullable=False, default="")
    source = Column(String(50), nullable=False, default="其他", index=True)
    notes = Column(Text, nullable=False, default="")
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    orders = relationship(
        "Order",
        back_populates="client",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(200), nullable=False, index=True)
    design_type = Column(String(50), nullable=False, default="其他", index=True)
    original_requirement = Column(Text, nullable=False, default="")
    structured_requirement = Column(Text, nullable=False, default="")
    usage = Column(String(200), nullable=False, default="")
    size = Column(String(100), nullable=False, default="")
    style = Column(String(100), nullable=False, default="")
    main_color = Column(String(100), nullable=False, default="")
    status = Column(String(50), nullable=False, default="待沟通", index=True)
    price = Column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    deadline = Column(DateTime(timezone=True), nullable=False, index=True)
    urgent = Column(Boolean, nullable=False, default=False)
    source_file_required = Column(Boolean, nullable=False, default=False)
    print_required = Column(Boolean, nullable=False, default=False)
    revision_limit = Column(Integer, nullable=False, default=1)
    revision_used = Column(Integer, nullable=False, default=0)
    payment_status = Column(String(50), nullable=False, default="未付款", index=True)
    notes = Column(Text, nullable=False, default="")
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now, index=True)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)

    client = relationship("Client", back_populates="orders")
    quotes = relationship(
        "Quote", back_populates="order", cascade="all, delete-orphan", passive_deletes=True
    )
    revisions = relationship(
        "Revision", back_populates="order", cascade="all, delete-orphan", passive_deletes=True
    )
    design_versions = relationship(
        "DesignVersion", back_populates="order", cascade="all, delete-orphan", passive_deletes=True
    )
    payments = relationship(
        "Payment", back_populates="order", cascade="all, delete-orphan", passive_deletes=True
    )

    __table_args__ = (Index("ix_orders_status_deadline", "status", "deadline"),)


class Quote(Base):
    __tablename__ = "quotes"

    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True)
    base_price = Column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    urgent_fee = Column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    source_file_fee = Column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    print_fee = Column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    complex_cutout_fee = Column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    redesign_fee = Column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    oversized_fee = Column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    complexity_fee = Column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    manual_adjustment = Column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    final_price = Column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    order = relationship("Order", back_populates="quotes")


class Revision(Base):
    __tablename__ = "revisions"

    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True)
    customer_feedback = Column(Text, nullable=False)
    revision_type = Column(String(50), nullable=False, default="其他")
    is_free = Column(Boolean, nullable=False, default=True)
    extra_fee = Column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    status = Column(String(50), nullable=False, default="待处理", index=True)
    notes = Column(Text, nullable=False, default="")
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    order = relationship("Order", back_populates="revisions")


class DesignVersion(Base):
    __tablename__ = "design_versions"

    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True)
    version_number = Column(String(30), nullable=False)
    file_name = Column(String(255), nullable=False)
    file_path = Column(String(1024), nullable=False)
    description = Column(Text, nullable=False, default="")
    is_final = Column(Boolean, nullable=False, default=False, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    order = relationship("Order", back_populates="design_versions")
    __table_args__ = (Index("ix_design_versions_order_version", "order_id", "version_number", unique=True),)


class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True)
    payment_type = Column(String(50), nullable=False)
    amount = Column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    payment_method = Column(String(50), nullable=False, default="其他")
    payment_date = Column(DateTime(timezone=True), nullable=False, default=utc_now, index=True)
    notes = Column(Text, nullable=False, default="")

    order = relationship("Order", back_populates="payments")
