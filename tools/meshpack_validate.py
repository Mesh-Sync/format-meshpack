#!/usr/bin/env python3
"""
MeshPack archive validator.

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
import os
import re
import sys
import zipfile
from typing import Iterable, List, Optional, Set, Tuple

from jsonschema import Draft7Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT7

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SHARD_ID_PATTERN = re.compile(r"^part-\d{5}$")
PATH_MAX_LENGTH = 1024
PATH_TRAVERSAL_PATTERN = re.compile(r"(^|/)\.\.(/|$)")
HASH_PATTERN = re.compile(
    r"^(sha256:[a-f0-9]{64}|sha512:[a-f0-9]{128}|blake3:[a-f0-9]{64})$"
)
SUPPORTED_ALGOS = {"sha256", "sha512", "blake3"}
SUPPORTED_FORMAT_MAJOR = 2
SEMVER_PATTERN = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHEMA_DIR = os.path.join(REPO_DIR, "schema")
EXTENSIONS_DIR = os.path.join(SCHEMA_DIR, "extensions")
RESOURCE_REF_PATTERN = re.compile(
    r"^([a-f0-9]{64}|[a-f0-9]{128})\.[A-Za-z0-9][A-Za-z0-9._-]{0,31}$"
)
OFFICIAL_EXTENSION_SCHEMAS = {
    "meshsync_content": "extensions/meshsync_content.schema.json",
    "meshsync_dependencies": "extensions/meshsync_dependencies.schema.json",
    "meshsync_geometry": "extensions/meshsync_geometry.schema.json",
    "meshsync_printability": "extensions/meshsync_printability.schema.json",
    "meshsync_thumbnails": "extensions/meshsync_thumbnails.schema.json",
}


def _zero_hash(algo: str) -> str:
    if algo == "sha512":
        return f"{algo}:{'0' * 128}"
    return f"{algo}:{'0' * 64}"


def _path_sort_key(path: object) -> bytes:
    return str(path).encode("utf-8")


def _load_schema(filename: str) -> dict:
    with open(os.path.join(SCHEMA_DIR, filename), "r", encoding="utf-8") as schema_file:
        return json.load(schema_file)


def _schema_registry() -> Registry:
    filenames = [
        "common.schema.json",
        "manifest.schema.json",
        "shard.schema.json",
        "sidecar.schema.json",
        "validation-finding.schema.json",
        *OFFICIAL_EXTENSION_SCHEMAS.values(),
    ]
    schemas = {filename: _load_schema(filename) for filename in filenames}
    registry = Registry()
    resources = []
    for filename, schema in schemas.items():
        resource = Resource.from_contents(schema, default_specification=DRAFT7)
        schema_id = schema.get("$id")
        if schema_id:
            resources.append((schema_id, resource))
        resources.append((f"https://meshsync.net/schemas/meshpack/2.0/{filename}", resource))
    return registry.with_resources(resources)


def _schema_validator(filename: str) -> Draft7Validator:
    schema = _load_schema(filename)
    return Draft7Validator(schema, registry=_schema_registry())


def _json_pointer(parts: Iterable[object]) -> str:
    encoded = []
    for part in parts:
        text = str(part).replace("~", "~0").replace("/", "~1")
        encoded.append(text)
    return "" if not encoded else "/" + "/".join(encoded)


def validate_json_schema(instance: object, schema_filename: str, archive_path: str, schema_mode: str) -> List["Finding"]:
    """Validate JSON against the canonical schema.

    Compat mode keeps forward-compatibility: unknown properties are warnings,
    while type, pattern, enum, and required-field failures remain errors.
    Strict mode treats all schema failures as errors.
    """
    findings: List[Finding] = []
    validator = _schema_validator(schema_filename)
    for error in sorted(validator.iter_errors(instance), key=lambda item: list(item.path)):
        pointer = _json_pointer(error.absolute_path)
        is_unknown_property = error.validator == "additionalProperties"
        severity = Severity.WARNING if schema_mode == "compat" and is_unknown_property else Severity.ERROR
        code = "SCH-002" if is_unknown_property else "SCH-001"
        location = archive_path + pointer
        findings.append(Finding(severity, code, f"{location}: {error.message}"))
    return findings


def validate_official_extensions(extensions: object, archive_path: str, schema_mode: str) -> List["Finding"]:
    """Validate official MeshSync extension envelopes against their schemas."""
    findings: List[Finding] = []
    if extensions is None:
        return findings
    if not isinstance(extensions, dict):
        findings.append(
            Finding(
                Severity.ERROR,
                "SCH-001",
                f"{archive_path}/extensions: extensions must be an object",
            )
        )
        return findings

    for extension_name, payload in extensions.items():
        if extension_name == "_deleted":
            continue

        schema_filename = OFFICIAL_EXTENSION_SCHEMAS.get(extension_name)
        if schema_filename is None:
            if extension_name.startswith("meshsync_") or extension_name.startswith("_"):
                findings.append(
                    Finding(
                        Severity.ERROR,
                        "EXT-002",
                        f"{archive_path}/extensions/{extension_name}: unknown extension uses a reserved prefix",
                    )
                )
            elif "_" not in extension_name and ":" not in extension_name:
                findings.append(
                    Finding(
                        Severity.WARNING,
                        "EXT-001",
                        f"{archive_path}/extensions/{extension_name}: custom extension key should use a namespace prefix",
                    )
                )
            continue
        extension_path = f"{archive_path}/extensions/{extension_name}"
        if not isinstance(payload, dict):
            findings.append(
                Finding(
                    Severity.ERROR,
                    "SCH-001",
                    f"{extension_path}: official extension payload must be an object",
                )
            )
            continue
        findings.extend(validate_json_schema(payload, schema_filename, extension_path, schema_mode))
    return findings

# ---------------------------------------------------------------------------
# Hash helpers
# ---------------------------------------------------------------------------


def _jcs_serialize_value(value: object) -> str:
    """Serialize a single JSON value per RFC 8785 (JCS) rules."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return _jcs_serialize_number(value)
    if isinstance(value, str):
        return _jcs_serialize_string(value)
    if isinstance(value, list):
        return "[" + ",".join(_jcs_serialize_value(v) for v in value) + "]"
    if isinstance(value, dict):
        # RFC 8785 §3.2.3: sort keys by UTF-16 code unit order
        sorted_keys = sorted(value.keys())
        pairs = [_jcs_serialize_string(k) + ":" + _jcs_serialize_value(value[k])
                 for k in sorted_keys]
        return "{" + ",".join(pairs) + "}"
    raise TypeError(f"JCS: unsupported type {type(value)}")


def _jcs_serialize_number(value) -> str:
    """Serialize a number per RFC 8785 §3.2.2.3 (ES6 Number serialization).

    Implements ECMAScript Number.prototype.toString() formatting:
    - Integers and whole-number floats below 10^21 render without decimal/exponent
    - Small decimals (10^-6 < |x| < 1) use "0.000..." form
    - Very large/small numbers use exponential notation "Ne+X" / "Ne-X"
    """
    if isinstance(value, bool):
        raise TypeError("JCS: bool is not a number")
    if isinstance(value, int):
        return str(value)
    if value != value:  # NaN
        raise ValueError("JCS: NaN is not allowed in canonical JSON")
    if value == float("inf") or value == float("-inf"):
        raise ValueError("JCS: Infinity is not allowed in canonical JSON")
    if value == 0.0:
        return "0"

    sign = "-" if value < 0 else ""
    abs_value = abs(value)

    # Whole-number floats below 10^21 render as integers (ES6 rule: k ≤ n ≤ 21)
    if abs_value.is_integer() and abs_value < 1e21:
        return sign + str(int(abs_value))

    # Get shortest decimal representation via repr
    s = repr(abs_value)

    if "e" in s or "E" in s:
        mantissa_str, exp_str = s.lower().split("e")
        exp_offset = int(exp_str)
        if "." in mantissa_str:
            int_part, frac_part = mantissa_str.split(".")
        else:
            int_part, frac_part = mantissa_str, ""
        digits = int_part + frac_part
        n = exp_offset + len(int_part)  # ES6's n (10^(n-1) ≤ |x| < 10^n)
    else:
        if "." in s:
            int_part, frac_part = s.split(".")
        else:
            int_part, frac_part = s, ""
        digits = int_part + frac_part
        n = len(int_part)

    digits = digits.rstrip("0")
    k = len(digits)

    # ES6 Number.prototype.toString() formatting rules
    if k <= n <= 21:
        return sign + digits + "0" * (n - k)
    elif 0 < n <= 21:
        return sign + digits[:n] + "." + digits[n:]
    elif -6 < n <= 0:
        return sign + "0." + "0" * (-n) + digits
    elif k == 1:
        return sign + digits + "e" + ("+" if n - 1 >= 0 else "") + str(n - 1)
    else:
        return sign + digits[0] + "." + digits[1:] + "e" + ("+" if n - 1 >= 0 else "") + str(n - 1)


def _jcs_serialize_string(value: str) -> str:
    """Serialize a string per RFC 8785 §3.2.2.2 (JSON string escaping).

    Uses Python's json.dumps which handles required escapes (\\, \", control
    characters) and preserves non-ASCII characters as-is (ensure_ascii=False)
    per RFC 8785 requirements.
    """
    return json.dumps(value, ensure_ascii=False)


def jcs_canonicalize(obj: object) -> bytes:
    """Serialize *obj* to canonical JSON bytes per RFC 8785 (JCS).

    Implements proper RFC 8785 canonicalization:
    - Recursive key sorting (UTF-16 code unit order)
    - Deterministic number formatting (ES6 Number serialization)
    - No whitespace between tokens
    - UTF-8 encoding of the result
    """
    return _jcs_serialize_value(obj).encode("utf-8")


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


def check_readme_layout(zf: zipfile.ZipFile) -> List[Finding]:
    """Validate mandatory human-readable README entries for public L2 archives."""
    findings: List[Finding] = []
    names = set(zf.namelist())

    if "_README.md" not in names:
        findings.append(
            Finding(
                Severity.WARNING,
                "LAY-001",
                "Root _README.md is missing; L2 writers must include a human-readable root description.",
            )
        )

    has_index_shards = any(name.startswith("index/part-") and name.endswith(".json") for name in names)
    if has_index_shards and "index/_README.md" not in names:
        findings.append(
            Finding(
                Severity.WARNING,
                "LAY-002",
                "index/_README.md is missing; L2 writers must document the sharded index directory.",
            )
        )

    has_resources = any(name.startswith("resources/") and name != "resources/_README.md" for name in names)
    if has_resources and "resources/_README.md" not in names:
        findings.append(
            Finding(
                Severity.WARNING,
                "LAY-003",
                "resources/_README.md is missing while embedded resources are present.",
            )
        )

    for readme_path in ("_README.md", "index/_README.md", "resources/_README.md"):
        if readme_path not in names:
            continue
        try:
            data = zf.read(readme_path)
        except KeyError:
            continue
        if b"\r" in data:
            findings.append(
                Finding(
                    Severity.ERROR,
                    "LAY-004",
                    f"{readme_path} must use LF line endings, not CRLF/CR.",
                )
            )

    return findings


ALLOWED_COMPRESSION = {zipfile.ZIP_DEFLATED, zipfile.ZIP_STORED}


def check_zip_compression(zf: zipfile.ZipFile) -> List[Finding]:
    """Spec §2.1: only DEFLATE (8) or STORE (0) compression allowed."""
    findings: List[Finding] = []
    for info in zf.infolist():
        if info.compress_type not in ALLOWED_COMPRESSION:
            findings.append(
                Finding(
                    Severity.ERROR,
                    "ZIP-003",
                    f"Entry '{info.filename}' uses unsupported compression method "
                    f"{info.compress_type} (only DEFLATE/STORE allowed)",
                )
            )
    return findings


# Default zip bomb limits
MAX_DECOMPRESSED_SIZE = 10 * 1024**3  # 10 GB
MAX_COMPRESSION_RATIO = 100           # 100:1


def check_zip_bomb(
    zf: zipfile.ZipFile,
    max_size: int = MAX_DECOMPRESSED_SIZE,
    max_ratio: int = MAX_COMPRESSION_RATIO,
) -> List[Finding]:
    """FR-053: zip bomb protection — check decompression ratio and total size."""
    findings: List[Finding] = []
    total_decompressed = 0

    for info in zf.infolist():
        total_decompressed += info.file_size

        if info.compress_size > 0:
            ratio = info.file_size / info.compress_size
            if ratio > max_ratio:
                findings.append(
                    Finding(
                        Severity.ERROR,
                        "ZIP-004",
                        f"Entry '{info.filename}' has compression ratio {ratio:.0f}:1 "
                        f"(limit: {max_ratio}:1) — possible zip bomb",
                    )
                )

    if total_decompressed > max_size:
        size_gb = total_decompressed / 1024**3
        limit_gb = max_size / 1024**3
        findings.append(
            Finding(
                Severity.ERROR,
                "ZIP-005",
                f"Total decompressed size {size_gb:.1f} GB exceeds limit of "
                f"{limit_gb:.1f} GB — possible zip bomb",
            )
        )

    return findings


def check_manifest_fields(manifest: dict) -> List[Finding]:
    """Validate required manifest fields and value constraints."""
    findings: List[Finding] = []

    # Required top-level fields (must match manifest.schema.json required array)
    required = ["format_version", "created_at", "creator_info", "platform_info", "index_summary", "hash_algo", "shard_list"]
    for field in required:
        if field not in manifest:
            findings.append(
                Finding(Severity.ERROR, "MAN-010", f"Missing required field: {field}")
            )

    # format_version semver and compatibility checks
    fv = manifest.get("format_version", "")
    version_match = SEMVER_PATTERN.match(fv) if isinstance(fv, str) else None
    if fv and not version_match:
        findings.append(
            Finding(Severity.WARNING, "MAN-011", f"format_version '{fv}' is not valid semver")
        )
    elif version_match:
        major = int(version_match.group(1))
        if major > SUPPORTED_FORMAT_MAJOR:
            findings.append(
                Finding(
                    Severity.ERROR,
                    "MAN-013",
                    f"Unsupported format_version {fv}; maximum supported major version is {SUPPORTED_FORMAT_MAJOR}.x.x",
                )
            )

    # hash_algo
    algo = manifest.get("hash_algo", "")
    if algo and algo not in ("sha256", "sha512", "blake3"):
        findings.append(
            Finding(Severity.ERROR, "MAN-012", f"Unsupported hash_algo: '{algo}'")
        )

    # shard_list structure validation
    if "shard_list" in manifest:
        if not isinstance(manifest["shard_list"], list) or len(manifest["shard_list"]) < 1:
            findings.append(
                Finding(Severity.ERROR, "MAN-014", "shard_list must be a non-empty array")
            )

    # index_summary
    summary = manifest.get("index_summary")
    if isinstance(summary, dict):
        for sf in ("total_files", "total_shards", "total_size_bytes"):
            if sf not in summary:
                findings.append(
                    Finding(Severity.ERROR, "MAN-015", f"index_summary missing required field: {sf}")
                )

    return findings


def check_manifest_cross_fields(manifest: dict) -> List[Finding]:
    """Validate manifest relationships that JSON Schema cannot express."""
    findings: List[Finding] = []

    workspace_id = manifest.get("workspace_id")
    if workspace_id:
        ids = manifest.get("ids")
        workspace_ids = []
        if isinstance(ids, list):
            workspace_ids = [
                item.get("id")
                for item in ids
                if isinstance(item, dict) and item.get("ns") == "meshsync:workspace"
            ]
        if workspace_id not in workspace_ids:
            findings.append(
                Finding(
                    Severity.ERROR,
                    "MAN-020",
                    "workspace_id must match an ids entry with ns='meshsync:workspace'",
                )
            )

    generation = manifest.get("generation")
    if isinstance(generation, dict) and generation.get("partial") is True:
        if not generation.get("base_pack_hash"):
            findings.append(
                Finding(
                    Severity.ERROR,
                    "MAN-021",
                    "generation.partial=true requires generation.base_pack_hash",
                )
            )

    return findings


def check_index_summary(manifest: dict, total_entries: int, total_size_bytes: int, total_shards: int) -> List[Finding]:
    """Validate manifest.index_summary against parsed shard contents."""
    findings: List[Finding] = []
    summary = manifest.get("index_summary")
    if not isinstance(summary, dict):
        return findings

    expected = {
        "total_files": total_entries,
        "total_shards": total_shards,
        "total_size_bytes": total_size_bytes,
    }
    for field, actual_value in expected.items():
        declared_value = summary.get(field)
        if declared_value is not None and declared_value != actual_value:
            findings.append(
                Finding(
                    Severity.ERROR,
                    "MAN-022",
                    f"index_summary.{field} mismatch: manifest={declared_value} actual={actual_value}",
                )
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
                Severity.ERROR,
                "ENT-003",
                f"Absolute path in {shard_path}: {path}",
            )
        )

    # Windows drive letter paths (e.g., C:\Users\file.stl)
    if len(path) >= 2 and path[0].isalpha() and path[1] == ":":
        findings.append(
            Finding(
                Severity.ERROR,
                "ENT-004",
                f"Drive letter path in {shard_path}: {path}",
            )
        )

    # UNC paths (e.g., \\server\share\file.stl)
    if path.startswith("\\\\"):
        findings.append(
            Finding(
                Severity.ERROR,
                "ENT-005",
                f"UNC path in {shard_path}: {path}",
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


def check_resource_ref(resource_ref: object, field_name: str, shard_path: str, entry_path: str) -> List[Finding]:
    """Validate resource/preview references before using them as ZIP paths."""
    findings: List[Finding] = []
    if resource_ref is None or resource_ref == "":
        return findings
    if not isinstance(resource_ref, str):
        findings.append(
            Finding(
                Severity.ERROR,
                "RES-004",
                f"{field_name} for {shard_path}:{entry_path} must be a string",
            )
        )
        return findings

    if ":" in resource_ref:
        findings.append(
            Finding(
                Severity.WARNING,
                "RES-003",
                f"{field_name} contains ':' in {shard_path}:{entry_path}. "
                "Resource filenames should be hex-hash only with an extension, no algorithm prefix.",
            )
        )

    unsafe_path = (
        "/" in resource_ref
        or "\\" in resource_ref
        or PATH_TRAVERSAL_PATTERN.search(resource_ref)
        or resource_ref.startswith("/")
        or resource_ref.startswith("\\\\")
        or (len(resource_ref) >= 2 and resource_ref[0].isalpha() and resource_ref[1] == ":")
    )
    if unsafe_path or not RESOURCE_REF_PATTERN.match(resource_ref):
        findings.append(
            Finding(
                Severity.ERROR,
                "RES-004",
                f"Unsafe or non-canonical {field_name} in {shard_path}:{entry_path}: {resource_ref}",
            )
        )

    return findings


def verify_entries_hash(
    entries: List[dict], algo: str, expected_hash: str
) -> Tuple[bool, str]:
    """Compute entries_hash using canonical JSON (RFC 8785 JCS)."""
    sorted_entries = sorted(entries, key=lambda e: _path_sort_key(e.get("path", "")))
    encoded = jcs_canonicalize(sorted_entries)
    digest = compute_digest([encoded], algo)
    actual = f"{algo}:{digest}"
    return actual == expected_hash, actual


def verify_shards(zf: zipfile.ZipFile, manifest: dict, schema_mode: str) -> List[Finding]:
    """Validate all shards referenced by the manifest."""
    findings: List[Finding] = []
    algo = manifest.get("hash_algo", "sha256")
    archive_names: Set[str] = set(zf.namelist())
    total_entries = 0
    total_size_bytes = 0
    listed_shard_paths: Set[str] = set()

    shard_list = manifest.get("shard_list")
    if shard_list is not None and not isinstance(shard_list, list):
        shard_list = []
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
        listed_shard_paths.add(shard_path)

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

        findings.extend(validate_json_schema(shard, "shard.schema.json", shard_path, schema_mode))

        if shard.get("shard_id") != shard_id:
            findings.append(
                Finding(
                    Severity.ERROR,
                    "SHD-008",
                    f"shard_id mismatch for {shard_path}: manifest={shard_id} shard={shard.get('shard_id')}",
                )
            )

        manifest_version = manifest.get("format_version")
        shard_version = shard.get("format_version")
        if manifest_version and shard_version and manifest_version != shard_version:
            findings.append(
                Finding(
                    Severity.ERROR,
                    "SHD-009",
                    f"format_version mismatch for {shard_path}: manifest={manifest_version} shard={shard_version}",
                )
            )

        entries = shard.get("entries", [])
        if not isinstance(entries, list):
            continue

        total_entries += len(entries)
        total_size_bytes += sum(
            entry.get("size_bytes", 0)
            for entry in entries
            if isinstance(entry, dict) and isinstance(entry.get("size_bytes"), int)
        )

        # Check entry ordering (UTF-8 byte order by path)
        paths = [e.get("path", "") for e in entries]
        if paths != sorted(paths, key=_path_sort_key):
            findings.append(
                Finding(Severity.WARNING, "SHD-004", f"Entries not sorted by UTF-8 path order in {shard_path}")
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

        shard_count = shard.get("entries_count")
        if shard_count is not None and shard_count != len(entries):
            findings.append(
                Finding(
                    Severity.ERROR,
                    "SHD-005",
                    f"entries_count mismatch in {shard_path}: shard={shard_count} actual={len(entries)}",
                )
            )

        # Validate entries_hash
        expected_hash = shard_meta.get("entries_hash") or shard.get("entries_hash")
        shard_hash = shard.get("entries_hash")
        meta_hash = shard_meta.get("entries_hash")
        if meta_hash and shard_hash and meta_hash != shard_hash:
            findings.append(
                Finding(
                    Severity.ERROR,
                    "SHD-012",
                    f"entries_hash mismatch between manifest and {shard_path}: manifest={meta_hash} shard={shard_hash}",
                )
            )
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
            if not isinstance(entry, dict):
                continue
            entry_path = entry.get("path", "<unknown>")

            # Path constraints
            findings.extend(check_entry_path(entry, shard_path))

            # Official extension payloads
            findings.extend(
                validate_official_extensions(
                    entry.get("extensions"),
                    f"{shard_path}:{entry_path}",
                    schema_mode,
                )
            )

            # Hash format
            entry_hash = entry.get("hash", "")
            findings.extend(check_hash_format(entry_hash, shard_path, entry_path))
            if entry.get("resource_hash"):
                findings.extend(check_hash_format(entry.get("resource_hash", ""), shard_path, entry_path))

            if entry.get("operation") == "delete":
                if entry.get("size_bytes") != 0:
                    findings.append(
                        Finding(
                            Severity.ERROR,
                            "DEL-001",
                            f"delete entry must have size_bytes=0 in {shard_path}:{entry_path}",
                        )
                    )
                if entry_hash != _zero_hash(algo):
                    findings.append(
                        Finding(
                            Severity.ERROR,
                            "DEL-002",
                            f"delete entry must use zero hash {_zero_hash(algo)} in {shard_path}:{entry_path}",
                        )
                    )
                if entry.get("resource_ref") or entry.get("preview_ref"):
                    findings.append(
                        Finding(
                            Severity.ERROR,
                            "DEL-003",
                            f"delete entry must not reference embedded resources in {shard_path}:{entry_path}",
                        )
                    )

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
                findings.extend(check_resource_ref(resource_ref, "resource_ref", shard_path, entry_path))
                resource_path = f"resources/{resource_ref}"
                if resource_path not in archive_names:
                    findings.append(
                        Finding(
                            Severity.ERROR,
                            "RES-002",
                            f"Missing embedded resource: {resource_path} (referenced by {entry_path})",
                        )
                    )
                else:
                    resource_bytes = zf.read(resource_path)
                    if resource_hash:
                        try:
                            actual_hash = f"{algo}:{compute_digest([resource_bytes], algo)}"
                            if actual_hash != resource_hash:
                                findings.append(
                                    Finding(
                                        Severity.ERROR,
                                        "RES-005",
                                        f"resource_hash mismatch for {resource_path}: expected {resource_hash}, got {actual_hash}",
                                    )
                                )
                        except ValueError as exc:
                            findings.append(Finding(Severity.WARNING, "RES-006", str(exc)))
                    resource_size = entry.get("resource_size_bytes")
                    if resource_size is not None and resource_size != len(resource_bytes):
                        findings.append(
                            Finding(
                                Severity.ERROR,
                                "RES-007",
                                f"resource_size_bytes mismatch for {resource_path}: expected {resource_size}, got {len(resource_bytes)}",
                            )
                        )

            preview_ref = entry.get("preview_ref")
            if preview_ref:
                findings.extend(check_resource_ref(preview_ref, "preview_ref", shard_path, entry_path))
                preview_path = f"resources/{preview_ref}"
                if preview_path not in archive_names:
                    findings.append(
                        Finding(
                            Severity.ERROR,
                            "RES-002",
                            f"Missing embedded resource: {preview_path} (referenced by {entry_path})",
                        )
                    )

    actual_shards = {name for name in archive_names if re.match(r"^index/part-\d+\.json$", name)}
    for rogue_shard in sorted(actual_shards - listed_shard_paths):
        findings.append(
            Finding(
                Severity.ERROR,
                "SHD-011",
                f"Archive contains unlisted shard: {rogue_shard}",
            )
        )

    findings.extend(check_index_summary(manifest, total_entries, total_size_bytes, len(shard_list)))

    return findings


def verify_sidecar(
    meshpack_path: str,
    sidecar_path: Optional[str],
    manifest: dict,
    schema_mode: str,
    verify_sigs: bool = False,
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

    findings.extend(validate_json_schema(sidecar, "sidecar.schema.json", sidecar_path, schema_mode))
    findings.extend(validate_official_extensions(sidecar.get("extensions"), sidecar_path, schema_mode))

    pack_name = sidecar.get("pack_name")
    if pack_name and pack_name != os.path.basename(meshpack_path):
        findings.append(
            Finding(
                Severity.ERROR,
                "SDC-006",
                f"Sidecar pack_name mismatch: sidecar expects {pack_name}, archive is {os.path.basename(meshpack_path)}",
            )
        )

    pack_size_bytes = sidecar.get("pack_size_bytes")
    if isinstance(pack_size_bytes, int):
        actual_size = os.path.getsize(meshpack_path)
        if pack_size_bytes != actual_size:
            findings.append(
                Finding(
                    Severity.ERROR,
                    "SDC-007",
                    f"Sidecar pack_size_bytes mismatch: sidecar expects {pack_size_bytes}, archive is {actual_size}",
                )
            )

    # Verify pack_hash
    sidecar_algo = sidecar.get("hash_algo", "")
    sidecar_hash = sidecar.get("pack_hash", "")
    manifest_algo = manifest.get("hash_algo", "") if manifest else ""
    if sidecar_algo and manifest_algo and sidecar_algo != manifest_algo:
        findings.append(
            Finding(
                Severity.ERROR,
                "SDC-008",
                f"Sidecar hash_algo mismatch: sidecar uses {sidecar_algo}, manifest uses {manifest_algo}",
            )
        )
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

    signatures = sidecar.get("signatures")
    if signatures and verify_sigs:
        findings.extend(verify_signature_entries(signatures, sidecar_hash))
    elif signatures:
        findings.append(
            Finding(
                Severity.INFO,
                "SDC-011",
                f"Sidecar contains {len(signatures)} signature(s). "
                "Use --verify-signatures to check them.",
            )
        )

    return findings


def verify_signature_entries(
    signatures: List[dict], pack_hash: str
) -> List[Finding]:
    """Verify cryptographic signatures over pack_hash (REQ-L3-030)."""
    findings: List[Finding] = []

    try:
        import base64
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        from cryptography.hazmat.primitives.asymmetric.padding import PSS, MGF1
        from cryptography.hazmat.primitives.hashes import SHA256
        from cryptography.hazmat.primitives.serialization import load_der_public_key
    except ImportError:
        findings.append(
            Finding(
                Severity.WARNING,
                "SIG-001",
                "Signature verification requires the 'cryptography' package: "
                "pip install cryptography",
            )
        )
        return findings

    # The signed data is the pack_hash string encoded as UTF-8
    signed_data = pack_hash.encode("utf-8")

    for i, sig_entry in enumerate(signatures):
        alg = sig_entry.get("alg", "")
        pub_key_b64 = sig_entry.get("public_key", "")
        sig_b64 = sig_entry.get("signature", "")
        signer = sig_entry.get("signer_id", f"signature[{i}]")

        if not alg or not pub_key_b64 or not sig_b64:
            findings.append(
                Finding(Severity.ERROR, "SIG-002",
                        f"{signer}: missing required field (alg/public_key/signature)")
            )
            continue

        try:
            pub_key_bytes = base64.b64decode(pub_key_b64)
            sig_bytes = base64.b64decode(sig_b64)
        except Exception as exc:
            findings.append(
                Finding(Severity.ERROR, "SIG-003",
                        f"{signer}: invalid base64 encoding — {exc}")
            )
            continue

        if alg == "ed25519":
            try:
                key_bytes = pub_key_bytes if len(pub_key_bytes) == 32 else pub_key_bytes[-32:]
                key = Ed25519PublicKey.from_public_bytes(key_bytes)
                key.verify(sig_bytes, signed_data)
                findings.append(
                    Finding(Severity.INFO, "SIG-010",
                            f"{signer}: Ed25519 signature verified successfully")
                )
            except Exception as exc:
                findings.append(
                    Finding(Severity.ERROR, "SIG-004",
                            f"{signer}: Ed25519 signature verification failed — {exc}")
                )
        elif alg == "rsa-pss-sha256":
            try:
                key = load_der_public_key(pub_key_bytes)
                key.verify(sig_bytes, signed_data, PSS(mgf=MGF1(SHA256()), salt_length=PSS.MAX_LENGTH), SHA256())
                findings.append(
                    Finding(Severity.INFO, "SIG-010",
                            f"{signer}: RSA-PSS-SHA256 signature verified successfully")
                )
            except Exception as exc:
                findings.append(
                    Finding(Severity.ERROR, "SIG-004",
                            f"{signer}: RSA-PSS-SHA256 signature verification failed — {exc}")
                )
        else:
            findings.append(
                Finding(Severity.INFO, "SIG-005",
                        f"{signer}: unsupported algorithm '{alg}' — skipped")
            )

    return findings


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


def validate(
    meshpack_path: str,
    sidecar_path: Optional[str] = None,
    max_size: int = MAX_DECOMPRESSED_SIZE,
    max_ratio: int = MAX_COMPRESSION_RATIO,
    verify_sigs: bool = False,
    schema_mode: str = "compat",
) -> List[Finding]:
    """Run all validation checks on a .meshpack archive."""
    findings: List[Finding] = []
    if schema_mode not in {"compat", "strict"}:
        raise ValueError("schema_mode must be 'compat' or 'strict'")

    # Open archive
    try:
        zf = zipfile.ZipFile(meshpack_path, "r")
    except (zipfile.BadZipFile, FileNotFoundError) as exc:
        findings.append(Finding(Severity.ERROR, "ARC-001", f"Cannot open archive: {exc}"))
        return findings

    with zf:
        # ZIP ordering
        findings.extend(check_zip_ordering(zf))

        # Human-readable layout entries
        findings.extend(check_readme_layout(zf))

        # ZIP compression methods
        findings.extend(check_zip_compression(zf))

        # Zip bomb protection
        findings.extend(check_zip_bomb(zf, max_size, max_ratio))

        # Manifest
        manifest, man_findings = load_manifest(zf)
        findings.extend(man_findings)
        if manifest is None:
            return findings  # Cannot proceed without manifest

        # Manifest field validation
        findings.extend(check_manifest_fields(manifest))
        findings.extend(check_manifest_cross_fields(manifest))
        findings.extend(
            validate_json_schema(manifest, "manifest.schema.json", "manifest.json", schema_mode)
        )
        findings.extend(
            validate_official_extensions(manifest.get("extensions"), "manifest.json", schema_mode)
        )

        # Shard validation
        findings.extend(verify_shards(zf, manifest, schema_mode))

    # Sidecar verification (outside ZIP context — reads file from disk)
    findings.extend(verify_sidecar(meshpack_path, sidecar_path, manifest, schema_mode, verify_sigs))

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
    parser.add_argument(
        "--max-size",
        type=int,
        default=MAX_DECOMPRESSED_SIZE,
        help=f"Max total decompressed size in bytes (default: {MAX_DECOMPRESSED_SIZE})",
    )
    parser.add_argument(
        "--max-ratio",
        type=int,
        default=MAX_COMPRESSION_RATIO,
        help=f"Max compression ratio per entry (default: {MAX_COMPRESSION_RATIO}:1)",
    )
    parser.add_argument(
        "--verify-signatures",
        action="store_true",
        help="Verify cryptographic signatures (requires 'cryptography' package)",
    )
    parser.add_argument(
        "--schema-mode",
        choices=("compat", "strict"),
        default="compat",
        help="Schema validation mode: compat warns on unknown fields; strict errors on all schema violations.",
    )
    args = parser.parse_args()

    findings = validate(
        args.meshpack, args.sidecar, args.max_size, args.max_ratio,
        verify_sigs=args.verify_signatures,
        schema_mode=args.schema_mode,
    )

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
