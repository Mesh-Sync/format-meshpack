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
The generated SDKs (Python, Rust, TypeScript) follow their own SemVer but aim to track the Format Version where possible.

*   SDK `1.2.0` is guaranteed to support Format `1.2.x` and `1.0.x`.
