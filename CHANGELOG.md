# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2026-03-06

### Added
- **Common Schema**: `common.schema.json` with shared definitions (`hashValue`, `signatureEntry`, etc.)
- **Sidecar Schema**: `sidecar.schema.json` for companion metadata files
- **Extension Schemas**:
  - `meshsync_geometry.schema.json` — mesh geometry metadata (vertex/face counts, manifold, watertight)
  - `meshsync_printability.schema.json` — print analysis (FDM/SLA/SLS/MJF tech-specific data)
  - `meshsync_dependencies.schema.json` — material and texture references
  - `meshsync_content.schema.json` — content metadata (title, description, tags)
  - `meshsync_thumbnails.schema.json` — thumbnail and preview references
- **Validator Tool**: `tools/meshpack_validate.py` — comprehensive .meshpack archive validator
  - RFC 8785 (JCS) canonicalization for entries hash verification
  - ZIP compression method validation (ZIP-003)
  - Zip bomb protection with configurable limits (ZIP-004, ZIP-005)
  - Ed25519 and RSA-PSS-SHA256 signature verification
  - Path security checks (absolute, drive letter, UNC, traversal)
  - BLAKE3 hash algorithm support
- **Conformance Test Suite**: 64 tests across L1/L2/L3 conformance levels
  - Static test fixtures (valid and invalid .meshpack reference archives)
  - Fixture generator script with `just generate-fixtures` target
- **SDK Typed Extension Models**: Python, TypeScript, and Rust SDKs now generate typed models for all extension schemas
- **Geometry Canonical Fields Documentation**: `docs/geometry-canonical-fields.md`

### Fixed
- Import policy key naming inconsistency in requirement docs and tests (#6, #12)
- Sample manifest `workspace_id: null` conflict with `ids[meshsync:workspace]` entry (#9)
- Cross-file `$ref` resolution in SDK generator for `common.schema.json`
- Validator `check_entry_path` ENT-003 upgraded from WARNING to ERROR per REQ-L1-013

### Changed
- Extension schemas use `allOf` + `$ref` pattern for cross-file references (Draft-07 compatibility)
- `meshsync_geometry` v1 now sets `additionalProperties: false` for strict validation

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
