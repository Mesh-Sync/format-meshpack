"""
Shared fixtures and helpers for MeshPack conformance tests.
"""

from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from tools.meshpack_validate import jcs_canonicalize, compute_digest  # noqa: E402

FIXTURES_DIR = Path(__file__).parent / "fixtures"
VALID_DIR = FIXTURES_DIR / "valid"
INVALID_DIR = FIXTURES_DIR / "invalid"

_SENTINEL = object()


# ---------------------------------------------------------------------------
# Custom markers for requirement traceability
# ---------------------------------------------------------------------------

def pytest_configure(config: pytest.Config) -> None:
    """Register custom markers for all requirement IDs."""
    for level in ("L1", "L2", "L3"):
        for i in range(200):
            marker = f"REQ_{level}_{i:03d}"
            config.addinivalue_line("markers", f"{marker}: Traces to requirement REQ-{level}-{i:03d}")


# ---------------------------------------------------------------------------
# Pack builder helper
# ---------------------------------------------------------------------------

class MeshPackBuilder:
    """Fluent builder for creating .meshpack archives in tests."""

    def __init__(self) -> None:
        self._manifest: Dict[str, Any] = {
            "format_version": "1.0.0",
            "created_at": "2026-01-01T00:00:00+00:00",
            "workspace_id": "test-conformance",
            "hash_algo": "sha256",
            "index_summary": {
                "total_files": 0,
                "total_shards": 0,
                "total_size_bytes": 0,
            },
            "shard_list": [],
        }
        self._shards: Dict[str, Dict[str, Any]] = {}
        self._resources: Dict[str, bytes] = {}
        self._extra_files: Dict[str, bytes] = {}
        self._manifest_first: bool = True

    def set_manifest_field(self, key: str, value: Any) -> "MeshPackBuilder":
        self._manifest[key] = value
        return self

    def remove_manifest_field(self, key: str) -> "MeshPackBuilder":
        self._manifest.pop(key, None)
        return self

    def _compute_entries_hash(self, entries: List[Dict[str, Any]]) -> str:
        """Compute entries_hash per REQ-L2-010 using RFC 8785 (JCS)."""
        algo = self._manifest.get("hash_algo", "sha256")
        sorted_entries = sorted(entries, key=lambda e: e.get("path", ""))
        encoded = jcs_canonicalize(sorted_entries).encode("utf-8")
        digest = compute_digest([encoded], algo)
        return f"{algo}:{digest}"

    def add_shard(
        self,
        shard_id: str,
        entries: List[Dict[str, Any]],
        entries_count: Optional[int] = None,
        entries_hash: Any = _SENTINEL,
    ) -> "MeshPackBuilder":
        self._shards[shard_id] = {
            "shard_id": shard_id,
            "format_version": "1.0.0",
            "entries": entries,
        }

        # Auto-compute entries_hash via JCS when not explicitly provided
        if entries_hash is _SENTINEL:
            entries_hash = self._compute_entries_hash(entries)

        if entries_count is not None:
            self._shards[shard_id]["entries_count"] = entries_count
        if entries_hash is not None:
            self._shards[shard_id]["entries_hash"] = entries_hash

        # Update manifest shard_list
        shard_ref: Dict[str, Any] = {"id": shard_id}
        if entries_count is not None:
            shard_ref["entries_count"] = entries_count
        if entries_hash is not None:
            shard_ref["entries_hash"] = entries_hash
        self._manifest["shard_list"].append(shard_ref)
        self._manifest["index_summary"]["total_shards"] = len(self._shards)
        total_files = sum(len(s["entries"]) for s in self._shards.values())
        self._manifest["index_summary"]["total_files"] = total_files
        return self

    def add_resource(self, name: str, data: bytes) -> "MeshPackBuilder":
        self._resources[name] = data
        return self

    def add_extra_file(self, path: str, data: bytes) -> "MeshPackBuilder":
        """Add an arbitrary file to the ZIP (for negative tests)."""
        self._extra_files[path] = data
        return self

    def set_manifest_not_first(self) -> "MeshPackBuilder":
        """For negative tests: manifest will NOT be the first ZIP entry."""
        self._manifest_first = False
        return self

    def build(self) -> bytes:
        """Build the .meshpack ZIP archive as bytes."""
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            manifest_bytes = json.dumps(self._manifest, indent=2).encode("utf-8")

            if self._manifest_first:
                zf.writestr("manifest.json", manifest_bytes)

            # Shards
            for shard_id, shard_data in self._shards.items():
                zf.writestr(
                    f"index/{shard_id}.json",
                    json.dumps(shard_data, indent=2).encode("utf-8"),
                )

            # Resources
            for name, data in self._resources.items():
                zf.writestr(f"resources/{name}", data)

            # Extra files
            for path, data in self._extra_files.items():
                zf.writestr(path, data)

            if not self._manifest_first:
                zf.writestr("manifest.json", manifest_bytes)

        return buf.getvalue()

    def build_to_file(self, path: Optional[str] = None) -> str:
        """Build and write to a temporary file. Returns file path."""
        data = self.build()
        if path is None:
            fd, path = tempfile.mkstemp(suffix=".meshpack")
            os.close(fd)
        with open(path, "wb") as f:
            f.write(data)
        return path


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def pack_builder() -> MeshPackBuilder:
    """Provides a fresh MeshPackBuilder for each test."""
    return MeshPackBuilder()


@pytest.fixture
def minimal_valid_entry() -> Dict[str, Any]:
    """A minimal valid FileEntry."""
    return {
        "path": "models/cube.stl",
        "original_name": "cube.stl",
        "size_bytes": 1234,
        "hash": "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        "modified_at": "2026-01-01T00:00:00+00:00",
    }


@pytest.fixture
def tmp_meshpack(pack_builder: MeshPackBuilder, minimal_valid_entry: Dict[str, Any]) -> str:
    """Creates a minimal valid .meshpack file and returns its path."""
    path = pack_builder.add_shard(
        "part-00001", [minimal_valid_entry], entries_count=1
    ).build_to_file()
    yield path  # type: ignore[misc]
    os.unlink(path)
