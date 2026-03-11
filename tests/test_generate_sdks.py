"""Tests for SDK generation: extension type extraction and number type handling."""

import os
import sys
import json
import pytest

# Add generators/ to path so we can import generate_sdks
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'generators'))

from generate_sdks import (
    get_type_info,
    snake_to_pascal,
    extract_extension_models,
    load_extension_schemas,
)


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
