"""Runtime parity checks for generated SDK validators."""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

from tools.meshpack_validate import Severity, validate
from tests.conformance.conftest import MeshPackBuilder


REPO_ROOT = Path(__file__).resolve().parents[1]
PYTHON_SDK = REPO_ROOT / "generated" / "sdks" / "python"
SAMPLE = REPO_ROOT / "samples" / "test-workspace.mpack"


def _import_python_sdk():
    if not (PYTHON_SDK / "meshpack" / "__init__.py").exists():
        import pytest

        pytest.skip("generated Python SDK not present; run just generate first")
    sys.path.insert(0, str(PYTHON_SDK))
    return importlib.import_module("meshpack")


def _codes(findings, severity: str | None = None) -> set[str]:
    return {
        finding.code
        for finding in findings
        if severity is None or finding.severity == severity
    }


def test_generated_python_validator_matches_reference_on_public_sample() -> None:
    sdk = _import_python_sdk()

    reference_findings = validate(str(SAMPLE), schema_mode="strict")
    sdk_result = sdk.validate_meshpack(str(SAMPLE))

    assert not [finding for finding in reference_findings if finding.severity == Severity.ERROR]
    assert sdk_result.valid, sdk_result.findings
    assert "SDC-010" in _codes(reference_findings)
    assert "SDC-010" in _codes(sdk_result.findings)


def test_generated_python_validator_matches_reference_on_unsafe_resource_ref() -> None:
    sdk = _import_python_sdk()
    entry = {
        "path": "models/test.stl",
        "original_name": "test.stl",
        "size_bytes": 10,
        "hash": "sha256:" + "aa" * 32,
        "modified_at": "2026-05-09T00:00:00Z",
        "resource_ref": "../secret.png",
        "resource_hash": "sha256:" + "bb" * 32,
    }
    pack = MeshPackBuilder().add_shard(
        "part-00001",
        [entry],
        entries_count=1,
        entries_hash="sha256:" + "00" * 32,
    ).build_to_file()

    try:
        reference_findings = validate(pack)
        sdk_result = sdk.validate_meshpack(pack)
    finally:
        os.unlink(pack)

    assert "RES-004" in _codes(reference_findings, "ERROR")
    assert "RES-004" in _codes(sdk_result.findings, "ERROR")


def test_generated_python_validator_matches_reference_on_future_major() -> None:
    sdk = _import_python_sdk()
    pack_builder = MeshPackBuilder()
    pack_builder.set_manifest_field("format_version", "3.0.0")
    pack = pack_builder.add_shard("part-00001", []).build_to_file()

    try:
        reference_findings = validate(pack)
        sdk_result = sdk.validate_meshpack(pack)
    finally:
        os.unlink(pack)

    assert "MAN-013" in _codes(reference_findings, "ERROR")
    assert "MAN-013" in _codes(sdk_result.findings, "ERROR")