# Schema Hosting Policy

MeshPack schemas are published under versioned canonical URLs:

```text
https://meshsync.net/schemas/meshpack/<major>.<minor>/<name>.schema.json
https://meshsync.net/schemas/meshpack/<major>.<minor>/extensions/<extension>.schema.json
```

For MeshPack `2.0.0`, the canonical base is:

```text
https://meshsync.net/schemas/meshpack/2.0/
```

The repository keeps Draft-07 schemas for the `2.x` line because Draft-07 has broad validator support across Python, JavaScript, Java, Rust tooling, and build systems used by SDK consumers. A future schema-draft migration requires a minor release if the accepted document set is unchanged, or a major release if validation semantics change.

## Alias Policy

`/schemas/meshpack/latest/` may point to the latest stable minor line, but generated SDKs, validators, docs, and examples must reference versioned URLs. Release automation verifies that schema `$id` values and package versions agree with `VERSION`.

## Catalog

[schema/catalog.json](../schema/catalog.json) is the machine-readable index for the current release line. Public site deployment must publish this file alongside the schemas.
