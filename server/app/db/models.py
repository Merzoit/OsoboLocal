from __future__ import annotations

import uuid
from datetime import date, datetime, time

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Integer,
    PrimaryKeyConstraint,
    String,
    Text,
    Time,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON, Uuid

from app.db.base import Base, MenuRevisionMixin, SyncableMixin
from app.db.types import UTCDateTime

# --- Menu ---


class Category(Base, SyncableMixin, MenuRevisionMixin):
    __tablename__ = "category"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    items: Mapped[list[MenuItem]] = relationship(back_populates="category")


class MenuItem(Base, SyncableMixin, MenuRevisionMixin):
    __tablename__ = "menu_item"
    __table_args__ = (
        CheckConstraint("price >= 0", name="price_nonneg"),
        Index("ix_menu_item_category_id_active", "category_id", "active"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    category_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("category.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    price: Mapped[int] = mapped_column(Integer, nullable=False)
    image_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    available_from: Mapped[time | None] = mapped_column(Time, nullable=True)
    available_to: Mapped[time | None] = mapped_column(Time, nullable=True)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("staff.id"), nullable=True
    )

    category: Mapped[Category] = relationship(back_populates="items")
    stations: Mapped[list[ItemStation]] = relationship(back_populates="item")
    modifier_groups: Mapped[list[MenuItemModifierGroup]] = relationship(back_populates="item")


class ModifierGroup(Base, SyncableMixin, MenuRevisionMixin):
    __tablename__ = "modifier_group"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    min_select: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_select: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    modifiers: Mapped[list[Modifier]] = relationship(back_populates="group")


class Modifier(Base, SyncableMixin, MenuRevisionMixin):
    __tablename__ = "modifier"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    group_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("modifier_group.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    price_delta: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    group: Mapped[ModifierGroup] = relationship(back_populates="modifiers")


class MenuItemModifierGroup(Base):
    __tablename__ = "menu_item_modifier_group"
    __table_args__ = (
        PrimaryKeyConstraint("item_id", "group_id", name="pk_menu_item_modifier_group"),
    )

    item_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("menu_item.id"), nullable=False
    )
    group_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("modifier_group.id"), nullable=False
    )

    item: Mapped[MenuItem] = relationship(back_populates="modifier_groups")
    group: Mapped[ModifierGroup] = relationship()


# --- Stations ---


class Station(Base, SyncableMixin):
    __tablename__ = "station"
    __table_args__ = (
        CheckConstraint("capacity > 0", name="capacity_positive"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    code: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class ItemStation(Base, SyncableMixin, MenuRevisionMixin):
    __tablename__ = "item_station"
    __table_args__ = (
        CheckConstraint("prep_seconds > 0", name="prep_seconds_positive"),
        UniqueConstraint("item_id", "station_id", "step_name", name="item_station_step"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    item_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("menu_item.id"), nullable=False
    )
    station_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("station.id"), nullable=False
    )
    step_name: Mapped[str] = mapped_column(Text, nullable=False)
    prep_seconds: Mapped[int] = mapped_column(Integer, nullable=False)

    item: Mapped[MenuItem] = relationship(back_populates="stations")
    station: Mapped[Station] = relationship()


# --- Orders ---


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (
        CheckConstraint(
            "type IN ('dine_in', 'takeaway')",
            name="type",
        ),
        CheckConstraint(
            "status IN ('awaiting_payment', 'paid', 'in_progress', 'ready', "
            "'completed', 'cancelled', 'refunded')",
            name="status",
        ),
        UniqueConstraint("business_date", "seq", name="business_date_seq"),
        Index("ix_orders_status_created_at", "status", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    business_date: Mapped[date] = mapped_column(Date, nullable=False)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    number: Mapped[str] = mapped_column(Text, nullable=False)
    kiosk_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("device.id"), nullable=False
    )
    type: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    guest_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("guest.id"), nullable=True
    )
    discount_percent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    subtotal: Mapped[int | None] = mapped_column(Integer, nullable=True)
    discount_total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    paid_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    ready_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)

    lines: Mapped[list[OrderLine]] = relationship(back_populates="order")


class OrderLine(Base):
    __tablename__ = "order_line"
    __table_args__ = (CheckConstraint("qty > 0", name="qty_positive"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("orders.id"), nullable=False
    )
    item_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("menu_item.id"), nullable=False
    )
    item_name: Mapped[str] = mapped_column(Text, nullable=False)
    unit_price: Mapped[int] = mapped_column(Integer, nullable=False)
    qty: Mapped[int] = mapped_column(Integer, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    line_total: Mapped[int] = mapped_column(Integer, nullable=False)

    order: Mapped[Order] = relationship(back_populates="lines")
    modifiers: Mapped[list[OrderLineModifier]] = relationship(back_populates="order_line")


class OrderLineModifier(Base):
    __tablename__ = "order_line_modifier"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    order_line_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("order_line.id"), nullable=False
    )
    modifier_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("modifier.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    price_delta: Mapped[int] = mapped_column(Integer, nullable=False)

    order_line: Mapped[OrderLine] = relationship(back_populates="modifiers")


class StationTask(Base):
    __tablename__ = "station_task"
    __table_args__ = (
        CheckConstraint(
            "status IN ('planned', 'cooking', 'ready', 'cancelled')",
            name="status",
        ),
        Index(
            "ix_station_task_station_id_status_planned_start_at",
            "station_id",
            "status",
            "planned_start_at",
        ),
        Index("ix_station_task_order_id", "order_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("orders.id"), nullable=False
    )
    order_line_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("order_line.id"), nullable=False
    )
    station_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("station.id"), nullable=False
    )
    step_name: Mapped[str] = mapped_column(Text, nullable=False)
    prep_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    planned_start_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    planned_ready_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    ready_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)


# --- Payments ---


class Terminal(Base):
    __tablename__ = "terminal"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    name: Mapped[str | None] = mapped_column(Text, nullable=True)
    model: Mapped[str | None] = mapped_column(Text, nullable=True)
    protocol: Mapped[str | None] = mapped_column(Text, nullable=True)
    host: Mapped[str | None] = mapped_column(Text, nullable=True)
    port: Mapped[int | None] = mapped_column(Integer, nullable=True)
    kiosk_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("device.id"), nullable=True
    )
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)


class Payment(Base):
    __tablename__ = "payment"
    __table_args__ = (
        CheckConstraint(
            "status IN ('created', 'in_progress', 'approved', 'declined', "
            "'cancelled', 'unknown', 'refunded')",
            name="status",
        ),
        Index("ix_payment_order_id", "order_id"),
        Index("ix_payment_status", "status"),
        Index(
            "uq_payment_active",
            "order_id",
            unique=True,
            sqlite_where=text("status IN ('created', 'in_progress', 'unknown')"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("orders.id"), nullable=False
    )
    attempt: Mapped[int] = mapped_column(Integer, nullable=False)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    terminal_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("terminal.id"), nullable=True
    )
    idempotency_key: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), nullable=False, unique=True
    )
    reference: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    provider_txn_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    auth_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    rrn: Mapped[str | None] = mapped_column(Text, nullable=True)
    card_last4: Mapped[str | None] = mapped_column(String(4), nullable=True)
    card_scheme: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_response: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("staff.id"), nullable=True
    )
    resolution_note: Mapped[str | None] = mapped_column(Text, nullable=True)


class Refund(Base):
    __tablename__ = "refund"
    __table_args__ = (
        CheckConstraint(
            "status IN ('requested', 'done', 'failed')",
            name="status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    payment_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("payment.id"), nullable=False
    )
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    provider_txn_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("staff.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)


# --- Guests / loyalty ---


class Guest(Base, SyncableMixin):
    __tablename__ = "guest"
    __table_args__ = (
        CheckConstraint(
            "qr_status IN ('active', 'revoked')",
            name="qr_status",
        ),
        CheckConstraint(
            "discount_percent BETWEEN 0 AND 100",
            name="discount_percent_range",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    name: Mapped[str | None] = mapped_column(Text, nullable=True)
    phone: Mapped[str | None] = mapped_column(Text, nullable=True)
    email: Mapped[str | None] = mapped_column(Text, nullable=True)
    qr_token_hash: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    qr_status: Mapped[str] = mapped_column(Text, nullable=False)
    discount_percent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    consent_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)


class LoyaltyTx(Base):
    __tablename__ = "loyalty_tx"
    __table_args__ = (
        CheckConstraint(
            "type IN ('accrual', 'redemption', 'reversal', 'adjustment')",
            name="type",
        ),
        Index("ix_loyalty_tx_guest_id_created_at", "guest_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    guest_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("guest.id"), nullable=False
    )
    order_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("orders.id"), nullable=True
    )
    type: Mapped[str] = mapped_column(Text, nullable=False)
    points: Mapped[int] = mapped_column(Integer, nullable=False)
    basis_amount: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reverses_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("loyalty_tx.id"), nullable=True
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)


class GuestLock(Base):
    __tablename__ = "guest_lock"
    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'released', 'consumed')",
            name="status",
        ),
        Index(
            "uq_guest_lock_active",
            "guest_id",
            unique=True,
            sqlite_where=text("status = 'active'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    guest_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("guest.id"), nullable=False
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("orders.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(Text, nullable=False)
    locked_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    released_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)


class QrScanLog(Base):
    __tablename__ = "qr_scan_log"
    __table_args__ = (
        CheckConstraint(
            "result IN ('ok', 'unknown', 'revoked', 'locked', 'invalid_signature')",
            name="result",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    guest_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    kiosk_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("device.id"), nullable=False
    )
    result: Mapped[str] = mapped_column(Text, nullable=False)
    scanned_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)


# --- Devices / staff / audit ---


class Staff(Base, SyncableMixin):
    __tablename__ = "staff"
    __table_args__ = (
        CheckConstraint("role IN ('operator', 'admin')", name="role"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False)
    pin_hash: Mapped[str] = mapped_column(Text, nullable=False)
    failed_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Device(Base, SyncableMixin):
    __tablename__ = "device"
    __table_args__ = (
        CheckConstraint(
            "role IN ('kiosk', 'station', 'expo', 'operator')",
            name="role",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    name: Mapped[str | None] = mapped_column(Text, nullable=True)
    role: Mapped[str] = mapped_column(Text, nullable=False)
    station_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("station.id"), nullable=True
    )
    token_hash: Mapped[str] = mapped_column(Text, nullable=False)
    app_version: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class DeviceRegistrationCode(Base):
    """One-time device enrollment codes (not in SPEC §5; required for §12.1)."""

    __tablename__ = "device_registration_code"
    __table_args__ = (
        CheckConstraint(
            "role IN ('kiosk', 'station', 'expo', 'operator')",
            name="role",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    code_hash: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    role: Mapped[str] = mapped_column(Text, nullable=False)
    station_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("station.id"), nullable=True
    )
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    actor_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    entity: Mapped[str | None] = mapped_column(Text, nullable=True)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    before: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    after: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)


# --- Sync / idempotency ---


class SyncOutbox(Base):
    __tablename__ = "sync_outbox"
    __table_args__ = (
        CheckConstraint("op IN ('upsert', 'append')", name="op"),
        Index("ix_sync_outbox_synced_at_id", "synced_at", "id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    entity: Mapped[str] = mapped_column(Text, nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    op: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    synced_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)


class SyncState(Base):
    __tablename__ = "sync_state"

    key: Mapped[str] = mapped_column(Text, primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)


class IdempotencyKey(Base):
    __tablename__ = "idempotency_key"

    key: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    endpoint: Mapped[str] = mapped_column(Text, nullable=False)
    request_hash: Mapped[str] = mapped_column(Text, nullable=False)
    response_status: Mapped[int] = mapped_column(Integer, nullable=False)
    response_body: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
