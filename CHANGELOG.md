# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Common Schema**: `common.schema.json` defining shared type definitions
  (`hashAlgorithm`, `hashValue`, `semver`, `namespacedId`, `signatureEntry`,
  `importPolicy`) referenced by manifest, shard, and sidecar schemas.
- **Sidecar Schema**: `sidecar.schema.json` defining detached integrity
  verification files (`*.meshpack.integrity`) for pack-level hash and signature
  validation.
- **Extension Schemas**:
  - `meshsync_geometry.schema.json` — geometry analysis metadata (vertex/face
    counts, manifold status, volume, surface area).
  - `meshsync_dependencies.schema.json` — file dependency tracking for
    multi-file formats (OBJ+MTL, FBX with textures).
  - `meshsync_printability.schema.json` — 3D printing analysis results with
    technology-specific parameters (FDM, SLA, SLS, MJF).
- **Conformance Test Suite**: Three-level pytest-based test suite
  (`tests/conformance/`) with requirement traceability markers:
  - L1 (Minimal Reader) — ZIP format, manifest parsing, basic validation.
  - L2 (Standard Reader/Writer) — read/write, sharding, pack hashing.
  - L3 (Full Ecosystem) — delta packs, signatures, import policies.
- **Validator Tool**: `tools/meshpack_validate.py` for validating `.meshpack`
  archives — checks manifest schema, ZIP entry ordering, shard integrity,
  resource-hash consistency, path constraints, and optional sidecar
  verification.
- **SDK Generator Templates**: Jinja2 templates for Python (Pydantic), Rust
  (Serde), and TypeScript (typed interfaces) under `generators/templates/`.
- **Specification Requirements**: Formal requirements documents for each
  conformance level (`definition/requirements/L1-minimal.md`,
  `L2-standard.md`, `L3-full.md`) with traceability matrix.
- **Extension Guidelines**: `EXTENSIONS.md` documenting extension namespace
  registry and versioning conventions.

### Changed
- Enhanced `manifest.schema.json` and `shard.schema.json` with `$ref`
  references to common definitions and metamodel support.
- Updated CI workflow to enforce self-hosted runners and bump action versions.

## [1.0.0] - 2026-01-13

### Added
- Initial public release of MeshPack Standard.
- **Manifest Schema**: `manifest.schema.json` defining root metadata.
- **Shard Schema**: `shard.schema.json` defining sharded index structure.
- **Generators**: Python script to generate SDKs for Python, Rust, and TypeScript.
- **Documentation**: Comprehensive specification in `definition/README.md`.
- **Project Infrastructure**: `Justfile` for build automation.

### Changed
- Standardized file extension to `.meshpack`.
- Updated creator contact info to official MeshSync contacts.

### Security
- Defined initial security policy.
