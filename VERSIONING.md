# Versioning Strategy

This project adheres to [Semantic Versioning 2.0.0](https://semver.org/) (SemVer).

## Format Versioning
The `.meshpack` format itself has a versioning scheme `MAJOR.MINOR.PATCH` stored in `manifest.json`.

*   **MAJOR version (X.y.z)**: Incompatible changes to the file format or schema.
    *   Example: Renaming required fields, changing the folder structure inside the ZIP, changing the sidecar format.
    *   *Parsers explicitly check this and reject versions they don't support.*

*   **MINOR version (x.Y.z)**: Backwards-compatible additions.
    *   Example: Adding a new optional field to `FileEntry`, adding a new known value to `platform_info`, adding a new extension schema.
    *   *Old parsers can read new files (ignoring unknown fields).*

*   **PATCH version (x.y.Z)**: Backwards-compatible bug fixes or clarifications.
    *   Example: Updating description in schema, fixing regex pattern without changing valid set, correcting documentation.

## SDK Versioning
The generated SDKs (Python, Rust, TypeScript, and Java 17) follow their own SemVer but aim to track the Format Version where possible.

*   SDK `1.2.0` is guaranteed to support Format `1.2.x` and `1.0.x`.

The repository-level `VERSION` file is the single source for generated package versions. `just generate` reads that file, `just check-version` verifies generated package metadata, and release tags must match it exactly (`v1.2.0` for `VERSION=1.2.0`).

## Schema URL Versioning

Schema `$id` values use versioned minor-release URLs such as `https://meshsync.net/schemas/meshpack/1.1/manifest.schema.json`. Patch releases within the same minor line may update descriptions, examples, or non-semantic metadata without changing the URL base. Changes that alter validation behavior require a new minor or major line.
