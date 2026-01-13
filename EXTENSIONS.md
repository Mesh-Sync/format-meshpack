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
