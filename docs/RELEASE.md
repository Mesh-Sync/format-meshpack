# Release Checklist

1. Update `VERSION` and [CHANGELOG.md](../CHANGELOG.md).
2. Confirm schema `$id` values use the matching `<major>.<minor>` URL base.
3. Run `just clean` and `just publish-dry-run` locally.
4. Run `just determinism-check` and confirm no generated source drift.
5. Validate public fixture archives with `python3 tools/meshpack_validate.py <file> --schema-mode strict` for representative L1/L2/L3 samples.
6. Review [docs/CONFORMANCE_MATRIX.md](CONFORMANCE_MATRIX.md) for any claim changes, especially BLAKE3 and sidecar/signature coverage.
7. Publish versioned schemas and [schema/catalog.json](../schema/catalog.json) to the public schema host.
8. Create and sign tag `vX.Y.Z` from the release commit.
9. Let CI publish Python, npm, and Cargo packages. Java 17 is packaged and attested, but Maven Central deployment is intentionally disabled until credentials and namespace verification are complete.
10. Download CI artifacts and verify SBOM/provenance attestations are present.
11. Verify fresh installs for Python, Rust, TypeScript, and Java package artifacts.
12. If release verification fails, delete/mark failed artifacts where registries allow it, publish a patch release, and document the rollback in the changelog.
