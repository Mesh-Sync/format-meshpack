# Validation Contract

The Python reference validator in [tools/meshpack_validate.py](../tools/meshpack_validate.py) is the authoritative behavior source. Generated SDK validators expose the same finding shape so applications can consume validation results consistently across Python, Rust, TypeScript, and Java 17.

## Finding Shape

Each finding has:

| Field | Meaning |
|-------|---------|
| `severity` | `ERROR`, `WARNING`, or `INFO` |
| `code` | Stable code in the form `AAA-000` |
| `message` | Human-readable diagnostic |
| `path` | Optional archive path, JSON pointer, or resource path |

The machine-readable schema is [schema/validation-finding.schema.json](../schema/validation-finding.schema.json).

## Required SDK Validator Coverage

All generated SDK validators must implement these public-readiness checks:

| Area | Codes |
|------|-------|
| Archive open/read errors | `ARC-001` |
| Manifest presence and parse errors | `MAN-001`, `MAN-002` |
| Manifest required fields and hash algorithm | `MAN-010`, `MAN-011`, `MAN-012`, `MAN-014`, `MAN-015` |
| ZIP ordering, compression, and bomb limits | `ZIP-001`, `ZIP-003`, `ZIP-004`, `ZIP-005` |
| Shard presence, parse, order, count, hash | `SHD-001`, `SHD-002`, `SHD-003`, `SHD-004`, `SHD-005`, `SHD-006`, `SHD-007` |
| Entry path and hash safety | `ENT-001`, `ENT-002`, `ENT-003`, `ENT-004`, `ENT-005`, `HSH-001` |
| Resource references | `RES-001`, `RES-002`, `RES-003`, `RES-004` |
| Sidecar integrity | `SDC-001`, `SDC-002`, `SDC-003`, `SDC-004`, `SDC-005`, `SDC-006`, `SDC-007`, `SDC-008`, `SDC-010`, `SDC-011` |
| Signature verification | `SIG-001`, `SIG-002`, `SIG-003`, `SIG-004`, `SIG-005`, `SIG-010` |

The Python reference validator additionally performs JSON Schema validation:

| Code | Meaning |
|------|---------|
| `SCH-001` | Required/type/enum/pattern schema failure |
| `SCH-002` | Unknown property rejected by schema `additionalProperties: false` |

## Schema Modes

The reference validator supports two schema modes:

| Mode | Behavior |
|------|----------|
| `compat` | Default. Unknown properties are reported as `SCH-002` warnings so newer producers can be inspected by older validators. Other schema failures remain errors. |
| `strict` | All schema failures, including unknown properties, are errors. Use this for release gates and public fixtures. |

The CLI flag is `--schema-mode compat|strict`. The separate `--strict` flag still means warnings are treated as process-failing findings.

## Resource References

`resource_ref` and `preview_ref` are filenames inside `resources/`, not paths. Validators and readers must reject non-canonical references before constructing `resources/<name>`.

Valid references use `{hex_hash}.{ext}` with a 64-character hash for `sha256`/`blake3` or a 128-character hash for `sha512`. They must not include slashes, backslashes, drive letters, UNC prefixes, traversal segments, or algorithm prefixes such as `sha256:`.

Pack-level sidecar and signature checks remain fully authoritative in the Python reference validator. SDKs may expose those checks as optional features, but they must not claim L3/full compliance until they pass the shared conformance vectors.

## Sidecar Hashes and Signatures

The sidecar `pack_hash` is the authoritative pack-level integrity value. MeshPack 2.0 hashes the complete `.meshpack` / `.mpack` archive bytes; there are no ZIP-entry exclusions. `mapping.db` is therefore included in `pack_hash` if present. `manifest.pack_hash` and `manifest.signatures` are informational only and MUST NOT be used as the trust root for L3 validation.

Validators must compare `sidecar.pack_size_bytes` with the archive size, require `sidecar.hash_algo` to match `manifest.hash_algo`, compute the archive digest, and compare it with `sidecar.pack_hash`. When signature verification is requested, signatures are verified over the exact `sidecar.pack_hash` string.
