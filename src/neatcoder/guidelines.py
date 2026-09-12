"""Read the small, dependency-free NEATcoder guideline format."""

from __future__ import annotations

from dataclasses import dataclass, field
from fnmatch import fnmatch

from .models import Severity


@dataclass(frozen=True)
class Rule:
    id: str
    severity: Severity
    instruction: str


@dataclass
class Guidelines:
    priorities: list[str] = field(default_factory=list)
    rules: list[Rule] = field(default_factory=list)
    exclusions: list[str] = field(default_factory=list)

    def excludes(self, path: str) -> bool:
        return any(fnmatch(path, pattern) for pattern in self.exclusions)


def parse_guidelines(content: str) -> Guidelines:
    """Parse supported list sections while leaving normal Markdown harmless."""
    result = Guidelines()
    section: str | None = None
    current: dict[str, str] | None = None

    def finish_rule() -> None:
        nonlocal current
        if current is None:
            return
        if {"id", "severity", "instruction"} <= current.keys():
            try:
                result.rules.append(
                    Rule(
                        id=current["id"],
                        severity=Severity(current["severity"].lower()),
                        instruction=current["instruction"],
                    )
                )
            except ValueError:
                pass
        current = None

    for raw_line in content.splitlines():
        line = raw_line.strip()
        if line.startswith("## "):
            finish_rule()
            heading = line[3:].lower()
            section = heading if heading in {"priorities", "rules", "exclusions"} else None
            continue
        if section == "rules" and line.startswith("- id:"):
            finish_rule()
            current = {"id": line.split(":", 1)[1].strip()}
            continue
        if section == "rules" and current is not None and ":" in line:
            key, value = line.split(":", 1)
            if key.strip() in {"severity", "instruction"}:
                current[key.strip()] = value.strip()
            continue
        if section == "priorities" and line.startswith("- "):
            result.priorities.append(line[2:].strip())
        elif section == "exclusions" and line.startswith("- "):
            result.exclusions.append(line[2:].strip())
    finish_rule()
    return result
