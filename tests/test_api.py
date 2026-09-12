import asyncio
import hashlib
import hmac
from dataclasses import replace
from typing import Any

import pytest
from starlette.requests import Request

import neatcoder.api as api
from neatcoder.api import _verify_signature
from neatcoder.config import Settings


def _request(path: str, body: bytes, headers: dict[str, str]) -> Request:
    async def receive() -> dict[str, Any]:
        return {"type": "http.request", "body": body}

    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": path,
            "headers": [(name.lower().encode(), value.encode()) for name, value in headers.items()],
        },
        receive,
    )


def test_verifies_github_signature() -> None:
    payload = b'{"ok": true}'
    signature = "sha256=" + hmac.new(b"secret", payload, hashlib.sha256).hexdigest()
    assert _verify_signature(payload, signature, "secret")
    assert not _verify_signature(payload, signature, "wrong")


def test_acknowledges_verified_review_delivery(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = b'{"action":"reopened","number":24,"pull_request":{"draft":false}}'
    signature = "sha256=" + hmac.new(b"secret", payload, hashlib.sha256).hexdigest()
    queued: list[tuple[dict[str, Any], str | None]] = []

    class FakeReviewTaskQueue:
        def __init__(self, settings: Settings) -> None:
            pass

        def enqueue(self, delivery: dict[str, Any], delivery_id: str | None) -> None:
            queued.append((delivery, delivery_id))

    monkeypatch.setattr(api, "settings", replace(api.settings, webhook_secret="secret"))
    monkeypatch.setattr(api, "ReviewTaskQueue", FakeReviewTaskQueue)
    api.processed_deliveries.clear()

    response = asyncio.run(api.github_webhook(_request(
        "/webhooks/github",
        payload,
        {
            "Content-Type": "application/json",
            "X-GitHub-Delivery": "delivery-1",
            "X-GitHub-Event": "pull_request",
            "X-Hub-Signature-256": signature,
        },
    )))

    assert response.status_code == 202
    assert queued == [
        ({"action": "reopened", "number": 24, "pull_request": {"draft": False}}, "delivery-1")
    ]


def test_processes_authorized_review_task(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {"number": 24}
    handled: list[dict[str, Any]] = []
    monkeypatch.setattr(api, "settings", replace(api.settings, task_secret="task-secret"))
    monkeypatch.setattr(api, "_handle_pull_request", lambda delivery: handled.append(delivery))

    response = asyncio.run(
        api.review_task(
            _request(
                "/tasks/review",
                b'{"number":24}',
                {"Content-Type": "application/json", "Authorization": "Bearer task-secret"},
            )
        )
    )

    assert response.status_code == 204
    assert handled == [payload]
