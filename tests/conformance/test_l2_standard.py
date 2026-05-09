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
from .conftest import MeshPackBuilder  # noqa: E402


def _write_sidecar(path: str, pack_hash: str | None = None) -> str:
    with open(path, "rb") as archive_file:
        digest = hashlib.sha256(archive_file.read()).hexdigest()
    sidecar = {
        "pack_name": os.path.basename(path),
        "pack_size_bytes": os.path.getsize(path),
        "hash_algo": "sha256",
        "pack_hash": pack_hash or f"sha256:{digest}",
        "computed_at": "2026-05-09T00:00:00Z",
        "signatures": [],
    }
    sidecar_path = path + ".integrity"
    with open(sidecar_path, "w", encoding="utf-8") as sidecar_file:
        json.dump(sidecar, sidecar_file)
    return sidecar_path


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
# REQ-L2-001: only DEFLATE or STORE compression methods
# ---------------------------------------------------------------------------

@pytest.mark.REQ_L2_001
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
# FR-053: zip bomb protection
# ---------------------------------------------------------------------------

class TestZipBombProtection:
    def test_normal_archive_passes(self, tmp_meshpack: str) -> None:
        """Normal archives should not trigger zip bomb errors."""
        findings = validate(tmp_meshpack)
        bomb_errors = [f for f in findings if f.code in ("ZIP-004", "ZIP-005")]
        assert not bomb_errors

    def test_low_ratio_triggers_zip004(self, tmp_meshpack: str) -> None:
        """An archive exceeding a very low max_ratio should produce ZIP-004."""
        # Use max_ratio=1 — any DEFLATED entry will have ratio > 1
        findings = validate(tmp_meshpack, max_ratio=1)
        ratio_errors = [f for f in findings if f.code == "ZIP-004"]
        assert ratio_errors, "Expected ZIP-004 for max_ratio=1"

    def test_low_max_size_triggers_zip005(self, tmp_meshpack: str) -> None:
        """An archive exceeding a very low max_size should produce ZIP-005."""
        findings = validate(tmp_meshpack, max_size=1)
        size_errors = [f for f in findings if f.code == "ZIP-005"]
        assert size_errors, "Expected ZIP-005 for max_size=1"


# ---------------------------------------------------------------------------
# REQ-L1-003: shard_list MUST be present and non-empty
# ---------------------------------------------------------------------------

@pytest.mark.REQ_L1_003
class TestShardList:
    def test_shard_list_present(self, tmp_meshpack: str) -> None:
        """Manifest must contain shard_list."""
        with zipfile.ZipFile(tmp_meshpack) as zf:
            manifest = json.loads(zf.read("manifest.json"))
        assert "shard_list" in manifest
        assert len(manifest["shard_list"]) >= 1


# ---------------------------------------------------------------------------
# REQ-L2-003: Shard IDs MUST match ^part-\d{5}$
# ---------------------------------------------------------------------------

@pytest.mark.REQ_L2_003
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
            "format_version": "2.0.0",
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
# REQ-L2-003: entries MUST be sorted lexicographically by path
# ---------------------------------------------------------------------------

@pytest.mark.REQ_L2_003
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
                "original_name": "z_file.stl",
                "size_bytes": 10,
                "hash": "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                "modified_at": "2026-01-01T00:00:00+00:00",
            },
            {
                "path": "a_file.stl",
                "original_name": "a_file.stl",
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

    def test_utf8_byte_order_for_non_ascii_paths(self, pack_builder: MeshPackBuilder) -> None:
        """Path sorting is defined by UTF-8 byte order, not locale collation."""
        ascii_entry = {
            "path": "models/z.stl",
            "original_name": "z.stl",
            "size_bytes": 10,
            "hash": "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            "modified_at": "2026-01-01T00:00:00+00:00",
        }
        unicode_entry = {
            "path": "models/é.stl",
            "original_name": "é.stl",
            "size_bytes": 20,
            "hash": "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            "modified_at": "2026-01-01T00:00:00+00:00",
        }
        path = pack_builder.add_shard("part-00001", [ascii_entry, unicode_entry], entries_count=2).build_to_file()
        try:
            findings = validate(path)
            warnings = [f for f in findings if f.severity == Severity.WARNING]
            assert not [f for f in warnings if f.code == "SHD-004"], warnings
        finally:
            os.unlink(path)


@pytest.mark.REQ_L1_030
class TestReadmeLayout:
    def test_missing_root_and_index_readmes_warned(self, pack_builder: MeshPackBuilder, minimal_valid_entry: dict) -> None:
        path = pack_builder.add_shard("part-00001", [minimal_valid_entry]).build_to_file()
        try:
            findings = validate(path)
            warnings = {f.code for f in findings if f.severity == Severity.WARNING}
            assert "LAY-001" in warnings
            assert "LAY-002" in warnings
        finally:
            os.unlink(path)

    def test_missing_resource_readme_warned_when_resources_present(self, pack_builder: MeshPackBuilder, minimal_valid_entry: dict) -> None:
        path = pack_builder.add_shard("part-00001", [minimal_valid_entry]).add_resource("a" * 64 + ".png", b"abc").build_to_file()
        try:
            findings = validate(path)
            warnings = {f.code for f in findings if f.severity == Severity.WARNING}
            assert "LAY-003" in warnings
        finally:
            os.unlink(path)

    def test_readme_crlf_rejected(self, pack_builder: MeshPackBuilder, minimal_valid_entry: dict) -> None:
        path = pack_builder.add_shard("part-00001", [minimal_valid_entry]).add_extra_file(
            "_README.md",
            b"MeshPack archive\r\n",
        ).build_to_file()
        try:
            findings = validate(path)
            errors = {f.code for f in findings if f.severity == Severity.ERROR}
            assert "LAY-004" in errors
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# REQ-L2-002: generated shard_list entries_count MUST match actual entry count
# ---------------------------------------------------------------------------

@pytest.mark.REQ_L2_002
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


@pytest.mark.REQ_L2_002
class TestManifestSummary:
    def test_total_files_mismatch_error(self, pack_builder: MeshPackBuilder, minimal_valid_entry: dict) -> None:
        path = pack_builder.add_shard("part-00001", [minimal_valid_entry]).build_to_file()
        pack_builder._manifest["index_summary"]["total_files"] = 999
        path = pack_builder.build_to_file(path=path)
        try:
            findings = validate(path)
            errors = [f for f in findings if f.severity == Severity.ERROR]
            assert any(f.code == "MAN-022" and "total_files" in f.message for f in errors)
        finally:
            os.unlink(path)

    def test_total_size_mismatch_error(self, pack_builder: MeshPackBuilder, minimal_valid_entry: dict) -> None:
        path = pack_builder.add_shard("part-00001", [minimal_valid_entry]).build_to_file()
        pack_builder._manifest["index_summary"]["total_size_bytes"] = 999
        path = pack_builder.build_to_file(path=path)
        try:
            findings = validate(path)
            errors = [f for f in findings if f.severity == Severity.ERROR]
            assert any(f.code == "MAN-022" and "total_size_bytes" in f.message for f in errors)
        finally:
            os.unlink(path)


@pytest.mark.REQ_L1_010
@pytest.mark.REQ_L2_002
class TestShardManifestConsistency:
    def test_unlisted_shard_rejected(self, pack_builder: MeshPackBuilder, minimal_valid_entry: dict) -> None:
        rogue_shard = {
            "shard_id": "part-00002",
            "format_version": "2.0.0",
            "entries_count": 0,
            "entries_hash": "sha256:4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
            "entries": [],
        }
        path = pack_builder.add_shard("part-00001", [minimal_valid_entry]).add_extra_file(
            "index/part-00002.json",
            json.dumps(rogue_shard).encode("utf-8"),
        ).build_to_file()
        try:
            findings = validate(path)
            errors = [f for f in findings if f.severity == Severity.ERROR]
            assert any(f.code == "SHD-011" for f in errors)
        finally:
            os.unlink(path)

    def test_shard_filename_id_mismatch_rejected(self, pack_builder: MeshPackBuilder, minimal_valid_entry: dict) -> None:
        pack_builder.add_shard("part-00001", [minimal_valid_entry])
        pack_builder._shards["part-00001"]["shard_id"] = "part-00002"
        path = pack_builder.build_to_file()
        try:
            findings = validate(path)
            errors = [f for f in findings if f.severity == Severity.ERROR]
            assert any(f.code == "SHD-008" for f in errors)
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# REQ-L2-010: entries_hash MUST be verified using RFC 8785 (JCS)
# ---------------------------------------------------------------------------

@pytest.mark.REQ_L2_010
@pytest.mark.REQ_L2_011
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

    def test_jcs_object_keys_sort_by_utf16_code_units(self) -> None:
        """Supplementary-plane keys must sort by UTF-16 code units, not Unicode scalar value."""
        data = {"\ue000": 2, "\U0001f600": 1}

        result = jcs_canonicalize(data)

        assert result == '{"\U0001f600":1,"\ue000":2}'.encode("utf-8")

    def test_entries_hash_with_utf16_key_order_vector(self) -> None:
        """Shared SDK vector: nested extension keys exercise RFC 8785 UTF-16 sorting."""
        vector_path = os.path.join(os.path.dirname(__file__), "..", "sdk_validation_vectors.json")
        with open(vector_path, "r", encoding="utf-8") as vector_file:
            vector = json.load(vector_file)["vectors"][0]

        ok, actual = verify_entries_hash([vector["entry"]], "sha256", vector["entries_hash"])

        assert ok, f"Hash mismatch: expected {vector['entries_hash']}, got {actual}"

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
            "original_name": "a.txt",
            "size_bytes": 10,
            "hash": "sha256:" + "aa" * 32,
            "modified_at": "2026-01-01T00:00:00+00:00",
        }
        entry_z = {
            "path": "z.txt",
            "original_name": "z.txt",
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
                "original_name": "a.stl",
                "size_bytes": 100,
                "hash": "sha256:" + "aa" * 32,
                "modified_at": "2026-01-01T00:00:00+00:00",
            },
            {
                "path": "models/b.stl",
                "original_name": "b.stl",
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
@pytest.mark.REQ_L2_021
class TestResourceRefFormat:
    def test_colon_in_ref_warned(self, pack_builder: MeshPackBuilder) -> None:
        """resource_ref with colon (algo prefix) should produce a warning."""
        entry = {
            "path": "models/test.stl",
            "original_name": "test.stl",
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

    def test_resource_hash_mismatch_rejected(self, pack_builder: MeshPackBuilder) -> None:
        """resource_hash must match the actual embedded resource bytes."""
        resource_ref = "a" * 64 + ".png"
        entry = {
            "path": "models/test.stl",
            "original_name": "test.stl",
            "size_bytes": 100,
            "hash": "sha256:" + "aa" * 32,
            "modified_at": "2026-01-01T00:00:00+00:00",
            "resource_ref": resource_ref,
            "resource_hash": "sha256:" + "00" * 32,
            "resource_size_bytes": 3,
        }
        path = pack_builder.add_shard("part-00001", [entry]).add_resource(resource_ref, b"abc").build_to_file()
        try:
            findings = validate(path)
            errors = [f for f in findings if f.severity == Severity.ERROR]
            assert any(f.code == "RES-005" for f in errors)
        finally:
            os.unlink(path)

    def test_resource_size_mismatch_rejected(self, pack_builder: MeshPackBuilder) -> None:
        """resource_size_bytes must match the actual embedded resource bytes."""
        resource_ref = "a" * 64 + ".png"
        digest = hashlib.sha256(b"abc").hexdigest()
        entry = {
            "path": "models/test.stl",
            "original_name": "test.stl",
            "size_bytes": 100,
            "hash": "sha256:" + "aa" * 32,
            "modified_at": "2026-01-01T00:00:00+00:00",
            "resource_ref": resource_ref,
            "resource_hash": "sha256:" + digest,
            "resource_size_bytes": 999,
        }
        path = pack_builder.add_shard("part-00001", [entry]).add_resource(resource_ref, b"abc").build_to_file()
        try:
            findings = validate(path)
            errors = [f for f in findings if f.severity == Severity.ERROR]
            assert any(f.code == "RES-007" for f in errors)
        finally:
            os.unlink(path)

    @pytest.mark.parametrize(
        "resource_ref",
        [
            "../secret.png",
            "nested/thumb.png",
            "C:\\Users\\thumb.png",
            "\\\\server\\share\\thumb.png",
            "not-a-hash.png",
        ],
    )
    def test_unsafe_resource_ref_rejected(
        self, pack_builder: MeshPackBuilder, resource_ref: str
    ) -> None:
        """resource_ref is a resource filename, not an arbitrary ZIP path."""
        entry = {
            "path": "models/test.stl",
            "original_name": "test.stl",
            "size_bytes": 100,
            "hash": "sha256:aabbccdd" + "00" * 28,
            "modified_at": "2026-01-01T00:00:00+00:00",
            "resource_ref": resource_ref,
            "resource_hash": "sha256:aabbccdd" + "00" * 28,
        }
        path = pack_builder.add_shard("part-00001", [entry]).build_to_file()
        try:
            findings = validate(path)
            errors = [f for f in findings if f.severity == Severity.ERROR]
            assert any("RES-004" in f.code for f in errors)
        finally:
            os.unlink(path)


@pytest.mark.REQ_L2_012
@pytest.mark.REQ_L2_060
class TestMappingDbIntegrity:
    def test_mapping_db_bytes_are_included_in_sidecar_hash(self, pack_builder: MeshPackBuilder, minimal_valid_entry: dict) -> None:
        """A sidecar hash computed without mapping.db must not verify an archive that contains it."""
        without_mapping = pack_builder.add_shard("part-00001", [minimal_valid_entry]).build_to_file()
        with open(without_mapping, "rb") as archive_file:
            digest_without_mapping = hashlib.sha256(archive_file.read()).hexdigest()

        path = pack_builder.add_extra_file("mapping.db", b"cache bytes").build_to_file(path=without_mapping)
        sidecar_path = _write_sidecar(path, pack_hash=f"sha256:{digest_without_mapping}")

        try:
            findings = validate(path, schema_mode="strict")
            errors = [f for f in findings if f.severity == Severity.ERROR]
            assert any(f.code == "SDC-005" for f in errors)
        finally:
            os.unlink(path)
            os.unlink(sidecar_path)


@pytest.mark.REQ_L1_020
class TestSchemaMode:
    def test_unknown_manifest_fields_warn_in_compat_mode(self, pack_builder: MeshPackBuilder) -> None:
        pack_builder.set_manifest_field("future_field", True)
        path = pack_builder.add_shard("part-00001", [], entries_count=0).build_to_file()
        try:
            findings = validate(path, schema_mode="compat")
            warnings = [f for f in findings if f.severity == Severity.WARNING]
            assert any(f.code == "SCH-002" for f in warnings)
        finally:
            os.unlink(path)

    def test_unknown_manifest_fields_error_in_strict_mode(self, pack_builder: MeshPackBuilder) -> None:
        pack_builder.set_manifest_field("future_field", True)
        path = pack_builder.add_shard("part-00001", [], entries_count=0).build_to_file()
        try:
            findings = validate(path, schema_mode="strict")
            errors = [f for f in findings if f.severity == Severity.ERROR]
            assert any(f.code == "SCH-002" for f in errors)
        finally:
            os.unlink(path)


@pytest.mark.REQ_L3_040
class TestOfficialExtensionValidation:
    def test_valid_thumbnail_v2_extension_accepted(self, pack_builder: MeshPackBuilder) -> None:
        entry = {
            "path": "models/test.stl",
            "original_name": "test.stl",
            "size_bytes": 100,
            "hash": "sha256:" + "aa" * 32,
            "modified_at": "2026-01-01T00:00:00+00:00",
            "extensions": {
                "meshsync_thumbnails": {
                    "v2": {
                        "static": "a" * 64 + ".png",
                    }
                }
            },
        }
        path = pack_builder.add_shard("part-00001", [entry], entries_count=1).build_to_file()
        try:
            findings = validate(path, schema_mode="strict")
            errors = [f for f in findings if f.severity == Severity.ERROR]
            assert not errors
        finally:
            os.unlink(path)

    def test_invalid_official_extension_rejected(self, pack_builder: MeshPackBuilder) -> None:
        entry = {
            "path": "models/test.stl",
            "original_name": "test.stl",
            "size_bytes": 100,
            "hash": "sha256:" + "aa" * 32,
            "modified_at": "2026-01-01T00:00:00+00:00",
            "extensions": {
                "meshsync_thumbnails": {
                    "v2": {
                        "static": "sha256:" + "aa" * 32 + ".png",
                    }
                }
            },
        }
        path = pack_builder.add_shard("part-00001", [entry], entries_count=1).build_to_file()
        try:
            findings = validate(path, schema_mode="strict")
            errors = [f for f in findings if f.severity == Severity.ERROR]
            assert any(f.code == "SCH-001" for f in errors)
        finally:
            os.unlink(path)

# ---------------------------------------------------------------------------
# BLAKE3 hash algorithm support
# ---------------------------------------------------------------------------

blake3 = pytest.importorskip("blake3", reason="blake3 package not installed")


class TestBlake3Support:
    """Verify that archives using BLAKE3 hash_algo pass validation."""

    def _blake3_hash(self, data: bytes) -> str:
        return "blake3:" + blake3.blake3(data).hexdigest()

    def test_blake3_hash_accepted(self, pack_builder: MeshPackBuilder) -> None:
        """A pack with hash_algo=blake3 and correct hashes must pass."""
        pack_builder.set_manifest_field("hash_algo", "blake3")
        entry = {
            "path": "models/cube.stl",
            "original_name": "cube.stl",
            "size_bytes": 1234,
            "hash": self._blake3_hash(b"test-content"),
            "modified_at": "2026-01-01T00:00:00+00:00",
        }
        path = pack_builder.add_shard("part-00001", [entry], entries_count=1).build_to_file()
        try:
            findings = validate(path)
            errors = [f for f in findings if f.severity == Severity.ERROR]
            algo_errors = [f for f in errors if "blake3" in f.message.lower() or "MAN-012" in f.code]
            assert not algo_errors, f"Unexpected blake3-related errors: {algo_errors}"
        finally:
            os.unlink(path)

    def test_blake3_entries_hash_verified(self, pack_builder: MeshPackBuilder) -> None:
        """entries_hash with blake3 must be verified correctly."""
        pack_builder.set_manifest_field("hash_algo", "blake3")
        entry = {
            "path": "models/test.stl",
            "original_name": "test.stl",
            "size_bytes": 100,
            "hash": self._blake3_hash(b"data"),
            "modified_at": "2026-01-01T00:00:00+00:00",
        }
        path = pack_builder.add_shard("part-00001", [entry], entries_count=1).build_to_file()
        try:
            findings = validate(path)
            errors = [f for f in findings if f.severity == Severity.ERROR]
            hash_errors = [f for f in errors if f.code == "SHD-007"]
            assert not hash_errors, f"BLAKE3 entries_hash mismatch: {hash_errors}"
        finally:
            os.unlink(path)
