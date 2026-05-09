"""Tests for SDK generation: extension type extraction and number type handling."""

import os
import sys
import json
import pytest

# Add generators/ to path so we can import generate_sdks
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'generators'))

from generate_sdks import (
    audit_generator_inputs,
    clean_generated_sdks,
    get_type_info,
    snake_to_pascal,
    extract_extension_models,
    load_extension_schemas,
    load_sdk_validation_vectors,
    load_version,
    MODEL_OUTPUTS,
)


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


# ---- get_type_info tests ----


class TestGetTypeInfoNumber:
    """Verify that JSON Schema 'number' type is handled correctly."""

    def test_number_returns_primitive(self):
        result = get_type_info({"type": "number"}, "score")
        assert result["base"] == "number"
        assert result["is_primitive"] is True

    def test_number_in_array_items(self):
        result = get_type_info(
            {"type": "array", "items": {"type": "number"}},
            "coordinates",
        )
        assert result["is_array"] is True
        assert result["item_type"]["base"] == "number"

    def test_integer_still_works(self):
        result = get_type_info({"type": "integer"}, "count")
        assert result["base"] == "integer"
        assert result["is_primitive"] is True


# ---- snake_to_pascal tests ----


class TestSnakeToPascal:
    def test_single_word(self):
        assert snake_to_pascal("geometry") == "Geometry"

    def test_snake_case(self):
        assert snake_to_pascal("file_entry") == "FileEntry"

    def test_already_pascal(self):
        assert snake_to_pascal("FileEntry") == "FileEntry"

    def test_abbreviation(self):
        assert snake_to_pascal("fdm") == "Fdm"


# ---- extract_extension_models tests ----


class TestExtractExtensionModels:
    """Verify typed model extraction from extension version schemas."""

    def test_simple_extension_produces_one_model(self):
        """A flat extension (no nested objects) should produce exactly one root model."""
        version_schema = {
            "type": "object",
            "properties": {
                "vertex_count": {"type": "integer", "minimum": 0},
                "is_manifold": {"type": "boolean"},
                "surface_area_mm2": {"type": "number", "minimum": 0},
            },
        }
        models = extract_extension_models(version_schema, "meshsync_geometry", "v1")

        assert len(models) == 1
        root = models[0]
        assert root["name"] == "GeometryV1"
        assert root["is_root"] is True

        field_names = [f["name"] for f in root["fields"]]
        assert "vertex_count" in field_names
        assert "is_manifold" in field_names
        assert "surface_area_mm2" in field_names

    def test_field_types_are_correct(self):
        version_schema = {
            "type": "object",
            "properties": {
                "count": {"type": "integer"},
                "ratio": {"type": "number"},
                "flag": {"type": "boolean"},
                "name": {"type": "string"},
            },
        }
        models = extract_extension_models(version_schema, "meshsync_test", "v1")
        root = models[0]
        fields_by_name = {f["name"]: f for f in root["fields"]}

        assert fields_by_name["count"]["type"]["base"] == "integer"
        assert fields_by_name["ratio"]["type"]["base"] == "number"
        assert fields_by_name["flag"]["type"]["base"] == "boolean"
        assert fields_by_name["name"]["type"]["base"] == "string"

    def test_nested_objects_produce_sub_models(self):
        """Nested objects (like fdm in printability) should create sub-model classes."""
        version_schema = {
            "type": "object",
            "properties": {
                "score": {"type": "number"},
                "fdm": {
                    "type": "object",
                    "properties": {
                        "print_time": {"type": "number"},
                        "has_bridging": {"type": "boolean"},
                    },
                },
            },
        }
        models = extract_extension_models(version_schema, "meshsync_printability", "v1")

        # Should have 2 models: sub-model first, root model last
        assert len(models) == 2

        sub_model = models[0]
        assert sub_model["name"] == "PrintabilityV1Fdm"
        assert sub_model["is_root"] is False
        sub_fields = {f["name"] for f in sub_model["fields"]}
        assert "print_time" in sub_fields
        assert "has_bridging" in sub_fields

        root = models[1]
        assert root["name"] == "PrintabilityV1"
        assert root["is_root"] is True
        # The fdm field should reference the sub-model
        fdm_field = [f for f in root["fields"] if f["name"] == "fdm"][0]
        assert fdm_field["type"]["base"] == "PrintabilityV1Fdm"
        assert fdm_field["type"].get("is_inline_class") is True

    def test_array_fields(self):
        version_schema = {
            "type": "object",
            "properties": {
                "materials": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "coordinates": {
                    "type": "array",
                    "items": {"type": "number"},
                },
            },
        }
        models = extract_extension_models(version_schema, "meshsync_deps", "v1")
        root = models[0]
        fields_by_name = {f["name"]: f for f in root["fields"]}

        mat = fields_by_name["materials"]["type"]
        assert mat["is_array"] is True
        assert mat["item_type"]["base"] == "string"

        coords = fields_by_name["coordinates"]["type"]
        assert coords["is_array"] is True
        assert coords["item_type"]["base"] == "number"

    def test_all_fields_optional_when_no_required(self):
        """Extension fields should be optional when no 'required' list is present."""
        version_schema = {
            "type": "object",
            "properties": {
                "a": {"type": "integer"},
                "b": {"type": "string"},
            },
        }
        models = extract_extension_models(version_schema, "meshsync_test", "v1")
        for field in models[0]["fields"]:
            assert field["required"] is False

    def test_naming_convention_v2(self):
        """Version names other than v1 should produce correct class names."""
        version_schema = {
            "type": "object",
            "properties": {"x": {"type": "integer"}},
        }
        models = extract_extension_models(version_schema, "meshsync_geometry", "v2")
        assert models[0]["name"] == "GeometryV2"

    def test_reserved_json_field_names_get_safe_language_identifiers(self):
        """JSON names stay intact while Rust/Java avoid reserved keywords."""
        version_schema = {
            "type": "object",
            "properties": {"static": {"type": "string"}},
        }
        models = extract_extension_models(version_schema, "meshsync_thumbnails", "v1")
        field = models[0]["fields"][0]

        assert field["name"] == "static"
        assert field["rust_name"] == "static_"
        assert field["java_name"] == "static_"


# ---- load_extension_schemas tests ----


class TestLoadExtensionSchemas:
    """Verify that load_extension_schemas produces version_models."""

    def test_returns_version_models_key(self):
        extensions = load_extension_schemas()
        # Should find at least the three known extensions
        assert len(extensions) >= 3
        for ext in extensions:
            assert "version_models" in ext
            assert "versions" in ext
            for v in ext["versions"]:
                assert v in ext["version_models"]
                models = ext["version_models"][v]
                assert len(models) >= 1
                # Last model should be root
                assert models[-1]["is_root"] is True

    def test_geometry_v1_has_expected_fields(self):
        extensions = load_extension_schemas()
        geo = [e for e in extensions if e["name"] == "meshsync_geometry"][0]
        root = geo["version_models"]["v1"][-1]
        field_names = {f["name"] for f in root["fields"]}
        assert "vertex_count" in field_names
        assert "face_count" in field_names
        assert "is_manifold" in field_names
        assert "surface_area_mm2" in field_names

    def test_printability_v1_has_sub_models(self):
        extensions = load_extension_schemas()
        p = [e for e in extensions if e["name"] == "meshsync_printability"][0]
        models = p["version_models"]["v1"]
        model_names = [m["name"] for m in models]
        assert "PrintabilityV1" in model_names
        assert "PrintabilityV1Fdm" in model_names
        assert "PrintabilityV1Sla" in model_names
        assert "PrintabilityV1Sls" in model_names
        assert "PrintabilityV1Mjf" in model_names

    def test_dependencies_v1_has_array_fields(self):
        extensions = load_extension_schemas()
        dep = [e for e in extensions if e["name"] == "meshsync_dependencies"][0]
        root = dep["version_models"]["v1"][-1]
        fields_by_name = {f["name"]: f for f in root["fields"]}
        assert fields_by_name["materials"]["type"]["is_array"] is True
        assert fields_by_name["textures"]["type"]["is_array"] is True
        assert fields_by_name["references"]["type"]["is_array"] is True

    def test_deterministic_order(self):
        """Extensions should be sorted by filename for deterministic output."""
        extensions = load_extension_schemas()
        names = [e["name"] for e in extensions]
        assert names == sorted(names)


class TestGenerationReleaseReadiness:
    def test_version_file_is_single_source(self):
        assert load_version() == "2.0.0"

    def test_load_version_rejects_invalid_semver(self, tmp_path):
        version_file = tmp_path / "VERSION"
        version_file.write_text("not-a-version\n", encoding="utf-8")

        with pytest.raises(ValueError):
            load_version(str(version_file))

    @pytest.mark.parametrize("version", ["2.0.0-rc.1", "2.0.0+build.1"])
    def test_load_version_rejects_non_canonical_format_versions(self, tmp_path, version):
        version_file = tmp_path / "VERSION"
        version_file.write_text(version + "\n", encoding="utf-8")

        with pytest.raises(ValueError, match="Invalid MeshPack format version"):
            load_version(str(version_file))

    def test_sdk_validation_vectors_are_loaded_for_generated_tests(self):
        vectors = load_sdk_validation_vectors()

        ids = {vector["id"] for vector in vectors["vectors"]}

        assert "jcs-utf16-key-order" in ids
        assert all("entry_json" in vector for vector in vectors["vectors"])

    def test_generator_schema_audit_accepts_current_schemas(self):
        audit_generator_inputs()

    def test_generator_schema_audit_rejects_broken_refs(self, tmp_path):
        schema_dir = tmp_path / "schema"
        extensions_dir = schema_dir / "extensions"
        schema_dir.mkdir()
        extensions_dir.mkdir()
        (schema_dir / "broken.schema.json").write_text(
            json.dumps({"$schema": "http://json-schema.org/draft-07/schema#", "$ref": "missing.schema.json#/definitions/item"}),
            encoding="utf-8",
        )

        with pytest.raises(ValueError, match="Generator schema audit failed"):
            audit_generator_inputs(str(schema_dir), str(extensions_dir))

    def test_clean_generated_sdks_removes_stale_files(self, tmp_path):
        output_dir = tmp_path / "generated" / "sdks"
        stale_file = output_dir / "typescript" / "stale.js"
        stale_file.parent.mkdir(parents=True)
        stale_file.write_text("stale", encoding="utf-8")

        clean_generated_sdks(str(output_dir))

        assert output_dir.exists()
        assert not stale_file.exists()

    def test_typescript_template_has_explicit_root_dir(self):
        with open(
            os.path.join(REPO_ROOT, "generators", "templates", "typescript", "tsconfig.json.j2"),
            "r",
            encoding="utf-8",
        ) as template:
            contents = template.read()

        assert '"rootDir": "./src"' in contents

    @pytest.mark.parametrize(
        "template_path",
        [
            ("python", "README.md.j2"),
            ("rust", "Cargo.toml.j2"),
            ("rust", "README.md.j2"),
            ("typescript", "package.json.j2"),
            ("typescript", "README.md.j2"),
            ("java", "pom.xml.j2"),
            ("java", "README.md.j2"),
        ],
    )
    def test_package_metadata_is_templated(self, template_path):
        path = os.path.join(REPO_ROOT, "generators", "templates", *template_path)
        assert os.path.exists(path)

    def test_generator_no_longer_embeds_package_metadata(self):
        with open(
            os.path.join(REPO_ROOT, "generators", "generate_sdks.py"),
            "r",
            encoding="utf-8",
        ) as generator:
            contents = generator.read()

        assert 'name = "meshpack"' not in contents
        assert '"name": "@mesh-sync/meshpack"' not in contents
        assert "<artifactId>meshpack</artifactId>" not in contents

    def test_java_template_maps_wire_enums_and_ignores_unknown_fields(self):
        with open(
            os.path.join(REPO_ROOT, "generators", "templates", "java", "MeshPack.java.j2"),
            "r",
            encoding="utf-8",
        ) as template:
            contents = template.read()

        assert "@JsonCreator" in contents
        assert "@JsonValue" in contents
        assert "@JsonIgnoreProperties(ignoreUnknown = true)" in contents

    @pytest.mark.parametrize(
        ("template_path", "markers"),
        [
            (
                ("python", "models.py.j2"),
                ["class ValidationFinding", "def validate_meshpack"],
            ),
            (
                ("typescript", "index.ts.j2"),
                ["export interface MeshPackValidationFinding", "export async function validateMeshPack"],
            ),
            (
                ("rust", "lib.rs.j2"),
                ["pub struct ValidationFinding", "pub fn validate_meshpack"],
            ),
            (
                ("java", "MeshPack.java.j2"),
                ["public record ValidationFinding", "public static ValidationResult validate"],
            ),
        ],
    )
    def test_sdk_templates_expose_validator_api(self, template_path, markers):
        with open(
            os.path.join(REPO_ROOT, "generators", "templates", *template_path),
            "r",
            encoding="utf-8",
        ) as template:
            contents = template.read()

        for marker in markers:
            assert marker in contents

    @pytest.mark.parametrize(
        ("template_path", "markers"),
        [
            (
                ("python", "models.py.j2"),
                ["RESOURCE_REF_PATTERN", "def _check_resource_ref", "def _is_safe_resource_ref"],
            ),
            (
                ("typescript", "index.ts.j2"),
                ["RESOURCE_REF_PATTERN", "function validateResourceRef", "Unsafe or non-canonical resource name"],
            ),
            (
                ("rust", "lib.rs.j2"),
                ["fn is_safe_resource_ref", "fn validate_resource_ref", "RES-004"],
            ),
            (
                ("java", "MeshPack.java.j2"),
                ["RESOURCE_REF_PATTERN", "validateResourceRef", "RES-004"],
            ),
        ],
    )
    def test_sdk_templates_enforce_resource_ref_safety(self, template_path, markers):
        with open(
            os.path.join(REPO_ROOT, "generators", "templates", *template_path),
            "r",
            encoding="utf-8",
        ) as template:
            contents = template.read()

        for marker in markers:
            assert marker in contents

    @pytest.mark.parametrize(
        ("template_path", "markers"),
        [
            (
                ("python", "models.py.j2"),
                ["def _check_sidecar", "SDC-010", "def _verify_signature_entries"],
            ),
            (
                ("typescript", "index.ts.j2"),
                ["validateSidecar", "SDC-010", "verifySignatureEntries"],
            ),
            (
                ("rust", "lib.rs.j2"),
                ["verify_sidecar", "SDC-010", "verify_signature_entries"],
            ),
            (
                ("java", "MeshPack.java.j2"),
                ["verifySidecar", "SDC-010", "verifySignatureEntries"],
            ),
        ],
    )
    def test_sdk_templates_verify_sidecar_integrity(self, template_path, markers):
        with open(
            os.path.join(REPO_ROOT, "generators", "templates", *template_path),
            "r",
            encoding="utf-8",
        ) as template:
            contents = template.read()

        for marker in markers:
            assert marker in contents

    @pytest.mark.parametrize(
        "template_path",
        [
            ("typescript", "index.test.ts.j2"),
            ("rust", "lib.rs.j2"),
            ("java", "MeshPackTest.java.j2"),
        ],
    )
    def test_sdk_templates_consume_shared_validation_vectors(self, template_path):
        with open(
            os.path.join(REPO_ROOT, "generators", "templates", *template_path),
            "r",
            encoding="utf-8",
        ) as template:
            contents = template.read()

        assert "jcs-utf16-key-order" in contents
        assert "JCS_UTF16_VECTOR_ENTRIES_HASH" in contents


class TestJavaSdkTarget:
    """Verify the generator declares the required Java 17 SDK output target."""

    def test_java_output_target_exists(self):
        java_outputs = [path for path in MODEL_OUTPUTS if "generated/sdks/java" in path]
        assert java_outputs, "Java SDK output directory must be part of SDK generation"
