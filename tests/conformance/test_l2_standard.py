"""
L2 Conformance Tests -- Standard Reader/Writer.

Tests in this module verify that a MeshPack archive meets the L2 (Standard
Reader/Writer) requirements from definition/requirements/L2-standard.md.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import zipfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from tools.meshpack_validate import (  # noqa: E402
    validate,
    Severity,
    jcs_canonicalize,
    verify_entries_hash,
    _jcs_serialize_number,
    _jcs_serialize_string,
)
from conftest import MeshPackBuilder  # noqa: E402


# ---------------------------------------------------------------------------
# REQ-L2-000: manifest.json MUST be the first ZIP entry
# ---------------------------------------------------------------------------

@pytest.mark.REQ_L2_000
class TestZipOrdering:
    def test_manifest_first(self, tmp_meshpack: str) -> None:
        """manifest.json should be the first entry in the ZIP."""
        with zipfile.ZipFile(tmp_meshpack) as zf:
            assert zf.namelist()[0] == "manifest.json"

    def test_manifest_not_first_warned(self, pack_builder: MeshPackBuilder, minimal_valid_entry: dict) -> None:
        """Archive where manifest is NOT first should produce a warning."""
        pack_builder.set_manifest_not_first()
        path = pack_builder.add_shard("part-00001", [minimal_valid_entry]).build_to_file()
        try:
            findings = validate(path)
            warnings = [f for f in findings if f.severity == Severity.WARNING]
            assert any("ZIP-001" in f.code for f in warnings)
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# Spec §2.1: only DEFLATE or STORE compression methods
# ---------------------------------------------------------------------------

class TestZipCompression:
    def test_deflate_accepted(self, tmp_meshpack: str) -> None:
        """DEFLATE compression must not produce ZIP-003."""
        findings = validate(tmp_meshpack)
        errors = [f for f in findings if f.code == "ZIP-003"]
        assert not errors

    def test_bzip2_rejected(self, pack_builder: MeshPackBuilder, minimal_valid_entry: dict) -> None:
        """Archive with BZIP2 compressed entries should produce ZIP-003."""
        path = pack_builder.add_shard("part-00001", [minimal_valid_entry]).build_to_file(
            compression=zipfile.ZIP_BZIP2
        )
        try:
            findings = validate(path)
            errors = [f for f in findings if f.code == "ZIP-003"]
            assert errors, "Expected ZIP-003 error for BZIP2 compression"
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# REQ-L2-001: shard_list MUST be present and non-empty
# ---------------------------------------------------------------------------

@pytest.mark.REQ_L2_001
class TestShardList:
    def test_shard_list_present(self, tmp_meshpack: str) -> None:
        """Manifest must contain shard_list."""
        with zipfile.ZipFile(tmp_meshpack) as zf:
            manifest = json.loads(zf.read("manifest.json"))
        assert "shard_list" in manifest
        assert len(manifest["shard_list"]) >= 1


# ---------------------------------------------------------------------------
# REQ-L2-002: Shard IDs MUST match ^part-\d{5}$
# ---------------------------------------------------------------------------

@pytest.mark.REQ_L2_002
class TestShardIdFormat:
    def test_valid_shard_id(self, tmp_meshpack: str) -> None:
        """Shards should have 5-digit zero-padded IDs."""
        import re
        with zipfile.ZipFile(tmp_meshpack) as zf:
            manifest = json.loads(zf.read("manifest.json"))
        for shard in manifest.get("shard_list", []):
            assert re.match(r"^part-\d{5}$", shard["id"]), f"Bad shard ID: {shard['id']}"

    def test_old_format_warned(self, pack_builder: MeshPackBuilder, minimal_valid_entry: dict) -> None:
        """Shard with 3-digit ID should produce a warning."""
        pack_builder._manifest["shard_list"].append({"id": "part-001"})
        # Manually add shard file with old name
        pack_builder._shards["part-001"] = {
            "shard_id": "part-001",
            "format_version": "1.0.0",
            "entries": [minimal_valid_entry],
        }
        path = pack_builder.build_to_file()
        try:
            findings = validate(path)
            warnings = [f for f in findings if f.severity == Severity.WARNING]
            assert any("SHD-001" in f.code for f in warnings)
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# REQ-L2-005: entries MUST be sorted lexicographically by path
# ---------------------------------------------------------------------------

@pytest.mark.REQ_L2_005
class TestEntrySorting:
    def test_sorted_entries(self, tmp_meshpack: str) -> None:
        """Entries must be sorted by path."""
        with zipfile.ZipFile(tmp_meshpack) as zf:
            for name in zf.namelist():
                if name.startswith("index/part-"):
                    shard = json.loads(zf.read(name))
                    paths = [e["path"] for e in shard.get("entries", [])]
                    assert paths == sorted(paths), f"Entries not sorted in {name}"

    def test_unsorted_warned(self, pack_builder: MeshPackBuilder) -> None:
        """Unsorted entries should produce a warning."""
        entries = [
            {
                "path": "z_file.stl",
                "size_bytes": 10,
                "hash": "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                "modified_at": "2026-01-01T00:00:00+00:00",
            },
            {
                "path": "a_file.stl",
                "size_bytes": 20,
                "hash": "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                "modified_at": "2026-01-01T00:00:00+00:00",
            },
        ]
        path = pack_builder.add_shard("part-00001", entries, entries_count=2).build_to_file()
        try:
            findings = validate(path)
            warnings = [f for f in findings if f.severity == Severity.WARNING]
            assert any("SHD-004" in f.code for f in warnings)
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# REQ-L2-010: entries_count MUST match actual entry count
# ---------------------------------------------------------------------------

@pytest.mark.REQ_L2_010
class TestEntriesCount:
    def test_count_mismatch_error(self, pack_builder: MeshPackBuilder, minimal_valid_entry: dict) -> None:
        """Mismatched entries_count must produce an error."""
        path = pack_builder.add_shard(
            "part-00001", [minimal_valid_entry], entries_count=999
        ).build_to_file()
        try:
            findings = validate(path)
            errors = [f for f in findings if f.severity == Severity.ERROR]
            assert any("SHD-005" in f.code for f in errors)
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# REQ-L2-010: entries_hash MUST be verified using RFC 8785 (JCS)
# ---------------------------------------------------------------------------

@pytest.mark.REQ_L2_010
class TestEntriesHashRFC8785:
    """Verify that entries_hash uses RFC 8785 (JCS) canonical JSON."""

    def test_valid_hash_accepted(self, pack_builder: MeshPackBuilder, minimal_valid_entry: dict) -> None:
        """A pack with a correctly computed JCS entries_hash must pass validation."""
        path = pack_builder.add_shard(
            "part-00001", [minimal_valid_entry], entries_count=1
        ).build_to_file()
        try:
            findings = validate(path)
            errors = [f for f in findings if f.severity == Severity.ERROR]
            hash_errors = [f for f in errors if f.code == "SHD-007"]
            assert not hash_errors, f"Unexpected hash mismatch: {hash_errors}"
        finally:
            os.unlink(path)

    def test_wrong_hash_rejected(self, pack_builder: MeshPackBuilder, minimal_valid_entry: dict) -> None:
        """A pack with a bogus entries_hash must produce SHD-007."""
        bogus_hash = "sha256:" + "0" * 64
        path = pack_builder.add_shard(
            "part-00001", [minimal_valid_entry],
            entries_count=1, entries_hash=bogus_hash,
        ).build_to_file()
        try:
            findings = validate(path)
            errors = [f for f in findings if f.severity == Severity.ERROR]
            assert any("SHD-007" in f.code for f in errors)
        finally:
            os.unlink(path)

    def test_hash_uses_jcs_not_json_dumps(self) -> None:
        """Ensure jcs_canonicalize differs from naive json.dumps for non-ASCII."""
        # Non-ASCII characters must NOT be \\uXXXX-escaped in JCS
        data = {"key": "caf\u00e9"}
        jcs_out = jcs_canonicalize(data)
        naive_out = json.dumps(data, sort_keys=True, separators=(",", ":"))
        # Python's json.dumps with ensure_ascii=True escapes the e-acute
        assert "caf\u00e9".encode() in jcs_out, "JCS must pass non-ASCII through verbatim"
        assert "\\u00e9" in naive_out, "json.dumps should escape non-ASCII by default"

    def test_jcs_recursive_key_sorting(self) -> None:
        """Keys must be sorted recursively through nested objects."""
        data = {"z": {"b": 2, "a": 1}, "a": 0}
        result = jcs_canonicalize(data)
        assert result == b'{"a":0,"z":{"a":1,"b":2}}'

    def test_jcs_number_integer(self) -> None:
        """Integers must be rendered without decimal point."""
        assert _jcs_serialize_number(42) == "42"
        assert _jcs_serialize_number(0) == "0"
        assert _jcs_serialize_number(-1) == "-1"

    def test_jcs_number_float_whole(self) -> None:
        """Whole-number floats below 10^21 render as integers per ECMAScript."""
        assert _jcs_serialize_number(1.0) == "1"
        assert _jcs_serialize_number(1e20) == "100000000000000000000"

    def test_jcs_number_float_exponential(self) -> None:
        """Large/small floats use ECMAScript exponential notation."""
        assert _jcs_serialize_number(1e21) == "1e+21"
        assert _jcs_serialize_number(1e-7) == "1e-7"

    def test_jcs_number_float_small_decimal(self) -> None:
        """Small decimals use 0.000... form when -6 < n <= 0."""
        assert _jcs_serialize_number(1e-6) == "0.000001"
        assert _jcs_serialize_number(0.1) == "0.1"

    def test_jcs_number_negative_zero(self) -> None:
        """Negative zero must render as '0' per RFC 8785."""
        assert _jcs_serialize_number(-0.0) == "0"

    def test_jcs_number_nan_infinity_rejected(self) -> None:
        """NaN and Infinity must raise ValueError."""
        import math
        with pytest.raises(ValueError):
            _jcs_serialize_number(float("nan"))
        with pytest.raises(ValueError):
            _jcs_serialize_number(float("inf"))

    def test_jcs_string_control_chars(self) -> None:
        """Control characters must use correct JCS escape sequences."""
        assert _jcs_serialize_string("\t") == '"\\t"'
        assert _jcs_serialize_string("\n") == '"\\n"'
        assert _jcs_serialize_string("\x00") == '"\\u0000"'
        assert _jcs_serialize_string("\x1f") == '"\\u001f"'

    def test_jcs_string_non_ascii_verbatim(self) -> None:
        """Non-ASCII characters must NOT be escaped in JCS."""
        result = _jcs_serialize_string("\u00e9")  # e-acute
        assert result == '"\u00e9"'

    def test_entries_hash_sorts_before_hashing(self) -> None:
        """verify_entries_hash must sort entries by path before hashing."""
        entry_a = {
            "path": "a.txt",
            "size_bytes": 10,
            "hash": "sha256:" + "aa" * 32,
            "modified_at": "2026-01-01T00:00:00+00:00",
        }
        entry_z = {
            "path": "z.txt",
            "size_bytes": 20,
            "hash": "sha256:" + "bb" * 32,
            "modified_at": "2026-01-01T00:00:00+00:00",
        }
        # Compute the expected hash from sorted order
        sorted_entries = [entry_a, entry_z]
        canonical = jcs_canonicalize(sorted_entries)
        expected = "sha256:" + hashlib.sha256(canonical).hexdigest()

        # Pass entries in reverse order -- hash should still match
        ok, actual = verify_entries_hash([entry_z, entry_a], "sha256", expected)
        assert ok, f"Hash mismatch: expected {expected}, got {actual}"

    def test_entries_hash_with_multiple_entries(self, pack_builder: MeshPackBuilder) -> None:
        """End-to-end: archive with multiple entries passes hash verification."""
        entries = [
            {
                "path": "models/a.stl",
                "size_bytes": 100,
                "hash": "sha256:" + "aa" * 32,
                "modified_at": "2026-01-01T00:00:00+00:00",
            },
            {
                "path": "models/b.stl",
                "size_bytes": 200,
                "hash": "sha256:" + "bb" * 32,
                "modified_at": "2026-01-01T00:00:00+00:00",
            },
        ]
        path = pack_builder.add_shard(
            "part-00001", entries, entries_count=2
        ).build_to_file()
        try:
            findings = validate(path)
            errors = [f for f in findings if f.severity == Severity.ERROR]
            hash_errors = [f for f in errors if f.code == "SHD-007"]
            assert not hash_errors, f"Hash mismatch with multiple entries: {hash_errors}"
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# REQ-L2-020: resource_ref filenames MUST NOT contain colons
# ---------------------------------------------------------------------------

@pytest.mark.REQ_L2_020
class TestResourceRefFormat:
    def test_colon_in_ref_warned(self, pack_builder: MeshPackBuilder) -> None:
        """resource_ref with colon (algo prefix) should produce a warning."""
        entry = {
            "path": "models/test.stl",
            "size_bytes": 100,
            "hash": "sha256:aabbccdd" + "00" * 28,
            "modified_at": "2026-01-01T00:00:00+00:00",
            "resource_ref": "sha256:aabbccdd" + "00" * 28 + ".stl",
            "resource_hash": "sha256:aabbccdd" + "00" * 28,
        }
        path = pack_builder.add_shard("part-00001", [entry]).build_to_file()
        try:
            findings = validate(path)
            warnings = [f for f in findings if f.severity == Severity.WARNING]
            assert any("RES-003" in f.code for f in warnings)
        finally:
            os.unlink(path)
