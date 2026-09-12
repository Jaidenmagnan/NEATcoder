"""Cloud Tasks boundary for durable pull-request review jobs."""

from __future__ import annotations

import json
from typing import Any

from google.api_core.exceptions import AlreadyExists
from google.cloud import tasks_v2
from google.protobuf.duration_pb2 import Duration  # type: ignore[import-untyped]

from .config import Settings


class ReviewTaskQueue:
    def __init__(self, settings: Settings) -> None:
        settings.require_task_queue_settings()
        assert settings.gcp_project is not None
        assert settings.task_queue is not None
        assert settings.task_target_url is not None
        assert settings.task_secret is not None
        self._settings = settings
        self._client = tasks_v2.CloudTasksClient()
        self._queue_path = self._client.queue_path(
            settings.gcp_project, settings.task_location, settings.task_queue
        )

    def enqueue(self, payload: dict[str, Any], delivery_id: str | None) -> None:
        task = tasks_v2.Task(
            http_request=tasks_v2.HttpRequest(
                http_method=tasks_v2.HttpMethod.POST,
                url=self._settings.task_target_url,
                headers={
                    "Authorization": f"Bearer {self._settings.task_secret}",
                    "Content-Type": "application/json",
                },
                body=json.dumps(payload, separators=(",", ":")).encode(),
            ),
            dispatch_deadline=Duration(seconds=1800),
        )
        if delivery_id:
            task.name = f"{self._queue_path}/tasks/github-{delivery_id}"
        try:
            self._client.create_task(parent=self._queue_path, task=task, timeout=10)
        except AlreadyExists:
            # GitHub redelivered an event that is already queued; one review is sufficient.
            return
