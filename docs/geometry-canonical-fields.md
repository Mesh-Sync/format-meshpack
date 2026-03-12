# Geometry Extension — Canonical Field Names

> **Schema**: `schema/extensions/meshsync_geometry.schema.json`
> **Extension key**: `meshsync_geometry`
> **Current version**: `v1`

## Canonical Field Reference

The following field names are **authoritative** as defined in the JSON Schema.
All consumers (SDKs, backend mappers, CLI tools) **MUST** use these exact names.

| Canonical Name       | Type      | Unit   | Description                                          |
|----------------------|-----------|--------|------------------------------------------------------|
| `vertex_count`       | `integer` | —      | Number of vertices in the mesh                       |
| `face_count`         | `integer` | —      | Number of faces in the mesh                          |
| `edge_count`         | `integer` | —      | Number of edges in the mesh                          |
| `triangle_count`     | `integer` | —      | Number of triangles (may differ from `face_count`)   |
| `is_manifold`        | `boolean` | —      | Each edge shared by exactly 2 faces                  |
| `is_watertight`      | `boolean` | —      | Mesh is closed with no holes                         |
| `has_normals`        | `boolean` | —      | Vertex or face normals present                       |
| `has_uvs`            | `boolean` | —      | UV texture coordinates present                       |
| `has_vertex_colors`  | `boolean` | —      | Per-vertex colors present                            |
| `surface_area_mm2`   | `number`  | mm²    | Total surface area                                   |
| `volume_mm3`         | `number`  | mm³    | Volume (negative if inverted normals)                |

## Known Consumer Mismatches

Some downstream consumers use non-canonical field names. These **do not conform**
to the schema and will fail validation:

| Non-canonical (wrong) | Canonical (correct) | Notes                        |
|------------------------|---------------------|------------------------------|
| `vertices`             | `vertex_count`      | Backend mapper legacy name   |
| `faces`                | `face_count`        | Backend mapper legacy name   |
| `edges`                | `edge_count`        | Backend mapper legacy name   |
| `volume_cubic_mm`      | `volume_mm3`        | Unit suffix divergence       |

## Migration Guide

If your code uses the non-canonical names, update your mappers:

```typescript
// BEFORE (non-conforming)
const geometry = {
  vertices: mesh.vertexCount,
  faces: mesh.faceCount,
  volume_cubic_mm: mesh.volume,
};

// AFTER (conforming)
const geometry = {
  vertex_count: mesh.vertexCount,
  face_count: mesh.faceCount,
  volume_mm3: mesh.volume,
};
```

The generated SDKs (TypeScript, Python, Rust) use the canonical names.
Use the SDK types to get compile-time enforcement:

```typescript
import { MeshsyncGeometryV1 } from '@mesh-sync/meshpack';

const geo: MeshsyncGeometryV1 = {
  vertex_count: 15420,  // ✅ correct
  // vertices: 15420,   // ❌ TypeScript error — not in interface
};
```
