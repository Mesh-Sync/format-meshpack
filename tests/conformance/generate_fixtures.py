#!/usr/bin/env python3
"""
Generate static .meshpack fixture files for conformance testing.

These fixtures provide pre-built reference archives that third-party
implementers can use to verify their own parsers and validators without
depending on the MeshPackBuilder test infrastructure.

Run:
    python tests/conformance/generate_fixtures.py

Outputs:
    tests/conformance/fixtures/valid/*.meshpack
    tests/conformance/fixtures/invalid/*.meshpack
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import sys
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
VALID_DIR = FIXTURES_DIR / "valid"
INVALID_DIR = FIXTURES_DIR / "invalid"

DUMMY_HASH = "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
TIMESTAMP = "2026-01-01T00:00:00+00:00"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _compute_entries_hash(entries: List[Dict[str, Any]], algo: str = "sha256") -> str:
    """Compute the canonical entries_hash (RFC 8785 canonical JSON)."""
    encoded = json.dumps(entries, sort_keys=True, separators=(",", ":")).encode("utf-8")
    h = hashlib.new(algo)
    h.update(encoded)
    return f"{algo}:{h.hexdigest()}"


def _build_manifest(
    *,
    shards: List[Dict[str, Any]],
    total_files: int,
    total_size_bytes: int = 0,
    hash_algo: str = "sha256",
    extra_fields: Optional[Dict[str, Any]] = None,
    remove_fields: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Build a manifest dict with computed shard references."""
    manifest: Dict[str, Any] = {
        "format_version": "1.0.0",
        "created_at": TIMESTAMP,
        "workspace_id": "fixture-test",
        "hash_algo": hash_algo,
        "index_summary": {
            "total_files": total_files,
            "total_shards": len(shards),
            "total_size_bytes": total_size_bytes,
        },
        "shard_list": shards,
    }
    if extra_fields:
        manifest.update(extra_fields)
    if remove_fields:
        for field in remove_fields:
            manifest.pop(field, None)
    return manifest


def _build_shard(
    shard_id: str,
    entries: List[Dict[str, Any]],
    *,
    entries_count: Optional[int] = None,
    entries_hash: Optional[str] = None,
    algo: str = "sha256",
) -> Dict[str, Any]:
    """Build a shard dict with optional overrides for negative tests."""
    if entries_hash is None:
        entries_hash = _compute_entries_hash(entries, algo)
    if entries_count is None:
        entries_count = len(entries)
    return {
        "shard_id": shard_id,
        "format_version": "1.0.0",
        "entries": entries,
        "entries_count": entries_count,
        "entries_hash": entries_hash,
    }


def _write_pack(
    path: Path,
    manifest: Dict[str, Any],
    shards: Dict[str, Dict[str, Any]],
    *,
    resources: Optional[Dict[str, bytes]] = None,
    manifest_first: bool = True,
) -> None:
    """Write a .meshpack ZIP archive to disk."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        manifest_bytes = json.dumps(manifest, indent=2).encode("utf-8")

        if manifest_first:
            zf.writestr("manifest.json", manifest_bytes)

        for shard_id, shard_data in shards.items():
            zf.writestr(
                f"index/{shard_id}.json",
                json.dumps(shard_data, indent=2).encode("utf-8"),
            )

        if resources:
            for name, data in resources.items():
                zf.writestr(f"resources/{name}", data)

        if not manifest_first:
            zf.writestr("manifest.json", manifest_bytes)

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(buf.getvalue())
    print(f"  Created {path.relative_to(FIXTURES_DIR)}")


# ---------------------------------------------------------------------------
# Valid fixtures
# ---------------------------------------------------------------------------


def generate_valid_minimal() -> None:
    """Bare-minimum valid archive: one shard, one entry, correct hashes."""
    entries = [
        {
            "path": "models/cube.stl",
            "original_name": "cube.stl",
            "size_bytes": 1234,
            "hash": DUMMY_HASH,
            "modified_at": TIMESTAMP,
        },
    ]
    shard_id = "part-00001"
    shard = _build_shard(shard_id, entries)
    shard_ref = {
        "id": shard_id,
        "entries_count": shard["entries_count"],
        "entries_hash": shard["entries_hash"],
    }
    manifest = _build_manifest(shards=[shard_ref], total_files=1, total_size_bytes=1234)
    _write_pack(VALID_DIR / "minimal.meshpack", manifest, {shard_id: shard})


def generate_valid_multi_entry() -> None:
    """Multiple entries in one shard, correctly sorted by path."""
    entries = [
        {
            "path": "assets/logo.png",
            "original_name": "logo.png",
            "size_bytes": 5678,
            "hash": "sha256:" + "aa" * 32,
            "modified_at": TIMESTAMP,
        },
        {
            "path": "models/bracket.step",
            "original_name": "bracket.step",
            "size_bytes": 20480,
            "hash": "sha256:" + "bb" * 32,
            "modified_at": TIMESTAMP,
        },
        {
            "path": "models/cube.stl",
            "original_name": "cube.stl",
            "size_bytes": 1234,
            "hash": DUMMY_HASH,
            "modified_at": TIMESTAMP,
        },
    ]
    shard_id = "part-00001"
    shard = _build_shard(shard_id, entries)
    shard_ref = {
        "id": shard_id,
        "entries_count": shard["entries_count"],
        "entries_hash": shard["entries_hash"],
    }
    total_size = sum(e["size_bytes"] for e in entries)
    manifest = _build_manifest(shards=[shard_ref], total_files=3, total_size_bytes=total_size)
    _write_pack(VALID_DIR / "multi_entry.meshpack", manifest, {shard_id: shard})


def generate_valid_multi_shard() -> None:
    """Two shards, each with entries, correctly referenced in manifest."""
    entries_1 = [
        {
            "path": "docs/readme.txt",
            "original_name": "readme.txt",
            "size_bytes": 512,
            "hash": "sha256:" + "cc" * 32,
            "modified_at": TIMESTAMP,
        },
    ]
    entries_2 = [
        {
            "path": "models/gear.obj",
            "original_name": "gear.obj",
            "size_bytes": 8192,
            "hash": "sha256:" + "dd" * 32,
            "modified_at": TIMESTAMP,
        },
        {
            "path": "models/shaft.obj",
            "original_name": "shaft.obj",
            "size_bytes": 4096,
            "hash": "sha256:" + "ee" * 32,
            "modified_at": TIMESTAMP,
        },
    ]
    shard1 = _build_shard("part-00001", entries_1)
    shard2 = _build_shard("part-00002", entries_2)
    shard_refs = [
        {"id": "part-00001", "entries_count": shard1["entries_count"], "entries_hash": shard1["entries_hash"]},
        {"id": "part-00002", "entries_count": shard2["entries_count"], "entries_hash": shard2["entries_hash"]},
    ]
    total_size = sum(e["size_bytes"] for e in entries_1 + entries_2)
    manifest = _build_manifest(shards=shard_refs, total_files=3, total_size_bytes=total_size)
    _write_pack(
        VALID_DIR / "multi_shard.meshpack",
        manifest,
        {"part-00001": shard1, "part-00002": shard2},
    )


def generate_valid_with_resource() -> None:
    """Archive with an embedded resource in resources/."""
    resource_data = b"FAKE-STL-BINARY-CONTENT-FOR-TESTING"
    resource_hash_hex = hashlib.sha256(resource_data).hexdigest()
    resource_ref = f"{resource_hash_hex}.stl"
    resource_hash = f"sha256:{resource_hash_hex}"

    entries = [
        {
            "path": "models/widget.stl",
            "original_name": "widget.stl",
            "size_bytes": len(resource_data),
            "hash": "sha256:" + "ff" * 32,
            "modified_at": TIMESTAMP,
            "resource_ref": resource_ref,
            "resource_hash": resource_hash,
            "resource_size_bytes": len(resource_data),
        },
    ]
    shard_id = "part-00001"
    shard = _build_shard(shard_id, entries)
    shard_ref = {
        "id": shard_id,
        "entries_count": shard["entries_count"],
        "entries_hash": shard["entries_hash"],
    }
    manifest = _build_manifest(
        shards=[shard_ref],
        total_files=1,
        total_size_bytes=len(resource_data),
    )
    _write_pack(
        VALID_DIR / "with_resource.meshpack",
        manifest,
        {shard_id: shard},
        resources={resource_ref: resource_data},
    )


def generate_valid_delta_pack() -> None:
    """Delta pack with add/modify/delete operations."""
    entries = [
        {
            "path": "models/added.stl",
            "original_name": "added.stl",
            "size_bytes": 100,
            "hash": "sha256:" + "a1" * 32,
            "modified_at": TIMESTAMP,
            "operation": "add",
        },
        {
            "path": "models/deleted.stl",
            "original_name": "deleted.stl",
            "size_bytes": 0,
            "hash": "sha256:" + "00" * 32,
            "modified_at": TIMESTAMP,
            "operation": "delete",
        },
        {
            "path": "models/modified.stl",
            "original_name": "modified.stl",
            "size_bytes": 200,
            "hash": "sha256:" + "b2" * 32,
            "modified_at": TIMESTAMP,
            "operation": "modify",
        },
    ]
    shard_id = "part-00001"
    shard = _build_shard(shard_id, entries)
    shard_ref = {
        "id": shard_id,
        "entries_count": shard["entries_count"],
        "entries_hash": shard["entries_hash"],
    }
    manifest = _build_manifest(
        shards=[shard_ref],
        total_files=3,
        total_size_bytes=300,
        extra_fields={
            "generation": {
                "generator": "fixture-generator@1.0.0",
                "partial": True,
                "base_pack_hash": "sha256:" + "ab" * 32,
            },
        },
    )
    _write_pack(VALID_DIR / "delta_pack.meshpack", manifest, {shard_id: shard})


# ---------------------------------------------------------------------------
# Invalid fixtures
# ---------------------------------------------------------------------------


def generate_invalid_not_a_zip() -> None:
    """Not a ZIP file at all — triggers ARC-001."""
    path = INVALID_DIR / "not_a_zip.meshpack"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"THIS IS NOT A ZIP FILE\x00\x01\x02\x03")
    print(f"  Created {path.relative_to(FIXTURES_DIR)}")


def generate_invalid_no_manifest() -> None:
    """Valid ZIP but missing manifest.json — triggers MAN-001."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(
            "index/part-00001.json",
            json.dumps({"shard_id": "part-00001", "format_version": "1.0.0", "entries": []}).encode(),
        )
    path = INVALID_DIR / "no_manifest.meshpack"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(buf.getvalue())
    print(f"  Created {path.relative_to(FIXTURES_DIR)}")


def generate_invalid_missing_hash_algo() -> None:
    """Manifest without hash_algo — triggers MAN-010."""
    entries = [
        {
            "path": "models/cube.stl",
            "original_name": "cube.stl",
            "size_bytes": 1234,
            "hash": DUMMY_HASH,
            "modified_at": TIMESTAMP,
        },
    ]
    shard_id = "part-00001"
    shard = _build_shard(shard_id, entries)
    shard_ref = {
        "id": shard_id,
        "entries_count": shard["entries_count"],
        "entries_hash": shard["entries_hash"],
    }
    manifest = _build_manifest(
        shards=[shard_ref], total_files=1, remove_fields=["hash_algo"],
    )
    _write_pack(INVALID_DIR / "missing_hash_algo.meshpack", manifest, {shard_id: shard})


def generate_invalid_unsupported_hash_algo() -> None:
    """Manifest with hash_algo=md5 — triggers MAN-012."""
    entries = [
        {
            "path": "models/cube.stl",
            "original_name": "cube.stl",
            "size_bytes": 1234,
            "hash": DUMMY_HASH,
            "modified_at": TIMESTAMP,
        },
    ]
    shard_id = "part-00001"
    shard = _build_shard(shard_id, entries)
    shard_ref = {
        "id": shard_id,
        "entries_count": shard["entries_count"],
        "entries_hash": shard["entries_hash"],
    }
    manifest = _build_manifest(
        shards=[shard_ref], total_files=1, hash_algo="md5",
    )
    _write_pack(INVALID_DIR / "unsupported_hash_algo.meshpack", manifest, {shard_id: shard})


def generate_invalid_bad_shard_id() -> None:
    """Shard with 3-digit ID (part-001) — triggers SHD-001."""
    entries = [
        {
            "path": "models/cube.stl",
            "original_name": "cube.stl",
            "size_bytes": 1234,
            "hash": DUMMY_HASH,
            "modified_at": TIMESTAMP,
        },
    ]
    bad_shard_id = "part-001"
    shard = _build_shard(bad_shard_id, entries)
    shard_ref = {
        "id": bad_shard_id,
        "entries_count": shard["entries_count"],
        "entries_hash": shard["entries_hash"],
    }
    manifest = _build_manifest(shards=[shard_ref], total_files=1)
    _write_pack(INVALID_DIR / "bad_shard_id.meshpack", manifest, {bad_shard_id: shard})


def generate_invalid_entries_count_mismatch() -> None:
    """entries_count says 999 but shard has 1 entry — triggers SHD-005."""
    entries = [
        {
            "path": "models/cube.stl",
            "original_name": "cube.stl",
            "size_bytes": 1234,
            "hash": DUMMY_HASH,
            "modified_at": TIMESTAMP,
        },
    ]
    shard_id = "part-00001"
    shard = _build_shard(shard_id, entries, entries_count=999)
    shard_ref = {
        "id": shard_id,
        "entries_count": 999,
        "entries_hash": shard["entries_hash"],
    }
    manifest = _build_manifest(shards=[shard_ref], total_files=1)
    _write_pack(INVALID_DIR / "entries_count_mismatch.meshpack", manifest, {shard_id: shard})


def generate_invalid_path_traversal() -> None:
    """Entry with '../' traversal sequence — triggers ENT-002."""
    entries = [
        {
            "path": "../etc/passwd",
            "original_name": "passwd",
            "size_bytes": 0,
            "hash": DUMMY_HASH,
            "modified_at": TIMESTAMP,
        },
    ]
    shard_id = "part-00001"
    shard = _build_shard(shard_id, entries)
    shard_ref = {
        "id": shard_id,
        "entries_count": shard["entries_count"],
        "entries_hash": shard["entries_hash"],
    }
    manifest = _build_manifest(shards=[shard_ref], total_files=1)
    _write_pack(INVALID_DIR / "path_traversal.meshpack", manifest, {shard_id: shard})


def generate_invalid_path_too_long() -> None:
    """Entry with path exceeding 1024 chars — triggers ENT-001."""
    long_path = "a" * 1025
    entries = [
        {
            "path": long_path,
            "original_name": "a" * 255,
            "size_bytes": 0,
            "hash": DUMMY_HASH,
            "modified_at": TIMESTAMP,
        },
    ]
    shard_id = "part-00001"
    shard = _build_shard(shard_id, entries)
    shard_ref = {
        "id": shard_id,
        "entries_count": shard["entries_count"],
        "entries_hash": shard["entries_hash"],
    }
    manifest = _build_manifest(shards=[shard_ref], total_files=1)
    _write_pack(INVALID_DIR / "path_too_long.meshpack", manifest, {shard_id: shard})


def generate_invalid_manifest_not_first() -> None:
    """manifest.json is NOT the first ZIP entry — triggers ZIP-001."""
    entries = [
        {
            "path": "models/cube.stl",
            "original_name": "cube.stl",
            "size_bytes": 1234,
            "hash": DUMMY_HASH,
            "modified_at": TIMESTAMP,
        },
    ]
    shard_id = "part-00001"
    shard = _build_shard(shard_id, entries)
    shard_ref = {
        "id": shard_id,
        "entries_count": shard["entries_count"],
        "entries_hash": shard["entries_hash"],
    }
    manifest = _build_manifest(shards=[shard_ref], total_files=1, total_size_bytes=1234)
    _write_pack(
        INVALID_DIR / "manifest_not_first.meshpack",
        manifest,
        {shard_id: shard},
        manifest_first=False,
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    print("Generating valid fixtures:")
    generate_valid_minimal()
    generate_valid_multi_entry()
    generate_valid_multi_shard()
    generate_valid_with_resource()
    generate_valid_delta_pack()

    print("\nGenerating invalid fixtures:")
    generate_invalid_not_a_zip()
    generate_invalid_no_manifest()
    generate_invalid_missing_hash_algo()
    generate_invalid_unsupported_hash_algo()
    generate_invalid_bad_shard_id()
    generate_invalid_entries_count_mismatch()
    generate_invalid_path_traversal()
    generate_invalid_path_too_long()
    generate_invalid_manifest_not_first()

    print("\nDone.")


if __name__ == "__main__":
    main()
