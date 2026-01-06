# Standard MeshPack (.meshpack)

The official specification, schemas, and tooling for the **MeshPack** format — an universal, portable container for 3D assets, metadata, and cross-platform indices.

## Overview

MeshPack (`.meshpack`) is a ZIP-based container format designed to solve the fragmentation in 3D asset management. It bundles:
- **3D Models**: STL, OBJ, 3MF, etc. (deduplicated via content addressing).
- **Metadata**: Rich JSON manifest with licensing, creator info, and platform compatibility.
- **Indices**: Sharded search indices for fast local access without unpacking.
- **Portability**: Self-contained "files" that act like databases.

## Repository Structure

- **[`definition/`](definition/README.md)**: The human-readable specification (RFC-style). **Start here.**
- **[`schema/`](schema/)**: Canonical JSON Schemas (`manifest.schema.json`, `shard.schema.json`) used for validation and code generation.
- **[`generators/`](generators/)**: Python scripts and Jinja2 templates that generate client libraries from the schemas.
- **[`generated/`](generated/)**: (Gitignored) The output directory for generated SDKs.

## Usage

This repository uses [`just`](https://github.com/casey/just) for task automation.

### Prerequisites
- **Python 3.10+** (for generators)
- **Node.js/npm** (for TypeScript SDK build)
- **Rust/Cargo** (for Rust SDK build)
- **Just** (`curl --proto '=https' --tlsv1.2 -sSf https://just.systems/install.sh | bash -s -- --to ~/bin`)

### Commands

| Command | Description |
|---------|-------------|
| `just generate` | Generates SDK code for Python, Rust, and TypeScript into `generated/sdks/`. |
| `just validate` | Validates the JSON schemas against the meta-schema. |
| `just compile` | Builds the generated SDKs (Python Wheel, Rust Crate, NPM Package). |
| `just all` | Runs generate, validate, and compile. |
| `just clean` | Removes the `generated/` directory. |

## SDKs

The generator produces strongly-typed client libraries ensuring 100% compliance with the spec.

- **Python**: Pydantic models with `zipfile` abstraction.
- **Rust**: Serde structs with `zip` crate integration.
- **TypeScript**: Typed interfaces with `jszip`.

## Contributing

1.  **Modify the Spec**: Edit `definition/README.md`.
2.  **Update Schemas**: Edit `schema/*.json`.
3.  **Update Generators**:
    *   Logic: `generators/generate_sdks.py`
    *   Templates: `generators/templates/`
4.  **Regenerate**: Run `just generate` to verify your changes produce valid code.
5.  **Test**: Run `just compile` to ensure the generated code builds.
