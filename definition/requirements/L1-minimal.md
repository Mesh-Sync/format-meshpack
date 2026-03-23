# L1 Requirements: Minimal Conformance

**Target**: File browsers, simple viewers, archive extraction tools, documentation generators

**Scope**: Read-only operations on valid `.meshpack` archives

---

## 1. Archive Format Requirements

### REQ-L1-001: ZIP Container Recognition

**Category**: Archive
**Type**: MUST
**Testable**: Yes

Implementations MUST recognize `.meshpack` and `.mpack` file extensions as ZIP archives using DEFLATE (method 8) or STORE (method 0) compression.

**Rationale**: Ensures universal accessibility without specialized decompression libraries.

**Verification**: Open `samples/*.meshpack` files with standard ZIP library, verify no decompression errors.

---

### REQ-L1-002: Format Version Validation

**Category**: Manifest
**Type**: MUST
**Testable**: Yes

Implementations MUST parse `manifest.json` and validate the `format_version` field before processing. If the major version exceeds the implementation's supported version, processing MUST halt with an appropriate error message.

**Rationale**: Prevents silent data corruption from incompatible schema changes.

**Verification**: 
1. Create test pack with `format_version: "1.0.0"` → should parse successfully
2. Create test pack with `format_version: "2.0.0"` → should return version error

---

### REQ-L1-003: Manifest Required Fields

**Category**: Manifest
**Type**: MUST
**Testable**: Yes

Implementations MUST validate the presence of the following required fields in `manifest.json`:

| Field | Type | Description |
|-------|------|-------------|
| `format_version` | string | SemVer format specification version |
| `created_at` | string | ISO 8601 datetime |
| `creator_info` | object | At minimum `{ "name": string }` |
| `platform_info` | object | Contains `os`, `path_separator`, `is_case_sensitive` |
| `index_summary` | object | Contains `total_files`, `total_shards`, `total_size_bytes` |
| `hash_algo` | string | One of: `sha256`, `sha512`, `blake3` |
| `shard_list` | array | Non-empty array of shard references |

**Rationale**: These fields are essential for basic package interpretation.

**Verification**: Validate against `schema/manifest.schema.json`, test with missing fields.

---

## 2. Index Shard Requirements

### REQ-L1-010: Shard Discovery

**Category**: Shard
**Type**: MUST
**Testable**: Yes

Implementations MUST read all shards listed in `manifest.json#shard_list` from the `index/` directory. Shards are named `part-XXXXX.json` (1-based, **5-digit** zero-padded, e.g., `part-00001.json`).

**Rationale**: Complete file enumeration requires all shards.

**Verification**: Create pack with 3 shards, verify all entries are accessible.

---

### REQ-L1-011: Shard Required Fields

**Category**: Shard
**Type**: MUST
**Testable**: Yes

Each shard file MUST contain:

| Field | Type | Description |
|-------|------|-------------|
| `shard_id` | string | Matches filename (e.g., `part-00001`) |
| `format_version` | string | Must match manifest version |
| `entries_count` | integer | Number of entries in this shard |
| `entries_hash` | string | Hash of sorted entries (for integrity) |
| `entries` | array | Array of `FileEntry` objects |

**Rationale**: Ensures shard validity and enables integrity verification at higher conformance levels.

**Verification**: Validate against `schema/shard.schema.json`.

---

### REQ-L1-012: FileEntry Required Fields

**Category**: Shard
**Type**: MUST
**Testable**: Yes

Each `FileEntry` in `entries` array MUST contain:

| Field | Type | Description |
|-------|------|-------------|
| `path` | string | Relative path from root, POSIX separators (`/`), max 1024 chars |
| `original_name` | string | Original filename (may differ from path basename) |
| `size_bytes` | integer | File size in bytes |
| `hash` | string | Content hash in format `{algo}:{hex}` where algo matches `manifest.hash_algo` |
| `modified_at` | string | ISO 8601 datetime of last modification |

**Rationale**: Minimum data required to identify and locate files.

**Verification**: Parse sample pack, verify all entries have required fields.

---

### REQ-L1-013: Path Normalization

**Category**: Shard
**Type**: MUST
**Testable**: Yes

Implementations MUST:
1. Accept paths using forward slashes (`/`) only
2. Reject paths containing `..` (parent directory traversal)
3. Reject absolute paths (starting with `/` or drive letter)
4. Handle both case-sensitive and case-insensitive matching based on `platform_info.is_case_sensitive`
5. Reject paths exceeding 1024 characters

**Rationale**: Security, cross-platform compatibility, and filesystem limit protection.

**Verification**: 
1. Path `vehicles/car.stl` → valid
2. Path `../../../etc/passwd` → reject
3. Path `/root/secret.stl` → reject
4. Path `C:\Users\file.stl` → reject

---

## 3. Optional Field Handling

### REQ-L1-020: Unknown Field Tolerance

**Category**: General
**Type**: MUST
**Testable**: Yes

Implementations MUST silently ignore unknown fields in `manifest.json`, shards, and file entries without raising errors. This enables forward compatibility with future schema additions.

**Rationale**: Allows older implementations to read packs created by newer tools.

**Verification**: Add `"future_field": "test"` to manifest, verify no parsing error.

---

### REQ-L1-021: Optional FileEntry Fields

**Category**: Shard
**Type**: SHOULD
**Testable**: Yes

Implementations SHOULD support parsing these optional `FileEntry` fields if present:

| Field | Type | Description |
|-------|------|-------------|
| `mime_type` | string | MIME type (e.g., `model/stl`) |
| `units` | string | One of: `mm`, `cm`, `m`, `in`, `ft`, `unitless` |
| `up_axis` | string | One of: `+Z`, `-Z`, `+Y`, `-Y` |
| `bounding_box` | object | `{ min: [x,y,z], max: [x,y,z] }` |
| `metamodel_id` | string | UUID of parent metamodel |
| `metamodel_role` | string | One of: `canonical`, `variant`, `accessory`, `doc` |
| `resource_ref` | string | Reference to embedded resource |
| `preview_ref` | string | Reference to preview thumbnail |
| `attributes` | object | `{ is_symlink, is_hidden }` |
| `extensions` | object | Arbitrary extension data |

**Rationale**: Rich metadata improves user experience in viewers.

**Verification**: Parse sample pack with all optional fields, verify accessible via API.

---

## 4. Documentation Requirements

### REQ-L1-030: README Awareness

**Category**: Documentation
**Type**: SHOULD
**Testable**: No

Implementations SHOULD recognize and optionally display the contents of:
- `/_README.md` - Root documentation
- `/index/_README.md` - Index structure explanation
- `/resources/_README.md` - Embedded resource documentation (if folder exists)

**Rationale**: Self-documenting packages improve usability for manual inspection.

**Verification**: Manual review of documentation display in viewer.

---

## 5. Error Handling Requirements

### REQ-L1-040: Graceful Degradation

**Category**: Error Handling
**Type**: SHOULD
**Testable**: Yes

When encountering non-critical errors, implementations SHOULD:
1. Log warnings without halting processing
2. Continue processing remaining valid entries
3. Report summary of skipped entries after completion

Non-critical errors include:
- Individual corrupted shard (if others are valid)
- Missing optional fields
- Invalid entries in an otherwise valid shard

**Rationale**: Maximizes data recovery from partially corrupted archives.

**Verification**: Create pack with one invalid entry among 100 valid, verify 99 are accessible.

---

### REQ-L1-041: Critical Error Reporting

**Category**: Error Handling
**Type**: MUST
**Testable**: Yes

Implementations MUST report clear error messages for critical failures:

| Error Condition | Required Message Content |
|-----------------|-------------------------|
| Missing manifest.json | "Missing required manifest.json" |
| Invalid JSON syntax | "JSON parse error at line X" |
| Unsupported format_version | "Unsupported format version X.Y.Z, maximum supported: A.B.C" |
| No shards found | "No index shards found in index/" |
| All shards corrupted | "All shards failed validation" |

**Rationale**: Enables users and support to diagnose issues.

**Verification**: Trigger each error condition, verify message matches specification.

---

## 6. Performance Recommendations

### REQ-L1-050: Streaming Support

**Category**: Performance
**Type**: MAY
**Testable**: No

Implementations MAY support streaming access without fully extracting the archive:
1. Random access to `manifest.json` via ZIP central directory
2. Sequential shard loading to minimize memory
3. Lazy extraction of `resources/` on demand

**Rationale**: Enables handling of large archives on memory-constrained systems.

---

### REQ-L1-051: Entry Iteration

**Category**: Performance
**Type**: SHOULD
**Testable**: No

Implementations SHOULD provide an iterator/generator interface for file entries to avoid loading all shards into memory simultaneously.

**Rationale**: Supports archives with millions of entries.

---

## Summary: L1 Compliance Checklist

| ID | Requirement | Type | Status |
|----|-------------|------|--------|
| REQ-L1-001 | ZIP Container Recognition | MUST | ☐ |
| REQ-L1-002 | Format Version Validation | MUST | ☐ |
| REQ-L1-003 | Manifest Required Fields | MUST | ☐ |
| REQ-L1-010 | Shard Discovery | MUST | ☐ |
| REQ-L1-011 | Shard Required Fields | MUST | ☐ |
| REQ-L1-012 | FileEntry Required Fields | MUST | ☐ |
| REQ-L1-013 | Path Normalization | MUST | ☐ |
| REQ-L1-020 | Unknown Field Tolerance | MUST | ☐ |
| REQ-L1-021 | Optional FileEntry Fields | SHOULD | ☐ |
| REQ-L1-030 | README Awareness | SHOULD | ☐ |
| REQ-L1-040 | Graceful Degradation | SHOULD | ☐ |
| REQ-L1-041 | Critical Error Reporting | MUST | ☐ |
| REQ-L1-050 | Streaming Support | MAY | ☐ |
| REQ-L1-051 | Entry Iteration | SHOULD | ☐ |

**Minimum for L1 Compliance**: All MUST requirements (8 total)
