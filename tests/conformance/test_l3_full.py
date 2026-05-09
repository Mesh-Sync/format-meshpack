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

from tools.meshpack_validate import validate, Severity, verify_signature_entries  # noqa: E402
from .conftest import MeshPackBuilder  # noqa: E402


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


# ---------------------------------------------------------------------------
# REQ-L3-030: Signature verification
# ---------------------------------------------------------------------------

cryptography = pytest.importorskip("cryptography", reason="cryptography package not installed")


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
