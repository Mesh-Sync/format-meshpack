---
id: MPACK-DEF-001
tags:
  - specification
  - meshpack
  - data-interchange
title: 'MeshPack (.meshpack) Standard Definition'
status: draft
created_date: 2026-01-06
updated_date: 2026-01-06
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

Physically, a `.meshpack` file is a **ZIP archive** with a custom extension. It uses standard DEFLATE compression to minimize transfer size.

### Extension
- Primary: `.meshpack`
- Alternative: `.meshpack`

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
└── mapping.db          # (Optional) SQLite cache for local acceleration
```

Each directory contains a `_README.md` file describing its purpose and strict usage rules, ensuring human readability when extracted.

---

## 4. Manifest Schema (`manifest.json`)

The `manifest.json` file is the entry point for the package. It defines the ownership, global context, and processing rules.

### JSON Schema

```json
{
  "format_version": "1.0.0", // SemVer of the .meshpack specification
  "created_at": "2026-01-06T12:00:00Z",
  "workspace_id": "uuid-string", // The workspace this snapshot belongs to
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
*   **`platform_info`**: CRITICAL for cross-platform processing.
    *   **`os`**: Source operating system.
    *   **`path_separator`**: Separator used in the *original* file system (for reference only).
    *   **`is_case_sensitive`**: Hints if `Logo.png` and `logo.png` should be treated as distinct files.
*   **`extensions`**: A dictionary for storing non-standard metadata without breaking strict schema validation.

---

## 5. Index Sharding (`index/*.json`)

To handle libraries with hundreds of thousands of files without loading a monolithic JSON into memory, the file list is split into multiple shards.

### Sharding Strategy
- Files are distributed across `part-XYZ.json` files.
- Shards are **Objects**, not Arrays, to allow for shard-specific metadata.
- The consumer MUST read ALL shards to build a complete view of the package.

### Shard JSON Schema

```json
{
  "shard_id": "part-001",
  "format_version": "1.0.0",
  "creator_info": {             // Redundant but required for standalone valid JSONs
     "name": "Jordane Masson",
     "email": "contact@meshsync.net"
  },
  "entries": [
      {
        "path": "vehicles/cars/sports_car_v2.stl",
        "original_name": "Sports Car V2.stl",
        "size_bytes": 500021,
        "hash": "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        "modified_at": "2025-12-01T09:30:00Z",
        "resource_ref": null,   // null or hash if included in resources/
        "attributes": {
            "is_symlink": false,
            "is_hidden": false
        },
        "extensions": {}        // Per-file extensibility
      },
      ...
  ] 
}
```

### FileEntry Definition
*   **`path`**: **Relative Path** from the root of the scanned directory. MUST NOT contain workspace ID or absolute system paths. MUST use forward slashes (`/`).
*   **`resource_ref`**: If the actual file content is included in the `.meshpack` (e.g. usage for thumbnails or small text files), this field contains the filename in the `resources/` folder.
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

## 8. Usage Scenarios

### 8.1. Local Storage Agent
The `plugin-storage-localfilesystem` generates `.meshpack` files during its "Scan" phase.
1.  **Scan**: Walk directory, calculate hashes.
2.  **Pack**: Stream entries into `index/part-XXX.json` object arrays inside the ZIP.
3.  **Embed**: If config `include_thumbnails=true`, copy relevant files to `resources/` and link in `FileEntry`.
4.  **Deploy**: The `.meshpack` file is ready.

### 8.2. Heuristic Analysis
A separate "Heuristic Engine" can mount this package. Because it is read-only and structured:
- It can process the file structure without needing physical access to the user's hard drive.
- It enables "Remote Analysis" where the user only uploads the structure (the `.meshpack` manifest), not the actual 500GB of heavy STL files.

## 9. Security & Privacy

*   **Metadata Leakage**: Users must understand that `index/` reveals their folder names and hierarchy.
*   **Creator Info**: The `creator_info` field allows tracing the source of the package (e.g. "My Laptop Agent") but might contain PII (email). Agents should allow anonymizing this.
*   **Safe Parsing**: Consumers of `.meshpack` MUST validate `format_version` before parsing to avoid incompatible schema structure issues.
