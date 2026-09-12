"""Domain models shared by analysis and GitHub reporting."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class Severity(StrEnum):
    CRITICAL = "critical"
    WARNING = "warning"
    SUGGESTION = "suggestion"


class Category(StrEnum):
    SECURITY = "security"
    CORRECTNESS = "correctness"
    TESTS = "tests"
    MAINTAINABILITY = "maintainability"


@dataclass(frozen=True)
class Finding:
    category: Category
    severity: Severity
    title: str
    body: str
    path: str | None = None
    line: int | None = None
    rule_id: str | None = None
    confidence: float = 1.0


@dataclass(frozen=True)
class Strength:
    category: Category
    detail: str


@dataclass
class ReviewResult:
    findings: list[Finding] = field(default_factory=list)
    strengths: list[Strength] = field(default_factory=list)
    skipped_files: int = 0

    def by_category(self, category: Category) -> list[Finding]:
        return [finding for finding in self.findings if finding.category == category]
