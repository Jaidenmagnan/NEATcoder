"""GitHub webhook endpoint for NEATcoder."""

from __future__ import annotations

import hashlib
import hmac
import logging
from typing import Any

from fastapi import FastAPI, HTTPException, Request, Response

from .config import Settings, load_settings
from .github_client import GitHubReviewClient
from .reviewer import review_files

settings: Settings = load_settings()
logging.basicConfig(level=settings.log_level)
logger = logging.getLogger(__name__)
app = FastAPI(title="NEATcoder", version="0.1.0")
processed_deliveries: set[str] = set()


def _verify_signature(payload: bytes, signature: str | None, secret: str | None) -> bool:
    if not secret or not signature or not signature.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "NEATcoder"}


@app.post("/webhooks/github", status_code=202)
async def github_webhook(request: Request) -> Response:
    payload_bytes = await request.body()
    if not _verify_signature(
        payload_bytes, request.headers.get("X-Hub-Signature-256"), settings.webhook_secret
    ):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    delivery_id = request.headers.get("X-GitHub-Delivery")
    if delivery_id and delivery_id in processed_deliveries:
        return Response(status_code=202)
    payload: dict[str, Any] = await request.json()
    if request.headers.get("X-GitHub-Event") != "pull_request":
        return Response(status_code=202)
    if payload.get("action") not in {"opened", "reopened", "synchronize", "ready_for_review"}:
        return Response(status_code=202)
    if payload.get("pull_request", {}).get("draft"):
        return Response(status_code=202)

    try:
        _handle_pull_request(payload)
    except Exception:
        logger.exception("Failed to process GitHub delivery %s", delivery_id)
        raise HTTPException(status_code=500, detail="Review processing failed") from None
    if delivery_id:
        processed_deliveries.add(delivery_id)
    return Response(status_code=202)


def _handle_pull_request(payload: dict[str, Any]) -> None:
    installation_id = int(payload["installation"]["id"])
    full_name = str(payload["repository"]["full_name"])
    pull_number = int(payload["number"])
    client = GitHubReviewClient(settings)
    context = client.get_context(installation_id, full_name, pull_number)
    result = review_files(context.files, context.guidelines, settings)
    client.publish(installation_id, full_name, pull_number, context.head_sha, result)


def main() -> None:
    import uvicorn

    uvicorn.run("neatcoder.api:app", host="0.0.0.0", port=settings.port, reload=False)
