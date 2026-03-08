# IANA Media Type Registration: `application/vnd.meshsync.meshpack+zip`

This document contains the IANA media type registration template for the MeshPack
format, following the procedures defined in [RFC 6838](https://www.rfc-editor.org/rfc/rfc6838)
and the [IANA media type registration form](https://www.iana.org/form/media-types).

## Registration Status

- **Status**: PENDING — Not yet submitted to IANA.
- **Tracking Issue**: [#21](https://github.com/mesh-sync/standard-meshpack/issues/21)
- **Tree**: Vendor (`vnd.`) per RFC 6838 §3.2

---

## Media Type Registration Template

### Type name

application

### Subtype name

vnd.meshsync.meshpack+zip

### Required parameters

None.

### Optional parameters

None.

### Encoding considerations

Binary. MeshPack files are ZIP archives (per ISO/IEC 21320-1) containing
JSON metadata and optional binary resources. The archive MUST use DEFLATE
(method 8) or STORE (method 0) compression only.

### Security considerations

MeshPack files are ZIP archives and share the general security considerations
of ZIP-based formats:

- **Path traversal**: Consumers MUST validate that all `path` values within
  index entries reject `..` segments, absolute paths, and drive letters to
  prevent directory traversal attacks.
- **Zip bombs**: Consumers SHOULD enforce reasonable limits on decompressed
  size and entry count to prevent denial-of-service via decompression bombs.
- **Metadata leakage**: The index shards within a MeshPack reveal filesystem
  directory structure and filenames. The `creator_info` field may contain
  personally identifiable information (PII) such as names and email addresses.
  Generators SHOULD provide options to redact or hash PII before distribution.
- **Integrity verification**: MeshPack supports detached integrity sidecar
  files (`.meshpack.integrity`) with cryptographic hash verification and
  optional Ed25519/RSA-PSS signatures. Consumers SHOULD verify integrity
  before processing untrusted archives.
- **No executable content**: The format does not define executable content.
  However, embedded resources (in the `resources/` directory) could contain
  arbitrary file types. Consumers MUST NOT execute embedded resources without
  explicit user consent and appropriate sandboxing.
- **JSON parsing**: All JSON within the archive MUST be parsed with safe
  parsers that reject duplicate keys and enforce size limits.

### Interoperability considerations

MeshPack files are standard ZIP archives (DEFLATE/STORE only) and can be
opened by any compliant ZIP implementation. The internal structure uses
UTF-8 encoded JSON (without BOM) and follows a well-defined directory
layout documented in the MeshPack Standard Definition.

Three conformance levels (L1-Minimal, L2-Standard, L3-Full) are defined
to support incremental implementation. All levels share the same container
format and MIME type.

Archives exceeding 4 GB or 65,535 entries MUST use ZIP64 extensions per
the specification.

### Published specification

The MeshPack Standard Definition is maintained at:
https://github.com/mesh-sync/standard-meshpack

The specification includes:
- Human-readable format definition: `definition/README.md`
- Canonical JSON Schemas: `schema/manifest.schema.json`,
  `schema/shard.schema.json`, `schema/sidecar.schema.json`,
  `schema/common.schema.json`
- Conformance level requirements: `definition/requirements/`

### Applications which use this media type

MeshPack is used within the Mesh-Sync ecosystem for:

- **3D asset management**: Packaging collections of 3D models (STL, OBJ,
  3MF, glTF) with structured metadata, content-addressed resources, and
  sharded indices.
- **Filesystem synchronization**: Representing snapshots of file systems
  as portable, verifiable containers for the decoupling of scanning and
  processing phases.
- **Cross-platform data exchange**: Transferring 3D asset libraries between
  systems with full provenance, integrity verification, and platform metadata.

Tools and libraries that produce or consume MeshPack files include:
- `plugin-storage-localfilesystem` (MeshSync scanner agent)
- Generated SDKs for Python, Rust, and TypeScript

### Fragment identifier considerations

None. Fragment identifiers are not defined for this media type.

### Restrictions on usage

None.

### Additional information

- **Deprecated alias names for this type**: None.
- **Magic number(s)**: `PK` (0x50 0x4B) — standard ZIP magic bytes.
- **File extension(s)**: `.meshpack` (primary), `.mpack` (alternative)
- **Macintosh file type code**: None.
- **Object Identifiers**: None.

### Person to contact for further information

- **Name**: Jordane Masson
- **Email**: contact@meshsync.net

### Intended usage

COMMON

### Author/Change controller

- **Author**: Jordane Masson
- **Change controller**: Mesh-Sync Project (https://github.com/mesh-sync)

---

## Submission Procedure

To complete the IANA registration:

1. Review and finalize this template with all stakeholders.
2. Submit via the IANA media type registration form:
   https://www.iana.org/form/media-types
3. Respond to any IANA reviewer feedback.
4. Update the **Registration Status** section above upon approval.
5. Update the specification (`definition/README.md` §2.5) to reflect
   the registered status.

## References

- [RFC 6838 — Media Type Specifications and Registration Procedures](https://www.rfc-editor.org/rfc/rfc6838)
- [RFC 6839 — Additional Media Type Structured Syntax Suffixes](https://www.rfc-editor.org/rfc/rfc6839)
- [IANA Media Types Registry](https://www.iana.org/assignments/media-types/)
- [IANA Media Type Registration Form](https://www.iana.org/form/media-types)
- [MeshPack Standard Definition](definition/README.md)
