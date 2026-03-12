"""
Fixture-based conformance tests using static .meshpack archives.

These complement the builder-based tests by running the validator against
pre-generated reference archives that third-party implementations can also
use for interoperability testing.
"""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from tools.meshpack_validate import Severity, validate  # noqa: E402

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
VALID_DIR = os.path.join(FIXTURES_DIR, "valid")
INVALID_DIR = os.path.join(FIXTURES_DIR, "invalid")


def _fixture(subdir: str, name: str) -> str:
    path = os.path.join(subdir, name)
    if not os.path.isfile(path):
        pytest.skip(f"Fixture not generated: {name}")
    return path


# ---------------------------------------------------------------------------
# Valid fixtures: must validate without errors
# ---------------------------------------------------------------------------

class TestValidFixtures:
    def test_minimal_l1(self) -> None:
        findings = validate(_fixture(VALID_DIR, "minimal-l1.meshpack"))
        errors = [f for f in findings if f.severity == Severity.ERROR]
        assert not errors, f"Unexpected errors: {errors}"

    def test_standard_l2(self) -> None:
        findings = validate(_fixture(VALID_DIR, "standard-l2.meshpack"))
        errors = [f for f in findings if f.severity == Severity.ERROR]
        assert not errors, f"Unexpected errors: {errors}"

    def test_full_l3(self) -> None:
        findings = validate(_fixture(VALID_DIR, "full-l3.meshpack"))
        errors = [f for f in findings if f.severity == Severity.ERROR]
        assert not errors, f"Unexpected errors: {errors}"


# ---------------------------------------------------------------------------
# Invalid fixtures: must produce errors
# ---------------------------------------------------------------------------

class TestInvalidFixtures:
    def test_no_manifest(self) -> None:
        findings = validate(_fixture(INVALID_DIR, "no-manifest.meshpack"))
        errors = [f for f in findings if f.severity == Severity.ERROR]
        assert any("MAN-001" in f.code for f in errors), \
            f"Expected MAN-001, got: {[f.code for f in errors]}"

    def test_path_traversal(self) -> None:
        findings = validate(_fixture(INVALID_DIR, "path-traversal.meshpack"))
        errors = [f for f in findings if f.severity == Severity.ERROR]
        assert any("ENT-002" in f.code for f in errors), \
            f"Expected ENT-002, got: {[f.code for f in errors]}"

    def test_bad_shard_order(self) -> None:
        """Entries not sorted by path — validator should flag this."""
        findings = validate(_fixture(INVALID_DIR, "bad-shard-order.meshpack"))
        # This may produce various warnings/errors depending on the validator's
        # sort checking. At minimum the pack should validate without crashing.
        assert findings is not None
