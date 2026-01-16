# MeshPack Specification Requirements

This directory contains the formal requirements for the MeshPack (`.meshpack`) file format standard, organized by conformance level.

## Conformance Levels Overview

The MeshPack specification defines **three conformance levels** to accommodate different implementation complexity and use cases:

| Level | Name | Target Implementers | Complexity |
|-------|------|---------------------|------------|
| **L1** | Minimal | File browsers, simple viewers, archive tools | Low |
| **L2** | Standard | Desktop agents, sync clients, 3D viewers | Medium |
| **L3** | Full | MeshSync ecosystem, processing pipelines, marketplaces | High |

## Requirements Files

- [L1-minimal.md](L1-minimal.md) - Minimal conformance (readers only)
- [L2-standard.md](L2-standard.md) - Standard conformance (readers + writers)
- [L3-full.md](L3-full.md) - Full conformance (ecosystem integration)

## How to Read Requirements

Each requirement follows this format:

```
### REQ-LX-NNN: Requirement Title

**Category**: Manifest | Shard | Resource | Integrity | Extension
**Type**: MUST | SHOULD | MAY
**Testable**: Yes | No

Description of the requirement.

**Rationale**: Why this requirement exists.

**Verification**: How to test compliance.
```

## Relationship Between Levels

```
┌────────────────────────────────────────────────────────────────┐
│ L3: Full Ecosystem                                             │
│  ├── Delta pack merge algorithm                                │
│  ├── Assembly transform support                                │
│  ├── Namespace ID resolution (meshsync:model, thingiverse:*)  │
│  ├── Signature verification (ed25519)                          │
│  └── Extension schema validation                               │
│ ┌────────────────────────────────────────────────────────────┐ │
│ │ L2: Standard Read/Write                                    │ │
│ │  ├── Generate valid packs with correct sharding            │ │
│ │  ├── Compute and verify entries_hash per shard             │ │
│ │  ├── Compute and verify pack_hash via sidecar              │ │
│ │  ├── Resource embedding with hash linking                  │ │
│ │  └── Platform-aware path normalization                     │ │
│ │ ┌────────────────────────────────────────────────────────┐ │ │
│ │ │ L1: Minimal Read-Only                                  │ │ │
│ │ │  ├── Parse manifest.json                               │ │ │
│ │ │  ├── Read all index shards                             │ │ │
│ │ │  ├── Iterate file entries                              │ │ │
│ │ │  ├── Validate format_version compatibility             │ │ │
│ │ │  └── Handle unknown fields gracefully                  │ │ │
│ │ └────────────────────────────────────────────────────────┘ │ │
│ └────────────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────┘
```

## Traceability Matrix

| Requirement | Manifest Schema | Shard Schema | Extension Schema | SDK Function |
|-------------|-----------------|--------------|------------------|--------------|
| REQ-L1-001  | `format_version` | - | - | `validateVersion()` |
| REQ-L1-002  | `shard_list` | `shard_id` | - | `loadShards()` |
| REQ-L2-001  | `hash_algo` | `entries_hash` | - | `verifyShardHash()` |
| REQ-L2-002  | `pack_hash` | - | - | `verifySidecar()` |
| REQ-L3-001  | `ids` | `ids` | - | `resolveNamespace()` |
| REQ-L3-002  | - | `assembly` | - | `buildAssemblyTree()` |

## Related Documents

- [../README.md](../README.md) - MeshPack Definition Specification
- [../../EXTENSIONS.md](../../EXTENSIONS.md) - Extension Namespace Guidelines
- [../../schema/](../../schema/) - JSON Schema definitions
