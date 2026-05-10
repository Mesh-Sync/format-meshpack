# SDK Quickstarts

## Python

```python
from meshpack.models import MeshPackReader, validate_meshpack

result = validate_meshpack("sample.meshpack")
assert result.valid

reader = MeshPackReader("sample.meshpack")
print(reader.manifest.format_version)
print([entry.path for entry in reader.list_model_entries()])
reader.close()
```


## Rust

```rust
use meshpack::{validate_meshpack, MeshPackReader};

let result = validate_meshpack("sample.meshpack")?;
assert!(result.is_valid());

let mut reader = MeshPackReader::open("sample.meshpack")?;
let manifest = reader.get_manifest()?;
println!("{}", manifest.format_version);
println!("{}", reader.list_model_entries()?.len());
# Ok::<(), Box<dyn std::error::Error>>(())
```

## TypeScript

```ts
import { readFile } from "node:fs/promises";
import { readMeshPack, validateMeshPack } from "@mesh-sync/meshpack";

const bytes = await readFile("sample.meshpack");
const result = await validateMeshPack(bytes);
if (!result.valid) throw new Error(result.errors.map((f) => f.code).join(", "));

const document = await readMeshPack(bytes);
console.log(document.manifest.format_version);
```

## Java 17

```java
import java.nio.file.Path;
import net.meshsync.meshpack.MeshPack;

MeshPack.ValidationResult result = MeshPack.validate(Path.of("sample.meshpack"));
if (!result.valid()) {
  throw new IllegalStateException(result.findings().toString());
}

try (MeshPack.Reader reader = new MeshPack.Reader(Path.of("sample.meshpack"))) {
  MeshPack.MeshPackDocument document = reader.readDocument();
  System.out.println(document.manifest().format_version());
}
```

## Notes

SDK readers treat `resource_ref` and `preview_ref` as canonical resource filenames only. Unsafe values with paths, traversal, drive letters, backslashes, colons, or non-hash names are rejected before lookup.

Use the Python reference validator for release gates that require JSON Schema `strict` mode. Generated SDK validators expose detached sidecar hash checks and Ed25519/RSA-PSS-SHA256 signature verification hooks for application integration, with the Python reference validator remaining the conformance authority.
