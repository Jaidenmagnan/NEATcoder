from types import SimpleNamespace

from neatcoder.guidelines import Guidelines
from neatcoder.models import Category, Severity
from neatcoder.reviewer import added_lines_from_patch, review_files


def test_maps_added_lines_to_new_file_locations() -> None:
    patch = "@@ -1,2 +1,3 @@\n keep\n-old\n+new\n+second\n"
    assert list(added_lines_from_patch(patch)) == [(2, "new"), (3, "second")]


def test_comments_potential_secret_on_added_line() -> None:
    file = SimpleNamespace(
        filename="src/client.py", patch='@@ -0,0 +1 @@\n+token = "very-secret-value"'
    )
    result = review_files([file], Guidelines())
    finding = result.findings[0]
    assert finding.category is Category.SECURITY
    assert finding.severity is Severity.CRITICAL
    assert finding.path == "src/client.py"
    assert finding.line == 1


def test_reports_missing_tests_without_inline_location() -> None:
    file = SimpleNamespace(filename="src/client.py", patch="@@ -1 +1 @@\n+return 1")
    result = review_files([file], Guidelines())
    finding = next(item for item in result.findings if item.category is Category.TESTS)
    assert finding.path is None
