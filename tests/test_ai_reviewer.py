from neatcoder.ai_reviewer import _parse_findings


def test_discards_inline_finding_on_unchanged_line() -> None:
    items = [
        {
            "category": "correctness",
            "severity": "warning",
            "title": "Wrong line",
            "body": "Only changed lines can receive inline GitHub comments.",
            "path": "src/example.py",
            "line": 9,
            "rule_id": None,
            "confidence": 0.9,
        }
    ]

    assert _parse_findings(items, {"src/example.py": {10}}) == []


def test_accepts_valid_inline_finding() -> None:
    items = [
        {
            "category": "correctness",
            "severity": "warning",
            "title": "Possible division by zero",
            "body": "Validate the denominator before dividing.",
            "path": "src/example.py",
            "line": 10,
            "rule_id": "validate-input",
            "confidence": 0.9,
        }
    ]

    findings = _parse_findings(items, {"src/example.py": {10}})

    assert len(findings) == 1
    assert findings[0].line == 10
