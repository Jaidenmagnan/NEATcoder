"""OpenAI-backed pull-request review with bounded input and structured output."""

from __future__ import annotations

import json
from collections.abc import Iterable
from typing import TYPE_CHECKING

from openai import OpenAI

from .guidelines import Guidelines
from .models import Category, Finding, Severity

if TYPE_CHECKING:
    from .reviewer import ChangedFile


REVIEW_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "category": {"type": "string", "enum": [item.value for item in Category]},
                    "severity": {"type": "string", "enum": [item.value for item in Severity]},
                    "title": {"type": "string"},
                    "body": {"type": "string"},
                    "path": {"type": ["string", "null"]},
                    "line": {"type": ["integer", "null"]},
                    "rule_id": {"type": ["string", "null"]},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                },
                "required": [
                    "category",
                    "severity",
                    "title",
                    "body",
                    "path",
                    "line",
                    "rule_id",
                    "confidence",
                ],
                "additionalProperties": False,
            },
        }
    },
    "required": ["findings"],
    "additionalProperties": False,
}

INSTRUCTIONS = """Review the supplied pull-request patch. Report only concrete, high-confidence
security, correctness, testing, or maintainability defects. Follow repository rules when
present. Do not praise code, speculate, or report style preferences. Inline findings must refer
only to an added line from the patch. Return an empty findings list when nothing is actionable."""


def review_with_openai(
    files: Iterable[ChangedFile],
    guidelines: Guidelines,
    *,
    api_key: str,
    model: str,
    max_input_bytes: int,
    max_output_tokens: int,
) -> list[Finding]:
    """Review bounded patches and convert the model's JSON response to findings."""
    payload_files: list[dict[str, str]] = []
    added_lines: dict[str, set[int]] = {}
    remaining = max_input_bytes
    for file in files:
        if guidelines.excludes(file.filename) or not file.patch or remaining <= 0:
            continue
        patch = file.patch[:remaining]
        remaining -= len(patch.encode("utf-8"))
        payload_files.append({"path": file.filename, "patch": patch})
        added_lines[file.filename] = _added_line_numbers(patch)
    if not payload_files:
        return []

    payload = {
        "priorities": guidelines.priorities,
        "rules": [
            {"id": rule.id, "severity": rule.severity.value, "instruction": rule.instruction}
            for rule in guidelines.rules
        ],
        "files": payload_files,
    }
    response = OpenAI(api_key=api_key).responses.create(
        model=model,
        instructions=INSTRUCTIONS,
        input=json.dumps(payload),
        max_output_tokens=max_output_tokens,
        store=False,
        text={
            "format": {
                "type": "json_schema",
                "name": "pull_request_review",
                "strict": True,
                "schema": REVIEW_SCHEMA,
            }
        },
    )
    parsed = json.loads(response.output_text)
    return _parse_findings(parsed.get("findings"), added_lines)


def _added_line_numbers(patch: str) -> set[int]:
    from .reviewer import added_lines_from_patch

    return {line for line, _ in added_lines_from_patch(patch)}


def _parse_findings(items: object, added_lines: dict[str, set[int]]) -> list[Finding]:
    if not isinstance(items, list):
        return []
    findings: list[Finding] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        try:
            path = item["path"]
            line = item["line"]
            if path is not None and (not isinstance(path, str) or not isinstance(line, int)):
                continue
            if path is not None and line not in added_lines.get(path, set()):
                continue
            findings.append(
                Finding(
                    category=Category(item["category"]),
                    severity=Severity(item["severity"]),
                    title=str(item["title"])[:160],
                    body=str(item["body"])[:2000],
                    path=path,
                    line=line,
                    rule_id=item["rule_id"] if isinstance(item["rule_id"], str) else None,
                    confidence=max(0.0, min(1.0, float(item["confidence"]))),
                )
            )
        except (KeyError, TypeError, ValueError):
            continue
    return findings
