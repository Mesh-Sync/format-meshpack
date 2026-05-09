# Release Checklist

1. Update `VERSION` and [CHANGELOG.md](../CHANGELOG.md).
2. Confirm schema `$id` values use the matching `<major>.<minor>` URL base.
3. Run `just clean` and `just publish-dry-run` locally.
4. Run `just determinism-check` and confirm no generated source drift.
5. Validate public fixture archives with `python3 tools/meshpack_validate.py <file> --schema-mode strict` for representative L1/L2/L3 samples.
6. Review [docs/CONFORMANCE_MATRIX.md](CONFORMANCE_MATRIX.md) and [docs/REQUIREMENT_COVERAGE.md](REQUIREMENT_COVERAGE.md) for any claim changes, especially BLAKE3, sidecar/signature coverage, and L3 ecosystem responsibilities.
7. Confirm [tests/sdk_validation_vectors.json](../tests/sdk_validation_vectors.json) still runs through generated Python, Rust, TypeScript, and Java 17 tests.
8. Review public samples for privacy: no `creator_info.email`, no secrets, and sidecar `pack_size_bytes` equals the archive byte size rather than `manifest.index_summary.total_size_bytes`.
9. Publish versioned schemas and [schema/catalog.json](../schema/catalog.json) to the public schema host.
10. Create and sign tag `vX.Y.Z` from the release commit.
11. Let CI publish Python, npm, and Cargo packages. Java 17 is packaged and attested, but Maven Central deployment is intentionally disabled until credentials and namespace verification are complete.
12. Download CI artifacts and verify SBOM/provenance attestations are present.
13. Verify fresh installs for Python, Rust, TypeScript, and Java package artifacts.
14. If release verification fails, delete/mark failed artifacts where registries allow it, publish a patch release, and document the rollback in the changelog.
