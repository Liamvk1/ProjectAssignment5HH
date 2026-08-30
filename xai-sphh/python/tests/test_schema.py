"""
Asserts that the Python schema column list matches the Java schema document.

Both sides are compared against ``docs/trace-schema.md`` as the single source of
truth. This test will fail if the Python list is updated without a corresponding
update to the documentation, or vice versa.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from xaisphh.io.schema import FIXED_COLUMNS

# Path to the schema document relative to the repository root.
# Pytest is run from the python/ directory; adjust accordingly.
_REPO_ROOT = Path(__file__).parents[2]
_SCHEMA_DOC = _REPO_ROOT / "docs" / "trace-schema.md"

_COLUMN_PATTERN = re.compile(r"^\|\s*`([^`]+)`\s*\|")


def _parse_fixed_columns_from_doc() -> list[str]:
    """Extract fixed column names from the markdown table in trace-schema.md."""
    columns: list[str] = []
    in_fixed_section = False

    for line in _SCHEMA_DOC.read_text(encoding="utf-8").splitlines():
        if "## Fixed columns" in line:
            in_fixed_section = True
            continue
        if in_fixed_section and line.startswith("## "):
            break
        if in_fixed_section:
            m = _COLUMN_PATTERN.match(line)
            if m:
                columns.append(m.group(1))

    return columns


def test_schema_doc_exists() -> None:
    """The schema document must exist at the expected path."""
    assert _SCHEMA_DOC.exists(), (
        f"Schema document not found at {_SCHEMA_DOC}. "
        "Ensure the repository root is two levels above the python/ directory."
    )


def test_fixed_columns_match_schema_document() -> None:
    """Python FIXED_COLUMNS must equal the column names in docs/trace-schema.md."""
    doc_columns = _parse_fixed_columns_from_doc()

    assert doc_columns, (
        f"No column names were parsed from {_SCHEMA_DOC}. "
        "Check the regex or the document format."
    )

    assert FIXED_COLUMNS == doc_columns, (
        "Python FIXED_COLUMNS does not match docs/trace-schema.md.\n"
        f"  Python: {FIXED_COLUMNS}\n"
        f"  Doc:    {doc_columns}\n"
        "Update whichever is out of date and bump SCHEMA_VERSION."
    )
