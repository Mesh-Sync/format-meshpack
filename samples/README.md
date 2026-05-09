# MeshPack Samples

This directory contains example `.mpack` files for testing and validation.

## Available Samples

### test-workspace.mpack

- **Files:** 17
- **Indexed source size:** 3,179,581 bytes (`manifest.index_summary.total_size_bytes`)
- **Archive byte size:** recorded in `test-workspace.mpack.integrity#pack_size_bytes`
- **Format:** MeshPack v2.0.0
- **Contents:** 3D models (OBJ, STL), media files, nested structures
- **Integrity sidecar:** `test-workspace.mpack.integrity` with authoritative SHA-256 pack hash

The indexed source size is the sum of `FileEntry.size_bytes` values. It is intentionally distinct from the `.mpack` archive byte size used by the detached integrity sidecar.

## Usage

```bash
# Extract and inspect
unzip -l test-workspace.mpack
unzip test-workspace.mpack -d extracted/

# Validate with the reference validator
python ../tools/meshpack_validate.py --strict test-workspace.mpack

# Validate directly with an explicit sidecar path
python ../tools/meshpack_validate.py --strict --sidecar test-workspace.mpack.integrity test-workspace.mpack
```
