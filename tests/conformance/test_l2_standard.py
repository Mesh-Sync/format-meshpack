"""
L2 Conformance Tests — Standard Reader/Writer.

Tests in this module verify that a MeshPack archive meets the L2 (Standard
Reader/Writer) requirements from definition/requirements/L2-standard.md.
"""

from __future__ import annotations

import json
import os
import sys
import zipfile

import pytest

# Add project root so we can import the validator, and conformance dir for conftest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.dirname(__file__))

from tools.meshpack_validate import validate, Severity  # noqa: E402
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
