# IANA Media Type Registration

## application/vnd.meshsync.meshpack+zip

This document contains the IANA media type registration template for the
MeshPack container format, following [RFC 6838 §5.6](https://www.rfc-editor.org/rfc/rfc6838#section-5.6).

**Registration status**: PRE-SUBMISSION — this template is maintained for public review and will be submitted after the `1.1.0` schema URLs are publicly hosted.

---

### Registration Template

**Type name**: application

**Subtype name**: vnd.meshsync.meshpack+zip

**Required parameters**: N/A

**Optional parameters**: N/A

**Encoding considerations**: binary

The content is a ZIP archive (per ISO/IEC 21320-1) containing JSON metadata
files and optional binary resources. All JSON files within the archive are
encoded in UTF-8 without BOM.

**Security considerations**:

MeshPack archives share the security considerations common to ZIP-based
formats:

- **Path traversal**: File entry paths within the archive could contain `..`
  segments, absolute paths, or drive letters. Consumers MUST validate all
  `path` values before extraction (see specification §10 and REQ-L1-013).
- **Zip bombs**: Archives may contain entries with extreme compression ratios.
  Consumers SHOULD enforce decompressed size limits.
- **Metadata leakage**: The index shard files expose the original directory
  hierarchy and file names of the source filesystem. The `creator_info` field
  may contain personally identifiable information.
- **Integrity**: The format supports SHA-256, SHA-512, and BLAKE3 hashes for
  content verification, and Ed25519 or RSA-PSS-SHA256 signatures for
  authenticity. The authoritative integrity hash is stored in a detached
  `.meshpack.integrity` sidecar file, not in the archive itself.
- **Executable content**: MeshPack archives are not intended to contain
  executable code. Consumers SHOULD NOT execute any content extracted from a
  MeshPack archive.

**Interoperability considerations**:

MeshPack files are standard ZIP archives readable by any compliant ZIP
implementation. The specification mandates DEFLATE (method 8) or STORE
(method 0) compression only, ensuring broad compatibility. Archives
exceeding 4 GB or 65,535 entries MUST use ZIP64 extensions. The
`manifest.json` entry MUST be the first entry in the ZIP central directory
to support streaming readers.

**Published specification**:

The MeshPack Standard Definition is maintained at:

https://github.com/Mesh-Sync/standard-meshpack

Versioned schemas are published under:

https://meshsync.net/schemas/meshpack/1.1/

**Applications which use this media type**:

Applications within the Mesh-Sync ecosystem that scan, process, and
synchronize collections of 3D assets. This includes 3D scanning pipelines,
asset management systems, and 3D printing workflow tools.

**Fragment identifier considerations**: N/A

**Restrictions on usage**: N/A

**Additional information**:

- **Deprecated alias names for this type**: N/A
- **Magic number(s)**: `50 4B 03 04` (standard ZIP local file header)
- **File extension(s)**: `.meshpack` (primary), `.mpack` (alternative)
- **Macintosh file type code**: N/A

**Person & email address to contact for further information**:

Jordane Masson, contact@meshsync.net

**Intended usage**: COMMON

**Author/Change controller**:

Jordane Masson on behalf of the Mesh-Sync project.
https://github.com/Mesh-Sync
