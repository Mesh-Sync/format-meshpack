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
    @echo "  doc            Generate PDF documentation (requires 'pandoc')"
    @echo "  lint           Run code linters (Python, Rust, TS)"
    @echo "  test           Run tests (Python, Rust, TS)"
    @echo "  publish        Generate, Validate, Compile, Test, Lint and Upload"
    @echo "  all            Run compile sequence"

generate:
    @echo "Generating SDKs..."
    python3 generators/generate_sdks.py

doc:
    @echo "Generating PDF documentation..."
    pandoc definition/README.md -o definition/meshpack-spec.pdf --toc -V geometry:margin=1in
    @echo "Generated definition/meshpack-spec.pdf"

validate:
    @echo "Validating schemas..."
    # Ensure check-jsonschema is installed: pip install check-jsonschema
    check-jsonschema --check-metaschema schema/manifest.schema.json
    check-jsonschema --check-metaschema schema/shard.schema.json
    check-jsonschema --check-metaschema schema/sidecar.schema.json
    check-jsonschema --check-metaschema schema/common.schema.json

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

lint:
    @echo "Linting Python..."
    flake8 generators/
    # mypy generators/ # Enable when typed
    @echo "Linting Rust..."
    if command -v cargo >/dev/null 2>&1; then \
        cd generated/sdks/rust/meshpack && cargo clippy; \
    fi
    @echo "Linting TypeScript..."
    if command -v npm >/dev/null 2>&1; then \
        cd generated/sdks/typescript && npm run lint; \
    fi

test:
    @echo "Running conformance tests..."
    pytest tests/conformance/ -v --tb=short
    @echo "Testing Rust..."
    if command -v cargo >/dev/null 2>&1; then \
        cd generated/sdks/rust/meshpack && cargo test; \
    fi
    @echo "Testing TypeScript..."
    if command -v npm >/dev/null 2>&1; then \
        cd generated/sdks/typescript && npm test; \
    fi

publish: generate validate lint test compile
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

