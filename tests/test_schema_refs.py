"""
Tests for schema $ref consistency — verifies that manifest, shard, and sidecar
schemas reference common.schema.json definitions via $ref instead of inlining them.

This prevents definition drift (Issue #10) by ensuring a single source of truth
for shared types like hashAlgorithm, hashValue, signatureEntry, etc.
"""

import json
from pathlib import Path

import pytest

SCHEMA_DIR = Path(__file__).resolve().parent.parent / "schema"
REPO_DIR = SCHEMA_DIR.parent

COMMON_REF_PREFIX = "common.schema.json#/definitions/"
SCHEMA_ID_BASE = "https://meshsync.net/schemas/meshpack/1.1/"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def common_schema():
    with open(SCHEMA_DIR / "common.schema.json") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def manifest_schema():
    with open(SCHEMA_DIR / "manifest.schema.json") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def shard_schema():
    with open(SCHEMA_DIR / "shard.schema.json") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def sidecar_schema():
    with open(SCHEMA_DIR / "sidecar.schema.json") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _collect_refs(schema, path=""):
    """Recursively collect all $ref values from a schema, with their JSON path."""
    refs = []
    if isinstance(schema, dict):
        if "$ref" in schema:
            refs.append((path, schema["$ref"]))
        for key, val in schema.items():
            if key == "$ref":
                continue
            refs.extend(_collect_refs(val, f"{path}/{key}"))
    elif isinstance(schema, list):
        for i, item in enumerate(schema):
            refs.extend(_collect_refs(item, f"{path}[{i}]"))
    return refs


def _collect_common_refs(schema):
    """Return only $refs pointing to common.schema.json."""
    return [
        (path, ref) for path, ref in _collect_refs(schema)
        if ref.startswith(COMMON_REF_PREFIX)
    ]


def _referenced_def_names(schema):
    """Return the set of common definition names referenced by the schema."""
    return {ref.split("/")[-1] for _, ref in _collect_common_refs(schema)}


# ---------------------------------------------------------------------------
# Tests: common.schema.json has all expected definitions
# ---------------------------------------------------------------------------

class TestCommonDefinitions:
    """common.schema.json must define all shared types."""

    EXPECTED_DEFINITIONS = {
        "hashAlgorithm",
        "hashValue",
        "semver",
        "namespacedId",
        "signatureEntry",
        "importPolicy",
        "creatorInfo",
        "platformInfo",
        "shardReference",
        "metamodelRole",
        "assemblyRole",
        "units",
        "upAxis",
        "deltaOperation",
        "spdxLicense",
    }

    def test_all_expected_definitions_present(self, common_schema):
        actual = set(common_schema.get("definitions", {}).keys())
        missing = self.EXPECTED_DEFINITIONS - actual
        assert not missing, f"common.schema.json missing definitions: {missing}"


class TestSchemaIds:
    def test_core_schema_ids_are_versioned(self):
        for schema_path in sorted(SCHEMA_DIR.glob("*.schema.json")):
            data = json.loads(schema_path.read_text(encoding="utf-8"))
            assert data["$id"].startswith(SCHEMA_ID_BASE)
            assert data["$id"].endswith(f"/{schema_path.name}")

    def test_extension_schema_ids_are_versioned(self):
        for schema_path in sorted((SCHEMA_DIR / "extensions").glob("*.schema.json")):
            data = json.loads(schema_path.read_text(encoding="utf-8"))
            assert data["$id"].startswith(f"{SCHEMA_ID_BASE}extensions/")
            assert data["$id"].endswith(f"/{schema_path.name}")

    def test_catalog_matches_version_file(self):
        catalog = json.loads((SCHEMA_DIR / "catalog.json").read_text(encoding="utf-8"))
        version = (REPO_DIR / "VERSION").read_text(encoding="utf-8").strip()

        assert catalog["format_version"] == version
        assert catalog["schemas"]["manifest"] == f"{SCHEMA_ID_BASE}manifest.schema.json"


# ---------------------------------------------------------------------------
# Tests: $refs resolve to valid definitions
# ---------------------------------------------------------------------------

class TestRefsResolve:
    """Every $ref to common.schema.json must point to an existing definition."""

    @pytest.mark.parametrize("schema_name", ["manifest", "shard", "sidecar"])
    def test_all_common_refs_resolve(
        self, schema_name, common_schema,
        manifest_schema, shard_schema, sidecar_schema,
    ):
        schemas = {
            "manifest": manifest_schema,
            "shard": shard_schema,
            "sidecar": sidecar_schema,
        }
        schema = schemas[schema_name]
        common_defs = set(common_schema.get("definitions", {}).keys())

        for path, ref in _collect_common_refs(schema):
            def_name = ref.split("/")[-1]
            assert def_name in common_defs, (
                f"{schema_name}.schema.json at {path}: "
                f"$ref '{ref}' points to undefined definition '{def_name}'"
            )


# ---------------------------------------------------------------------------
# Tests: schemas use $ref instead of inlining
# ---------------------------------------------------------------------------

class TestManifestRefs:
    """manifest.schema.json must use $ref for all shared definitions."""

    EXPECTED_REFS = {
        "semver",
        "creatorInfo",
        "spdxLicense",
        "platformInfo",
        "hashAlgorithm",
        "hashValue",
        "signatureEntry",
        "shardReference",
        "namespacedId",
        "importPolicy",
    }

    def test_manifest_references_common_definitions(self, manifest_schema):
        ref_defs = _referenced_def_names(manifest_schema)
        missing = self.EXPECTED_REFS - ref_defs
        assert not missing, (
            f"manifest.schema.json should $ref these common definitions "
            f"but inlines them instead: {missing}"
        )


class TestShardRefs:
    """shard.schema.json must use $ref for all shared definitions."""

    EXPECTED_REFS = {
        "semver",
        "hashValue",
        "namespacedId",
        "units",
        "upAxis",
        "metamodelRole",
        "assemblyRole",
        "deltaOperation",
    }

    def test_shard_references_common_definitions(self, shard_schema):
        ref_defs = _referenced_def_names(shard_schema)
        missing = self.EXPECTED_REFS - ref_defs
        assert not missing, (
            f"shard.schema.json should $ref these common definitions "
            f"but inlines them instead: {missing}"
        )


class TestSidecarRefs:
    """sidecar.schema.json must use $ref for all shared definitions."""

    EXPECTED_REFS = {
        "hashAlgorithm",
        "hashValue",
        "signatureEntry",
    }

    def test_sidecar_references_common_definitions(self, sidecar_schema):
        ref_defs = _referenced_def_names(sidecar_schema)
        missing = self.EXPECTED_REFS - ref_defs
        assert not missing, (
            f"sidecar.schema.json should $ref these common definitions "
            f"but inlines them instead: {missing}"
        )


# ---------------------------------------------------------------------------
# Tests: SDK generator ref resolution
# ---------------------------------------------------------------------------

class TestGeneratorRefResolution:
    """The SDK generator must correctly resolve $ref to common definitions."""

    def test_resolve_bare_ref(self, common_schema):
        """Direct $ref should be replaced with the referenced definition."""
        import sys
        sys.path.insert(0, str(SCHEMA_DIR.parent / "generators"))
        from generate_sdks import resolve_common_refs

        common_defs = common_schema["definitions"]
        schema = {"$ref": "common.schema.json#/definitions/hashAlgorithm"}
        resolved = resolve_common_refs(schema, common_defs)

        assert resolved.get("type") == "string"
        assert resolved.get("enum") == ["sha256", "sha512", "blake3"]
        assert "$ref" not in resolved

    def test_resolve_allof_ref(self, common_schema):
        """allOf wrapping a single $ref with sibling description."""
        import sys
        sys.path.insert(0, str(SCHEMA_DIR.parent / "generators"))
        from generate_sdks import resolve_common_refs

        common_defs = common_schema["definitions"]
        schema = {
            "allOf": [{"$ref": "common.schema.json#/definitions/hashAlgorithm"}],
            "description": "Custom description here",
        }
        resolved = resolve_common_refs(schema, common_defs)

        assert resolved.get("type") == "string"
        assert resolved.get("enum") == ["sha256", "sha512", "blake3"]
        # Sibling description must override the common definition's description
        assert resolved["description"] == "Custom description here"
        assert "allOf" not in resolved

    def test_internal_ref_preserved(self, common_schema):
        """Internal refs (e.g., #/definitions/fileEntry) must stay untouched."""
        import sys
        sys.path.insert(0, str(SCHEMA_DIR.parent / "generators"))
        from generate_sdks import resolve_common_refs

        common_defs = common_schema["definitions"]
        schema = {"$ref": "#/definitions/fileEntry"}
        resolved = resolve_common_refs(schema, common_defs)

        assert resolved == {"$ref": "#/definitions/fileEntry"}

    def test_nested_refs_resolved(self, common_schema):
        """$refs nested in properties/items should also be resolved."""
        import sys
        sys.path.insert(0, str(SCHEMA_DIR.parent / "generators"))
        from generate_sdks import resolve_common_refs

        common_defs = common_schema["definitions"]
        schema = {
            "type": "array",
            "items": {
                "$ref": "common.schema.json#/definitions/signatureEntry",
            },
        }
        resolved = resolve_common_refs(schema, common_defs)

        assert resolved["type"] == "array"
        assert resolved["items"].get("type") == "object"
        assert "alg" in resolved["items"]["properties"]
        assert "$ref" not in resolved["items"]
