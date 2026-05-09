# Conformance Matrix

| Capability | Reference Validator | Python SDK | Rust SDK | TypeScript SDK | Java 17 SDK |
|------------|---------------------|------------|----------|----------------|-------------|
| Typed schema models | N/A | Yes | Yes | Yes | Yes |
| ZIP reader helpers | Yes | Yes | Yes | Yes | Yes |
| Manifest presence/parse checks | Yes | Yes | Yes | Yes | Yes |
| ZIP ordering warning | Yes | Yes | Yes | Partial | Yes |
| Compression method checks | Yes | Yes | Yes | Not exposed by JSZip | Yes |
| Zip bomb limits | Yes | Yes | Yes | Partial | Yes |
| Path traversal/absolute/drive/UNC checks | Yes | Yes | Yes | Yes | Yes |
| entries_count checks | Yes | Yes | Yes | Yes | Yes |
| entries_hash/JCS checks | Yes | Yes | Yes | Yes | Yes |
| Missing resource checks | Yes | Yes | Yes | Yes | Yes |
| Detached sidecar pack hash | Yes | No | No | No | No |
| Signature verification | Optional Python crypto | No | No | No | No |
| L1/L2 fixture parsing | Yes | Yes | Yes | Yes | Yes |
| L3 sidecar/signature fixture validation | Yes | No | No | No | No |

The generated SDKs now provide validator APIs for core public-reader safety. The Python reference validator remains the full L3 authority for sidecar and signature verification.
