# Requirement Coverage

The machine-readable coverage map is [tests/requirement_coverage.json](../tests/requirement_coverage.json). It is checked by [tests/test_requirement_traceability.py](../tests/test_requirement_traceability.py) so every documented MUST requirement has either automated evidence or an explicit non-test rationale.

Coverage statuses:

| Status | Meaning |
|--------|---------|
| `tested` | Covered by pytest requirement markers in the conformance suite. |
| `schema-backed` | Enforced by canonical JSON Schema or schema-driven generated models. |
| `generator-backed` | Implemented in generated SDK helpers/templates and guarded by generator tests. |
| `ecosystem-responsibility` | Required of MeshSync backend/viewer/importer implementations outside this standard package. |
| `scale-manual` | Requires large or long-running scale fixtures outside the default release gate. |

This map is intentionally conservative: it prevents public release notes from implying full L3 ecosystem compliance where this repository only defines schemas, generated SDK helpers, or validator behavior.

## Coverage Map

| Requirement | Status | Evidence | Rationale |
|-------------|--------|----------|-----------|
| REQ-L1-001 | `tested` | `tests/conformance/test_l1_minimal.py` |  |
| REQ-L1-002 | `tested` | `tests/conformance/test_l1_minimal.py` |  |
| REQ-L1-003 | `tested` | `tests/conformance/test_l1_minimal.py`, `tests/conformance/test_l2_standard.py` |  |
| REQ-L1-010 | `tested` | `tests/conformance/test_l1_minimal.py`, `tests/conformance/test_l2_standard.py` |  |
| REQ-L1-011 | `tested` | `tests/conformance/test_l1_minimal.py` |  |
| REQ-L1-012 | `tested` | `tests/conformance/test_l1_minimal.py` |  |
| REQ-L1-013 | `tested` | `tests/conformance/test_l1_minimal.py` |  |
| REQ-L1-020 | `tested` | `tests/conformance/test_l2_standard.py` |  |
| REQ-L1-041 | `tested` | `tests/conformance/test_l1_minimal.py` |  |
| REQ-L2-000 | `tested` | `tests/conformance/test_l2_standard.py` |  |
| REQ-L2-001 | `tested` | `tests/conformance/test_l2_standard.py` |  |
| REQ-L2-002 | `tested` | `tests/conformance/test_l2_standard.py` |  |
| REQ-L2-003 | `tested` | `tests/conformance/test_l2_standard.py` |  |
| REQ-L2-004 | `schema-backed` | `schema/shard.schema.json`, `tests/conformance/test_l1_minimal.py` | The schemas and L1 entry-field tests enforce FileEntry shape; source-filesystem population is a writer responsibility outside the reference validator. |
| REQ-L2-010 | `tested` | `tests/conformance/test_l2_standard.py`, `tests/sdk_validation_vectors.json` |  |
| REQ-L2-011 | `tested` | `tests/conformance/test_l2_standard.py` |  |
| REQ-L2-012 | `tested` | `tests/conformance/test_l2_standard.py`, `tests/conformance/test_l3_full.py` |  |
| REQ-L2-013 | `tested` | `tests/conformance/test_l1_minimal.py`, `tests/conformance/test_l2_standard.py` |  |
| REQ-L2-020 | `tested` | `tests/conformance/test_l2_standard.py` |  |
| REQ-L2-021 | `tested` | `tests/conformance/test_l2_standard.py` |  |
| REQ-L2-030 | `schema-backed` | `schema/shard.schema.json`, `tests/conformance/test_l1_minimal.py` | The standard schemas and path-safety tests reject non-portable paths; OS-specific extraction behavior is implementation-specific. |
| REQ-L2-060 | `tested` | `tests/conformance/test_l2_standard.py` |  |
| REQ-L3-001 | `schema-backed` | `schema/manifest.schema.json`, `schema/shard.schema.json` | Namespaced identifiers are represented in canonical schemas; identity reconciliation behavior belongs to consumers. |
| REQ-L3-002 | `ecosystem-responsibility` | `definition/requirements/L3-full.md` | Namespace lookup APIs are required of consuming implementations, not of this schema and validator package. |
| REQ-L3-003 | `tested` | `tests/conformance/test_l3_full.py` |  |
| REQ-L3-010 | `schema-backed` | `schema/shard.schema.json` | Metamodel fields and enums are represented in the shard schema; grouping reconstruction is a consuming implementation concern. |
| REQ-L3-011 | `schema-backed` | `schema/shard.schema.json` | Assembly graph fields are represented in the shard schema; transform rendering and application are implementation concerns. |
| REQ-L3-012 | `ecosystem-responsibility` | `definition/requirements/L3-full.md` | Assembly tree APIs are required of viewers/importers and are outside this format validator package. |
| REQ-L3-020 | `tested` | `tests/conformance/test_l3_full.py` |  |
| REQ-L3-021 | `ecosystem-responsibility` | `definition/requirements/L3-full.md` | Delta merge APIs require base-pack state management and are outside this validator and SDK generation package. |
| REQ-L3-022 | `tested` | `tests/conformance/test_l3_full.py` |  |
| REQ-L3-030 | `tested` | `tests/conformance/test_l3_full.py` |  |
| REQ-L3-031 | `tested` | `tests/conformance/test_l3_full.py` |  |
| REQ-L3-040 | `tested` | `tests/conformance/test_l2_standard.py` |  |
| REQ-L3-041 | `generator-backed` | `generators/templates/python/extensions.py.j2`, `generators/templates/typescript/index.ts.j2` | Generated SDK extension helpers select versioned extension payloads; full per-application version policy remains consumer-specific. |
| REQ-L3-042 | `tested` | `tests/conformance/test_l3_full.py` |  |
| REQ-L3-060 | `ecosystem-responsibility` | `definition/requirements/L3-full.md` | Backend export completeness requires MeshSync backend data and is validated in backend integration suites, not this standard package. |
| REQ-L3-061 | `ecosystem-responsibility` | `definition/requirements/L3-full.md`, `schema/common.schema.json` | Import conflict behavior is executed by backend importers; this repository defines the import_policy schema values. |
| REQ-L3-070 | `scale-manual` | `definition/requirements/L3-full.md`, `docs/RELEASE.md` | Large archive and ZIP64 behavior requires long-running scale fixtures that are not part of the default public release gate. |