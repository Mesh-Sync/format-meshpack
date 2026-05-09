# MeshPack Samples

This directory contains example `.mpack` files for testing and validation.

## Available Samples

### test-workspace.mpack

- **Files:** 17
- **Total Size:** 3,179,581 bytes
- **Format:** MeshPack v2.0.0
- **Contents:** 3D models (OBJ, STL), media files, nested structures
- **Integrity sidecar:** `test-workspace.mpack.integrity` with authoritative SHA-256 pack hash

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
