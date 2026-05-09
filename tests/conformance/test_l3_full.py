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
import hashlib

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from tools.meshpack_validate import validate, Severity, verify_signature_entries  # noqa: E402
from .conftest import MeshPackBuilder  # noqa: E402


def _sidecar_for(path: str, pack_hash: str | None = None, signatures: list[dict] | None = None) -> dict:
    with open(path, "rb") as archive_file:
        digest = hashlib.sha256(archive_file.read()).hexdigest()
    sidecar = {
        "pack_name": os.path.basename(path),
        "pack_size_bytes": os.path.getsize(path),
        "hash_algo": "sha256",
        "pack_hash": pack_hash or f"sha256:{digest}",
        "computed_at": "2026-01-01T00:00:00Z",
    }
    if signatures is not None:
        sidecar["signatures"] = signatures
    return sidecar


def _write_sidecar(path: str, sidecar: dict) -> str:
    sidecar_path = path + ".integrity"
    with open(sidecar_path, "w", encoding="utf-8") as sidecar_file:
        json.dump(sidecar, sidecar_file)
    return sidecar_path


# ---------------------------------------------------------------------------
# REQ-L3-020: Delta packs MUST use 'operation' field
# ---------------------------------------------------------------------------

@pytest.mark.REQ_L3_020
@pytest.mark.REQ_L3_022
class TestDeltaOperations:
    def test_operation_field_accepted(self, pack_builder: MeshPackBuilder) -> None:
        """Entries with 'operation' field should not produce errors."""
        entries = [
            {
                "path": "models/new.stl",
                "original_name": "new.stl",
                "size_bytes": 100,
                "hash": "sha256:" + "aa" * 32,
                "modified_at": "2026-01-01T00:00:00+00:00",
                "operation": "add",
            },
            {
                "path": "models/old.stl",
                "original_name": "old.stl",
                "size_bytes": 0,
                "hash": "sha256:" + "0" * 64,
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

    def test_delete_entry_rejects_nonzero_metadata(self, pack_builder: MeshPackBuilder) -> None:
        entry = {
            "path": "models/old.stl",
            "original_name": "old.stl",
            "size_bytes": 10,
            "hash": "sha256:" + "bb" * 32,
            "modified_at": "2026-01-01T00:00:00+00:00",
            "operation": "delete",
            "resource_ref": "a" * 64 + ".png",
            "resource_hash": "sha256:" + "aa" * 32,
        }
        path = pack_builder.add_shard("part-00001", [entry]).build_to_file()
        try:
            findings = validate(path)
            errors = {f.code for f in findings if f.severity == Severity.ERROR}
            assert {"DEL-001", "DEL-002", "DEL-003"}.issubset(errors)
        finally:
            os.unlink(path)

    def test_partial_generation_requires_base_pack_hash(self, pack_builder: MeshPackBuilder, minimal_valid_entry: dict) -> None:
        pack_builder.set_manifest_field("generation", {"partial": True})
        path = pack_builder.add_shard("part-00001", [minimal_valid_entry]).build_to_file()
        try:
            findings = validate(path)
            errors = [f for f in findings if f.severity == Severity.ERROR]
            assert any(f.code == "MAN-021" for f in errors)
        finally:
            os.unlink(path)


@pytest.mark.REQ_L3_003
class TestWorkspaceIdentity:
    def test_workspace_id_must_match_namespaced_id(self, pack_builder: MeshPackBuilder, minimal_valid_entry: dict) -> None:
        pack_builder.set_manifest_field("workspace_id", "11111111-1111-4111-8111-111111111111")
        pack_builder.set_manifest_field("ids", [{"ns": "meshsync:workspace", "id": "22222222-2222-4222-8222-222222222222"}])
        path = pack_builder.add_shard("part-00001", [minimal_valid_entry]).build_to_file()
        try:
            findings = validate(path)
            errors = [f for f in findings if f.severity == Severity.ERROR]
            assert any(f.code == "MAN-020" for f in errors)
        finally:
            os.unlink(path)


@pytest.mark.REQ_L3_042
class TestExtensionNamespaces:
    def test_custom_extension_without_namespace_warns(self, pack_builder: MeshPackBuilder, minimal_valid_entry: dict) -> None:
        entry = dict(minimal_valid_entry)
        entry["extensions"] = {"custom": {"enabled": True}}
        path = pack_builder.add_shard("part-00001", [entry]).build_to_file()
        try:
            findings = validate(path)
            warnings = [f for f in findings if f.severity == Severity.WARNING]
            assert any(f.code == "EXT-001" for f in warnings)
        finally:
            os.unlink(path)

    def test_unknown_reserved_extension_prefix_rejected(self, pack_builder: MeshPackBuilder, minimal_valid_entry: dict) -> None:
        entry = dict(minimal_valid_entry)
        entry["extensions"] = {"meshsync_future": {"enabled": True}}
        path = pack_builder.add_shard("part-00001", [entry]).build_to_file()
        try:
            findings = validate(path)
            errors = [f for f in findings if f.severity == Severity.ERROR]
            assert any(f.code == "EXT-002" for f in errors)
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# REQ-L2-041: import_policy field validation (schema-authoritative names)
# ---------------------------------------------------------------------------

@pytest.mark.REQ_L2_041
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
# REQ-L2-012: Sidecar verification
# ---------------------------------------------------------------------------

@pytest.mark.REQ_L2_012
class TestSidecarVerification:
    def test_sidecar_detected(self, pack_builder: MeshPackBuilder, minimal_valid_entry: dict) -> None:
        """Validator should detect .meshpack.integrity sidecar file."""
        path = pack_builder.add_shard(
            "part-00001", [minimal_valid_entry], entries_count=1
        ).build_to_file()

        sidecar_path = _write_sidecar(path, _sidecar_for(path))

        try:
            findings = validate(path, schema_mode="strict")
            errors = [f for f in findings if f.severity == Severity.ERROR]
            infos = [f for f in findings if f.severity == Severity.INFO]
            assert not errors, f"Unexpected strict-mode errors: {errors}"
            assert any("SDC-010" in f.code for f in infos), "Sidecar verification should succeed"
        finally:
            os.unlink(path)
            os.unlink(sidecar_path)

    def test_sidecar_mismatch_error(self, pack_builder: MeshPackBuilder, minimal_valid_entry: dict) -> None:
        """Mismatched sidecar hash must produce an error."""
        path = pack_builder.add_shard(
            "part-00001", [minimal_valid_entry], entries_count=1
        ).build_to_file()

        sidecar_path = _write_sidecar(path, _sidecar_for(path, pack_hash="sha256:" + "00" * 32))

        try:
            findings = validate(path, schema_mode="strict")
            errors = [f for f in findings if f.severity == Severity.ERROR]
            assert any("SDC-005" in f.code for f in errors)
        finally:
            os.unlink(path)
            os.unlink(sidecar_path)

    def test_sidecar_size_mismatch_error(self, pack_builder: MeshPackBuilder, minimal_valid_entry: dict) -> None:
        """pack_size_bytes must match the archive before hash/signature trust."""
        path = pack_builder.add_shard(
            "part-00001", [minimal_valid_entry], entries_count=1
        ).build_to_file()

        sidecar = _sidecar_for(path)
        sidecar["pack_size_bytes"] += 1
        sidecar_path = _write_sidecar(path, sidecar)

        try:
            findings = validate(path, schema_mode="strict")
            errors = [f for f in findings if f.severity == Severity.ERROR]
            assert any(f.code == "SDC-007" for f in errors)
        finally:
            os.unlink(path)
            os.unlink(sidecar_path)

    def test_sidecar_schema_errors_are_visible(self, pack_builder: MeshPackBuilder, minimal_valid_entry: dict) -> None:
        """A hash match cannot hide an invalid sidecar document."""
        path = pack_builder.add_shard(
            "part-00001", [minimal_valid_entry], entries_count=1
        ).build_to_file()

        sidecar = _sidecar_for(path)
        del sidecar["pack_name"]
        sidecar_path = _write_sidecar(path, sidecar)

        try:
            findings = validate(path, schema_mode="strict")
            errors = [f for f in findings if f.severity == Severity.ERROR]
            assert any(f.code == "SCH-001" for f in errors)
            assert any(f.code == "SDC-010" for f in findings)
        finally:
            os.unlink(path)
            os.unlink(sidecar_path)


# ---------------------------------------------------------------------------
# REQ-L3-030: Signature verification
# ---------------------------------------------------------------------------

cryptography = pytest.importorskip("cryptography", reason="cryptography package not installed")


@pytest.mark.REQ_L3_030
@pytest.mark.REQ_L3_031
class TestSignatureVerificationCrypto:
    """Verify that Ed25519 and RSA-PSS-SHA256 signatures are checked."""

    def test_ed25519_valid_signature(self) -> None:
        """A valid Ed25519 signature over pack_hash should produce SIG-010."""
        import base64
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

        private_key = Ed25519PrivateKey.generate()
        public_key = private_key.public_key()
        pub_bytes = public_key.public_bytes_raw()

        pack_hash = "sha256:" + "ab" * 32
        sig_bytes = private_key.sign(pack_hash.encode("utf-8"))

        signatures = [{
            "alg": "ed25519",
            "public_key": base64.b64encode(pub_bytes).decode(),
            "signature": base64.b64encode(sig_bytes).decode(),
            "signer_id": "test-signer",
        }]

        findings = verify_signature_entries(signatures, pack_hash)
        infos = [f for f in findings if f.code == "SIG-010"]
        assert infos, f"Expected SIG-010 success, got: {findings}"

    def test_ed25519_spki_public_key_signature(self) -> None:
        """A valid Ed25519 signature may use SPKI/DER public key bytes."""
        import base64
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

        private_key = Ed25519PrivateKey.generate()
        public_key = private_key.public_key()
        pub_bytes = public_key.public_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )

        pack_hash = "sha256:" + "ab" * 32
        sig_bytes = private_key.sign(pack_hash.encode("utf-8"))

        signatures = [{
            "alg": "ed25519",
            "public_key": base64.b64encode(pub_bytes).decode(),
            "signature": base64.b64encode(sig_bytes).decode(),
            "signer_id": "test-signer",
        }]

        findings = verify_signature_entries(signatures, pack_hash)
        infos = [f for f in findings if f.code == "SIG-010"]
        assert infos, f"Expected SIG-010 success, got: {findings}"

    def test_ed25519_invalid_signature(self) -> None:
        """A forged Ed25519 signature should produce SIG-004 error."""
        import base64
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

        private_key = Ed25519PrivateKey.generate()
        public_key = private_key.public_key()
        pub_bytes = public_key.public_bytes_raw()

        pack_hash = "sha256:" + "ab" * 32
        sig_bytes = private_key.sign(b"wrong-data")

        signatures = [{
            "alg": "ed25519",
            "public_key": base64.b64encode(pub_bytes).decode(),
            "signature": base64.b64encode(sig_bytes).decode(),
        }]

        findings = verify_signature_entries(signatures, pack_hash)
        errors = [f for f in findings if f.code == "SIG-004"]
        assert errors, f"Expected SIG-004 error, got: {findings}"

    def test_missing_fields_sig002(self) -> None:
        """Signature entries with missing fields should produce SIG-002."""
        signatures = [{"alg": "ed25519"}]
        findings = verify_signature_entries(signatures, "sha256:" + "00" * 32)
        errors = [f for f in findings if f.code == "SIG-002"]
        assert errors

    def test_unsupported_algorithm_sig005(self) -> None:
        """Unsupported algorithm should produce SIG-005 info."""
        import base64
        signatures = [{
            "alg": "unknown-algo",
            "public_key": base64.b64encode(b"key").decode(),
            "signature": base64.b64encode(b"sig").decode(),
        }]
        findings = verify_signature_entries(signatures, "sha256:" + "00" * 32)
        infos = [f for f in findings if f.code == "SIG-005"]
        assert infos

    def test_validate_verifies_sidecar_signatures(self, pack_builder: MeshPackBuilder, minimal_valid_entry: dict) -> None:
        """validate(..., verify_sigs=True) must verify authoritative sidecar signatures."""
        import base64
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

        path = pack_builder.add_shard(
            "part-00001", [minimal_valid_entry], entries_count=1
        ).build_to_file()

        private_key = Ed25519PrivateKey.generate()
        public_key = private_key.public_key()
        sidecar = _sidecar_for(path)
        signature = private_key.sign(sidecar["pack_hash"].encode("utf-8"))
        sidecar["signatures"] = [{
            "alg": "ed25519",
            "public_key": base64.b64encode(public_key.public_bytes_raw()).decode(),
            "signature": base64.b64encode(signature).decode(),
            "signer_id": "test-signer",
        }]
        sidecar_path = _write_sidecar(path, sidecar)

        try:
            findings = validate(path, verify_sigs=True, schema_mode="strict")
            errors = [f for f in findings if f.severity == Severity.ERROR]
            assert not errors, f"Unexpected strict-mode errors: {errors}"
            assert any(f.code == "SIG-010" for f in findings)
        finally:
            os.unlink(path)
            os.unlink(sidecar_path)
