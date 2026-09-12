"""Deterministic, conservative checks for newly-added pull-request lines."""

from __future__ import annotations

import re
from collections.abc import Iterable

from .models import Category, Finding, Severity, Strength

SECRET_ASSIGNMENT = re.compile(
    r"(?i)(?:api[_-]?key|secret|token|password|private[_-]?key)\s*[:=]\s*['\"][^'\"]{8,}"
)
PRIVATE_KEY = re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")
DEBUG_OUTPUT = re.compile(r"\b(?:print|console\.log|pdb\.set_trace)\s*\(")
TEST_PATH = re.compile(r"(^|/)(test|tests|__tests__)(/|$)|(^|[_./])test[_./]", re.I)
SOURCE_SUFFIXES = (".py", ".js", ".jsx", ".ts", ".tsx", ".go", ".java", ".rb", ".rs")


def analyze_added_lines(path: str, lines: Iterable[tuple[int, str]]) -> list[Finding]:
    findings: list[Finding] = []
    for line_number, text in lines:
        if PRIVATE_KEY.search(text) or SECRET_ASSIGNMENT.search(text):
            findings.append(
                Finding(
                    category=Category.SECURITY,
                    severity=Severity.CRITICAL,
                    title="Potential secret committed",
                    body=(
                        "This added line appears to contain a credential or private key. "
                        "Remove it from the change, rotate the exposed value, and load it from "
                        "a secret store."
                    ),
                    path=path,
                    line=line_number,
                    rule_id="no-secrets",
                )
            )
        elif DEBUG_OUTPUT.search(text):
            findings.append(
                Finding(
                    category=Category.MAINTAINABILITY,
                    severity=Severity.WARNING,
                    title="Debug output in changed code",
                    body=(
                        "Please remove this debug output or replace it with the project's "
                        "structured "
                        "logging convention before merging."
                    ),
                    path=path,
                    line=line_number,
                    rule_id="no-debug-output",
                )
            )
    return findings


def assess_test_coverage(changed_paths: Iterable[str]) -> list[Finding | Strength]:
    paths = list(changed_paths)
    production = [
        path for path in paths if path.endswith(SOURCE_SUFFIXES) and not TEST_PATH.search(path)
    ]
    tests = [path for path in paths if TEST_PATH.search(path)]
    if production and not tests:
        return [
            Finding(
                category=Category.TESTS,
                severity=Severity.WARNING,
                title="Production code changed without test changes",
                body=(
                    "This pull request modifies production source files but does not include "
                    "a test file. "
                    "Please add or explain the relevant test coverage."
                ),
                rule_id="tests-for-production-changes",
                confidence=0.7,
            )
        ]
    if production and tests:
        return [Strength(category=Category.TESTS, detail="The pull request includes test changes.")]
    return []
