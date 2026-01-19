---
id: MPACK-DEF-001
tags:
  - specification
  - meshpack
  - data-interchange
title: 'MeshPack (.meshpack) Standard Definition'
status: draft
created_date: 2026-01-06
updated_date: 2026-01-16
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
- **Verifiable**: Includes hashing for integrity capability.
- **Extensible**: Designed with forward-compatibility for future versioning.

## 2. File Format

Physically, a `.meshpack` file is a **ZIP archive** with a custom extension.

### Compression Policy
- **REQUIRED**: All entries MUST use **DEFLATE** compression (ZIP method 8) or **STORE** (method 0) for maximum compatibility.
- **PROHIBITED**: LZMA, Zstd, BZip2, or other compression methods that require extended ZIP features.
- **Rationale**: Ensures every ZIP library can read MeshPack files without special decompressor support.

### Extension
- Primary: `.meshpack`
- Alternative: `.mpack`

### Future Consideration: PTAR Format

> **Note for v2.0 evaluation**: The [PTAR format](https://www.plakar.io/posts/2025-06-27/it-doesnt-make-sense-to-wrap-modern-data-in-a-1979-format-introducing-.ptar/) from [Plakar](https://github.com/PlakarKorp/plakar) addresses several limitations of ZIP for sync-heavy workloads:
>
> | Capability | ZIP | PTAR |
> |------------|-----|------|
> | Content-addressed deduplication | ❌ | ✅ |
> | Native encryption (audited) | ❌ | ✅ |
> | Streaming writes | ❌ | ✅ |
> | Built-in tamper evidence (MAC) | ❌ | ✅ |
> | Multiple snapshots/versions | ❌ | ✅ |
> | Browser/WASM support | ✅ | ❌ |
>
> **Why ZIP for v1.0**: Browser compatibility (JSZip), universal tooling, industry precedent (3MF, XLSX, JAR).
>
> **References for future analysis**:
> - PTAR specification: https://www.plakar.io/posts/2025-06-27/it-doesnt-make-sense-to-wrap-modern-data-in-a-1979-format-introducing-.ptar/
> - Kloset immutable store: https://www.plakar.io/posts/2025-04-29/kloset-the-immutable-data-store/
> - Kapsul (PTAR tooling): https://github.com/PlakarKorp/kapsul
> - CDC chunking: https://www.plakar.io/posts/2025-07-11/introducing-go-cdc-chunkers-chunk-and-deduplicate-everything/
> - Crypto audit: https://www.plakar.io/posts/2025-02-28/audit-of-plakar-cryptography/
>
> **Potential migration path**: Add `archive_profile: "ptar"` field in manifest for experimental streaming/sync profile, evaluate for v2.0 default if PTAR gains browser support.

## 3. Internal Structure

A valid `.meshpack` archive MUST contain the following structure:

```
root/
├── manifest.json       # (Required) Root metadata and platform context
├── _README.md          # (Required) Explanation of content
├── index/              # (Required) Directory containing content shards
│   ├── _README.md
│   ├── part-001.json
│   ├── part-002.json
│   └── ...
├── resources/          # (Optional) Attached binaries/images
│   ├── _README.md
│   ├── <hash>.jpg
│   └── ...
└── mapping.db          # (Optional, EXCLUDED from hashing) SQLite cache
```

Each directory contains a `_README.md` file describing its purpose and strict usage rules, ensuring human readability when extracted.

### Note on `mapping.db`

The optional `mapping.db` SQLite file is a **local acceleration cache** for consumers. It is explicitly **EXCLUDED from integrity verification** because:
- SQLite files are non-deterministic (page ordering, vacuum behavior varies by platform)
- Two generators producing identical logical content will create different binary files

**Rules**:
- Generators MAY include `mapping.db` for convenience
- Verifiers MUST NOT include `mapping.db` in `pack_hash` computation
- Consumers SHOULD regenerate `mapping.db` from shards if integrity is critical

---

## 4. Manifest Schema (`manifest.json`)

The `manifest.json` file is the entry point for the package. It defines the ownership, global context, and processing rules.

### JSON Schema

```json
{
  "format_version": "1.0.0", // SemVer of the .meshpack specification
  "created_at": "2026-01-06T12:00:00Z",
  "workspace_id": "uuid-string", // The workspace this snapshot belongs to
  "ids": [                      // Namespaced identifiers for portability
    { "ns": "meshsync:workspace", "id": "uuid-string" }
  ],
  "creator_info": {
     "name": "Jordane Masson",
     "email": "contact@meshsync.net"
  },
  "license": "Proprietary", // License of the CONTENT, not the format
  "platform_info": {
    "os": "linux",              // "linux" | "windows" | "darwin"
    "path_separator": "/",      // "/" or "\\"
    "is_case_sensitive": true   // boolean
  },
  "index_summary": {
    "total_files": 15420,
    "total_shards": 2,
    "total_size_bytes": 104857600
  },
  "shard_list": [
    { "id": "part-00001.json", "entries_count": 10000, "entries_hash": "sha256:..." }
  ],
  "hash_algo": "sha256",
  "pack_hash": "sha256:<hash-of-zip>",           // Integrity across the whole archive
  "signatures": [                                // Optional authentication over pack_hash
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
  "extensions": {               // Reserved for future use
     "custom_plugin_data": {}
  }
}
```

### Fields Description

*   **`format_version`**: Semantic versioning of the `.meshpack` format itself. Parsers should use this to determine compatibility.
*   **`creator_info`**: Details about the entity that generated this pack.
*   **`license`**: License applicable to the files *referenced* in this pack.
*   **`workspace_id`**: **Scope Context**. The Manifest holds the workspace identity so that individual file entries remain portable and context-agnostic.
*   **`ids`**: Namespaced identifiers (`ns` + `id`) so different systems can recognize the workspace/library.
*   **`platform_info`**: CRITICAL for cross-platform processing.
    *   **`os`**: Source operating system.
    *   **`path_separator`**: Separator used in the *original* file system (for reference only).
    *   **`is_case_sensitive`**: Hints if `Logo.png` and `logo.png` should be treated as distinct files.
*   **`shard_list`**: Canonical ordering of shards with per-shard hashes for deterministic loading.
*   **`hash_algo` / `pack_hash`**: Required for integrity verification. **Important**: `pack_hash` is computed over the finalized archive bytes and MUST be distributed via a **detached sidecar file** (`<name>.meshpack.sig`) or transmitted out-of-band. The `pack_hash` field in `manifest.json` serves as a **placeholder** that is populated AFTER archive creation for reference purposes only. Verifiers MUST use the sidecar signature, not the embedded value.
*   **`signatures`**: Optional signatures over `pack_hash` (e.g., ed25519) for authenticity.
*   **`generation`**: Provenance (generator version, config flags, partial/resume markers, optional `base_pack_hash` for deltas).
    *   **`metamodel_filter`** (v1.1+): Configurable export filter for metamodel context. Since models can belong to **multiple metamodels**, this specifies what was exported:
        *   `mode: "all"` - Export all metamodel assignments (default)
        *   `mode: "single"` + `metamodel_ids: ["uuid"]` - Export in context of one metamodel
        *   `mode: "include"` / `mode: "exclude"` + `metamodel_ids: [...]` - Filter by list
        *   `collapse_roles: true` - When mode=single, use only the role from that metamodel
*   **`import_policy`**: Guidance for conflict handling when importing into another backend.
*   **`extensions`**: A dictionary for storing non-standard metadata without breaking strict schema validation.

---

## 5. Index Sharding (`index/*.json`)

To handle libraries with hundreds of thousands of files without loading a monolithic JSON into memory, the file list is split into multiple shards.

### Sharding Strategy
- Files are distributed across `part-XXXXX.json` files (1-based, zero-padded).
- Shards are **Objects**, not Arrays, to allow for shard-specific metadata.
- The consumer MUST read ALL shards to build a complete view of the package.
- **Deterministic ordering**: entries are sorted by `path` (UTF-8, byte order) before sharding.
- **Shard limits**: recommended max 10k entries or 5 MB per shard (whichever comes first).
- Each shard records `entries_count` and `entries_hash` (hash over the sorted `entries` array).

### Shard JSON Schema

```json
{
  "shard_id": "part-001",
  "format_version": "1.0.0",
  "creator_info": {             // DEPRECATED: For backwards compat only. Omit in new implementations.
     "name": "Jordane Masson"
  },
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
        "resource_ref": null,   // null or hash if included in resources/
        "resource_hash": null,  // hash of embedded blob, if present
        "resource_size_bytes": 2048,
        "attributes": {
            "is_symlink": false,
            "is_hidden": false
        },
        // 1:N metamodel support (v1.1+): use metamodels[] array
        "metamodels": [
          { "id": "uuid-metamodel-1", "role": "canonical" },
          { "id": "uuid-metamodel-2", "role": "canonical" }  // Same file, main in 2 kits
        ],
        // DEPRECATED: Single metamodel fields (v1.0 compatibility)
        "metamodel_id": "uuid-string",
        "metamodel_role": "canonical",
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
        "preview_ref": "sha256:...jpg",
        "extensions": {}        // Per-file extensibility
      },
      ...
  ] 
}
```

### FileEntry Definition
*   **`path`**: **Relative Path** from the root of the scanned directory. MUST NOT contain workspace ID or absolute system paths. MUST use forward slashes (`/`).
*   **`ids`**: Namespaced identifiers for cross-system reconciliation (e.g., `meshsync:model`, `meshsync:metamodel`, `thingiverse:model`).
*   **`metamodels`** (v1.1+): Array of metamodel memberships. A file CAN belong to **multiple metamodels simultaneously** (e.g., a generic wheel is `canonical` in both "Car Kit" and "Truck Kit"). Each entry specifies `id` and `role`. Supersedes the deprecated single fields when present.
*   **`metamodel_id` / `metamodel_role`** (DEPRECATED): Legacy single-metamodel fields for v1.0 compatibility. If `metamodels[]` is present, these are ignored.
*   **`assembly`**: Optional assembly graph info with transforms to render models in-place.
    *   **Transform Matrix Convention**: 4x4 homogeneous transformation matrix in **column-major order** (OpenGL/glTF convention). Coordinate system is **right-handed, +Y up**. Scale is in the units specified by the parent entry's `units` field. Transform is **relative to parent assembly**, not absolute world space.
*   **`mime_type`, `units`, `up_axis`, `bounding_box`, `preview_ref`**: Make assets renderable locally without additional context.
*   **`resource_ref`**: If the actual file content is included in the `.meshpack` (e.g. usage for thumbnails or small text files), this field contains the filename in the `resources/` folder (format: `<hash>.<ext>`).
*   **`resource_hash` / `resource_size_bytes`**: Integrity for embedded blobs. **Clarification**: `hash` refers to the content hash of the **original file on the source filesystem**. `resource_hash` refers to the hash of the **embedded blob in resources/**. These SHOULD be identical if the file was embedded without transformation. They MAY differ if the embedded resource is a derivative (e.g., compressed thumbnail).
*   **`extensions`**: Allows tagging files with extra data (e.g. "preview_generated": true) without altering the core schema.

---

## 6. Resources Folder (`resources/`)

If configured, the `.meshpack` may contain actual file content, not just metadata. 

### Flattening Strategy
*   To avoid directory depth issues and path collisions, all files in `resources/` are **flattened**.
*   **Naming Convention**: `<SHA256-HASH>.<EXTENSION>` (e.g., `e3b0c44...855.jpg`).
*   **Linking**: The `FileEntry` in the index links to this file via the `resource_ref` field (which stores the hash) or implicitly if the `hash` matches.

**Usage Rules**:
*   Should only be used for small files (thumbnails, licenses, READMEs) to keep the `.meshpack` portable.
*   The `_README.md` in this folder must explain exactly what filtering logic was used to decide which files to include.
*   Every embedded file must have its `hash` and `size_bytes` captured in the corresponding `FileEntry` (`resource_hash`, `resource_size_bytes`).

---

## 7. Documentation Requirements

To ensure the `.meshpack` is self-describing, the following `_README.md` files are mandatory:

1.  **`/_README.md`**:
    *   "This MeshPack was generated by [Creator] on [Date]. It contains metadata for [WorkspaceID]."
    *   Instructions on how to parse the `manifest.json`.

2.  **`/index/_README.md`**:
    *   "This directory contains [N] JSON shards defining the file structure."
    *   "Entries are distributed for performance."

3.  **`/resources/_README.md`** (If folder exists):
    *   "This directory contains flattened file content."
    *   "Files are named by their SHA-256 hash."
    *   "Included types: [.jpg, .png, .txt]."
    *   "Hash algorithm used: [sha256|sha512|blake3]."

## 8. Integrity & Authentication

### 8.1 The Pack Hash Problem

Computing a hash of an archive and storing it *inside* the archive is logically impossible (chicken-and-egg). MeshPack solves this with a **two-file approach**:

| File | Contents |
|------|----------|
| `library.meshpack` | The archive itself (manifest contains placeholder `pack_hash`) |
| `library.meshpack.sig` | Detached sidecar with authoritative hash and signatures |

### 8.2 Sidecar File Format (`*.meshpack.sig`)

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
      "signer_id": "agent@meshsync.net"
    }
  ]
}
```

### 8.3 Verification Algorithm

1. Compute hash of `library.meshpack` bytes using `hash_algo`
2. Compare against `pack_hash` in `.sig` file (NOT the embedded manifest value)
3. If signatures present, verify each against `pack_hash`
4. For each shard: compute hash of sorted `entries` array, compare against `shard_list[].entries_hash`

### 8.4 Hash Exclusions

The following MUST be excluded from `pack_hash` computation:
- `mapping.db` (non-deterministic SQLite)

### 8.5 Additional Integrity

* **Shard hashes**: Each shard exposes `entries_hash` over the sorted `entries` array; manifest lists them in `shard_list` for verification.
* **Encryption**: If used, record `encryption.alg` and `recipients`. Avoid mixing encrypted resources with plaintext indices.

## 9. Usage Scenarios

### 9.1. Local Storage Agent
The `plugin-storage-localfilesystem` generates `.meshpack` files during its "Scan" phase.
1.  **Scan**: Walk directory, calculate hashes.
2.  **Pack**: Stream entries into `index/part-XXX.json` object arrays inside the ZIP.
3.  **Embed**: If config `include_thumbnails=true`, copy relevant files to `resources/` and link in `FileEntry`.
4.  **Deploy**: The `.meshpack` file is ready.

### 9.2. Heuristic Analysis
A separate "Heuristic Engine" can mount this package. Because it is read-only and structured:
- It can process the file structure without needing physical access to the user's hard drive.
- It enables "Remote Analysis" where the user only uploads the structure (the `.meshpack` manifest), not the actual 500GB of heavy STL files.

### 9.3. Backend Export / Import
- Exporters SHOULD populate `ids` with `meshsync:*` namespaces, metamodel/assembly fields, and sign `pack_hash`.
- Importers SHOULD verify `pack_hash`, `entries_hash`, and signatures before ingesting.
- Conflict handling SHOULD respect `import_policy` (`id_conflict`, `metamodel_merge`, `strip_creator_info`).

## 10. Security & Privacy

*   **Metadata Leakage**: Users must understand that `index/` reveals their folder names and hierarchy.
*   **Creator Info**: The `creator_info` field allows tracing the source of the package (e.g. "My Laptop Agent") but might contain PII (email). Agents should allow anonymizing this.
*   **Safe Parsing**: Consumers of `.meshpack` MUST validate `format_version` before parsing to avoid incompatible schema structure issues.

---

## 11. Delta / Incremental Updates

For synchronization scenarios, `.meshpack` supports **delta packs** that reference a base pack.

### Delta Pack Structure

A delta pack MUST set `generation.partial = true` and `generation.base_pack_hash` to the hash of the base pack.

### Delta Entry Semantics

Each `FileEntry` in a delta pack includes an implicit or explicit **operation**:

| Scenario | Representation |
|----------|----------------|
| **New file** | Entry present, no matching `path` in base pack |
| **Modified file** | Entry present, `hash` differs from base pack entry with same `path` |
| **Deleted file** | Entry with `"_deleted": true` in `extensions` field |
| **Unchanged** | Entry NOT present (inherited from base) |

### Merge Algorithm

1. Load base pack entries into a map keyed by `path`
2. For each entry in delta pack:
   - If `extensions._deleted == true`: Remove from map
   - Otherwise: Upsert into map (add or replace)
3. Result map represents the merged state

### Constraints

- Delta packs SHOULD NOT contain `resources/` for deleted files
- A delta pack without a resolvable `base_pack_hash` is **invalid**
- Chains of deltas (delta-of-delta) are NOT supported in v1.0; flatten before distribution

---

## 12. 3D Asset Metadata (Extended)

For 3D model entries, the following optional fields provide richer context:

### Geometry Metadata

Add to `FileEntry.extensions` under namespace `meshsync_geometry`:

```json
"extensions": {
  "meshsync_geometry": {
    "vertex_count": 15420,
    "face_count": 30000,
    "edge_count": 45000,
    "is_manifold": true,
    "is_watertight": true,
    "has_normals": true,
    "has_uvs": false
  }
}
```

### Material & Texture Dependencies

```json
"extensions": {
  "meshsync_dependencies": {
    "materials": ["materials/chrome.mtl"],
    "textures": ["textures/diffuse.png", "textures/normal.png"]
  }
}
```

### Print-Specific Metadata

```json
"extensions": {
  "meshsync_printability": {
    "estimated_print_time_minutes": 240,
    "estimated_filament_grams": 45,
    "recommended_layer_height_mm": 0.2,
    "requires_supports": true,
    "optimal_orientation": [0, 0, 1]
  }
}
```

---

## 13. Glossary

| Term | Definition |
|------|------------|
| **Metamodel** | A logical grouping of related files representing a single 3D asset (e.g., STL + textures + license) |
| **Assembly** | A hierarchical composition of metamodels with spatial transforms |
| **Shard** | A JSON file containing a subset of the total file entries for memory efficiency |
| **Delta Pack** | An incremental `.meshpack` containing only changes relative to a base pack |

---

## 14. Conformance Levels

### Level 1: Minimal (Reader)
- Parse `manifest.json` and all shards
- Validate `format_version` compatibility
- Iterate file entries

### Level 2: Standard (Reader/Writer)
- All of Level 1
- Verify `entries_hash` for each shard
- Verify `pack_hash` via sidecar
- Generate valid packs with correct hashing

### Level 3: Full (Ecosystem)
- All of Level 2
- Support `ids` namespace resolution
- Support `assembly` transforms
- Support delta pack merge
- Signature verification
