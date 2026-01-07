# Justfile for standard-meshpack

# Environment variables for publishing (Optional)
# NEXUS_URL := env_var("NEXUS_URL")
# NEXUS_USER := env_var("NEXUS_USER")
# NEXUS_PASS := env_var("NEXUS_PASS")

default: help

help:
    @echo "Available commands:"
    @echo "  generate       Generate client libraries (Python, Rust, TS) from templates"
    @echo "  validate       Check schema validity (requires 'check-jsonschema')"
    @echo "  compile        Build packages for all languages"
    @echo "  publish        Generate, Validate, Compile and Upload to Nexus"
    @echo "  all            Run compile sequence"

generate:
    @echo "Generating SDKs..."
    python3 generators/generate_sdks.py

validate:
    @echo "Validating schemas..."
    # Ensure check-jsonschema is installed: pip install check-jsonschema
    check-jsonschema --check-metaschema schema/manifest.schema.json
    check-jsonschema --check-metaschema schema/shard.schema.json

compile:
    @echo "Compiling Python..."
    # Ensure build is installed: pip install build
    cd generated/sdks/python && python3 -m build
    @echo "Compiling Rust..."
    if command -v cargo >/dev/null 2>&1; then \
        cd generated/sdks/rust/meshpack && cargo build --release; \
    else \
        echo "Warning: 'cargo' not found in PATH. Skipping Rust compilation."; \
    fi
    @echo "Compiling TypeScript..."
    if command -v npm >/dev/null 2>&1; then \
        cd generated/sdks/typescript && npm install && npm run build; \
    else \
        echo "Warning: 'npm' not found in PATH. Skipping TypeScript compilation."; \
    fi

publish: generate validate compile
    @echo "Publishing..."
    @echo "Please configure your registry credentials to publish."
    # Python
    # twine upload dist/*
    # Rust
    # cargo publish
    # TypeScript
    # npm publish

all: generate validate compile

clean:
    rm -rf generated/

