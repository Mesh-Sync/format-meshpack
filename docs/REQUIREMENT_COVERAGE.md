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