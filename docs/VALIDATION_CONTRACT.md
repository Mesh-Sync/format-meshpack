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
| Resource references | `RES-001`, `RES-002`, `RES-003` |

Pack-level sidecar and signature checks remain fully authoritative in the Python reference validator. SDKs may expose those checks as optional features, but they must not claim L3/full compliance until they pass the shared conformance vectors.
