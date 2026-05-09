import copy
import json
import os
import re
import shutil
from typing import Any, Dict, Iterable, List, Optional, Tuple

from jinja2 import Environment, FileSystemLoader


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.dirname(BASE_DIR)
VERSION_FILE = os.path.join(REPO_DIR, "VERSION")
SDK_VALIDATION_VECTORS_FILE = os.path.join(REPO_DIR, "tests", "sdk_validation_vectors.json")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
OUTPUT_DIR = os.path.join(REPO_DIR, "generated", "sdks")
SCHEMA_DIR = os.path.join(REPO_DIR, "schema")
EXTENSIONS_DIR = os.path.join(SCHEMA_DIR, "extensions")

MODEL_OUTPUTS = [
    os.path.join(OUTPUT_DIR, "python", "meshpack"),
    os.path.join(OUTPUT_DIR, "rust", "meshpack", "src"),
    os.path.join(OUTPUT_DIR, "typescript", "src"),
    os.path.join(
        OUTPUT_DIR,
        "java",
        "meshpack",
        "src",
        "main",
        "java",
        "net",
        "meshsync",
        "meshpack",
    ),
]

RUST_RESERVED = {
    "as", "break", "const", "continue", "crate", "else", "enum", "extern",
    "false", "fn", "for", "if", "impl", "in", "let", "loop", "match", "mod",
    "move", "mut", "pub", "ref", "return", "self", "Self", "static", "struct",
    "super", "trait", "true", "type", "unsafe", "use", "where", "while", "async",
    "await", "dyn",
}

JAVA_RESERVED = {
    "abstract", "assert", "boolean", "break", "byte", "case", "catch", "char", "class",
    "const", "continue", "default", "do", "double", "else", "enum", "extends", "final",
    "finally", "float", "for", "goto", "if", "implements", "import", "instanceof", "int",
    "interface", "long", "native", "new", "package", "private", "protected", "public",
    "return", "short", "static", "strictfp", "super", "switch", "synchronized", "this",
    "throw", "throws", "transient", "try", "void", "volatile", "while", "true", "false",
    "null", "record", "sealed", "permits", "yield", "var",
}


def load_schema(filename: str) -> Dict[str, Any]:
    with open(os.path.join(SCHEMA_DIR, filename), "r", encoding="utf-8") as schema_file:
        return json.load(schema_file)


def load_version(version_file: str = VERSION_FILE) -> str:
    with open(version_file, "r", encoding="utf-8") as file:
        version = file.read().strip()
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise ValueError(f"Invalid MeshPack format version in {version_file}: {version!r}")
    return version


def load_sdk_validation_vectors(path: str = SDK_VALIDATION_VECTORS_FILE) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as vectors_file:
        data = json.load(vectors_file)

    vectors = []
    for vector in data.get("vectors", []):
        normalized = dict(vector)
        normalized["entry_json"] = json.dumps(
            vector["entry"],
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        )
        vectors.append(normalized)

    return {"version": data.get("version"), "vectors": vectors}


def _schema_pointer_get(schema: Dict[str, Any], pointer: str) -> Any:
    current: Any = schema
    for raw_part in pointer.lstrip("/").split("/") if pointer else []:
        part = raw_part.replace("~1", "/").replace("~0", "~")
        if not isinstance(current, dict) or part not in current:
            raise KeyError(pointer)
        current = current[part]
    return current


def _walk_schema_nodes(node: Any) -> Iterable[Dict[str, Any]]:
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from _walk_schema_nodes(value)
    elif isinstance(node, list):
        for item in node:
            yield from _walk_schema_nodes(item)


def audit_generator_inputs(schema_dir: str = SCHEMA_DIR, extensions_dir: str = EXTENSIONS_DIR) -> None:
    schemas: Dict[str, Dict[str, Any]] = {}

    for filename in sorted(os.listdir(schema_dir)):
        if filename.endswith(".schema.json"):
            schemas[filename] = (
                load_schema(filename)
                if schema_dir == SCHEMA_DIR
                else _load_schema_at(os.path.join(schema_dir, filename))
            )

    if os.path.exists(extensions_dir):
        for filename in sorted(os.listdir(extensions_dir)):
            if filename.endswith(".schema.json"):
                schemas[filename] = _load_schema_at(os.path.join(extensions_dir, filename))

    errors: List[str] = []
    for source_name, schema in schemas.items():
        for node in _walk_schema_nodes(schema):
            ref = node.get("$ref")
            if not isinstance(ref, str):
                continue
            file_part, _, fragment = ref.partition("#")
            target_name = file_part or source_name
            target_schema = schemas.get(target_name)
            if target_schema is None:
                errors.append(f"{source_name}: unresolved schema file in $ref {ref!r}")
                continue
            try:
                _schema_pointer_get(target_schema, fragment)
            except KeyError:
                errors.append(f"{source_name}: unresolved pointer in $ref {ref!r}")

    if errors:
        raise ValueError("Generator schema audit failed:\n" + "\n".join(f"- {error}" for error in errors))


def clean_generated_sdks(output_dir: str = OUTPUT_DIR) -> None:
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)
    os.makedirs(output_dir, exist_ok=True)


def _load_schema_at(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as schema_file:
        return json.load(schema_file)


_common_schema = load_schema("common.schema.json")
_common_definitions = _common_schema.get("definitions", {})


def snake_to_pascal(name: str) -> str:
    """Convert snake_case, kebab-case, or camelCase to PascalCase."""
    if not name:
        return name
    parts = re.split(r"[_\-\s]+", name)
    if len(parts) > 1:
        return "".join(part[:1].upper() + part[1:] for part in parts if part)
    return name[:1].upper() + name[1:]


def _singularize(name: str) -> str:
    if name.endswith("ies") and len(name) > 3:
        return name[:-3] + "y"
    if name.endswith("ses"):
        return name[:-2]
    if name.endswith("s") and not name.endswith("ss"):
        return name[:-1]
    return name


def _extension_prefix(ext_name: str) -> str:
    if ext_name.startswith("meshsync_"):
        ext_name = ext_name[len("meshsync_"):]
    return snake_to_pascal(ext_name)


def _safe_identifier(name: str, reserved: set[str]) -> str:
    safe = re.sub(r"\W", "_", name)
    if not safe or safe[0].isdigit():
        safe = f"_{safe}"
    if safe in reserved:
        safe = f"{safe}_"
    return safe


def _field(name: str, type_info: Dict[str, Any], required: bool) -> Dict[str, Any]:
    return {
        "name": name,
        "rust_name": _safe_identifier(name, RUST_RESERVED),
        "java_name": _safe_identifier(name, JAVA_RESERVED),
        "type": type_info,
        "required": required,
        "nullable": type_info.get("is_optional", False),
    }


def _schema_type(prop: Dict[str, Any]) -> Any:
    schema_type = prop.get("type")
    if isinstance(schema_type, list):
        non_null = [item for item in schema_type if item != "null"]
        return non_null[0] if non_null else "null"
    return schema_type


def _is_nullable(prop: Dict[str, Any]) -> bool:
    schema_type = prop.get("type")
    return isinstance(schema_type, list) and "null" in schema_type


def _merge_schema(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    merged = copy.deepcopy(base)
    for key, value in override.items():
        if key not in {"$ref", "allOf"}:
            merged[key] = copy.deepcopy(value)
    return merged


def _resolve_ref_with_name(
    ref: str,
    local_definitions: Optional[Dict[str, Any]] = None,
) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
    if "#" not in ref:
        return None, None

    file_part, fragment = ref.split("#", 1)
    parts = [part for part in fragment.split("/") if part]
    if len(parts) < 2 or parts[0] != "definitions":
        return None, None

    definition_name = parts[-1]
    if file_part == "common.schema.json":
        return definition_name, copy.deepcopy(_common_definitions.get(definition_name))
    if file_part == "" and local_definitions is not None:
        return definition_name, copy.deepcopy(local_definitions.get(definition_name))
    return None, None


def resolve_ref(ref: str) -> Optional[Dict[str, Any]]:
    """Resolve a cross-file common.schema.json reference."""
    _, schema = _resolve_ref_with_name(ref, None)
    return schema


def resolve_common_refs(schema: Any, common_definitions: Optional[Dict[str, Any]] = None) -> Any:
    """Resolve common.schema.json refs recursively while preserving internal refs."""
    common_definitions = common_definitions or _common_definitions

    if isinstance(schema, list):
        return [resolve_common_refs(item, common_definitions) for item in schema]
    if not isinstance(schema, dict):
        return schema

    if "$ref" in schema and schema["$ref"].startswith("common.schema.json#/definitions/"):
        definition_name = schema["$ref"].split("/")[-1]
        resolved = copy.deepcopy(common_definitions[definition_name])
        return resolve_common_refs(_merge_schema(resolved, schema), common_definitions)

    all_of = schema.get("allOf")
    if (
        isinstance(all_of, list)
        and len(all_of) == 1
        and isinstance(all_of[0], dict)
        and all_of[0].get("$ref", "").startswith("common.schema.json#/definitions/")
    ):
        definition_name = all_of[0]["$ref"].split("/")[-1]
        resolved = copy.deepcopy(common_definitions[definition_name])
        return resolve_common_refs(_merge_schema(resolved, schema), common_definitions)

    return {
        key: resolve_common_refs(value, common_definitions)
        for key, value in schema.items()
    }


def _primitive_type_info(base: str, **extra: Any) -> Dict[str, Any]:
    info = {"base": base, "is_primitive": True}
    info.update(extra)
    return info


def get_type_info(prop: Dict[str, Any], prop_name: str, definitions: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    definitions = definitions or {}
    nullable = _is_nullable(prop)

    all_of = prop.get("allOf")
    if isinstance(all_of, list) and all_of:
        for sub_schema in all_of:
            ref = sub_schema.get("$ref") if isinstance(sub_schema, dict) else None
            if ref:
                ref_name, resolved = _resolve_ref_with_name(ref, definitions)
                if resolved:
                    merged = _merge_schema(resolved, prop)
                    if _schema_type(resolved) == "object" and resolved.get("properties"):
                        return {
                            "base": snake_to_pascal(ref_name or prop_name),
                            "is_ref": True,
                            "ref_name": ref_name,
                            "schema": resolved,
                            "is_optional": nullable,
                        }
                    info = get_type_info(merged, prop_name, definitions)
                    info["is_optional"] = info.get("is_optional", False) or nullable
                    return info

    ref = prop.get("$ref")
    if ref:
        ref_name, resolved = _resolve_ref_with_name(ref, definitions)
        if resolved:
            if _schema_type(resolved) == "object" and resolved.get("properties"):
                return {
                    "base": snake_to_pascal(ref_name or prop_name),
                    "is_ref": True,
                    "ref_name": ref_name,
                    "schema": resolved,
                    "is_optional": nullable,
                }
            info = get_type_info(resolved, prop_name, definitions)
            info["is_optional"] = info.get("is_optional", False) or nullable
            return info
        return {"base": snake_to_pascal(ref.split("/")[-1]), "is_ref": True, "is_optional": nullable}

    schema_type = _schema_type(prop)

    if schema_type == "string":
        if prop_name == "os" and prop.get("enum") == ["linux", "windows", "darwin", "unknown"]:
            return {"base": "OSType", "is_enum": True, "is_optional": nullable}
        fmt = prop.get("format")
        if fmt == "date-time":
            return _primitive_type_info("datetime", is_optional=nullable)
        if fmt == "email":
            return _primitive_type_info("email", is_optional=nullable)
        return _primitive_type_info("string", enum_values=prop.get("enum"), is_optional=nullable)

    if schema_type == "integer":
        return _primitive_type_info("integer", is_optional=nullable)
    if schema_type == "number":
        return _primitive_type_info("number", is_optional=nullable)
    if schema_type == "boolean":
        return _primitive_type_info("boolean", is_optional=nullable)

    if schema_type == "array":
        item_schema = prop.get("items", {})
        item_type = get_type_info(item_schema, _singularize(prop_name), definitions)
        if item_type.get("is_inline_class"):
            item_type["base"] = snake_to_pascal(_singularize(prop_name))
        return {"base": item_type["base"], "is_array": True, "item_type": item_type, "is_optional": nullable}

    if schema_type == "object":
        if "properties" in prop:
            class_name = snake_to_pascal(_singularize(prop_name))
            if prop_name == "attributes":
                class_name = "FileAttributes"
            return {
                "base": class_name,
                "is_inline_class": True,
                "properties": prop["properties"],
                "required_fields": prop.get("required", []),
                "schema": prop,
                "is_optional": nullable,
            }
        return _primitive_type_info("dictionary", is_dictionary=True, is_optional=nullable)

    return _primitive_type_info("unknown", is_optional=nullable)


class ModelRegistry:
    def __init__(self, definitions: Dict[str, Any]) -> None:
        self.definitions = definitions
        self.models: List[Dict[str, Any]] = []
        self._seen: set[str] = set()

    def add_model(self, name: str, schema: Dict[str, Any]) -> None:
        if name in self._seen or not isinstance(schema, dict):
            return
        if _schema_type(schema) != "object" or "properties" not in schema:
            return

        self._seen.add(name)
        required = set(schema.get("required", []))
        fields = []

        for prop_name, prop_schema in schema.get("properties", {}).items():
            type_info = get_type_info(prop_schema, prop_name, self.definitions)
            self._ensure_nested_models(type_info)
            fields.append(_field(prop_name, type_info, prop_name in required))

        self.models.append({"name": name, "fields": fields})

    def _ensure_nested_models(self, type_info: Dict[str, Any]) -> None:
        if type_info.get("is_ref") and type_info.get("schema"):
            self.add_model(type_info["base"], type_info["schema"])
        if type_info.get("is_inline_class") and type_info.get("schema"):
            self.add_model(type_info["base"], type_info["schema"])
        if type_info.get("is_array"):
            item_type = type_info["item_type"]
            if item_type.get("is_ref") and item_type.get("schema"):
                self.add_model(item_type["base"], item_type["schema"])
            if item_type.get("is_inline_class") and item_type.get("schema"):
                self.add_model(item_type["base"], item_type["schema"])


def extract_models(schema_data: Dict[str, Any], root_name: str) -> List[Dict[str, Any]]:
    definitions = schema_data.get("definitions", {})
    registry = ModelRegistry(definitions)
    registry.add_model(root_name, schema_data)
    for definition_name, definition_schema in definitions.items():
        registry.add_model(snake_to_pascal(definition_name), definition_schema)
    return registry.models


def _deduplicate_models(models: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    deduped: Dict[str, Dict[str, Any]] = {}
    for model in models:
        deduped.setdefault(model["name"], model)
    return list(deduped.values())


def render_template(template_path: str, context: Dict[str, Any], output_path: str) -> None:
    env = Environment(loader=FileSystemLoader(TEMPLATES_DIR), trim_blocks=True, lstrip_blocks=True)
    template = env.get_template(template_path)
    output = template.render(context)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as output_file:
        output_file.write(output)
    print(f"Generated: {output_path}")


def extract_extension_models(version_schema: Dict[str, Any], ext_name: str, version_name: str) -> List[Dict[str, Any]]:
    """Extract typed models from one extension version schema.

    Sub-models are emitted before the root model so languages with simple
    forward-reference handling can compile deterministic generated output.
    """
    root_name = _extension_prefix(ext_name) + snake_to_pascal(version_name)
    models: List[Dict[str, Any]] = []

    def process_fields(schema: Dict[str, Any], parent_model_name: str) -> List[Dict[str, Any]]:
        required = set(schema.get("required", []))
        fields = []
        for prop_name, prop_schema in schema.get("properties", {}).items():
            type_info = get_type_info(prop_schema, prop_name)

            if type_info.get("is_inline_class"):
                nested_name = parent_model_name + snake_to_pascal(prop_name)
                type_info["base"] = nested_name
                nested_schema = type_info["schema"]
                models.append({
                    "name": nested_name,
                    "fields": process_fields(nested_schema, nested_name),
                    "is_root": False,
                })
            elif type_info.get("is_array") and type_info["item_type"].get("is_inline_class"):
                nested_name = parent_model_name + snake_to_pascal(_singularize(prop_name))
                type_info["item_type"]["base"] = nested_name
                nested_schema = type_info["item_type"]["schema"]
                models.append({
                    "name": nested_name,
                    "fields": process_fields(nested_schema, nested_name),
                    "is_root": False,
                })

            fields.append(_field(prop_name, type_info, prop_name in required))
        return fields

    root_fields = process_fields(version_schema, root_name)
    models.append({"name": root_name, "fields": root_fields, "is_root": True})
    return models


def extract_extension_version_models(
    ext_name: str,
    version_name: str,
    version_schema: Dict[str, Any],
) -> List[Dict[str, Any]]:
    return extract_extension_models(version_schema, ext_name, version_name)


def load_extension_schemas() -> List[Dict[str, Any]]:
    extensions = []
    if not os.path.exists(EXTENSIONS_DIR):
        return extensions

    for filename in sorted(os.listdir(EXTENSIONS_DIR)):
        if not filename.endswith(".schema.json"):
            continue
        filepath = os.path.join(EXTENSIONS_DIR, filename)
        with open(filepath, "r", encoding="utf-8") as schema_file:
            schema = json.load(schema_file)
        ext_name = filename.replace(".schema.json", "")
        version_models = {
            version_name: extract_extension_models(version_schema, ext_name, version_name)
            for version_name, version_schema in schema.get("properties", {}).items()
        }
        extensions.append({
            "name": ext_name,
            "schema": schema,
            "versions": list(schema.get("properties", {}).keys()),
            "version_models": version_models,
        })
    return extensions


def _write_json(path: str, data: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as output_file:
        json.dump(data, output_file, indent=2)
        output_file.write("\n")
    print(f"Generated: {path}")


def _write_text(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as output_file:
        output_file.write(text)
    print(f"Generated: {path}")


def main() -> None:
    version = load_version()
    audit_generator_inputs()
    clean_generated_sdks()

    schemas = [
        ("Manifest", load_schema("manifest.schema.json")),
        ("Shard", load_schema("shard.schema.json")),
        ("Sidecar", load_schema("sidecar.schema.json")),
    ]

    schema_models: List[Dict[str, Any]] = []
    for root_name, schema in schemas:
        schema_models.extend(extract_models(schema, root_name))

    all_models = [{"name": "OSType", "fields": []}] + _deduplicate_models(schema_models)
    extensions = load_extension_schemas()

    context = {
        "version": version,
        "format_major": int(version.split(".", 1)[0]),
        "models": all_models,
        "extensions": extensions,
        "sdk_validation_vectors": load_sdk_validation_vectors(),
        "java_package": "net.meshsync.meshpack",
    }

    render_template(
        "python/models.py.j2",
        context,
        os.path.join(OUTPUT_DIR, "python", "meshpack", "models.py"),
    )
    render_template(
        "python/extensions.py.j2",
        context,
        os.path.join(OUTPUT_DIR, "python", "meshpack", "extensions.py"),
    )
    render_template(
        "python/pyproject.toml.j2",
        context,
        os.path.join(OUTPUT_DIR, "python", "pyproject.toml"),
    )
    _write_text(
        os.path.join(OUTPUT_DIR, "python", "meshpack", "__init__.py"),
        "from .models import *\nfrom .extensions import *\n",
    )
    render_template(
        "python/README.md.j2",
        context,
        os.path.join(OUTPUT_DIR, "python", "README.md"),
    )

    render_template(
        "rust/lib.rs.j2",
        context,
        os.path.join(OUTPUT_DIR, "rust", "meshpack", "src", "lib.rs"),
    )
    render_template(
        "rust/Cargo.toml.j2",
        context,
        os.path.join(OUTPUT_DIR, "rust", "meshpack", "Cargo.toml"),
    )
    render_template(
        "rust/README.md.j2",
        context,
        os.path.join(OUTPUT_DIR, "rust", "meshpack", "README.md"),
    )

    render_template(
        "typescript/index.ts.j2",
        context,
        os.path.join(OUTPUT_DIR, "typescript", "src", "index.ts"),
    )
    render_template(
        "typescript/index.test.ts.j2",
        context,
        os.path.join(OUTPUT_DIR, "typescript", "src", "index.test.ts"),
    )
    render_template(
        "typescript/tsconfig.json.j2",
        context,
        os.path.join(OUTPUT_DIR, "typescript", "tsconfig.json"),
    )
    render_template(
        "typescript/package.json.j2",
        context,
        os.path.join(OUTPUT_DIR, "typescript", "package.json"),
    )
    render_template(
        "typescript/README.md.j2",
        context,
        os.path.join(OUTPUT_DIR, "typescript", "README.md"),
    )

    render_template(
        "java/MeshPack.java.j2",
        context,
        os.path.join(
            OUTPUT_DIR,
            "java",
            "meshpack",
            "src",
            "main",
            "java",
            "net",
            "meshsync",
            "meshpack",
            "MeshPack.java",
        ),
    )
    render_template(
        "java/MeshPackTest.java.j2",
        context,
        os.path.join(
            OUTPUT_DIR,
            "java",
            "meshpack",
            "src",
            "test",
            "java",
            "net",
            "meshsync",
            "meshpack",
            "MeshPackTest.java",
        ),
    )
    render_template(
        "java/pom.xml.j2",
        context,
        os.path.join(OUTPUT_DIR, "java", "meshpack", "pom.xml"),
    )
    render_template(
        "java/README.md.j2",
        context,
        os.path.join(OUTPUT_DIR, "java", "meshpack", "README.md"),
    )


if __name__ == "__main__":
    main()
