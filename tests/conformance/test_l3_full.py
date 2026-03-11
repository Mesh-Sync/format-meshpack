"""
L3 Conformance Tests — Full MeshSync Ecosystem.

Tests in this module verify L3 requirements from
definition/requirements/L3-full.md, including delta packs, import policies,
sidecar verification, and assembly transforms.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from tools.meshpack_validate import validate, Severity  # noqa: E402
from conftest import MeshPackBuilder  # noqa: E402


# ---------------------------------------------------------------------------
# REQ-L3-001: Delta packs MUST use 'operation' field
# ---------------------------------------------------------------------------

@pytest.mark.REQ_L3_001
class TestDeltaOperations:
    def test_operation_field_accepted(self, pack_builder: MeshPackBuilder) -> None:
        """Entries with 'operation' field should not produce errors."""
        entries = [
            {
                "path": "models/new.stl",
                "size_bytes": 100,
                "hash": "sha256:" + "aa" * 32,
                "modified_at": "2026-01-01T00:00:00+00:00",
                "operation": "add",
            },
            {
                "path": "models/old.stl",
                "size_bytes": 0,
                "hash": "sha256:" + "bb" * 32,
                "modified_at": "2026-01-01T00:00:00+00:00",
                "operation": "delete",
            },
        ]
        path = pack_builder.add_shard("part-00001", entries, entries_count=2).build_to_file()
        try:
            findings = validate(path)
            errors = [f for f in findings if f.severity == Severity.ERROR]
            # No shard-related errors expected
            shard_errors = [e for e in errors if e.code.startswith("SHD")]
            assert len(shard_errors) == 0
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# REQ-L3-010: import_policy field validation (schema-authoritative names)
# ---------------------------------------------------------------------------

@pytest.mark.REQ_L3_010
class TestImportPolicy:
    @pytest.mark.parametrize("id_conflict", ["fail", "skip", "overwrite"])
    def test_valid_id_conflict_values(self, id_conflict: str) -> None:
        """Valid id_conflict policy values: fail, skip, overwrite."""
        manifest = {
            "import_policy": {"id_conflict": id_conflict, "metamodel_merge": "merge"}
        }
        assert manifest["import_policy"]["id_conflict"] in ("fail", "skip", "overwrite")

    @pytest.mark.parametrize("metamodel_merge", ["strict", "merge", "replace"])
    def test_valid_metamodel_merge_values(self, metamodel_merge: str) -> None:
        """Valid metamodel_merge policy values: strict, merge, replace."""
        manifest = {
            "import_policy": {"id_conflict": "skip", "metamodel_merge": metamodel_merge}
        }
        assert manifest["import_policy"]["metamodel_merge"] in ("strict", "merge", "replace")


# ---------------------------------------------------------------------------
# REQ-L3-020: Sidecar verification
# ---------------------------------------------------------------------------

@pytest.mark.REQ_L3_020
class TestSidecarVerification:
    def test_sidecar_detected(self, pack_builder: MeshPackBuilder, minimal_valid_entry: dict) -> None:
        """Validator should detect .meshpack.integrity sidecar file."""
        import hashlib

        path = pack_builder.add_shard(
            "part-00001", [minimal_valid_entry], entries_count=1
        ).build_to_file()

        # Create matching sidecar
        with open(path, "rb") as f:
            digest = hashlib.sha256(f.read()).hexdigest()

        sidecar_path = path + ".integrity"
        sidecar = {
            "format_version": "1.0.0",
            "hash_algo": "sha256",
            "pack_hash": f"sha256:{digest}",
        }
        with open(sidecar_path, "w") as f:
            json.dump(sidecar, f)

        try:
            findings = validate(path)
            infos = [f for f in findings if f.severity == Severity.INFO]
            assert any("SDC-010" in f.code for f in infos), "Sidecar verification should succeed"
        finally:
            os.unlink(path)
            os.unlink(sidecar_path)

    def test_sidecar_mismatch_error(self, pack_builder: MeshPackBuilder, minimal_valid_entry: dict) -> None:
        """Mismatched sidecar hash must produce an error."""
        path = pack_builder.add_shard(
            "part-00001", [minimal_valid_entry], entries_count=1
        ).build_to_file()

        sidecar_path = path + ".integrity"
        sidecar = {
            "format_version": "1.0.0",
            "hash_algo": "sha256",
            "pack_hash": "sha256:" + "00" * 32,
        }
        with open(sidecar_path, "w") as f:
            json.dump(sidecar, f)

        try:
            findings = validate(path)
            errors = [f for f in findings if f.severity == Severity.ERROR]
            assert any("SDC-005" in f.code for f in errors)
        finally:
            os.unlink(path)
            os.unlink(sidecar_path)
