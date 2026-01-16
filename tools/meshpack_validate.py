#!/usr/bin/env python3
"""
Minimal validator for .meshpack archives.
- Verifies pack hash/signature fields are present and checks pack hash.
- Verifies shard ordering, entry ordering, entries_count, and entries_hash.
- Spot-checks resource_ref/resource_hash pairs and presence of files in resources/.

Usage:
  python tools/meshpack_validate.py path/to/archive.meshpack
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from typing import Iterable, List, Tuple


def compute_digest(data_iter: Iterable[bytes], algo: str) -> str:
    algo = algo.lower()
    if algo == "sha256":
        h = hashlib.sha256()
    elif algo == "sha512":
        h = hashlib.sha512()
    else:
        raise ValueError(f"Unsupported hash algorithm: {algo}")
    for chunk in data_iter:
        h.update(chunk)
    return h.hexdigest()


def file_chunks(path: str, chunk_size: int = 65536) -> Iterable[bytes]:
    with open(path, "rb") as fh:
        while True:
            chunk = fh.read(chunk_size)
            if not chunk:
                break
            yield chunk


def load_manifest(zf: zipfile.ZipFile) -> dict:
    with zf.open("manifest.json") as fh:
        return json.load(fh)


def sorted_entry_paths(entries: List[dict]) -> List[str]:
    return [e["path"] for e in entries]


def verify_pack_hash(path: str, manifest: dict) -> List[str]:
    warnings: List[str] = []
    algo = manifest.get("hash_algo")
    pack_hash = manifest.get("pack_hash")
    if not algo or not pack_hash:
        warnings.append("manifest missing hash_algo or pack_hash; skipping pack hash verification")
        return warnings
    try:
        digest = compute_digest(file_chunks(path), algo)
    except ValueError as exc:
        warnings.append(str(exc))
        return warnings
    if f"{algo}:{digest}" != pack_hash:
        warnings.append(f"pack_hash mismatch: expected {pack_hash}, got {algo}:{digest}")
    return warnings


def verify_entries_hash(entries: List[dict], algo: str, expected_hash: str) -> Tuple[bool, str]:
    encoded = json.dumps(entries, sort_keys=True, separators=(",", ":")).encode("utf-8")
    digest = compute_digest([encoded], algo)
    actual = f"{algo}:{digest}"
    return actual == expected_hash, actual


def verify_shards(zf: zipfile.ZipFile, manifest: dict) -> List[str]:
    warnings: List[str] = []
    algo = manifest.get("hash_algo", "sha256")
    shard_list = manifest.get("shard_list")
    if not shard_list:
        # Fallback to all shards if manifest not updated.
        shard_list = [{"id": name, "entries_hash": None, "entries_count": None} for name in zf.namelist() if name.startswith("index/part-")]
    for shard_meta in shard_list:
        shard_path = f"index/{shard_meta['id']}" if not shard_meta["id"].startswith("index/") else shard_meta["id"]
        if shard_path not in zf.namelist():
            warnings.append(f"shard missing in archive: {shard_path}")
            continue
        with zf.open(shard_path) as fh:
            shard = json.load(fh)
        entries = shard.get("entries", [])
        paths = sorted_entry_paths(entries)
        if paths != sorted(paths):
            warnings.append(f"entries not sorted by path in {shard_path}")
        if shard_meta.get("entries_count") is not None and shard_meta["entries_count"] != len(entries):
            warnings.append(
                f"entries_count mismatch in {shard_path}: manifest={shard_meta['entries_count']} actual={len(entries)}"
            )
        expected_hash = shard_meta.get("entries_hash") or shard.get("entries_hash")
        if expected_hash:
            try:
                ok, actual = verify_entries_hash(entries, algo, expected_hash)
            except ValueError as exc:
                warnings.append(str(exc))
                ok = True
                actual = "unsupported-algo"
            if not ok:
                warnings.append(f"entries_hash mismatch in {shard_path}: expected {expected_hash}, got {actual}")
        for entry in entries:
            if entry.get("resource_ref") and not entry.get("resource_hash"):
                warnings.append(f"{shard_path}:{entry['path']} has resource_ref but missing resource_hash")
            if entry.get("resource_ref"):
                resource_path = f"resources/{entry['resource_ref']}"
                if resource_path not in zf.namelist():
                    warnings.append(f"missing embedded resource: {resource_path}")
    return warnings


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a .meshpack archive for integrity and determinism.")
    parser.add_argument("meshpack", help="Path to .meshpack file (zip archive)")
    args = parser.parse_args()

    warnings: List[str] = []
    with zipfile.ZipFile(args.meshpack, "r") as zf:
        manifest = load_manifest(zf)
        warnings.extend(verify_pack_hash(args.meshpack, manifest))
        warnings.extend(verify_shards(zf, manifest))

    if warnings:
        for w in warnings:
            print(f"WARNING: {w}", file=sys.stderr)
        return 1
    print("Meshpack validation passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
