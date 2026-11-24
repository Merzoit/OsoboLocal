from __future__ import annotations

import pytest
from app.db.models import Device, Guest, GuestLock, Order, Payment
from app.ids import new_uuid
from app.security import sha256_hex
from app.timeutil import utcnow
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session


def _device(db: Session) -> Device:
    now = utcnow()
    device = Device(
        id=new_uuid(),
        name="kiosk",
        role="kiosk",
        station_id=None,
        token_hash=sha256_hex("x"),
        app_version="1",
        last_seen_at=now,
        active=True,
        version=1,
        created_at=now,
        updated_at=now,
        deleted_at=None,
    )
    db.add(device)
    db.flush()
    return device


def _guest(db: Session) -> Guest:
    now = utcnow()
    guest = Guest(
        id=new_uuid(),
        name="G",
        phone=None,
        email=None,
        qr_token_hash=sha256_hex(str(new_uuid())),
        qr_status="active",
        discount_percent=0,
        consent_at=None,
        version=1,
        created_at=now,
        updated_at=now,
        deleted_at=None,
    )
    db.add(guest)
    db.flush()
    return guest


def _order(db: Session, device: Device, guest: Guest | None = None) -> Order:
    now = utcnow()
    order = Order(
        id=new_uuid(),
        business_date=now.date(),
        seq=1,
        number="A-001",
        kiosk_id=device.id,
        type="dine_in",
        status="awaiting_payment",
        guest_id=guest.id if guest else None,
        discount_percent=0,
        subtotal=100,
        discount_total=0,
        total=100,
        created_at=now,
        paid_at=None,
        ready_at=None,
        completed_at=None,
        cancelled_at=None,
        updated_at=now,
    )
    db.add(order)
    db.flush()
    return order


def test_uq_payment_active(db: Session) -> None:
    device = _device(db)
    order = _order(db, device)
    now = utcnow()

    db.add(
        Payment(
            id=new_uuid(),
            order_id=order.id,
            attempt=1,
            amount=100,
            currency="EUR",
            status="created",
            terminal_id=None,
            idempotency_key=new_uuid(),
            reference="ref-1",
            created_at=now,
        )
    )
    db.flush()

    db.add(
        Payment(
            id=new_uuid(),
            order_id=order.id,
            attempt=2,
            amount=100,
            currency="EUR",
            status="in_progress",
            terminal_id=None,
            idempotency_key=new_uuid(),
            reference="ref-2",
            created_at=now,
        )
    )
    with pytest.raises(IntegrityError):
        db.flush()


def test_uq_guest_lock_active(db: Session) -> None:
    device = _device(db)
    guest = _guest(db)
    order1 = _order(db, device, guest)
    now = utcnow()
    order2 = Order(
        id=new_uuid(),
        business_date=now.date(),
        seq=2,
        number="A-002",
        kiosk_id=device.id,
        type="dine_in",
        status="awaiting_payment",
        guest_id=guest.id,
        discount_percent=0,
        subtotal=100,
        discount_total=0,
        total=100,
        created_at=now,
        paid_at=None,
        ready_at=None,
        completed_at=None,
        cancelled_at=None,
        updated_at=now,
    )
    db.add(order2)
    db.flush()

    db.add(
        GuestLock(
            id=new_uuid(),
            guest_id=guest.id,
            order_id=order1.id,
            status="active",
            locked_at=now,
            released_at=None,
        )
    )
    db.flush()

    db.add(
        GuestLock(
            id=new_uuid(),
            guest_id=guest.id,
            order_id=order2.id,
            status="active",
            locked_at=now,
            released_at=None,
        )
    )
    with pytest.raises(IntegrityError):
        db.flush()
