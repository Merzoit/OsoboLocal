from __future__ import annotations

import uuid

from fastapi.testclient import TestClient


def test_idempotency_replay_and_conflict(client: TestClient) -> None:
    key = str(uuid.uuid4())
    headers = {"Idempotency-Key": key}
    payload = {"value": 1}

    first = client.post("/api/v1/_test/idempotent", json=payload, headers=headers)
    assert first.status_code == 200
    assert first.json() == {"ok": True, "echo": payload}

    second = client.post("/api/v1/_test/idempotent", json=payload, headers=headers)
    assert second.status_code == 200
    assert second.json() == first.json()

    conflict = client.post(
        "/api/v1/_test/idempotent",
        json={"value": 2},
        headers=headers,
    )
    assert conflict.status_code == 422
    assert conflict.json()["error"]["code"] == "idempotency_conflict"
