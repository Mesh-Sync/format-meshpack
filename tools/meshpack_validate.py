#!/usr/bin/env python3
"""
MeshPack archive validator (v1.0.0).

Validates .meshpack / .mpack archives against the MeshPack specification:
  - Manifest schema presence and required fields.
  - ZIP entry ordering (manifest.json MUST be first).
  - Shard integrity (entries_count, entries_hash, path ordering).
  - Resource-ref / resource-hash consistency.
  - Path traversal and length constraints.
  - Sidecar (.meshpack.integrity) verification when present.
  - Hash algorithm support (SHA-256, SHA-512, BLAKE3 stub).

Usage:
  python tools/meshpack_validate.py path/to/archive.meshpack
  python tools/meshpack_validate.py --sidecar path/to/archive.meshpack.integrity path/to/archive.meshpack
  python tools/meshpack_validate.py --strict path/to/archive.meshpack

Exit codes:
  0 — validation passed
  1 — one or more warnings (non-strict) or errors
  2 — fatal error (missing manifest, corrupt ZIP, etc.)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sys
import zipfile
from decimal import Decimal
from typing import Any, Iterable, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SHARD_ID_PATTERN = re.compile(r"^part-\d{5}$")
PATH_MAX_LENGTH = 1024
PATH_TRAVERSAL_PATTERN = re.compile(r"(^|/)\.\.(/|$)")
HASH_PATTERN = re.compile(
    r"^(sha256:[a-f0-9]{64}|sha512:[a-f0-9]{128}|blake3:[a-f0-9]{64})$"
)
SUPPORTED_ALGOS = {"sha256", "sha512"}  # blake3 requires optional dep

# ---------------------------------------------------------------------------
# Hash helpers
# ---------------------------------------------------------------------------


def _get_hasher(algo: str) -> "hashlib._Hash":
    """Return a hashlib instance for the given algorithm name."""
    algo = algo.lower()
    if algo == "sha256":
        return hashlib.sha256()
    if algo == "sha512":
        return hashlib.sha512()
    if algo == "blake3":
        try:
            import blake3 as _blake3  # type: ignore[import-untyped]

            return _blake3.blake3()  # type: ignore[return-value]
        except ImportError:
            raise ValueError(
                "BLAKE3 support requires the 'blake3' package: pip install blake3"
            )
    raise ValueError(f"Unsupported hash algorithm: {algo}")


def compute_digest(data_iter: Iterable[bytes], algo: str) -> str:
    """Compute hex digest over an iterable of byte chunks."""
    h = _get_hasher(algo)
    for chunk in data_iter:
        h.update(chunk)
    return h.hexdigest()


def file_chunks(path: str, chunk_size: int = 65_536) -> Iterable[bytes]:
    """Yield chunks of a file for streaming hash computation."""
    with open(path, "rb") as fh:
        while True:
            chunk = fh.read(chunk_size)
            if not chunk:
                break
            yield chunk


# ---------------------------------------------------------------------------
# RFC 8785 – JSON Canonicalization Scheme (JCS)
# ---------------------------------------------------------------------------


def _jcs_utf16_sort_key(s: str) -> List[int]:
    """Return a sort key based on UTF-16 code unit values (RFC 8785 §3.2.3).

    For characters in the Basic Multilingual Plane this is identical to
    sorting by Unicode code point, but characters above U+FFFF are
    represented as surrogate pairs and compared by code-unit order.
    """
    units: List[int] = []
    for ch in s:
        cp = ord(ch)
        if cp >= 0x10000:
            cp -= 0x10000
            units.append(0xD800 + (cp >> 10))
            units.append(0xDC00 + (cp & 0x3FF))
        else:
            units.append(cp)
    return units


def _jcs_serialize_string(s: str) -> str:
    """Serialize a string per RFC 8785 §3.2.2.2.

    Only the mandatory escape sequences are used; all other characters
    (including non-ASCII) are passed through verbatim as required by JCS.
    """
    parts: List[str] = ['"']
    for ch in s:
        cp = ord(ch)
        if ch == "\\":
            parts.append("\\\\")
        elif ch == '"':
            parts.append('\\"')
        elif ch == "\b":
            parts.append("\\b")
        elif ch == "\f":
            parts.append("\\f")
        elif ch == "\n":
            parts.append("\\n")
        elif ch == "\r":
            parts.append("\\r")
        elif ch == "\t":
            parts.append("\\t")
        elif cp < 0x20:
            parts.append(f"\\u{cp:04x}")
        else:
            parts.append(ch)
    parts.append('"')
    return "".join(parts)


def _jcs_serialize_number(value: Any) -> str:
    """Serialize a number per RFC 8785 §3.2.2.3.

    Follows the ECMAScript ``Number::toString`` algorithm (ECMA-262 §6.1.6.1.20):
    integers are rendered without a decimal point; floats use the shortest
    representation with ECMAScript-compatible exponential notation rules.
    """
    if isinstance(value, bool):
        raise TypeError("bool is not a JSON number")
    if isinstance(value, int):
        return str(value)

    # --- float handling ---
    if math.isnan(value) or math.isinf(value):
        raise ValueError("NaN and Infinity are not valid in JCS (RFC 8785)")
    if value == 0.0:  # handles both +0.0 and -0.0
        return "0"

    sign = "-" if value < 0 else ""
    abs_val = abs(value)

    # Whole-number floats below 10^21 → render as integer
    if abs_val.is_integer() and abs_val < 1e21:
        return sign + str(int(abs_val))

    # Decompose via Decimal for exact significant digits / exponent
    _, d_digits, d_exp = Decimal(repr(abs_val)).as_tuple()
    digits = "".join(str(d) for d in d_digits).rstrip("0") or "0"
    zeros_stripped = len(d_digits) - len(digits)

    k = len(digits)
    n = d_exp + zeros_stripped + k  # ECMAScript "n" (decimal-point position)

    # ECMAScript formatting rules (ECMA-262 §6.1.6.1.20, steps 5-9)
    if k <= n <= 21:
        result = digits + "0" * (n - k)
    elif 0 < n <= 21:
        result = digits[:n] + "." + digits[n:]
    elif -6 < n <= 0:
        result = "0." + "0" * (-n) + digits
    elif k == 1:
        e = n - 1
        result = digits + "e" + ("+" if e >= 0 else "") + str(e)
    else:
        e = n - 1
        result = (
            digits[0] + "." + digits[1:] + "e" + ("+" if e >= 0 else "") + str(e)
        )

    return sign + result


def jcs_canonicalize(value: Any) -> str:
    """Serialize *value* to canonical JSON per RFC 8785 (JCS).

    Recursively processes dicts, lists, strings, numbers, booleans, and None.
    Object keys are sorted by UTF-16 code-unit order; numbers follow the
    ECMAScript ``Number::toString`` algorithm; strings use JCS escape rules.
    """
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return _jcs_serialize_number(value)
    if isinstance(value, str):
        return _jcs_serialize_string(value)
    if isinstance(value, (list, tuple)):
        items = ",".join(jcs_canonicalize(item) for item in value)
        return f"[{items}]"
    if isinstance(value, dict):
        sorted_keys = sorted(value.keys(), key=_jcs_utf16_sort_key)
        pairs = ",".join(
            f"{_jcs_serialize_string(k)}:{jcs_canonicalize(value[k])}"
            for k in sorted_keys
        )
        return "{" + pairs + "}"
    raise TypeError(f"Unsupported type for JCS serialization: {type(value)}")


# ---------------------------------------------------------------------------
# Severity
# ---------------------------------------------------------------------------


class Severity:
    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"


class Finding:
    """A single validation finding."""

    __slots__ = ("severity", "code", "message")

    def __init__(self, severity: str, code: str, message: str) -> None:
        self.severity = severity
        self.code = code
        self.message = message

    def __str__(self) -> str:
        return f"[{self.severity}] {self.code}: {self.message}"


# ---------------------------------------------------------------------------
# Validators
# ---------------------------------------------------------------------------


def load_manifest(zf: zipfile.ZipFile) -> Tuple[Optional[dict], List[Finding]]:
    """Load and return manifest.json from the archive."""
    findings: List[Finding] = []
    if "manifest.json" not in zf.namelist():
        findings.append(
            Finding(Severity.ERROR, "MAN-001", "manifest.json not found in archive")
        )
        return None, findings
    try:
        with zf.open("manifest.json") as fh:
            manifest = json.load(fh)
    except (json.JSONDecodeError, KeyError) as exc:
        findings.append(
            Finding(Severity.ERROR, "MAN-002", f"Failed to parse manifest.json: {exc}")
        )
        return None, findings
    return manifest, findings


def check_zip_ordering(zf: zipfile.ZipFile) -> List[Finding]:
    """REQ-L2-000: manifest.json MUST be the first ZIP entry."""
    findings: List[Finding] = []
    names = zf.namelist()
    if names and names[0] != "manifest.json":
        findings.append(
            Finding(
                Severity.WARNING,
                "ZIP-001",
                f"manifest.json should be the first ZIP entry (found '{names[0]}' first). "
                "This is required for streaming readers (REQ-L2-000).",
            )
        )
    return findings


def check_manifest_fields(manifest: dict) -> List[Finding]:
    """Validate required manifest fields and value constraints."""
    findings: List[Finding] = []

    # Required top-level fields
    required = ["format_version", "created_at", "workspace_id", "hash_algo", "index_summary"]
    for field in required:
        if field not in manifest:
            findings.append(
                Finding(Severity.ERROR, "MAN-010", f"Missing required field: {field}")
            )

    # format_version semver check
    fv = manifest.get("format_version", "")
    if fv and not re.match(r"^\d+\.\d+\.\d+$", fv):
        findings.append(
            Finding(Severity.WARNING, "MAN-011", f"format_version '{fv}' is not valid semver")
        )

    # hash_algo
    algo = manifest.get("hash_algo", "")
    if algo and algo not in ("sha256", "sha512", "blake3"):
        findings.append(
            Finding(Severity.ERROR, "MAN-012", f"Unsupported hash_algo: '{algo}'")
        )

    # shard_list presence (required in v1.0)
    if "shard_list" not in manifest:
        findings.append(
            Finding(
                Severity.WARNING,
                "MAN-013",
                "Missing shard_list in manifest. Required for v1.0 packs.",
            )
        )
    elif not isinstance(manifest["shard_list"], list) or len(manifest["shard_list"]) < 1:
        findings.append(
            Finding(Severity.ERROR, "MAN-014", "shard_list must be a non-empty array")
        )

    # index_summary
    summary = manifest.get("index_summary")
    if isinstance(summary, dict):
        for sf in ("total_files", "total_shards", "total_size_bytes"):
            if sf not in summary:
                findings.append(
                    Finding(Severity.WARNING, "MAN-015", f"index_summary missing field: {sf}")
                )

    return findings


def check_shard_id(shard_id: str, shard_path: str) -> List[Finding]:
    """Validate shard_id matches the 5-digit pattern."""
    findings: List[Finding] = []
    if not SHARD_ID_PATTERN.match(shard_id):
        findings.append(
            Finding(
                Severity.WARNING,
                "SHD-001",
                f"shard_id '{shard_id}' in {shard_path} does not match pattern ^part-\\d{{5}}$. "
                "5-digit zero-padded IDs are required (e.g., part-00001).",
            )
        )
    return findings


def check_entry_path(entry: dict, shard_path: str) -> List[Finding]:
    """Validate path constraints on a single file entry."""
    findings: List[Finding] = []
    path = entry.get("path", "")

    if len(path) > PATH_MAX_LENGTH:
        findings.append(
            Finding(
                Severity.ERROR,
                "ENT-001",
                f"Path exceeds {PATH_MAX_LENGTH} chars in {shard_path}: {path[:80]}...",
            )
        )

    if PATH_TRAVERSAL_PATTERN.search(path):
        findings.append(
            Finding(
                Severity.ERROR,
                "ENT-002",
                f"Path traversal detected in {shard_path}: {path}",
            )
        )

    if path.startswith("/"):
        findings.append(
            Finding(
                Severity.WARNING,
                "ENT-003",
                f"Absolute path in {shard_path}: {path}",
            )
        )

    return findings


def check_hash_format(hash_value: str, shard_path: str, entry_path: str) -> List[Finding]:
    """Validate hash string format."""
    findings: List[Finding] = []
    if hash_value and not HASH_PATTERN.match(hash_value):
        findings.append(
            Finding(
                Severity.WARNING,
                "HSH-001",
                f"Hash format invalid for {entry_path} in {shard_path}: '{hash_value[:40]}...'",
            )
        )
    return findings


def verify_entries_hash(
    entries: List[dict], algo: str, expected_hash: str
) -> Tuple[bool, str]:
    """Compute entries_hash using RFC 8785 (JCS) canonical JSON.

    Per REQ-L2-010 the hash is computed over the canonicalised,
    path-sorted entries array:
        entries_hash = hash(canonical_json(sorted(entries)))
    """
    sorted_entries = sorted(entries, key=lambda e: e.get("path", ""))
    encoded = jcs_canonicalize(sorted_entries).encode("utf-8")
    digest = compute_digest([encoded], algo)
    actual = f"{algo}:{digest}"
    return actual == expected_hash, actual


def verify_shards(zf: zipfile.ZipFile, manifest: dict) -> List[Finding]:
    """Validate all shards referenced by the manifest."""
    findings: List[Finding] = []
    algo = manifest.get("hash_algo", "sha256")

    shard_list = manifest.get("shard_list")
    if not shard_list:
        # Fallback: discover shards from archive
        shard_list = [
            {"id": os.path.basename(name).replace(".json", ""), "entries_hash": None, "entries_count": None}
            for name in zf.namelist()
            if name.startswith("index/part-")
        ]
        if shard_list:
            findings.append(
                Finding(
                    Severity.INFO,
                    "SHD-010",
                    f"No shard_list in manifest; discovered {len(shard_list)} shards from archive.",
                )
            )

    for shard_meta in shard_list:
        shard_id = shard_meta.get("id", "")
        shard_path = f"index/{shard_id}.json"

        # Check shard_id format
        findings.extend(check_shard_id(shard_id, shard_path))

        # Check shard file exists in archive
        if shard_path not in zf.namelist():
            findings.append(
                Finding(Severity.ERROR, "SHD-002", f"Shard file missing in archive: {shard_path}")
            )
            continue

        # Load shard
        try:
            with zf.open(shard_path) as fh:
                shard = json.load(fh)
        except (json.JSONDecodeError, KeyError) as exc:
            findings.append(
                Finding(Severity.ERROR, "SHD-003", f"Failed to parse {shard_path}: {exc}")
            )
            continue

        entries = shard.get("entries", [])

        # Check entry ordering (lexicographic by path)
        paths = [e.get("path", "") for e in entries]
        if paths != sorted(paths):
            findings.append(
                Finding(Severity.WARNING, "SHD-004", f"Entries not sorted by path in {shard_path}")
            )

        # Validate entries_count
        expected_count = shard_meta.get("entries_count")
        if expected_count is not None and expected_count != len(entries):
            findings.append(
                Finding(
                    Severity.ERROR,
                    "SHD-005",
                    f"entries_count mismatch in {shard_path}: "
                    f"manifest={expected_count} actual={len(entries)}",
                )
            )

        # Validate entries_hash
        expected_hash = shard_meta.get("entries_hash") or shard.get("entries_hash")
        if expected_hash:
            try:
                ok, actual = verify_entries_hash(entries, algo, expected_hash)
            except ValueError as exc:
                findings.append(
                    Finding(Severity.WARNING, "SHD-006", f"Hash algo error in {shard_path}: {exc}")
                )
                ok = True
                actual = "unsupported-algo"
            if not ok:
                findings.append(
                    Finding(
                        Severity.ERROR,
                        "SHD-007",
                        f"entries_hash mismatch in {shard_path}: expected {expected_hash}, got {actual}",
                    )
                )

        # Validate individual entries
        for entry in entries:
            entry_path = entry.get("path", "<unknown>")

            # Path constraints
            findings.extend(check_entry_path(entry, shard_path))

            # Hash format
            entry_hash = entry.get("hash", "")
            findings.extend(check_hash_format(entry_hash, shard_path, entry_path))

            # Resource ref consistency
            resource_ref = entry.get("resource_ref")
            resource_hash = entry.get("resource_hash")
            if resource_ref and not resource_hash:
                findings.append(
                    Finding(
                        Severity.WARNING,
                        "RES-001",
                        f"{shard_path}:{entry_path} has resource_ref but missing resource_hash",
                    )
                )

            # Resource file presence
            if resource_ref:
                resource_path = f"resources/{resource_ref}"
                if resource_path not in zf.namelist():
                    findings.append(
                        Finding(
                            Severity.ERROR,
                            "RES-002",
                            f"Missing embedded resource: {resource_path} (referenced by {entry_path})",
                        )
                    )
                # Resource ref should be hex-only (no algo prefix, no colons)
                if ":" in resource_ref:
                    findings.append(
                        Finding(
                            Severity.WARNING,
                            "RES-003",
                            f"resource_ref contains ':' in {shard_path}:{entry_path}. "
                            "Resource filenames should be hex-hash only (e.g., 'a1b2c3...ext'), "
                            "no algorithm prefix.",
                        )
                    )

    return findings


def verify_sidecar(
    meshpack_path: str, sidecar_path: Optional[str], manifest: dict
) -> List[Finding]:
    """Verify pack integrity using the .meshpack.integrity sidecar file."""
    findings: List[Finding] = []

    # Auto-detect sidecar if not provided
    if sidecar_path is None:
        auto_path = meshpack_path + ".integrity"
        if os.path.exists(auto_path):
            sidecar_path = auto_path

    if sidecar_path is None:
        findings.append(
            Finding(
                Severity.INFO,
                "SDC-001",
                "No .meshpack.integrity sidecar found; skipping pack-level hash verification.",
            )
        )
        return findings

    # Load sidecar
    try:
        with open(sidecar_path, "r") as fh:
            sidecar = json.load(fh)
    except (json.JSONDecodeError, OSError) as exc:
        findings.append(
            Finding(Severity.ERROR, "SDC-002", f"Failed to load sidecar: {exc}")
        )
        return findings

    # Verify pack_hash
    sidecar_algo = sidecar.get("hash_algo", "")
    sidecar_hash = sidecar.get("pack_hash", "")
    if not sidecar_algo or not sidecar_hash:
        findings.append(
            Finding(Severity.WARNING, "SDC-003", "Sidecar missing hash_algo or pack_hash")
        )
        return findings

    try:
        digest = compute_digest(file_chunks(meshpack_path), sidecar_algo)
    except ValueError as exc:
        findings.append(Finding(Severity.WARNING, "SDC-004", str(exc)))
        return findings

    expected = sidecar_hash
    # Handle prefixed format (algo:hex) or bare hex
    if ":" in expected:
        actual = f"{sidecar_algo}:{digest}"
    else:
        actual = digest

    if actual != expected:
        findings.append(
            Finding(
                Severity.ERROR,
                "SDC-005",
                f"Pack hash mismatch: sidecar expects {expected}, computed {actual}",
            )
        )
    else:
        findings.append(
            Finding(Severity.INFO, "SDC-010", "Pack hash verified successfully via sidecar.")
        )

    # Verify signatures field if present
    signatures = sidecar.get("signatures")
    if signatures:
        findings.append(
            Finding(
                Severity.INFO,
                "SDC-011",
                f"Sidecar contains {len(signatures)} signature(s). "
                "Signature verification requires external key material (not checked here).",
            )
        )

    return findings


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


def validate(meshpack_path: str, sidecar_path: Optional[str] = None) -> List[Finding]:
    """Run all validation checks on a .meshpack archive."""
    findings: List[Finding] = []

    # Open archive
    try:
        zf = zipfile.ZipFile(meshpack_path, "r")
    except (zipfile.BadZipFile, FileNotFoundError) as exc:
        findings.append(Finding(Severity.ERROR, "ARC-001", f"Cannot open archive: {exc}"))
        return findings

    with zf:
        # ZIP ordering
        findings.extend(check_zip_ordering(zf))

        # Manifest
        manifest, man_findings = load_manifest(zf)
        findings.extend(man_findings)
        if manifest is None:
            return findings  # Cannot proceed without manifest

        # Manifest field validation
        findings.extend(check_manifest_fields(manifest))

        # Shard validation
        findings.extend(verify_shards(zf, manifest))

    # Sidecar verification (outside ZIP context — reads file from disk)
    findings.extend(verify_sidecar(meshpack_path, sidecar_path, manifest))

    return findings


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate a .meshpack archive for integrity, ordering, and spec compliance."
    )
    parser.add_argument("meshpack", help="Path to .meshpack / .mpack file")
    parser.add_argument(
        "--sidecar",
        default=None,
        help="Path to .meshpack.integrity sidecar file (auto-detected if adjacent)",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat warnings as errors (non-zero exit on any finding)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output findings as JSON array",
    )
    args = parser.parse_args()

    findings = validate(args.meshpack, args.sidecar)

    # Output
    if args.json_output:
        out = [
            {"severity": f.severity, "code": f.code, "message": f.message}
            for f in findings
        ]
        print(json.dumps(out, indent=2))
    else:
        for f in findings:
            stream = sys.stderr if f.severity in (Severity.ERROR, Severity.WARNING) else sys.stdout
            print(str(f), file=stream)

    # Determine exit code
    errors = [f for f in findings if f.severity == Severity.ERROR]
    warnings = [f for f in findings if f.severity == Severity.WARNING]

    if errors:
        if not args.json_output:
            print(
                f"\nValidation FAILED: {len(errors)} error(s), {len(warnings)} warning(s).",
                file=sys.stderr,
            )
        return 1

    if args.strict and warnings:
        if not args.json_output:
            print(
                f"\nValidation FAILED (strict mode): {len(warnings)} warning(s).",
                file=sys.stderr,
            )
        return 1

    if not args.json_output:
        info_count = len([f for f in findings if f.severity == Severity.INFO])
        print(
            f"\nMeshPack validation PASSED "
            f"({len(warnings)} warning(s), {info_count} info)."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
