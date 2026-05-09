---
id: MPACK-DEF-001
tags:
  - specification
  - meshpack
  - data-interchange
title: 'MeshPack (.meshpack) Standard Definition'
status: draft
created_date: 2026-01-06
updated_date: 2026-02-16
author: Jordane Masson
business_value: high
risk_level: medium
effort_estimate: M
---

# MeshPack (.meshpack) Standard Definition

## 1. Introduction

The `.meshpack` format is a standardized container format used within the Mesh-Sync ecosystem to represent a snapshot of a file system or a collection of 3D assets. It serves as an intermediate data structure for synchronization, allowing the decoupling of the "Scanning" phase from the "Processing" phase.

This format is designed to be:
- **Portable**: Can be moved across systems (with platform metadata).
- **Scalable**: Supports massive file counts via index sharding.
- **Verifiable**: Includes hashing for integrity and signatures for authenticity.
- **Extensible**: Designed with forward-compatibility for future versioning.

### 1.1 Notation Conventions

The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHOULD", "SHOULD NOT", "RECOMMENDED", "MAY", and "OPTIONAL" in this document are to be interpreted as described in [RFC 2119](https://www.rfc-editor.org/rfc/rfc2119).

### 1.2 Scope

This specification defines two layers:
1. **MeshPack Core** (Conformance Levels L1 + L2): The universal file format — any tool can implement this without knowledge of MeshSync.
2. **MeshPack MeshSync Profile** (Conformance Level L3): MeshSync ecosystem-specific extensions, identity resolution, and worker pipeline integration.

## 2. File Format

Physically, a `.meshpack` file is a **ZIP archive** with a custom extension.

### 2.1 Compression Policy
- **REQUIRED**: All entries MUST use **DEFLATE** compression (ZIP method 8) or **STORE** (method 0) for maximum compatibility.
- **PROHIBITED**: LZMA, Zstd, BZip2, or other compression methods that require extended ZIP features.
- **Rationale**: Ensures every ZIP library can read MeshPack files without special decompressor support.

### 2.2 ZIP Entry Ordering
- The `manifest.json` entry MUST be the **first** entry in the ZIP central directory.
- **Rationale**: Enables streaming readers to parse the manifest without seeking through arbitrarily large archives.

### 2.3 Wire Format Requirements
- All JSON files within the archive MUST be encoded in **UTF-8 without BOM**.
- `_README.md` files MUST use **LF** line endings (not CRLF).
- Archives larger than 4 GB or with more than 65,535 entries MUST use **ZIP64 extensions**.

### 2.4 Extension
- Primary: `.meshpack`
- Alternative: `.mpack`

### 2.5 Media Type
- MIME type: `application/vnd.meshsync.meshpack+zip`
- Structured syntax suffix: `+zip` per [RFC 6839](https://www.rfc-editor.org/rfc/rfc6839)
- IANA registration template: [`definition/iana-media-type-registration.md`](iana-media-type-registration.md)
- Implementations SHOULD register this type with the operating system for file association.

### 2.6 Future Consideration: PTAR Format

> **Note for v2.0 evaluation**: The [PTAR format](https://www.plakar.io/posts/2025-06-27/it-doesnt-make-sense-to-wrap-modern-data-in-a-1979-format-introducing-.ptar/) from [Plakar](https://github.com/PlakarKorp/plakar) addresses several limitations of ZIP for sync-heavy workloads:
>
> | Capability | ZIP | PTAR |
> |------------|-----|------|
> | Content-addressed deduplication | No | Yes |
> | Native encryption (audited) | No | Yes |
> | Streaming writes | No | Yes |
> | Built-in tamper evidence (MAC) | No | Yes |
> | Multiple snapshots/versions | No | Yes |
> | Browser/WASM support | Yes | No |
>
> **Why ZIP for v1.0**: Browser compatibility (JSZip), universal tooling, industry precedent (3MF, XLSX, JAR).

## 3. Internal Structure

A valid `.meshpack` archive MUST contain the following structure:

```
meshpack-archive  = manifest-entry index-dir [resources-dir] [mapping-db]
manifest-entry    = "manifest.json"         ; MUST be first ZIP entry
index-dir         = "index/" readme-file 1*shard-file
shard-file        = "index/part-" 5DIGIT ".json"  ; 1-based, zero-padded
resources-dir     = "resources/" readme-file *resource-file
resource-file     = "resources/" hex-hash "." extension
readme-file       = "_README.md"
mapping-db        = "mapping.db"            ; OPTIONAL cache, included in archive hash if present
```

Expanded layout:

```
root/
├── manifest.json       # (Required) Root metadata and platform context
├── _README.md          # (Required) Explanation of content
├── index/              # (Required) Directory containing content shards
│   ├── _README.md
│   ├── part-00001.json
│   ├── part-00002.json
│   └── ...
├── resources/          # (Optional) Attached binaries/images
│   ├── _README.md
│   ├── <hex-hash>.jpg  # Named WITHOUT algo prefix for Windows compat
│   └── ...
└── mapping.db          # (Optional) SQLite cache; included in whole-archive hashing if present
```

Each directory contains a `_README.md` file (underscore prefix forces sort-first ordering) describing its purpose, ensuring human readability when extracted.

### 3.1 Note on `mapping.db`

The optional `mapping.db` SQLite file is a **local acceleration cache** for consumers. Because MeshPack 2.0 sidecars hash the complete archive bytes, `mapping.db` is included in `pack_hash` if present. Producers that need reproducible package bytes SHOULD omit `mapping.db` and let consumers regenerate it from shards.

**Rules**:
- Generators MAY include `mapping.db` for convenience
- Verifiers MUST include every archive byte in `pack_hash` computation
- Consumers SHOULD regenerate `mapping.db` from shards if integrity is critical

> **Implementation status**: As of v1.1, no standard tooling generates or
> consumes `mapping.db`. Implementers are NOT required to support it.
> This feature MAY be promoted to a formal extension or removed in a future
> major version.

If implementing, use the following minimal SQLite schema:

```sql
CREATE TABLE file_index (
    path         TEXT PRIMARY KEY,
    shard_id     TEXT NOT NULL,
    entry_index  INTEGER NOT NULL
);
```

---

## 4. Manifest Schema (`manifest.json`)

The `manifest.json` file is the entry point for the package. It defines the ownership, global context, and processing rules.

### 4.1 JSON Schema

```json
{
  "format_version": "1.0.0",
  "created_at": "2026-01-06T12:00:00Z",
  "workspace_id": "uuid-string",
  "ids": [
    { "ns": "meshsync:workspace", "id": "uuid-string" }
  ],
  "creator_info": {
     "name": "Jordane Masson",
     "email": "contact@meshsync.net"
  },
  "license": "Proprietary",
  "platform_info": {
    "os": "linux",
    "path_separator": "/",
    "is_case_sensitive": true
  },
  "index_summary": {
    "total_files": 15420,
    "total_shards": 2,
    "total_size_bytes": 104857600
  },
  "shard_list": [
    { "id": "part-00001", "entries_count": 10000, "entries_hash": "sha256:..." }
  ],
  "hash_algo": "sha256",
  "pack_hash": "sha256:<hash-of-zip>",
  "signatures": [
    { "alg": "ed25519", "public_key": "<base64>", "signature": "<base64>" }
  ],
  "generation": {
    "generator": "plugin-storage-localfilesystem@1.4.0",
    "config": {
      "include_thumbnails": true,
      "max_resource_size_bytes": 524288
    },
    "partial": false,
    "base_pack_hash": null
  },
  "import_policy": {
    "id_conflict": "fail",
    "metamodel_merge": "strict",
    "strip_creator_info": false
  },
  "extensions": {}
}
```

### 4.2 Fields Description

*   **`format_version`** (REQUIRED): Semantic versioning of the `.meshpack` format. Parsers MUST check the major version for compatibility.
*   **`created_at`** (REQUIRED): ISO 8601 UTC timestamp of pack creation.
*   **`creator_info`** (REQUIRED): Details about the entity that generated this pack. **PII Note**: The `email` field may contain personal data. Generators SHOULD allow anonymizing or hashing this field for public distribution.
*   **`license`**: License applicable to the files *referenced* in this pack. SHOULD use [SPDX expression syntax](https://spdx.github.io/spdx-spec/v2.3/SPDX-license-expressions/) (e.g., `MIT`, `Apache-2.0`, `CC-BY-4.0`). Use `Proprietary` for non-open-source content, `LicenseRef-<id>` for custom licenses, or `null` if unknown.
*   **`workspace_id`**: **Scope Context**. If present, MUST match `ids[ns="meshsync:workspace"].id`. Required for MeshSync ecosystem (L3), optional for standalone use (may be `null`).
*   **`ids`**: Namespaced identifiers (`ns` + `id`) so different systems can recognize the workspace/library.
*   **`platform_info`** (REQUIRED): CRITICAL for cross-platform processing.
    *   **`os`**: Source operating system (`linux` | `windows` | `darwin` | `unknown`).
    *   **`path_separator`**: Separator used in the *original* file system (for reference only; paths in shards always use `/`).
    *   **`is_case_sensitive`**: Hints if `Logo.png` and `logo.png` should be treated as distinct files.
*   **`index_summary`** (REQUIRED): Aggregate statistics. `total_files` MUST equal the sum of all `shard_list[].entries_count`.
*   **`shard_list`** (REQUIRED): Canonical ordering of shards with per-shard hashes for deterministic loading. Shard IDs use 5-digit zero-padding (`part-00001`).
*   **`hash_algo`** (REQUIRED): One of `sha256`, `sha512`, `blake3`. Applies to `pack_hash`, `entries_hash`, file hashes, and resource hashes. Implementations SHOULD default to `sha256` for maximum compatibility.
*   **`pack_hash`**: **REFERENCE value only**. See §8 for the sidecar-based verification model. Populated after archive creation for informational purposes. Verifiers MUST NOT use this value for integrity checks.
*   **`signatures`**: Informational signatures in manifest; authoritative signatures are in the sidecar (§8.2).
*   **`generation`**: Provenance metadata.
    *   **`generator`**: Tool name and version.
    *   **`config`**: Configuration flags used during generation.
    *   **`partial`**: `true` for delta packs (see §11).
    *   **`base_pack_hash`**: Required when `partial=true`; the base pack this delta applies to.
    *   **`metamodel_filter`** (v1.1+): Export filter for metamodel context. See schema for `mode`, `metamodel_ids`, `collapse_roles`.
*   **`import_policy`**: Guidance for conflict handling when importing into another backend.
    *   **`id_conflict`**: `fail` | `skip` | `overwrite`
    *   **`metamodel_merge`**: `strict` | `merge` | `replace`
    *   **`strip_creator_info`**: If `true`, importer should remove creator_info.
*   **`extensions`**: A dictionary for storing non-standard metadata. Keys MUST use namespace prefixes (see EXTENSIONS.md).

---

## 5. Index Sharding (`index/*.json`)

To handle libraries with hundreds of thousands of files without loading a monolithic JSON into memory, the file list is split into multiple shards.

### 5.1 Sharding Strategy
- Files are distributed across `part-XXXXX.json` files (1-based, **5-digit zero-padded**).
- Shards are **Objects**, not Arrays, to allow for shard-specific metadata.
- The consumer MUST read ALL shards to build a complete view of the package.
- **Deterministic ordering**: entries are sorted by `path` (UTF-8, byte order) before sharding.
- **Shard limits**: MUST NOT exceed **10,000 entries** per shard. SHOULD NOT exceed 5 MB per shard.
- Each shard records `entries_count` and `entries_hash` (hash computed per §8.5).

### 5.2 Shard JSON Schema

```json
{
  "shard_id": "part-00001",
  "format_version": "1.0.0",
  "entries_count": 10000,
  "entries_hash": "sha256:...",
  "entries": [
      {
        "path": "vehicles/cars/sports_car_v2.stl",
        "original_name": "Sports Car V2.stl",
        "size_bytes": 500021,
        "hash": "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        "modified_at": "2025-12-01T09:30:00Z",
        "ids": [
          { "ns": "meshsync:model", "id": "uuid-string" },
          { "ns": "thingiverse:model", "id": "12345" }
        ],
        "resource_ref": null,
        "resource_hash": null,
        "resource_size_bytes": null,
        "attributes": {
            "is_symlink": false,
            "is_hidden": false
        },
        "metamodels": [
          { "id": "uuid-metamodel-1", "role": "canonical" },
          { "id": "uuid-metamodel-2", "role": "canonical" }
        ],
        "assembly": {
            "assembly_id": "uuid-string",
            "parent_assembly_id": null,
            "role": "body",
            "transform": { "matrix": [1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1] }
        },
        "mime_type": "model/stl",
        "units": "mm",
        "up_axis": "+Z",
        "bounding_box": { "min": [0,0,0], "max": [10,5,3] },
        "preview_ref": "abc123def456.jpg",
        "extensions": {}
      }
  ]
}
```

### 5.3 FileEntry Definition

*   **`path`** (REQUIRED): **Relative path** from the root of the scanned directory. MUST use forward slashes (`/`). MUST NOT contain `..`, absolute paths, or drive letters. MUST NOT exceed **1024 characters**.
*   **`original_name`** (REQUIRED): Original filename preserving case.
*   **`size_bytes`** (REQUIRED): File size from filesystem.
*   **`hash`** (REQUIRED): Content hash of the **original file on the source filesystem** using manifest's `hash_algo`. Format: `{algo}:{hex}`.
*   **`modified_at`** (REQUIRED): ISO 8601 timestamp of last modification.
*   **`ids`**: Namespaced identifiers for cross-system reconciliation (e.g., `meshsync:model`, `thingiverse:thing`).
*   **`metamodels`** (v1.1+): Array of metamodel memberships. A file CAN belong to **multiple metamodels simultaneously**. Each entry specifies `id` (UUID) and `role` (`canonical` | `variant` | `accessory` | `doc`). Supersedes the deprecated single fields when present.
*   **`metamodel_id` / `metamodel_role`** (DEPRECATED): Legacy single-metamodel fields for v1.0 compatibility. If `metamodels[]` is present, these are ignored.
*   **`assembly`**: Optional assembly graph info with transforms.
    *   **Transform Matrix Convention**: 4×4 homogeneous transformation matrix in **column-major order** (OpenGL/glTF convention). All transforms use the **canonical coordinate system: right-handed, +Y up**. If the source file uses a different `up_axis` (e.g., +Z for STL), the transform MUST be pre-converted to canonical +Y up. Scale is in the units specified by the entry's `units` field. Transform is **relative to parent assembly**, not absolute world space.
*   **`operation`**: Delta pack operation type (`add` | `modify` | `delete`). Only present when `manifest.generation.partial=true`. `delete` entries MUST have `size_bytes=0` and `hash` set to all zeros. Supersedes the deprecated `extensions._deleted` marker.
*   **`mime_type`**: MIME type of the file (e.g., `model/stl`, `model/gltf-binary`).
*   **`units`**: Measurement units (`mm` | `cm` | `m` | `in` | `ft` | `unitless`).
*   **`up_axis`**: Source model's up-axis orientation (`+Z` | `-Z` | `+Y` | `-Y`).
*   **`bounding_box`**: Axis-aligned bounding box in the **source** file's coordinate system. Units are inherited from the sibling `units` field.
*   **`resource_ref`**: Reference to embedded file in `resources/` folder. Format: `{hex_hash}.{ext}` (**no algorithm prefix** — the algorithm is implicit from `manifest.hash_algo`). This is a filename only, not a path; it MUST NOT contain slashes, backslashes, colons, drive letters, UNC prefixes, or `..` traversal segments.
*   **`resource_hash` / `resource_size_bytes`**: Integrity for embedded blobs. `hash` refers to the **original file**; `resource_hash` refers to the **embedded blob**. These SHOULD be identical unless the resource is a derivative (e.g., compressed thumbnail).
*   **`preview_ref`**: Reference to preview thumbnail in `resources/` (format: `{hex_hash}.{ext}`).
*   **`extensions`**: Allows tagging files with extra data. Keys MUST use namespace prefixes (see EXTENSIONS.md).

---

## 6. Resources Folder (`resources/`)

If configured, the `.meshpack` may contain actual file content, not just metadata.

### 6.1 Flattening Strategy
*   All files in `resources/` are **flattened** (no subdirectories).
*   **Naming Convention**: `<HEX-HASH>.<EXTENSION>` (e.g., `e3b0c44298fc1c149...855.jpg`). Note: **NO algorithm prefix** in the filename — the algorithm is implicit from `manifest.hash_algo`. Resource names are flat filenames only; path separators and traversal segments are invalid.
*   **Linking**: The `FileEntry` links to this file via the `resource_ref` field.

### 6.2 Usage Rules
*   SHOULD only be used for small files (thumbnails, licenses, READMEs) to keep the `.meshpack` portable. RECOMMENDED maximum individual file size: **512 KB**. RECOMMENDED total `resources/` budget: **50 MB**.
*   The `_README.md` in this folder MUST explain what filtering logic was used to decide which files to include.
*   Every embedded file MUST have its `resource_hash` and `resource_size_bytes` captured in the corresponding `FileEntry`.

---

## 7. Documentation Requirements

To ensure the `.meshpack` is self-describing, the following `_README.md` files are mandatory:

> **Note**: Files are prefixed with `_` to force sort-first ordering in file browsers and `ls` output.

1.  **`/_README.md`**:
    *   "This MeshPack was generated by [Creator] on [Date]. It contains metadata for [WorkspaceID]."
    *   Instructions on how to parse the `manifest.json`.

2.  **`/index/_README.md`**:
    *   "This directory contains [N] JSON shards defining the file structure."
    *   "Entries are distributed for performance."

3.  **`/resources/_README.md`** (If folder exists):
    *   "This directory contains flattened file content."
    *   "Files are named by their hex hash (algorithm: [sha256|sha512|blake3])."
    *   "Included types: [.jpg, .png, .txt]."

## 8. Integrity & Authentication

### 8.1 The Pack Hash Problem

Computing a hash of an archive and storing it *inside* the archive is logically impossible (chicken-and-egg). MeshPack solves this with a **two-file approach**:

| File | Contents |
|------|----------|
| `library.meshpack` | The archive itself (manifest contains placeholder `pack_hash`) |
| `library.meshpack.integrity` | Detached sidecar with authoritative hash and signatures |

### 8.2 Sidecar File Format (`*.meshpack.integrity`)

> **Note**: The `.integrity` extension is used instead of `.sig` to avoid confusion with PGP/GPG detached signature files (which use `.sig` for binary output).

```json
{
  "pack_name": "library.meshpack",
  "pack_size_bytes": 104857600,
  "hash_algo": "sha256",
  "pack_hash": "sha256:a1b2c3d4...",
  "computed_at": "2026-01-16T12:00:00Z",
  "signatures": [
    {
      "alg": "ed25519",
      "public_key": "base64...",
      "signature": "base64...",
      "signer_id": "agent@meshsync.net",
      "signed_at": "2026-01-16T12:00:01Z"
    }
  ]
}
```

### 8.3 Verification Algorithm

1. Read sidecar file (`library.meshpack.integrity`)
2. Quick sanity: compare `pack_size_bytes` against actual archive size
3. Compute hash of the complete `library.meshpack` archive bytes
4. Compare computed hash against `pack_hash` in the **sidecar** (NOT the embedded manifest value)
5. If signatures present, verify each against `pack_hash`
6. For each shard: compute hash of canonical JSON of sorted `entries` array, compare against `shard_list[].entries_hash`

**IMPORTANT**: Verifiers MUST use the sidecar for `pack_hash` verification. The `manifest.pack_hash` value is informational only.

### 8.4 Whole-Archive Hashing

MeshPack 2.0 uses whole-archive hashing for sidecars: every byte of the `.meshpack` / `.mpack` file is part of `pack_hash`. Optional acceleration files such as `mapping.db` are therefore integrity-protected if present, but they may make reproducible builds harder. Producers SHOULD omit non-deterministic cache files from public release artifacts.

### 8.5 Shard Hash Computation (Canonical JSON)

The `entries_hash` for each shard is computed as:

```
entries_hash = hash(canonical_json(sorted(entries)))
```

Where canonical JSON follows [RFC 8785 (JSON Canonicalization Scheme)](https://www.rfc-editor.org/rfc/rfc8785):
1. `sorted(entries)` = entries sorted by `path` (UTF-8 byte order)
2. `canonical_json()` = JCS canonicalization: keys sorted, no whitespace, UTF-8, numbers per RFC 8259 §6 (no NaN/Infinity, integers without decimal point)
3. `hash()` = Algorithm from `manifest.hash_algo`
4. Format: `{algorithm}:{lowercase_hex}` (e.g., `sha256:a1b2c3...`)

### 8.6 Additional Integrity

* **Shard hashes**: Each shard exposes `entries_hash`; manifest lists them in `shard_list` for cross-verification.
* **Encryption**: Deferred to v1.1. When specified, it will be an official extension (`meshsync_encryption`) with algorithm, recipients, and encrypted-content scope. **Do not mix encrypted resources with plaintext indices.**

## 9. Usage Scenarios

### 9.1. Local Storage Agent
The `plugin-storage-localfilesystem` generates `.meshpack` files during its "Scan" phase.
1.  **Scan**: Walk directory, calculate hashes.
2.  **Pack**: Stream entries into `index/part-XXXXX.json` shards inside the ZIP. `manifest.json` is written first.
3.  **Embed**: If config `include_thumbnails=true`, copy relevant files to `resources/` and link in `FileEntry`.
4.  **Sidecar**: Compute `pack_hash` of finalized archive, write `.meshpack.integrity` file.

### 9.2. Heuristic Analysis
A separate "Heuristic Engine" can mount this package. Because it is read-only and structured:
- It can process the file structure without needing physical access to the user's hard drive.
- It enables "Remote Analysis" where the user only uploads the structure (the `.meshpack` manifest), not the actual 500GB of heavy STL files.

### 9.3. Backend Export / Import
- Exporters SHOULD populate `ids` with `meshsync:*` namespaces, metamodel/assembly fields, and sign `pack_hash`.
- Importers SHOULD verify `pack_hash` via sidecar, `entries_hash` per shard, and signatures before ingesting.
- Conflict handling SHOULD respect `import_policy`:
  - `id_conflict`: `fail` | `skip` | `overwrite`
  - `metamodel_merge`: `strict` | `merge` | `replace`
  - `strip_creator_info`: boolean

## 10. Security & Privacy

*   **Metadata Leakage**: Users must understand that `index/` reveals their folder names and hierarchy.
*   **Creator Info**: The `creator_info` field allows tracing the source of the package but may contain PII (email). Generators SHOULD allow:
    - Hashing the email (e.g., `sha256:abc123...@redacted`)
    - Omitting the email entirely
    - Using a pseudonym instead of real name
*   **Safe Parsing**: Consumers of `.meshpack` MUST validate `format_version` before parsing to avoid incompatible schema structure issues.
*   **Path Traversal**: All `path` values MUST be validated to reject `..`, absolute paths, and drive letters (see REQ-L1-013).

---

## 11. Delta / Incremental Updates

For synchronization scenarios, `.meshpack` supports **delta packs** that reference a base pack.

### 11.1 Delta Pack Structure

A delta pack MUST set `generation.partial = true` and `generation.base_pack_hash` to the hash of the base pack.

### 11.2 Delta Entry Semantics

Each `FileEntry` in a delta pack includes an explicit `operation` field:

| Operation | `operation` value | Representation |
|-----------|-------------------|----------------|
| **New file** | `"add"` | Full entry with all fields |
| **Modified file** | `"modify"` | Full entry with updated `hash` |
| **Deleted file** | `"delete"` | Entry with `size_bytes=0`, hash all zeros |
| **Unchanged** | *(not present)* | Entry NOT present (inherited from base) |

> **DEPRECATED**: The `extensions._deleted: true` marker from v1.0 is superseded by `operation: "delete"`. Implementations SHOULD accept both for backwards compatibility.

### 11.3 Merge Algorithm

1. Load base pack entries into a map keyed by `path`
2. For each entry in delta pack:
   - If `operation == "delete"`: Remove from map
   - Otherwise: Upsert into map (add or replace)
3. Result map represents the merged state

### 11.4 Constraints

- Delta packs SHOULD NOT contain `resources/` for deleted files
- A delta pack without a resolvable `base_pack_hash` is **invalid**
- Chains of deltas (delta-of-delta) are NOT supported in v1.0; flatten before distribution

---

## 12. 3D Asset Metadata (Extended)

For 3D model entries, the following optional fields provide richer context. All are defined as official extensions with versioned envelopes (see EXTENSIONS.md).

### 12.1 Geometry Metadata

Extension: `meshsync_geometry.v1`

```json
"extensions": {
  "meshsync_geometry": {
    "v1": {
      "vertex_count": 15420,
      "face_count": 30000,
      "edge_count": 45000,
      "is_manifold": true,
      "is_watertight": true,
      "has_normals": true,
      "has_uvs": false
    }
  }
}
```

### 12.2 Material & Texture Dependencies

Extension: `meshsync_dependencies.v1`

```json
"extensions": {
  "meshsync_dependencies": {
    "v1": {
      "materials": ["materials/chrome.mtl"],
      "textures": ["textures/diffuse.png", "textures/normal.png"]
    }
  }
}
```

### 12.3 Print-Specific Metadata

Extension: `meshsync_printability.v1`

```json
"extensions": {
  "meshsync_printability": {
    "v1": {
      "printability_score": 0.85,
      "is_watertight": true,
      "requires_supports": true,
      "optimal_orientation": [0, 0, 1],
      "bounding_box_mm": [120, 80, 45],
      "fdm": { "estimated_print_time_minutes": 240 },
      "sla": { "estimated_resin_ml": 25.5 }
    }
  }
}
```

### 12.4 AI-Enriched Content Metadata

Extension: `meshsync_content.v1`

```json
"extensions": {
  "meshsync_content": {
    "v1": {
      "ai_generated_title": "Articulated Dragon Figurine",
      "ai_generated_description": "A detailed...",
      "ai_generated_tags": ["dragon", "fantasy"],
      "language": "en",
      "ai_model_version": "gpt-4o-2024-01",
      "generation_timestamp": "2026-01-16T12:00:00Z"
    }
  }
}
```

---

## 13. Glossary

| Term | Definition |
|------|------------|
| **Metamodel** | A logical grouping of related files representing a single 3D asset (e.g., STL + textures + license) |
| **Assembly** | A hierarchical composition of metamodels with spatial transforms in canonical +Y up space |
| **Shard** | A JSON file containing a subset of the total file entries for memory efficiency |
| **Delta Pack** | An incremental `.meshpack` containing only changes relative to a base pack |
| **Sidecar** | A detached `.meshpack.integrity` file containing the authoritative pack hash and signatures |
| **Canonical JSON** | JSON serialized per RFC 8785 (JCS) for deterministic hashing |
| **SPDX** | Software Package Data Exchange — standard for license identifiers |

---

## 14. Conformance Levels

### Level 1: Minimal (Reader)
- Parse `manifest.json` and all shards
- Validate `format_version` compatibility
- Iterate file entries
- Reject path traversal attacks

### Level 2: Standard (Reader/Writer)
- All of Level 1
- Generate valid packs with `manifest.json` as first ZIP entry
- Verify `entries_hash` for each shard (RFC 8785 canonical JSON)
- Verify `pack_hash` via sidecar (NOT manifest value)
- Resource embedding with content-addressed naming (no algo prefix)
- 5-digit zero-padded shard IDs

### Level 3: Full (MeshSync Ecosystem)
- All of Level 2
- Support `ids` namespace resolution
- Support `assembly` transforms (canonical +Y up)
- Support delta pack merge with `operation` field
- Signature verification
- `workspace_id` consistency with `ids` array
- Import policy enforcement
