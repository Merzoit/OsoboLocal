from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker
from tests.conftest import create_device, create_registration_code


def test_register_success(client: TestClient, db: Session) -> None:
    code = create_registration_code(db, role="kiosk")
    db.commit()

    response = client.post(
        "/api/v1/devices/register",
        json={"code": code, "role": "kiosk", "name": "Kiosk 1"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["role"] == "kiosk"
    assert "token" in body
    assert body["device_id"]


def test_register_code_reuse(client: TestClient, db: Session) -> None:
    code = create_registration_code(db, role="operator")
    db.commit()

    first = client.post(
        "/api/v1/devices/register",
        json={"code": code, "role": "operator"},
    )
    assert first.status_code == 200

    second = client.post(
        "/api/v1/devices/register",
        json={"code": code, "role": "operator"},
    )
    assert second.status_code == 400
    assert second.json()["error"]["code"] == "code_used"


def test_register_role_mismatch(client: TestClient, db: Session) -> None:
    code = create_registration_code(db, role="kiosk")
    db.commit()

    response = client.post(
        "/api/v1/devices/register",
        json={"code": code, "role": "expo"},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "role_mismatch"


def test_menu_unauthorized_without_token(client: TestClient, seeded_db: sessionmaker) -> None:
    response = client.get("/api/v1/menu")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


def test_menu_forbidden_wrong_role(
    client: TestClient, db: Session, seeded_db: sessionmaker
) -> None:
    _, token = create_device(db, role="station")
    db.commit()

    response = client.get("/api/v1/menu", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"
