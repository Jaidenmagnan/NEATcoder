"""Application configuration loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    environment: str
    log_level: str
    port: int
    app_id: int | None
    private_key_path: Path | None
    private_key: str | None
    webhook_secret: str | None
    max_files: int
    max_diff_bytes: int
    max_inline_comments: int

    @property
    def github_enabled(self) -> bool:
        return self.app_id is not None and (
            self.private_key_path is not None or self.private_key is not None
        )

    def require_github_credentials(self) -> None:
        if not self.github_enabled or not self.webhook_secret:
            raise RuntimeError(
                "Live GitHub handling requires NEATCODER_GITHUB_APP_ID, "
                "NEATCODER_GITHUB_PRIVATE_KEY_PATH, and NEATCODER_WEBHOOK_SECRET."
            )


def load_settings() -> Settings:
    load_dotenv()
    app_id_raw = os.getenv("NEATCODER_GITHUB_APP_ID")
    key_path_raw = os.getenv("NEATCODER_GITHUB_PRIVATE_KEY_PATH")
    return Settings(
        environment=os.getenv("NEATCODER_ENVIRONMENT", "development"),
        log_level=os.getenv("NEATCODER_LOG_LEVEL", "INFO"),
        port=int(os.getenv("NEATCODER_PORT", "8000")),
        app_id=int(app_id_raw) if app_id_raw else None,
        private_key_path=Path(key_path_raw) if key_path_raw else None,
        private_key=os.getenv("NEATCODER_GITHUB_PRIVATE_KEY"),
        webhook_secret=os.getenv("NEATCODER_WEBHOOK_SECRET"),
        max_files=int(os.getenv("NEATCODER_MAX_FILES", "100")),
        max_diff_bytes=int(os.getenv("NEATCODER_MAX_DIFF_BYTES", "500000")),
        max_inline_comments=int(os.getenv("NEATCODER_MAX_INLINE_COMMENTS", "20")),
    )
