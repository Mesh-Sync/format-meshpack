"""
BLAKE3 Conformance Tests.

Tests in this module verify that the BLAKE3 hash algorithm is fully supported
across all conformance levels (L1, L2, L3), as required by the specification.

The blake3 package is an optional dependency.  Tests in this module are
automatically skipped when it is not installed.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile

import pytest

blake3 = pytest.importorskip("blake3", reason="BLAKE3 tests require the 'blake3' package")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from tools.meshpack_validate import (  # noqa: E402
    SUPPORTED_ALGOS,
    Severity,
    compute_digest,
    validate,
    verify_entries_hash,
)
from conftest import MeshPackBuilder  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _blake3_hex(data: bytes) -> str:
    """Return the BLAKE3 hex digest of *data*."""
    return blake3.blake3(data).hexdigest()


def _blake3_prefixed(data: bytes) -> str:
    """Return a prefixed BLAKE3 hash string (``blake3:<hex>``)."""
    return f"blake3:{_blake3_hex(data)}"


def _make_blake3_entry(path: str = "models/cube.stl", size_bytes: int = 1234) -> dict:
    """Return a minimal FileEntry using BLAKE3 hashes."""
    dummy = path.encode("utf-8")
    return {
        "path": path,
        "size_bytes": size_bytes,
        "hash": _blake3_prefixed(dummy),
        "modified_at": "2026-01-01T00:00:00+00:00",
    }


# ---------------------------------------------------------------------------
# L1: BLAKE3 in SUPPORTED_ALGOS and manifest acceptance
# ---------------------------------------------------------------------------

@pytest.mark.REQ_L1_004
class TestBlake3AlgoSupport:
    """BLAKE3 must be a recognised hash algorithm."""

    def test_blake3_in_supported_algos(self) -> None:
        """blake3 must be listed in the SUPPORTED_ALGOS constant."""
        assert "blake3" in SUPPORTED_ALGOS

    def test_blake3_hash_algo_accepted(self, pack_builder: MeshPackBuilder) -> None:
        """Manifest with hash_algo='blake3' must not produce MAN-012 errors."""
        entry = _make_blake3_entry()
        pack_builder.set_manifest_field("hash_algo", "blake3")
        path = pack_builder.add_shard("part-00001", [entry], entries_count=1).build_to_file()
        try:
            findings = validate(path)
            errors = [f for f in findings if f.severity == Severity.ERROR]
            algo_errors = [e for e in errors if e.code == "MAN-012"]
            assert len(algo_errors) == 0, f"blake3 should be accepted: {algo_errors}"
        finally:
            os.unlink(path)

    def test_blake3_hash_format_accepted(self, pack_builder: MeshPackBuilder) -> None:
        """Entry hashes using blake3:<64hex> must pass format validation."""
        entry = _make_blake3_entry()
        pack_builder.set_manifest_field("hash_algo", "blake3")
        path = pack_builder.add_shard("part-00001", [entry], entries_count=1).build_to_file()
        try:
            findings = validate(path)
            warnings = [f for f in findings if f.severity == Severity.WARNING]
            hash_warnings = [w for w in warnings if w.code == "HSH-001"]
            assert len(hash_warnings) == 0, f"blake3 hash format should be valid: {hash_warnings}"
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# L1: compute_digest with BLAKE3
# ---------------------------------------------------------------------------

class TestBlake3ComputeDigest:
    """Low-level digest helpers must work with BLAKE3."""

    def test_compute_digest_blake3(self) -> None:
        """compute_digest must return the correct BLAKE3 hex digest."""
        data = b"hello meshpack"
        expected = _blake3_hex(data)
        actual = compute_digest([data], "blake3")
        assert actual == expected

    def test_compute_digest_blake3_chunked(self) -> None:
        """compute_digest must handle multiple chunks correctly with BLAKE3."""
        chunks = [b"hello ", b"mesh", b"pack"]
        full = b"hello meshpack"
        expected = _blake3_hex(full)
        actual = compute_digest(chunks, "blake3")
        assert actual == expected


# ---------------------------------------------------------------------------
# L2: entries_hash verification with BLAKE3
# ---------------------------------------------------------------------------

@pytest.mark.REQ_L2_010
class TestBlake3EntriesHash:
    """entries_hash computed with BLAKE3 must verify correctly."""

    def test_entries_hash_roundtrip(self) -> None:
        """verify_entries_hash should succeed for a correctly computed BLAKE3 hash."""
        entries = [
            {
                "path": "a.stl",
                "size_bytes": 10,
                "hash": _blake3_prefixed(b"a"),
                "modified_at": "2026-01-01T00:00:00+00:00",
            },
        ]
        # Compute expected hash the same way the validator does
        canonical = json.dumps(entries, sort_keys=True, separators=(",", ":")).encode("utf-8")
        digest = _blake3_hex(canonical)
        expected_hash = f"blake3:{digest}"

        ok, actual = verify_entries_hash(entries, "blake3", expected_hash)
        assert ok, f"Expected {expected_hash}, got {actual}"

    def test_entries_hash_mismatch_detected(self) -> None:
        """verify_entries_hash should detect a wrong BLAKE3 entries_hash."""
        entries = [_make_blake3_entry()]
        wrong_hash = "blake3:" + "00" * 32
        ok, actual = verify_entries_hash(entries, "blake3", wrong_hash)
        assert not ok

    def test_entries_hash_in_archive(self, pack_builder: MeshPackBuilder) -> None:
        """Full archive round-trip: entries_hash with BLAKE3 must validate."""
        entry = _make_blake3_entry()
        entries = [entry]

        # Compute correct entries_hash
        canonical = json.dumps(entries, sort_keys=True, separators=(",", ":")).encode("utf-8")
        digest = _blake3_hex(canonical)
        entries_hash = f"blake3:{digest}"

        pack_builder.set_manifest_field("hash_algo", "blake3")
        path = pack_builder.add_shard(
            "part-00001", entries, entries_count=1, entries_hash=entries_hash
        ).build_to_file()
        try:
            findings = validate(path)
            errors = [f for f in findings if f.severity == Severity.ERROR]
            hash_errors = [e for e in errors if e.code == "SHD-007"]
            assert len(hash_errors) == 0, f"entries_hash should verify: {hash_errors}"
        finally:
            os.unlink(path)

    def test_wrong_entries_hash_flagged(self, pack_builder: MeshPackBuilder) -> None:
        """Archive with wrong BLAKE3 entries_hash must produce SHD-007 error."""
        entry = _make_blake3_entry()
        wrong_hash = "blake3:" + "ff" * 32
        pack_builder.set_manifest_field("hash_algo", "blake3")
        path = pack_builder.add_shard(
            "part-00001", [entry], entries_count=1, entries_hash=wrong_hash
        ).build_to_file()
        try:
            findings = validate(path)
            errors = [f for f in findings if f.severity == Severity.ERROR]
            assert any(e.code == "SHD-007" for e in errors), "Wrong entries_hash should be flagged"
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# L3: Sidecar verification with BLAKE3
# ---------------------------------------------------------------------------

@pytest.mark.REQ_L3_020
class TestBlake3Sidecar:
    """Sidecar (.meshpack.integrity) verification must work with BLAKE3."""

    def test_sidecar_blake3_verified(self, pack_builder: MeshPackBuilder) -> None:
        """Sidecar with matching BLAKE3 pack_hash must pass verification."""
        entry = _make_blake3_entry()
        pack_builder.set_manifest_field("hash_algo", "blake3")
        path = pack_builder.add_shard(
            "part-00001", [entry], entries_count=1
        ).build_to_file()

        # Compute BLAKE3 hash of the archive file
        with open(path, "rb") as f:
            pack_data = f.read()
        digest = _blake3_hex(pack_data)

        sidecar_path = path + ".integrity"
        sidecar = {
            "format_version": "1.0.0",
            "hash_algo": "blake3",
            "pack_hash": f"blake3:{digest}",
        }
        with open(sidecar_path, "w") as f:
            json.dump(sidecar, f)

        try:
            findings = validate(path)
            infos = [f for f in findings if f.severity == Severity.INFO]
            assert any(
                f.code == "SDC-010" for f in infos
            ), "BLAKE3 sidecar verification should succeed"
        finally:
            os.unlink(path)
            os.unlink(sidecar_path)

    def test_sidecar_blake3_mismatch(self, pack_builder: MeshPackBuilder) -> None:
        """Sidecar with wrong BLAKE3 pack_hash must produce SDC-005 error."""
        entry = _make_blake3_entry()
        pack_builder.set_manifest_field("hash_algo", "blake3")
        path = pack_builder.add_shard(
            "part-00001", [entry], entries_count=1
        ).build_to_file()

        sidecar_path = path + ".integrity"
        sidecar = {
            "format_version": "1.0.0",
            "hash_algo": "blake3",
            "pack_hash": "blake3:" + "00" * 32,
        }
        with open(sidecar_path, "w") as f:
            json.dump(sidecar, f)

        try:
            findings = validate(path)
            errors = [f for f in findings if f.severity == Severity.ERROR]
            assert any(
                e.code == "SDC-005" for e in errors
            ), "Wrong BLAKE3 sidecar hash should produce SDC-005"
        finally:
            os.unlink(path)
            os.unlink(sidecar_path)
