"""PyGithub boundary: fetch PR context and publish a review safely."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from github import Auth, Github
from github.PullRequest import ReviewComment

from .config import Settings
from .guidelines import Guidelines, parse_guidelines
from .models import Finding, ReviewResult
from .reporting import BOT_MARKER, render_summary
from .reviewer import ChangedFile


@dataclass(frozen=True)
class PullRequestContext:
    files: list[ChangedFile]
    guidelines: Guidelines
    head_sha: str


class GitHubReviewClient:
    def __init__(self, settings: Settings) -> None:
        settings.require_github_credentials()
        assert settings.app_id is not None
        self._settings = settings
        private_key = (
            settings.private_key_path.read_text()
            if settings.private_key_path is not None
            else settings.private_key
        )
        assert private_key is not None
        self._app_auth = Auth.AppAuth(settings.app_id, private_key)

    def _github_for_installation(self, installation_id: int) -> Github:
        auth = self._app_auth.get_installation_auth(installation_id)
        return Github(auth=auth)

    def get_context(
        self, installation_id: int, full_name: str, pull_number: int
    ) -> PullRequestContext:
        github = self._github_for_installation(installation_id)
        repository = github.get_repo(full_name)
        pull_request = repository.get_pull(pull_number)
        files = cast(list[ChangedFile], list(pull_request.get_files()[: self._settings.max_files]))
        guidelines = self._load_guidelines(repository, pull_request.base.ref)
        return PullRequestContext(
            files=files, guidelines=guidelines, head_sha=pull_request.head.sha
        )

    @staticmethod
    def _load_guidelines(repository: object, ref: str) -> Guidelines:
        for path in (".github/neat.md", "neat.md"):
            try:
                contents = repository.get_contents(path, ref=ref)  # type: ignore[attr-defined]
                return parse_guidelines(contents.decoded_content.decode("utf-8"))
            except Exception as error:  # GitHub's 404 is intentionally a no-guidelines case.
                if getattr(error, "status", None) == 404:
                    continue
                raise
        return Guidelines()

    def publish(
        self,
        installation_id: int,
        full_name: str,
        pull_number: int,
        head_sha: str,
        result: ReviewResult,
    ) -> None:
        github = self._github_for_installation(installation_id)
        repository = github.get_repo(full_name)
        pull_request = repository.get_pull(pull_number)
        summary = render_summary(result)
        inline = self._inline_comments(result.findings)
        if inline:
            pull_request.create_review(
                commit=repository.get_commit(head_sha),
                body=summary,
                event="COMMENT",
                comments=inline,
            )
        else:
            self._upsert_summary(pull_request, summary)
        conclusion = (
            "failure" if any(f.severity.value == "critical" for f in result.findings) else "success"
        )
        repository.create_check_run(
            name="NEATcoder",
            head_sha=head_sha,
            status="completed",
            conclusion=conclusion,
            output={"title": "NEATcoder review", "summary": summary[:65535]},
        )

    def _inline_comments(self, findings: list[Finding]) -> list[ReviewComment]:
        comments: list[ReviewComment] = []
        for finding in findings:
            if finding.path is None or finding.line is None or finding.confidence < 0.8:
                continue
            comments.append(
                {
                    "path": finding.path,
                    "line": finding.line,
                    "side": "RIGHT",
                    "body": f"**{finding.severity.title()} — {finding.title}**\n\n{finding.body}",
                }
            )
            if len(comments) == self._settings.max_inline_comments:
                break
        return comments

    @staticmethod
    def _upsert_summary(pull_request: object, summary: str) -> None:
        for comment in pull_request.get_issue_comments():  # type: ignore[attr-defined]
            if BOT_MARKER in comment.body:
                comment.edit(summary)
                return
        pull_request.create_issue_comment(summary)  # type: ignore[attr-defined]
