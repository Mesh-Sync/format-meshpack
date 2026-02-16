# L2 Requirements: Standard Conformance

**Target**: Desktop sync agents, 3D model viewers, local storage plugins, export/import tools

**Scope**: Read and write operations with integrity verification

**Prerequisite**: Full L1 compliance

---

## 1. Pack Generation Requirements

### REQ-L2-000: ZIP Entry Ordering

**Category**: Archive
**Type**: MUST
**Testable**: Yes

The `manifest.json` entry MUST be the **first** entry in the ZIP central directory. This enables streaming readers to parse the manifest without seeking through arbitrarily large archives.

**Rationale**: Critical for streaming support and large archive performance.

**Verification**:
1. Generate pack, list ZIP entries
2. Verify `manifest.json` is the first entry

---

### REQ-L2-001: Valid Archive Creation

**Category**: Archive
**Type**: MUST
**Testable**: Yes

Implementations MUST generate valid ZIP archives with:
1. DEFLATE (method 8) or STORE (method 0) compression only
2. UTF-8 encoded filenames
3. Standard ZIP64 extensions for files > 4GB or > 65,535 entries
4. Correct CRC-32 checksums for all entries

**Rationale**: Ensures maximum compatibility with standard tools.

**Verification**: 
1. Generate pack, verify openable with `unzip`, `7z`, `WinZip`
2. Verify `unzip -t` reports no errors

---

### REQ-L2-002: Manifest Generation

**Category**: Manifest
**Type**: MUST
**Testable**: Yes

When generating a pack, implementations MUST:
1. Set `format_version` to their supported specification version
2. Set `created_at` to current UTC timestamp in ISO 8601 format
3. Populate `platform_info` based on the generating system:
   - `os`: Detect runtime OS (`linux`, `windows`, `darwin`)
   - `path_separator`: Use source filesystem separator
   - `is_case_sensitive`: Detect filesystem case sensitivity
4. Calculate `index_summary` after generating all shards:
   - `total_files`: Sum of all entry counts
   - `total_shards`: Number of generated shards
   - `total_size_bytes`: Sum of all `size_bytes` in entries
5. Populate `shard_list` with accurate `entries_count` and `entries_hash` per shard

**Rationale**: Complete manifest enables receivers to validate packages without extracting.

**Verification**: Generate pack, validate against `manifest.schema.json`.

---

### REQ-L2-003: Deterministic Sharding

**Category**: Shard
**Type**: MUST
**Testable**: Yes

Implementations MUST shard entries deterministically:
1. **Sort order**: Entries sorted by `path` field (UTF-8 byte order, ascending)
2. **Shard naming**: `part-00001.json`, `part-00002.json`, etc. (1-based, **5-digit** zero-padded)
3. **Shard limits**: MUST NOT exceed **10,000 entries** per shard. SHOULD NOT exceed 5 MB per shard.
4. **Distribution**: Last shard may have fewer entries

**Rationale**: Deterministic output enables reproducible builds and caching.

**Verification**: 
1. Generate pack twice from same source → identical `entries_hash` per shard
2. Verify shards don't exceed limits

---

### REQ-L2-004: FileEntry Generation

**Category**: Shard
**Type**: MUST
**Testable**: Yes

For each file in the source, implementations MUST populate:

| Field | Source |
|-------|--------|
| `path` | Relative path from root, normalized to POSIX `/` |
| `original_name` | Original filename (preserving case) |
| `size_bytes` | File size from filesystem or stream |
| `hash` | Computed using manifest's `hash_algo` |
| `modified_at` | File modification timestamp |

Implementations SHOULD populate when available:
- `mime_type`: Detect from extension or file magic
- `created_at`: File creation timestamp (if filesystem supports)
- `attributes.is_symlink`: Detect symbolic links
- `attributes.is_hidden`: Detect hidden files (dotfiles on Unix, hidden attribute on Windows)

**Rationale**: Rich metadata improves downstream processing and display.

**Verification**: Generate pack from test directory with various file types, verify fields populated.

---

## 2. Integrity Verification Requirements

### REQ-L2-010: Shard Hash Computation

**Category**: Integrity
**Type**: MUST
**Testable**: Yes

The `entries_hash` for each shard MUST be computed as:

```
entries_hash = hash(canonical_json(sorted(entries)))
```

Where:
1. `sorted(entries)` = entries sorted by `path` (UTF-8 byte order)
2. `canonical_json()` = JSON canonicalized per [RFC 8785 (JCS — JSON Canonicalization Scheme)](https://www.rfc-editor.org/rfc/rfc8785):
   - Keys sorted alphabetically (recursive)
   - No whitespace between tokens
   - UTF-8 encoding
   - Numbers serialized per RFC 8259 §6 (no NaN/Infinity, integers without decimal point)
   - No trailing newlines
   - No BOM
3. `hash()` = Algorithm from `manifest.hash_algo`
4. Format: `{algorithm}:{lowercase_hex}` (e.g., `sha256:a1b2c3...`)

**Rationale**: Deterministic hash enables tamper detection.

**Verification**: 
1. Compute `entries_hash` from shard file
2. Compare to value in `manifest.shard_list`
3. Modify one entry, verify hash changes

---

### REQ-L2-011: Shard Hash Verification

**Category**: Integrity
**Type**: MUST
**Testable**: Yes

When reading a pack, implementations MUST:
1. For each shard in `manifest.shard_list`:
   - Load shard from `index/{shard_id}.json`
   - Compute `entries_hash` using algorithm above
   - Compare computed hash to `manifest.shard_list[].entries_hash`
   - If mismatch: Mark shard as corrupted, optionally continue with warning
2. Report verification results to caller

**Rationale**: Detects corruption during transmission or storage.

**Verification**: Modify one character in shard file, verify hash mismatch detected.

---

### REQ-L2-012: Pack Hash via Sidecar

**Category**: Integrity
**Type**: MUST
**Testable**: Yes

The authoritative `pack_hash` MUST be distributed via a detached sidecar file:

**Sidecar filename**: `{packname}.meshpack.integrity`

> **Note**: The `.integrity` extension is used instead of `.sig` to avoid confusion with PGP/GPG detached signature files.

**Sidecar content** (JSON):
```json
{
  "pack_name": "library.meshpack",
  "pack_size_bytes": 104857600,
  "hash_algo": "sha256",
  "pack_hash": "sha256:a1b2c3d4...",
  "computed_at": "2026-01-16T12:00:00Z",
  "exclusions": ["mapping.db"],
  "signatures": []
}
```

**Generation sequence**:
1. Create complete archive (manifest contains placeholder `pack_hash`)
2. Compute hash of archive bytes
3. Write sidecar file with computed hash

**Verification sequence**:
1. Read sidecar file
2. Compute hash of archive bytes
3. Compare to `sidecar.pack_hash`
4. **MUST NOT** use `manifest.pack_hash` for verification (it's a reference only)

**Rationale**: Hash-in-file is impossible; sidecar solves chicken-and-egg problem.

**Verification**: 
1. Generate pack + sidecar
2. Verify sidecar hash matches recomputed hash
3. Modify archive, verify hash mismatch

---

### REQ-L2-013: Hash Algorithm Support

**Category**: Integrity
**Type**: MUST
**Testable**: Yes

Implementations MUST support these hash algorithms:

| Algorithm | Identifier | Output Size |
|-----------|------------|-------------|
| SHA-256 | `sha256` | 64 hex chars |
| SHA-512 | `sha512` | 128 hex chars |
| BLAKE3 | `blake3` | 64 hex chars (256-bit default) |

Implementations SHOULD default to `sha256` for maximum compatibility.

**Rationale**: SHA-256 is widely supported; BLAKE3 offers better performance for large files.

**Verification**: Generate pack with each algorithm, verify hash format correct.

---

## 3. Resource Embedding Requirements

### REQ-L2-020: Resource Folder Structure

**Category**: Resource
**Type**: MUST
**Testable**: Yes

When embedding resources, implementations MUST:
1. Create `resources/` folder in archive root
2. Name files as `{hash}.{extension}` where:
   - `{hash}` = Content hash **hex digits only** (no algorithm prefix) — algorithm is implicit from `manifest.hash_algo`. No colons in filenames for Windows compatibility.
   - `{extension}` = Original file extension (lowercase)
3. Include `resources/_README.md` documenting:
   - Hash algorithm used
   - File types included
   - Selection criteria

**Rationale**: Content-addressed naming enables deduplication and integrity verification.

**Verification**: 
1. Embed 3 files with same content → should produce single resource
2. Verify `resource_ref` in entry matches actual filename

---

### REQ-L2-021: Resource Linking in Entries

**Category**: Resource
**Type**: MUST
**Testable**: Yes

When a file is embedded in `resources/`, its `FileEntry` MUST include:

| Field | Value |
|-------|-------|
| `resource_ref` | Filename in resources (e.g., `e3b0c44298fc1c149...def.jpg`) — hex hash + extension, NO algo prefix |
| `resource_hash` | Hash of embedded resource bytes (with algo prefix, e.g., `sha256:abc123...`) |
| `resource_size_bytes` | Size of embedded resource |

The `hash` field continues to reference the **original source file hash** (may differ if resource is transformed, e.g., compressed thumbnail).

**Rationale**: Enables integrity verification of embedded content separately from source.

**Verification**: 
1. Embed file
2. Verify `resource_ref` points to existing file in `resources/`
3. Verify `resource_hash` matches computed hash of embedded file

---

### REQ-L2-022: Resource Selection Policy

**Category**: Resource
**Type**: SHOULD
**Testable**: No

Implementations SHOULD embed resources based on configurable criteria:

**Recommended defaults**:
- Maximum individual file size: 512 KB
- Allowed types: Images (`.jpg`, `.png`, `.gif`, `.webp`), Documents (`.txt`, `.md`, `.pdf`)
- Exclude: 3D model files (to keep pack portable)

**Configuration in manifest** (via `generation.config`):
```json
{
  "generation": {
    "config": {
      "include_thumbnails": true,
      "max_resource_size_bytes": 524288,
      "resource_patterns": ["*.jpg", "*.png", "LICENSE*", "README*"]
    }
  }
}
```

**Rationale**: Balance portability with self-contained previews.

---

## 4. Platform Handling Requirements

### REQ-L2-030: Path Conversion

**Category**: Platform
**Type**: MUST
**Testable**: Yes

When generating from Windows source:
1. Convert backslashes (`\`) to forward slashes (`/`) in `path`
2. Strip drive letters (e.g., `C:\` → paths relative to workspace root)
3. Preserve `platform_info.path_separator = "\\"` for reference

When reading on Windows:
1. Convert forward slashes to native path separator when extracting
2. Handle potential case conflicts using `platform_info.is_case_sensitive`

**Rationale**: Cross-platform portability.

**Verification**: Generate on Windows, read on Linux, verify paths work.

---

### REQ-L2-031: Case Sensitivity Handling

**Category**: Platform
**Type**: SHOULD
**Testable**: Yes

When importing to a case-insensitive filesystem from a case-sensitive source:
1. Detect potential collisions (e.g., `Model.stl` vs `model.stl`)
2. Report warnings for detected collisions
3. Apply consistent resolution (e.g., keep first occurrence)

**Rationale**: Prevent silent data loss.

**Verification**: 
1. Create pack on case-sensitive FS with `A.stl` and `a.stl`
2. Import on case-insensitive FS
3. Verify warning generated

---

## 5. Generation Metadata Requirements

### REQ-L2-040: Generator Provenance

**Category**: Manifest
**Type**: SHOULD
**Testable**: Yes

Implementations SHOULD populate `manifest.generation`:

```json
{
  "generation": {
    "generator": "meshsync-local-agent@1.4.0",
    "config": {
      "include_thumbnails": true,
      "max_resource_size_bytes": 524288
    },
    "partial": false,
    "base_pack_hash": null
  }
}
```

| Field | Description |
|-------|-------------|
| `generator` | Tool name and version |
| `config` | Configuration used for generation |
| `partial` | `true` if delta pack (see L3) |
| `base_pack_hash` | Reference to base pack for deltas |

**Rationale**: Enables debugging and reproducibility.

**Verification**: Generate pack, verify `generation` populated.

---

### REQ-L2-041: Import Policy Declaration

**Category**: Manifest
**Type**: MAY
**Testable**: Yes

Implementations MAY include `import_policy` to guide receivers:

```json
{
  "import_policy": {
    "id_conflict": "fail",         // "fail" | "skip" | "replace"
    "metamodel_merge": "strict",   // "strict" | "merge" | "replace"
    "strip_creator_info": false
  }
}
```

**Rationale**: Enables controlled import behavior for ecosystem integration.

---

## 6. 3D Model Specific Requirements

### REQ-L2-050: Model File Detection

**Category**: 3D Models
**Type**: SHOULD
**Testable**: Yes

Implementations SHOULD detect and populate `mime_type` for common 3D formats:

| Extension | MIME Type |
|-----------|-----------|
| `.stl` | `model/stl` |
| `.obj` | `model/obj` |
| `.fbx` | `model/fbx` |
| `.gltf` | `model/gltf+json` |
| `.glb` | `model/gltf-binary` |
| `.3mf` | `model/3mf` |
| `.step`, `.stp` | `model/step` |
| `.iges`, `.igs` | `model/iges` |
| `.ply` | `model/ply` |

**Rationale**: Enables viewers to select appropriate renderers.

**Verification**: Generate pack with various model files, verify `mime_type` correct.

---

### REQ-L2-051: Bounding Box Calculation

**Category**: 3D Models
**Type**: MAY
**Testable**: Yes

For detected 3D model files, implementations MAY compute and populate:

```json
{
  "bounding_box": {
    "min": [-10.5, 0, -5.2],
    "max": [10.5, 20.3, 5.2]
  },
  "units": "mm"
}
```

**Rationale**: Enables quick size assessment without parsing model.

---

### REQ-L2-052: Unit Detection

**Category**: 3D Models
**Type**: MAY
**Testable**: Yes

For formats that embed units (3MF, STEP), implementations MAY extract and populate:

| Units | `units` Value |
|-------|---------------|
| Millimeters | `mm` |
| Centimeters | `cm` |
| Meters | `m` |
| Inches | `in` |
| Feet | `ft` |
| Unknown/Dimensionless | `unitless` |

**Rationale**: Enables accurate scaling in viewers.

---

## 7. Exclusion Requirements

### REQ-L2-060: mapping.db Exclusion

**Category**: Integrity
**Type**: MUST
**Testable**: Yes

The optional `mapping.db` SQLite file:
1. MUST be excluded from `pack_hash` computation
2. MUST NOT be included in shard `entries`
3. MAY be included in archive for consumer convenience
4. Consumers SHOULD regenerate from shards if present

**Rationale**: SQLite files are non-deterministic (page ordering varies).

**Verification**: 
1. Generate pack with `mapping.db`
2. Delete and regenerate `mapping.db`
3. Verify `pack_hash` unchanged

---

## Summary: L2 Compliance Checklist

| ID | Requirement | Type | Status |
|----|-------------|------|--------|
| **L1 Prerequisites** | All L1 MUST requirements | MUST | ☐ |
| REQ-L2-001 | Valid Archive Creation | MUST | ☐ |
| REQ-L2-002 | Manifest Generation | MUST | ☐ |
| REQ-L2-003 | Deterministic Sharding | MUST | ☐ |
| REQ-L2-004 | FileEntry Generation | MUST | ☐ |
| REQ-L2-010 | Shard Hash Computation | MUST | ☐ |
| REQ-L2-011 | Shard Hash Verification | MUST | ☐ |
| REQ-L2-012 | Pack Hash via Sidecar | MUST | ☐ |
| REQ-L2-013 | Hash Algorithm Support | MUST | ☐ |
| REQ-L2-020 | Resource Folder Structure | MUST | ☐ |
| REQ-L2-021 | Resource Linking in Entries | MUST | ☐ |
| REQ-L2-022 | Resource Selection Policy | SHOULD | ☐ |
| REQ-L2-030 | Path Conversion | MUST | ☐ |
| REQ-L2-031 | Case Sensitivity Handling | SHOULD | ☐ |
| REQ-L2-040 | Generator Provenance | SHOULD | ☐ |
| REQ-L2-041 | Import Policy Declaration | MAY | ☐ |
| REQ-L2-050 | Model File Detection | SHOULD | ☐ |
| REQ-L2-051 | Bounding Box Calculation | MAY | ☐ |
| REQ-L2-052 | Unit Detection | MAY | ☐ |
| REQ-L2-060 | mapping.db Exclusion | MUST | ☐ |

**Minimum for L2 Compliance**: All L1 MUST + All L2 MUST requirements (20 total)
