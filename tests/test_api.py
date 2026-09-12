import hashlib
import hmac
from dataclasses import replace
from typing import Any

import pytest
from fastapi.testclient import TestClient

import neatcoder.api as api
from neatcoder.api import _verify_signature


def test_verifies_github_signature() -> None:
    payload = b'{"ok": true}'
    signature = "sha256=" + hmac.new(b"secret", payload, hashlib.sha256).hexdigest()
    assert _verify_signature(payload, signature, "secret")
    assert not _verify_signature(payload, signature, "wrong")


def test_acknowledges_verified_review_delivery(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = b'{"action":"reopened","number":24,"pull_request":{"draft":false}}'
    signature = "sha256=" + hmac.new(b"secret", payload, hashlib.sha256).hexdigest()
    handled: list[dict[str, Any]] = []
    monkeypatch.setattr(api, "settings", replace(api.settings, webhook_secret="secret"))
    monkeypatch.setattr(api, "_handle_pull_request", lambda delivery: handled.append(delivery))

    response = TestClient(api.app).post(
        "/webhooks/github",
        content=payload,
        headers={
            "Content-Type": "application/json",
            "X-GitHub-Delivery": "delivery-1",
            "X-GitHub-Event": "pull_request",
            "X-Hub-Signature-256": signature,
        },
    )

    assert response.status_code == 202
    assert handled == [{"action": "reopened", "number": 24, "pull_request": {"draft": False}}]
