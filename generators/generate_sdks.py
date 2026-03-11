import os
import json
from jinja2 import Environment, FileSystemLoader

# Configuration
VERSION = "1.0.0"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
# Fix: OUTPUT_DIR relative to BASE_DIR (generators/) is ../generated/sdks
OUTPUT_DIR = os.path.join(os.path.dirname(BASE_DIR), "generated", "sdks")
SCHEMA_DIR = os.path.join(os.path.dirname(BASE_DIR), "schema")
EXTENSIONS_DIR = os.path.join(SCHEMA_DIR, "extensions")

# Ensure output directories exist
os.makedirs(os.path.join(OUTPUT_DIR, "python", "meshpack"), exist_ok=True)
os.makedirs(os.path.join(OUTPUT_DIR, "rust", "meshpack", "src"), exist_ok=True)
os.makedirs(os.path.join(OUTPUT_DIR, "typescript", "src"), exist_ok=True)


def load_schema(filename):
    with open(os.path.join(SCHEMA_DIR, filename), "r") as f:
        return json.load(f)


# Pre-load common definitions for cross-file $ref resolution
_common_schema = load_schema("common.schema.json")
_common_definitions = _common_schema.get("definitions", {})


def resolve_ref(ref):
    """Resolve a $ref URI to the referenced schema fragment.
    Supports local (#/definitions/X) and cross-file (common.schema.json#/definitions/X) refs."""
    if "#" in ref:
        file_part, fragment = ref.split("#", 1)
    else:
        return None

    parts = [p for p in fragment.split("/") if p]

    if file_part == "" or file_part is None:
        return None  # local ref — handled by caller via definitions dict

    if file_part == "common.schema.json":
        node = _common_schema
        for part in parts:
            node = node.get(part, {})
        return node if node else None

    return None

# Simple implementation to deduce type from schema property


def snake_to_pascal(name: str) -> str:
    """Convert snake_case or camelCase to PascalCase."""
    # Handle snake_case
    if "_" in name:
        return "".join(word.capitalize() for word in name.split("_"))
    # Handle camelCase — just capitalize first letter
    return name[0].upper() + name[1:] if name else name


def get_type_info(prop, prop_name, definitions=None):
    # Handle allOf with $ref (e.g., {"allOf": [{"$ref": "common.schema.json#/..."}], "description": "..."})
    all_of = prop.get("allOf")
    if all_of:
        for sub in all_of:
            ref = sub.get("$ref")
            if ref:
                resolved = resolve_ref(ref)
                if resolved:
                    return get_type_info(resolved, prop_name, definitions)
                # Local ref fallback
                if ref.startswith("#/definitions/"):
                    def_name = ref.split("/")[-1]
                    return {"base": snake_to_pascal(def_name), "is_ref": True}
        # If no $ref found in allOf, try merging (simplified)
        return {"base": "unknown", "is_primitive": True}

    ref = prop.get("$ref")
    if ref:
        # Cross-file ref (e.g., "common.schema.json#/definitions/signatureEntry")
        resolved = resolve_ref(ref)
        if resolved:
            return get_type_info(resolved, prop_name, definitions)
        # Local ref: e.g., "#/definitions/fileEntry" -> "FileEntry"
        def_name = ref.split("/")[-1]
        return {"base": snake_to_pascal(def_name), "is_ref": True}

    t = prop.get("type")

    if t == "string":
        fmt = prop.get("format")
        if fmt == "date-time":
            return {"base": "datetime", "is_primitive": False}
        if fmt == "email":
            return {"base": "email", "is_primitive": False}
        if prop.get("enum"):
            # Simplify: treat enum as string for now,
            # or detect specific enums if needed
            # Ideally we check naming, e.g. "os" -> OSType
            if prop_name == "os":
                return {"base": "OSType", "is_enum": True}
            return {"base": "string", "is_primitive": True,
                    "enum_values": prop["enum"]}
        return {"base": "string", "is_primitive": True}

    if t == "integer":
        return {"base": "integer", "is_primitive": True}

    if t == "number":
        return {"base": "number", "is_primitive": True}

    if t == "boolean":
        return {"base": "boolean", "is_primitive": True}

    if t == "array":
        items = prop.get("items", {})
        item_type = get_type_info(items, prop_name, definitions)
        return {"base": item_type["base"],
                "is_array": True, "item_type": item_type}

    if t == "object":
        # Check if it has specific properties (inline object) or is a Dict
        if "properties" in prop:
            # Inline object -> derive class name via snake_to_pascal
            class_name = snake_to_pascal(prop_name)
            # Special case: 'attributes' -> 'FileAttributes' for clarity
            if prop_name == "attributes":
                class_name = "FileAttributes"
            return {"base": class_name, "is_inline_class": True,
                    "properties": prop["properties"]}

        # Generic object (Dict/Map)
        return {"base": "dictionary",
                "is_primitive": True, "is_dictionary": True}

    # Valid types can be ["string", "null"]
    if isinstance(t, list):
        # assume [type, "null"] -> optional
        actual_type = [x for x in t if x != "null"][0]
        # Recursively get the actual type
        sub = get_type_info({"type": actual_type}, prop_name, definitions)
        sub["is_optional"] = True
        return sub

    return {"base": "unknown", "is_primitive": True}


def extract_models(schema_data, root_name):
    """
    Extracts a flat list of models/classes from a JSON schema.
    Returns: [ { "name": "Manifest", "fields": [...] }, ... ]
    """
    models = []

    definitions = schema_data.get("definitions", {})

    # helper
    def process_properties(props, class_name):
        fields = []
        for pname, pdef in props.items():
            type_info = get_type_info(pdef, pname, definitions)

            # If it's an inline class, we need to extract that model too!
            if type_info.get("is_inline_class"):
                # Recursive extraction
                inline_model = {
                    "name": type_info["base"],
                    "fields": process_properties(
                        type_info["properties"],
                        type_info["base"])}
                # Avoid duplicates
                if not any(m["name"] == inline_model["name"] for m in models):
                    models.append(inline_model)

            field = {
                "name": pname,
                "type": type_info,
                # logic is simplified
                "required": (
                    pname in schema_data.get(
                        "required", []
                    )
                    or pname in pdef.get(
                        "required", []
                    )
                )
            }
            fields.append(field)
        return fields

    # Process Root
    root_props = schema_data.get("properties", {})
    # For Root, the 'required' list is in the root
    root_fields = []
    required_list = schema_data.get("required", [])

    for pname, pdef in root_props.items():
        type_info = get_type_info(pdef, pname, definitions)

        # Extract inline classes from root properties
        if type_info.get("is_inline_class"):
            # Logic for required fields inside the inline class is tricky here,
            # simplifying: assume all fields in inline
            # objects are required unless optional
            # logic is added.
            # Actually, JSON schema usually defines
            # 'required' inside the property definition
            # for object type.
            # get_type_info doesn't pass the parent
            # 'pdef' deeply enough, but let's check:
            # pdef['properties'] exists. pdef['required'] might.
            inline_required = pdef.get("required", [])

            inline_fields = []
            for ipname, ipdef in type_info["properties"].items():
                itype_info = get_type_info(ipdef, ipname, definitions)
                inline_fields.append({
                    "name": ipname,
                    "type": itype_info,
                    "required": ipname in inline_required
                })

            models.append({
                "name": type_info["base"],
                "fields": inline_fields
            })

        root_fields.append({
            "name": pname,
            "type": type_info,
            "required": pname in required_list
        })

    models.append({
        "name": root_name,
        "fields": root_fields
    })

    # Process Definitions (e.g., FileEntry)
    for def_name, def_body in definitions.items():
        # Capitalize
        model_name = def_name[0].upper() + def_name[1:]
        def_required = def_body.get("required", [])

        def_fields = []
        if "properties" in def_body:
            for pname, pdef in def_body["properties"].items():
                type_info = get_type_info(pdef, pname, definitions)

                # Check inline objects in definitions (e.g. attributes in
                # FileEntry)
                if type_info.get("is_inline_class"):
                    inline_req = pdef.get("required", [])
                    inline_fields = []
                    for ipname, ipdef in type_info["properties"].items():
                        itype_info = get_type_info(ipdef, ipname, definitions)
                        inline_fields.append({
                            "name": ipname,
                            "type": itype_info,
                            "required": ipname in inline_req
                        })
                    models.append({
                        "name": type_info["base"],
                        "fields": inline_fields
                    })

                def_fields.append({
                    "name": pname,
                    "type": type_info,
                    "required": pname in def_required
                })

        models.append({
            "name": model_name,
            "fields": def_fields
        })

    return models

# Helper to render templates


def render_template(template_path, context, output_path):
    env = Environment(loader=FileSystemLoader(TEMPLATES_DIR))
    template = env.get_template(template_path)
    output = template.render(context)

    with open(output_path, "w") as f:
        f.write(output)
    print(f"Generated: {output_path}")

def extract_extension_version_models(ext_name, version_name, version_schema):
    """Extract typed models from an extension version schema."""
    models = []
    root_name = snake_to_pascal(ext_name) + snake_to_pascal(version_name)

    properties = version_schema.get('properties', {})
    fields = []

    for prop_name, prop_def in properties.items():
        type_info = get_type_info(prop_def, prop_name)

        if type_info.get('is_inline_class'):
            inline_name = snake_to_pascal(prop_name)
            inline_fields = []
            for ipname, ipdef in type_info['properties'].items():
                itype_info = get_type_info(ipdef, ipname)
                inline_fields.append({
                    'name': ipname,
                    'type': itype_info,
                    'required': False
                })
            models.append({
                'name': inline_name,
                'fields': inline_fields,
                'is_root': False
            })

        fields.append({
            'name': prop_name,
            'type': type_info,
            'required': False
        })

    models.insert(0, {
        'name': root_name,
        'fields': fields,
        'is_root': True
    })

    return models


def load_extension_schemas():
    """Load all extension schemas from the extensions/ directory."""
    extensions = []
    if not os.path.exists(EXTENSIONS_DIR):
        return extensions

    for filename in sorted(os.listdir(EXTENSIONS_DIR)):
        if filename.endswith('.schema.json'):
            filepath = os.path.join(EXTENSIONS_DIR, filename)
            with open(filepath, 'r') as f:
                schema = json.load(f)
                # Extract extension name from filename:
                # meshsync_geometry.schema.json -> meshsync_geometry
                ext_name = filename.replace('.schema.json', '')
                version_models = {}
                for version_name, version_schema in schema.get('properties', {}).items():
                    version_models[version_name] = extract_extension_version_models(
                        ext_name, version_name, version_schema
                    )
                extensions.append({
                    'name': ext_name,
                    'schema': schema,
                    'versions': list(schema.get('properties', {}).keys()),
                    'version_models': version_models
                })
    return extensions


def main():
    manifest_schema = load_schema("manifest.schema.json")
    shard_schema = load_schema("shard.schema.json")

    manifest_models = extract_models(manifest_schema, "Manifest")
    shard_models = extract_models(shard_schema, "Shard")

    # Load extension schemas
    extensions = load_extension_schemas()

    # Merge models, deduplicate by name
    all_models_map = {}
    for m in manifest_models + shard_models:
        if m["name"] not in all_models_map:
            all_models_map[m["name"]] = m

    # Manually add OSType since it is handled specifically in templates but
    # not extracted as an object
    all_models_map["OSType"] = {"name": "OSType", "fields": []}

    # Ordered list (dependencies first would be ideal, but for now flat)
    all_models = list(all_models_map.values())

    context = {
        "version": VERSION,
        "models": all_models,
        "extensions": extensions
    }

    # Python
    render_template(
        "python/models.py.j2",
        context,
        os.path.join(OUTPUT_DIR, "python", "meshpack", "models.py")
    )
    # Generate extension helpers
    render_template(
        "python/extensions.py.j2",
        context,
        os.path.join(OUTPUT_DIR, "python", "meshpack", "extensions.py")
    )
    # Also create __init__.py
    init_path = os.path.join(
        OUTPUT_DIR, "python", "meshpack", "__init__.py"
    )
    with open(init_path, "w") as f:
        f.write("from .models import *\n")
        f.write("from .extensions import *\n")

    # pyproject.toml
    render_template(
        "python/pyproject.toml.j2",
        context,
        os.path.join(OUTPUT_DIR, "python", "pyproject.toml")
    )
    # README.md for python
    with open(os.path.join(OUTPUT_DIR, "python", "README.md"), "w") as f:
        f.write("# MeshPack Python SDK\n\nAuto-generated SDK.")

    # Rust
    render_template(
        "rust/lib.rs.j2",
        context,
        os.path.join(OUTPUT_DIR, "rust", "meshpack", "src", "lib.rs")
    )
    # Cargo.toml for Rust
    cargo_toml = f"""[package]
name = "meshpack"
version = "{VERSION}"
edition = "2021"
license = "MIT"
description = "Standard MeshPack SDK"

[dependencies]
serde = {{ version = "1.0", features = ["derive"] }}
serde_json = "1.0"
chrono = {{ version = "0.4", features = ["serde"] }}
zip = "0.6"
typed-builder = "0.18"
"""
    cargo_path = os.path.join(
        OUTPUT_DIR, "rust", "meshpack", "Cargo.toml"
    )
    with open(cargo_path, "w") as f:
        f.write(cargo_toml)

    # TypeScript
    render_template(
        "typescript/index.ts.j2",
        context,
        os.path.join(OUTPUT_DIR, "typescript", "src", "index.ts")
    )
    # tsconfig.json
    render_template(
        "typescript/tsconfig.json.j2",
        context,
        os.path.join(OUTPUT_DIR, "typescript", "tsconfig.json")
    )
    # package.json for TS
    package_json = {
        "name": "@mesh-sync/meshpack",
        "version": VERSION,
        "license": "MIT",
        "main": "dist/index.js",
        "types": "dist/index.d.ts",
        "scripts": {
            "build": "tsc"
        },
        "dependencies": {
            "jszip": "^3.10.1"
        },
        "devDependencies": {
            "typescript": "^5.0.0",
            "@types/node": "^20.0.0"
        }
    }
    pkg_path = os.path.join(
        OUTPUT_DIR, "typescript", "package.json"
    )
    with open(pkg_path, "w") as f:
        json.dump(package_json, f, indent=2)

    # tsconfig.json
    render_template(
        "typescript/tsconfig.json.j2",
        context,
        os.path.join(OUTPUT_DIR, "typescript", "tsconfig.json")
    )


if __name__ == "__main__":
    main()
