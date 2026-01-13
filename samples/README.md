# MeshPack Samples

This directory contains example .mpack files for testing and validation.

## Available Samples

### test-workspace.mpack

- **Files:** 17
- **Total Size:** 3,179,581 bytes
- **Format:** MeshPack v1.0.0
- **Contents:** 3D models (OBJ, STL), media files, nested structures

## Usage

```bash
# Extract and inspect
unzip -l test-workspace.mpack
unzip test-workspace.mpack -d extracted/

# Validate against schema
check-jsonschema --schemafile ../schema/manifest.schema.json extracted/manifest.json
```
