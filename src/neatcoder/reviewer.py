"""Coordinates parsing PR patches and deterministic analyzers."""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import TYPE_CHECKING, Protocol

from .ai_reviewer import review_with_openai
from .analyzers import analyze_added_lines, assess_test_coverage
from .guidelines import Guidelines
from .models import Category, Finding, ReviewResult, Strength

HUNK_HEADER = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")

if TYPE_CHECKING:
    from .config import Settings


class ChangedFile(Protocol):
    filename: str
    patch: str | None


def added_lines_from_patch(patch: str | None) -> Iterable[tuple[int, str]]:
    """Yield (new-file line number, content) for additions in a unified diff."""
    if not patch:
        return
    new_line: int | None = None
    for raw_line in patch.splitlines():
        header = HUNK_HEADER.match(raw_line)
        if header:
            new_line = int(header.group(1))
            continue
        if new_line is None:
            continue
        if raw_line.startswith("+") and not raw_line.startswith("+++"):
            yield new_line, raw_line[1:]
            new_line += 1
        elif raw_line.startswith("-") and not raw_line.startswith("---"):
            continue
        elif not raw_line.startswith("\\"):
            new_line += 1


def review_files(
    files: Iterable[ChangedFile], guidelines: Guidelines, settings: Settings | None = None
) -> ReviewResult:
    files = list(files)
    result = ReviewResult()
    changed_paths: list[str] = []
    seen: set[tuple[str | None, int | None, str]] = set()
    for file in files:
        path = file.filename
        if guidelines.excludes(path):
            result.skipped_files += 1
            continue
        changed_paths.append(path)
        for finding in analyze_added_lines(path, added_lines_from_patch(file.patch)):
            key = (finding.path, finding.line, finding.title)
            if key not in seen:
                result.findings.append(finding)
                seen.add(key)
    for item in assess_test_coverage(changed_paths):
        if isinstance(item, Finding):
            result.findings.append(item)
        else:
            result.strengths.append(item)
    if settings is not None and settings.openai_api_key:
        for finding in review_with_openai(
            files,
            guidelines,
            api_key=settings.openai_api_key,
            model=settings.openai_model,
            max_input_bytes=settings.max_diff_bytes,
            max_output_tokens=settings.max_ai_output_tokens,
        ):
            key = (finding.path, finding.line, finding.title)
            if key not in seen:
                result.findings.append(finding)
                seen.add(key)
    if not result.findings:
        result.strengths.append(
            Strength(
                category=Category.MAINTAINABILITY,
                detail="No deterministic issues found in changed lines.",
            )
        )
    return result
