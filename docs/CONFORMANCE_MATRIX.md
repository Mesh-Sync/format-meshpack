# Conformance Matrix

| Capability | Reference Validator | Python SDK | Rust SDK | TypeScript SDK | Java 17 SDK |
|------------|---------------------|------------|----------|----------------|-------------|
| Typed schema models | N/A | Yes | Yes | Yes | Yes |
| ZIP reader helpers | Yes | Yes | Yes | Yes | Yes |
| JSON Schema validation | Yes (`compat`/`strict`) | Model-level only | Model-level only | Model-level only | Model-level only |
| Manifest presence/parse checks | Yes | Yes | Yes | Yes | Yes |
| Future-major `format_version` rejection | Yes | Yes | Yes | Yes | Yes |
| README layout findings | Yes | Yes | Yes | Yes | Yes |
| ZIP ordering warning | Yes | Yes | Yes | Partial | Yes |
| Compression method checks | Yes | Yes | Yes | Not exposed by JSZip | Yes |
| Zip bomb limits | Yes | Yes | Yes | Partial | Yes |
| Path traversal/absolute/drive/UNC checks | Yes | Yes | Yes | Yes | Yes |
| entries_count checks | Yes | Yes | Yes | Yes | Yes |
| UTF-8 path ordering | Yes | Yes | Yes | Yes | Yes |
| entries_hash/JCS checks | Yes | Yes | Yes | Yes | Yes |
| BLAKE3 entries_hash | Optional `blake3` package | Optional `blake3` package | Yes | Yes | Yes |
| Missing resource checks | Yes | Yes | Yes | Yes | Yes |
| Unsafe resource/preview ref rejection | Yes | Yes | Yes | Yes | Yes |
| Detached sidecar pack hash | Yes | Yes | Yes | Yes | Yes |
| Signature verification | Optional Python crypto | Ed25519/RSA-PSS-SHA256 | Ed25519 | Ed25519/RSA-PSS-SHA256 | Ed25519/RSA-PSS-SHA256 |
| Conformance fixture validation | Yes | Public sample parity | Generated smoke tests | Generated smoke tests | Generated smoke tests |
| Generated SDK runtime parity tests | N/A | Public sample + unsafe resource refs + future-major versions | Sidecar + missing manifest + unsafe resource refs + future-major versions | Sidecar + missing manifest + unsafe resource refs + future-major versions | Sidecar + missing manifest + unsafe resource refs + future-major versions |
| L3 signature conformance tests | Yes | Via reference test suite | Ed25519 API coverage | API coverage | API coverage |

The generated SDKs provide validator APIs for core public-reader safety, BLAKE3 entry hashing, detached sidecar hash verification, and signature verification hooks. The Python reference validator remains the strict JSON Schema authority because generated SDKs deserialize typed models but do not implement full Draft-07 validation modes.
