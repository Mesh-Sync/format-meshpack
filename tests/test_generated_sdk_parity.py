"""Runtime parity checks for generated SDK validators."""

from __future__ import annotations

import importlib
import hashlib
import json
import os
import sys
from pathlib import Path

from tools.meshpack_validate import Severity, validate
from tests.conformance.conftest import MeshPackBuilder


REPO_ROOT = Path(__file__).resolve().parents[1]
PYTHON_SDK = REPO_ROOT / "generated" / "sdks" / "python"
SAMPLE = REPO_ROOT / "samples" / "test-workspace.mpack"
SDK_VALIDATION_VECTORS = REPO_ROOT / "tests" / "sdk_validation_vectors.json"


def _import_python_sdk():
    package_dir = PYTHON_SDK / "meshpack"
    if not package_dir.exists():
        import pytest

        pytest.skip("generated Python SDK not present; run just generate first")

    required_files = [package_dir / "__init__.py", package_dir / "models.py", package_dir / "extensions.py"]
    missing_files = [str(path.relative_to(REPO_ROOT)) for path in required_files if not path.exists()]
    if missing_files:
        raise AssertionError(f"generated Python SDK incomplete: {', '.join(missing_files)}")

    sdk_path = str(PYTHON_SDK)
    sys.path = [path for path in sys.path if path != sdk_path]
    sys.path.insert(0, sdk_path)
    for module_name in list(sys.modules):
        if module_name == "meshpack" or module_name.startswith("meshpack."):
            del sys.modules[module_name]
    importlib.invalidate_caches()
    return importlib.import_module("meshpack")


def _codes(findings, severity: str | None = None) -> set[str]:
    return {
        finding.code
        for finding in findings
        if severity is None or finding.severity == severity
    }


def _load_vector(vector_id: str) -> dict:
    import json

    with open(SDK_VALIDATION_VECTORS, "r", encoding="utf-8") as vector_file:
        vectors = json.load(vector_file)["vectors"]
    for vector in vectors:
        if vector["id"] == vector_id:
            return vector
    raise AssertionError(f"SDK validation vector not found: {vector_id}")


def _load_signature_vector(vector_id: str) -> dict:
    with open(SDK_VALIDATION_VECTORS, "r", encoding="utf-8") as vector_file:
        vectors = json.load(vector_file)["signature_vectors"]
    for vector in vectors:
        if vector["id"] == vector_id:
            return vector
    raise AssertionError(f"SDK signature validation vector not found: {vector_id}")


def _write_sidecar(path: str, signatures: list[dict]) -> str:
    with open(path, "rb") as archive_file:
        digest = hashlib.sha256(archive_file.read()).hexdigest()
    sidecar_path = path + ".integrity"
    with open(sidecar_path, "w", encoding="utf-8") as sidecar_file:
        json.dump(
            {
                "pack_name": os.path.basename(path),
                "pack_size_bytes": os.path.getsize(path),
                "hash_algo": "sha256",
                "pack_hash": f"sha256:{digest}",
                "computed_at": "2026-05-09T00:00:00Z",
                "signatures": signatures,
            },
            sidecar_file,
        )
    return sidecar_path


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


def test_generated_python_validator_matches_reference_on_jcs_utf16_vector() -> None:
    sdk = _import_python_sdk()
    vector = _load_vector("jcs-utf16-key-order")
    pack = MeshPackBuilder().add_shard(
        "part-00001",
        [vector["entry"]],
        entries_count=1,
        entries_hash=vector["entries_hash"],
    ).build_to_file()

    try:
        reference_findings = validate(pack)
        sdk_result = sdk.validate_meshpack(pack)
    finally:
        os.unlink(pack)

    assert "SHD-007" not in _codes(reference_findings, "ERROR")
    assert "SHD-007" not in _codes(sdk_result.findings, "ERROR")


def test_generated_python_validator_matches_reference_on_invalid_signature_base64() -> None:
    sdk = _import_python_sdk()
    vector = _load_signature_vector("invalid-base64-signature")
    pack = MeshPackBuilder().add_shard("part-00001", []).build_to_file()
    sidecar = _write_sidecar(pack, vector["signatures"])

    try:
        reference_findings = validate(pack, verify_sigs=True)
        sdk_result = sdk.validate_meshpack(pack, verify_signatures=True)
    finally:
        os.unlink(pack)
        os.unlink(sidecar)

    assert vector["expected_error_code"] in _codes(reference_findings, "ERROR")
    assert vector["expected_error_code"] in _codes(sdk_result.findings, "ERROR")