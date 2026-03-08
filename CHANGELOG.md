# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- IANA media type registration template for `application/vnd.meshsync.meshpack+zip` ([#21](https://github.com/mesh-sync/standard-meshpack/issues/21)).
- RFC 6838 and RFC 6839 references in specification §2.5.

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
