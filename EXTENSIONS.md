# Extensions Guide

The `.meshpack` format allows for extensibility via the `extensions` field present in both `Manifest` and `FileEntry`.

## Philosophy

Core schemas (`manifest.schema.json`, `shard.schema.json`) define the *common denominator* needed by all tools. Vendor-specific or experimental metadata should reside in `extensions` to avoid breaking validation for standard tools.

## The `extensions` Field

It is a key-value dictionary where:
- Keys are **Namespaced Strings**.
- Values are **Arbitrary JSON Objects**.

```json
"extensions": {
  "mycompany_preview_data": {
    "camera_angle": [0, 1, 0],
    "lighting": "studio"
  },
  "x_experimental_feature": true
}
```

## Namespace Rules

To prevent collisions, please stick to these conventions:

1.  **Vendor Prefixes**: Use `organization_pluginname`.
    *   Good: `adobe_preview`, `blender_custom_props`
    *   Bad: `preview`, `custom`

2.  **Experimental**: Use `x_` prefix.
    *   Good: `x_compression_v2`

3.  **Prohibited**: Do not use top-level keys similar to core spec fields (e.g., don't use `size_bytes` inside extensions if it might confusingly overlap with standard logic).

## Registry

(Currently informal)

If you are developing a widely used plugin or tool, please open a PR to add your namespace here to avoid collisions.

| Prefix | Owner | Description |
| :--- | :--- | :--- |
| `meshsync_` | MeshSync | Official extensions from MeshSync ecosystem |
| `vscode_` | VS Code Plugin | Metadata for VS Code extension display |
| `meshsync_geometry` | MeshSync | 3D geometry metadata (vertex/face counts, manifold status) |
| `meshsync_dependencies` | MeshSync | Material and texture file references |
| `meshsync_printability` | MeshSync | 3D printing analysis results |
| `_deleted` | MeshSync | Reserved for delta pack deletion markers |

---

## Extension Versioning Strategy

All official MeshSync extensions use **versioned data envelopes** to enable schema evolution without breaking backwards compatibility.

### Pattern

```json
"extensions": {
  "meshsync_<name>": {
    "v1": { /* v1 schema fields */ },
    "v2": { /* v2 schema fields, may coexist with v1 */ }
  }
}
```

### Rules

1. **Writers** SHOULD emit the latest stable version they support
2. **Writers** MAY emit multiple versions for compatibility (e.g., both `v1` and `v2`)
3. **Readers** MUST select the highest version they understand, ignore unknown versions
4. **Breaking changes** require a new version number
5. **Additive changes** (new optional fields) can stay in the same version

### Migration Example

```json
// Producer supports v2, emits both for compatibility
"extensions": {
  "meshsync_geometry": {
    "v1": { "vertex_count": 15420, "face_count": 30000 },
    "v2": { "vertex_count": 15420, "face_count": 30000, "topology": { ... } }
  }
}

// Old consumer reads v1, ignores v2
// New consumer reads v2, ignores v1
```

---

## Official MeshSync Extensions

The following extensions are defined by MeshSync and have stable schemas:

### `meshsync_geometry`

Geometry analysis metadata for 3D model files.

```json
"extensions": {
  "meshsync_geometry": {
    "v1": {
      "vertex_count": 15420,
      "face_count": 30000,
      "edge_count": 45000,
      "triangle_count": 30000,
      "is_manifold": true,
      "is_watertight": true,
      "has_normals": true,
      "has_uvs": false,
      "has_vertex_colors": false,
      "surface_area_mm2": 12500.5,
      "volume_mm3": 45000.0
    }
  }
}
```

### `meshsync_dependencies`

File dependencies for multi-file formats (OBJ+MTL, FBX with textures).

```json
"extensions": {
  "meshsync_dependencies": {
    "v1": {
      "materials": ["materials/chrome.mtl", "materials/glass.mtl"],
      "textures": ["textures/diffuse.png", "textures/normal.png"],
      "references": ["parts/wheel.obj"]
    }
  }
}
```

### `meshsync_printability`

3D printing analysis results. Technology-agnostic where possible, with technology-specific sub-objects.

```json
"extensions": {
  "meshsync_printability": {
    "v1": {
      "printability_score": 0.85,
      "is_watertight": true,
      "requires_supports": true,
      "has_overhangs": true,
      "optimal_orientation": [0, 0, 1],
      "bounding_box_mm": [120, 80, 45],
      
      "fdm": {
        "estimated_print_time_minutes": 240,
        "estimated_filament_grams": 45.5,
        "estimated_filament_meters": 15.2,
        "recommended_layer_height_mm": 0.2,
        "recommended_nozzle_mm": 0.4,
        "recommended_infill_percent": 20,
        "has_bridging": true,
        "max_overhang_angle_deg": 55
      },
      
      "sla": {
        "estimated_print_time_minutes": 180,
        "estimated_resin_ml": 25.5,
        "recommended_layer_height_um": 50,
        "estimated_cure_time_per_layer_s": 8,
        "support_contact_points": 42,
        "has_islands": false,
        "has_suction_cups": true
      },
      
      "sls": {
        "estimated_print_time_minutes": 120,
        "estimated_powder_grams": 85.0,
        "recommended_layer_height_um": 100,
        "min_wall_thickness_mm": 0.8,
        "can_nest": true,
        "packing_efficiency": 0.65
      },
      
      "mjf": {
        "estimated_print_time_minutes": 90,
        "estimated_powder_grams": 72.0,
        "recommended_layer_height_um": 80,
        "min_feature_size_mm": 0.5
      }
    }
  }
}
```

**Field Descriptions (v1):**

| Field | Scope | Description |
|-------|-------|-------------|
| `printability_score` | All | 0.0-1.0 overall printability rating |
| `is_watertight` | All | Required for most printing technologies |
| `requires_supports` | All | Whether model needs support structures |
| `optimal_orientation` | All | Unit vector for best print orientation |
| `bounding_box_mm` | All | [X, Y, Z] dimensions in mm |
| `has_islands` | SLA | Disconnected regions that would fail |
| `has_suction_cups` | SLA | Hollow regions that trap resin |
| `can_nest` | SLS/MJF | Whether multiple copies can be packed |
| `has_bridging` | FDM | Unsupported horizontal spans |

### `_deleted` (Reserved)

Used in delta packs to mark files for deletion. NOT a namespaced extension, NOT versioned.

```json
"extensions": {
  "_deleted": true
}
```
