#!/usr/bin/env python3
"""
Generate static .meshpack fixture files for interoperability testing.

Usage:
    python tests/conformance/generate_fixtures.py

Outputs to tests/conformance/fixtures/valid/ and fixtures/invalid/.
"""

from __future__ import annotations

import os
import sys
import hashlib

# Ensure conftest/builder is importable
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from conftest import MeshPackBuilder  # noqa: E402

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
VALID_DIR = os.path.join(FIXTURES_DIR, "valid")
INVALID_DIR = os.path.join(FIXTURES_DIR, "invalid")


def _write(directory: str, name: str, data: bytes) -> None:
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, name)
    with open(path, "wb") as f:
        f.write(data)
    print(f"  {path}")


# ── Valid fixtures ─────────────────────────────────────────────────────────

def generate_minimal_l1() -> bytes:
    """Minimal L1-conforming archive: manifest + 1 shard + 1 entry."""
    b = MeshPackBuilder()
    b.set_manifest_field("creator_info", {"name": "MeshPack Fixture Generator"})
    entry = {
        "path": "models/cube.stl",
        "original_name": "cube.stl",
        "size_bytes": 1234,
        "hash": "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        "modified_at": "2026-01-01T00:00:00+00:00",
    }
    return b.add_shard("part-00001", [entry], entries_count=1).build()


def generate_standard_l2() -> bytes:
    """L2-conforming archive: manifest + shard + resource + sidecar."""
    import json
    b = MeshPackBuilder()
    b.set_manifest_field("creator_info", {"name": "MeshPack Fixture Generator"})
    resource_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 8
    resource_digest = hashlib.sha256(resource_bytes).hexdigest()
    resource_ref = f"{resource_digest}.png"
    entry = {
        "path": "models/cube.stl",
        "original_name": "cube.stl",
        "size_bytes": 11,
        "hash": "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        "modified_at": "2026-01-01T00:00:00+00:00",
        "resource_ref": resource_ref,
        "resource_hash": f"sha256:{resource_digest}",
        "resource_size_bytes": len(resource_bytes),
    }
    b.add_shard("part-00001", [entry], entries_count=1)
    b.add_resource(resource_ref, resource_bytes)

    # Add sidecar
    sidecar = {
        "format_version": "2.0.0",
        "source_pack_hash": "sha256:" + "ab" * 32,
        "entries": [
            {
                "path": "models/cube.stl",
                "tags": ["manufacturing", "prototype"],
            }
        ],
    }
    b.add_extra_file("sidecar.json", json.dumps(sidecar, indent=2).encode("utf-8"))
    b.set_manifest_field("index_summary", {
        "total_files": 1,
        "total_shards": 1,
        "total_size_bytes": 11,
    })
    return b.build()


def generate_full_l3() -> bytes:
    """L3-conforming archive: manifest + shard with delta ops + extensions."""
    import json
    b = MeshPackBuilder()
    b.set_manifest_field("creator_info", {"name": "MeshPack Fixture Generator"})
    b.set_manifest_field("import_policy", {
        "id_conflict": "skip",
        "metamodel_merge": "strict",
    })
    b.set_manifest_field("extensions", {
        "meshsync_content": {
            "v1": {
                "title": "MeshPack L3 fixture",
                "description": "Reference archive with import policy and official extension metadata.",
                "language": "en",
                "tags": ["fixture", "l3"],
            }
        }
    })
    entry = {
        "path": "models/cube.stl",
        "original_name": "cube.stl",
        "size_bytes": 1234,
        "hash": "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        "modified_at": "2026-01-01T00:00:00+00:00",
        "operation": "add",
    }
    b.add_shard("part-00001", [entry], entries_count=1)
    return b.build()


# ── Invalid fixtures ──────────────────────────────────────────────────────

def generate_no_manifest() -> bytes:
    """ZIP file with no manifest.json."""
    import io, zipfile
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("index/part-00001.json", '{"entries": []}')
    return buf.getvalue()


def generate_path_traversal() -> bytes:
    """Archive with a path-traversal entry (../)."""
    b = MeshPackBuilder()
    entry = {
        "path": "../etc/passwd",
        "original_name": "passwd",
        "size_bytes": 0,
        "hash": "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        "modified_at": "2026-01-01T00:00:00+00:00",
    }
    return b.add_shard("part-00001", [entry]).build()


def generate_bad_shard_order() -> bytes:
    """Archive with entries deliberately not sorted by path."""
    b = MeshPackBuilder()
    entries = [
        {
            "path": "models/zebra.stl",
            "original_name": "zebra.stl",
            "size_bytes": 100,
            "hash": "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            "modified_at": "2026-01-01T00:00:00+00:00",
        },
        {
            "path": "models/alpha.stl",
            "original_name": "alpha.stl",
            "size_bytes": 200,
            "hash": "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            "modified_at": "2026-01-01T00:00:00+00:00",
        },
    ]
    # Force entries_hash to None so it doesn't auto-compute
    return b.add_shard("part-00001", entries, entries_count=2, entries_hash=None).build()


# ── Main ──────────────────────────────────────────────────────────────────

def main() -> None:
    print("Generating static .meshpack fixtures...")

    _write(VALID_DIR, "minimal-l1.meshpack", generate_minimal_l1())
    _write(VALID_DIR, "standard-l2.meshpack", generate_standard_l2())
    _write(VALID_DIR, "full-l3.meshpack", generate_full_l3())

    _write(INVALID_DIR, "no-manifest.meshpack", generate_no_manifest())
    _write(INVALID_DIR, "path-traversal.meshpack", generate_path_traversal())
    _write(INVALID_DIR, "bad-shard-order.meshpack", generate_bad_shard_order())

    print("Done.")


if __name__ == "__main__":
    main()
