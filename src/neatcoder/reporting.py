"""Render concise, GitHub-flavored Markdown reviews."""

from __future__ import annotations

from .models import Category, ReviewResult, Severity

BOT_MARKER = "<!-- neatcoder-review -->"


def _score(result: ReviewResult, category: Category) -> int:
    penalties = {Severity.CRITICAL: 55, Severity.WARNING: 20, Severity.SUGGESTION: 8}
    return max(0, 100 - sum(penalties[f.severity] for f in result.by_category(category)))


def render_summary(result: ReviewResult) -> str:
    categories = list(Category)
    criticals = sum(f.severity == Severity.CRITICAL for f in result.findings)
    verdict = "Changes requested" if criticals else "Review complete"
    rows = "\n".join(
        (
            f"| {category.value.title()} | {len(result.by_category(category))} "
            f"| {_score(result, category)}/100 |"
        )
        for category in categories
    )
    strengths = (
        "\n".join(f"- {item.detail}" for item in result.strengths)
        or "- No specific strengths recorded."
    )
    findings = (
        "\n".join(
            f"- **{item.severity.title()} — {item.title}:** {item.body}"
            for item in result.findings
            if item.path is None
        )
        or "- No repository-level concerns."
    )
    coverage = (
        f" {result.skipped_files} excluded file(s) were skipped." if result.skipped_files else ""
    )
    return (
        f"{BOT_MARKER}\n## NEATcoder review — {verdict}\n\n"
        "| Category | Findings | Score |\n|---|---:|---:|\n"
        f"{rows}\n\n"
        f"### Doing well\n{strengths}\n\n"
        f"### Needs attention\n{findings}\n\n"
        "Inline comments are limited to high-confidence findings on changed lines."
        f"{coverage}"
    )
