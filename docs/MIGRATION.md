# Migration Guide

## Migrating from pre-1.1 generated SDKs

MeshPack `1.1.0` makes Python, Rust, TypeScript, and Java 17 first-class generated SDK targets.

Important changes for SDK consumers:

1. Package versions are generated from the repository `VERSION` file.
2. Generated SDK output is cleaned before generation, so removed templates no longer leave stale package files behind.
3. SDKs expose validator result types using the shared `severity`/`code`/`message` finding shape.
4. Java records ignore unknown JSON fields and deserialize wire enum values such as `"linux"` correctly.
5. TypeScript is Node-first for validation because hashing uses Node crypto APIs.

The Python reference validator remains the authority for detached sidecar and signature verification.

## Migrating from `_deleted` Extension to `operation` Field

### Background

Prior to MeshPack v1.0, file deletions in delta packs were represented using
a `_deleted` extension on the FileEntry:

```json
{
  "path": "models/old-part.stl",
  "extensions": {
    "_deleted": { "v1": { "deleted": true } }
  }
}
```

Starting with v1.0, deletions use the first-class `operation` field on the
FileEntry (per TDD-050 AD-4):

```json
{
  "path": "models/old-part.stl",
  "operation": "delete"
}
```

### How to Migrate

For each entry in your shard that uses the `_deleted` extension:

1. **Remove** the `_deleted` key from `extensions`
2. **Add** `"operation": "delete"` to the FileEntry
3. If the `extensions` object is now empty, remove it entirely
4. Remove fields that are meaningless for deletions (`size_bytes`, `hash`, etc.) — only `path` and `operation` are required

#### Before (pre-v1.0)

```json
{
  "path": "models/old-part.stl",
  "size_bytes": 0,
  "hash": "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "modified_at": "2026-01-01T00:00:00+00:00",
  "extensions": {
    "_deleted": { "v1": { "deleted": true } }
  }
}
```

#### After (v1.0+)

```json
{
  "path": "models/old-part.stl",
  "operation": "delete",
  "modified_at": "2026-01-01T00:00:00+00:00"
}
```

### Supported `operation` Values

| Value     | Description                              |
|-----------|------------------------------------------|
| `add`     | New file added to the workspace          |
| `modify`  | Existing file modified                   |
| `delete`  | File removed from the workspace          |
| `rename`  | File renamed (use with `previous_path`)  |

### Deprecation Timeline

| Version | Status |
|---------|--------|
| < 1.0   | `_deleted` extension used for deletions |
| 1.0     | `operation` field introduced; `_deleted` deprecated |
| 2.0     | `_deleted` extension support will be **removed** |

Validators MAY emit a deprecation warning (DEP-001) when `_deleted` is
encountered in v1.x archives.
