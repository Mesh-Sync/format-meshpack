"""
L1 Conformance Tests — Minimal Reader.

Tests in this module verify that a MeshPack archive meets the L1 (Minimal Reader)
requirements from definition/requirements/L1-minimal.md.
"""

from __future__ import annotations

import json
import os
import sys
import zipfile

import pytest

# Add project root so we can import the validator
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from tools.meshpack_validate import validate, Severity  # noqa: E402
from conftest import MeshPackBuilder  # noqa: E402


# ---------------------------------------------------------------------------
# REQ-L1-001: Archive MUST be a valid ZIP
# ---------------------------------------------------------------------------

@pytest.mark.REQ_L1_001
class TestArchiveFormat:
    def test_valid_zip(self, tmp_meshpack: str) -> None:
        """A valid .meshpack is a valid ZIP archive."""
        assert zipfile.is_zipfile(tmp_meshpack)

    def test_corrupt_zip_rejected(self, tmp_path: str) -> None:
        """A non-ZIP file must produce errors."""
        bad = os.path.join(str(tmp_path), "bad.meshpack")
        with open(bad, "wb") as f:
            f.write(b"this is not a zip file")
        findings = validate(bad)
        errors = [f for f in findings if f.severity == Severity.ERROR]
        assert any("ARC-001" in f.code for f in errors)


# ---------------------------------------------------------------------------
# REQ-L1-001 / Spec §2.1: Only DEFLATE (method 8) or STORE (method 0)
# ---------------------------------------------------------------------------

@pytest.mark.REQ_L1_001
class TestCompressionMethods:
    def test_deflate_accepted(self, tmp_meshpack: str) -> None:
        """DEFLATE compression (default) must not produce ZIP-002 errors."""
        findings = validate(tmp_meshpack)
        errors = [f for f in findings if f.code == "ZIP-002"]
        assert len(errors) == 0

    def test_store_accepted(
        self, pack_builder: MeshPackBuilder, minimal_valid_entry: dict
    ) -> None:
        """STORE compression (method 0) must not produce ZIP-002 errors."""
        pack_builder.set_compression(zipfile.ZIP_STORED)
        path = pack_builder.add_shard(
            "part-00001", [minimal_valid_entry], entries_count=1
        ).build_to_file()
        try:
            findings = validate(path)
            errors = [f for f in findings if f.code == "ZIP-002"]
            assert len(errors) == 0
        finally:
            os.unlink(path)

    def test_bzip2_rejected(
        self, pack_builder: MeshPackBuilder, minimal_valid_entry: dict
    ) -> None:
        """BZip2 compression (method 12) must produce ZIP-002 errors."""
        pack_builder.set_compression(zipfile.ZIP_BZIP2)
        path = pack_builder.add_shard(
            "part-00001", [minimal_valid_entry], entries_count=1
        ).build_to_file()
        try:
            findings = validate(path)
            errors = [f for f in findings if f.severity == Severity.ERROR]
            assert any(f.code == "ZIP-002" for f in errors)
            # Verify the error message mentions the offending method
            zip002 = [f for f in errors if f.code == "ZIP-002"]
            assert any("BZIP2" in f.message for f in zip002)
        finally:
            os.unlink(path)

    def test_lzma_rejected(
        self, pack_builder: MeshPackBuilder, minimal_valid_entry: dict
    ) -> None:
        """LZMA compression (method 14) must produce ZIP-002 errors."""
        pack_builder.set_compression(zipfile.ZIP_LZMA)
        path = pack_builder.add_shard(
            "part-00001", [minimal_valid_entry], entries_count=1
        ).build_to_file()
        try:
            findings = validate(path)
            errors = [f for f in findings if f.severity == Severity.ERROR]
            assert any(f.code == "ZIP-002" for f in errors)
            zip002 = [f for f in errors if f.code == "ZIP-002"]
            assert any("LZMA" in f.message for f in zip002)
        finally:
            os.unlink(path)

    def test_unsupported_compression_reports_all_entries(
        self, pack_builder: MeshPackBuilder, minimal_valid_entry: dict
    ) -> None:
        """Each entry using a prohibited method must generate its own ZIP-002 finding."""
        second_entry = {
            "path": "models/sphere.stl",
            "size_bytes": 5678,
            "hash": "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            "modified_at": "2026-01-01T00:00:00+00:00",
        }
        pack_builder.set_compression(zipfile.ZIP_BZIP2)
        path = pack_builder.add_shard(
            "part-00001",
            [minimal_valid_entry, second_entry],
            entries_count=2,
        ).build_to_file()
        try:
            findings = validate(path)
            zip002 = [f for f in findings if f.code == "ZIP-002"]
            # Should flag every entry in the archive (manifest + shard)
            assert len(zip002) >= 2
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# REQ-L1-002: manifest.json MUST exist at ZIP root
# ---------------------------------------------------------------------------

@pytest.mark.REQ_L1_002
class TestManifestPresence:
    def test_manifest_exists(self, tmp_meshpack: str) -> None:
        """manifest.json must be present in the archive."""
        with zipfile.ZipFile(tmp_meshpack) as zf:
            assert "manifest.json" in zf.namelist()

    def test_missing_manifest_is_error(self, pack_builder: MeshPackBuilder) -> None:
        """Archive without manifest.json must be rejected."""
        # Build a pack, then recreate ZIP without manifest
        import io
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("index/part-00001.json", '{"shard_id":"part-00001","entries":[]}')
        data = buf.getvalue()
        import tempfile
        fd, path = tempfile.mkstemp(suffix=".meshpack")
        os.close(fd)
        try:
            with open(path, "wb") as f:
                f.write(data)
            findings = validate(path)
            errors = [f for f in findings if f.severity == Severity.ERROR]
            assert any("MAN-001" in f.code for f in errors)
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# REQ-L1-003: format_version MUST be valid semver
# ---------------------------------------------------------------------------

@pytest.mark.REQ_L1_003
class TestFormatVersion:
    def test_valid_semver(self, tmp_meshpack: str) -> None:
        """format_version in manifest is valid semver."""
        with zipfile.ZipFile(tmp_meshpack) as zf:
            manifest = json.loads(zf.read("manifest.json"))
        import re
        assert re.match(r"^\d+\.\d+\.\d+$", manifest["format_version"])


# ---------------------------------------------------------------------------
# REQ-L1-004: hash_algo MUST be present and supported
# ---------------------------------------------------------------------------

@pytest.mark.REQ_L1_004
class TestHashAlgo:
    def test_hash_algo_required(self, pack_builder: MeshPackBuilder, minimal_valid_entry: dict) -> None:
        """Missing hash_algo is flagged."""
        pack_builder.remove_manifest_field("hash_algo")
        path = pack_builder.add_shard("part-00001", [minimal_valid_entry]).build_to_file()
        try:
            findings = validate(path)
            errors = [f for f in findings if f.severity == Severity.ERROR]
            assert any("MAN-010" in f.code for f in errors)
        finally:
            os.unlink(path)

    def test_unsupported_algo_rejected(self, pack_builder: MeshPackBuilder, minimal_valid_entry: dict) -> None:
        """Unsupported hash_algo value is flagged."""
        pack_builder.set_manifest_field("hash_algo", "md5")
        path = pack_builder.add_shard("part-00001", [minimal_valid_entry]).build_to_file()
        try:
            findings = validate(path)
            errors = [f for f in findings if f.severity == Severity.ERROR]
            assert any("MAN-012" in f.code for f in errors)
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# REQ-L1-010: Entries MUST have path, size_bytes, hash
# ---------------------------------------------------------------------------

@pytest.mark.REQ_L1_010
class TestEntryRequiredFields:
    def test_entry_has_path(self, tmp_meshpack: str) -> None:
        """Every entry must have a 'path' field."""
        with zipfile.ZipFile(tmp_meshpack) as zf:
            for name in zf.namelist():
                if name.startswith("index/part-"):
                    shard = json.loads(zf.read(name))
                    for entry in shard.get("entries", []):
                        assert "path" in entry, f"Entry missing 'path' in {name}"


# ---------------------------------------------------------------------------
# REQ-L1-011: Paths MUST NOT exceed 1024 chars
# ---------------------------------------------------------------------------

@pytest.mark.REQ_L1_011
class TestPathLength:
    def test_long_path_flagged(self, pack_builder: MeshPackBuilder) -> None:
        """Path exceeding 1024 chars must produce an error."""
        long_entry = {
            "path": "a" * 1025,
            "size_bytes": 0,
            "hash": "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            "modified_at": "2026-01-01T00:00:00+00:00",
        }
        path = pack_builder.add_shard("part-00001", [long_entry]).build_to_file()
        try:
            findings = validate(path)
            errors = [f for f in findings if f.severity == Severity.ERROR]
            assert any("ENT-001" in f.code for f in errors)
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# REQ-L1-012: Paths MUST NOT contain traversal sequences
# ---------------------------------------------------------------------------

@pytest.mark.REQ_L1_012
class TestPathTraversal:
    def test_traversal_flagged(self, pack_builder: MeshPackBuilder) -> None:
        """Paths with '..' must produce an error."""
        bad_entry = {
            "path": "../etc/passwd",
            "size_bytes": 0,
            "hash": "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            "modified_at": "2026-01-01T00:00:00+00:00",
        }
        path = pack_builder.add_shard("part-00001", [bad_entry]).build_to_file()
        try:
            findings = validate(path)
            errors = [f for f in findings if f.severity == Severity.ERROR]
            assert any("ENT-002" in f.code for f in errors)
        finally:
            os.unlink(path)
