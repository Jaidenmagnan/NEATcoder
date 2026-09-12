from neatcoder.guidelines import parse_guidelines
from neatcoder.models import Severity


def test_parses_rules_and_exclusions() -> None:
    guide = parse_guidelines(
        """# Guide
## Rules
- id: no-debug
  severity: warning
  instruction: Avoid debug output.
## Exclusions
- generated/**
"""
    )
    assert guide.rules[0].id == "no-debug"
    assert guide.rules[0].severity is Severity.WARNING
    assert guide.excludes("generated/client.py")
