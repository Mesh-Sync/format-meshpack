# Justfile for standard-meshpack

# Environment variables for publishing (Optional)
# NEXUS_URL := env_var("NEXUS_URL")
# NEXUS_USER := env_var("NEXUS_USER")
# NEXUS_PASS := env_var("NEXUS_PASS")

default: help

help:
    @echo "Available commands:"
    @echo "  generate       Generate client libraries (Python, Rust, TypeScript, Java 17) from templates"
    @echo "  check-version  Verify generated package versions match VERSION"
    @echo "  determinism-check  Verify generated SDK output is deterministic"
    @echo "  artifact-hygiene  Scan generated packages and public samples for exposure risks"
    @echo "  check-clean    Fail if tracked or untracked non-ignored files changed"
    @echo "  validate       Check schema validity (requires 'check-jsonschema')"
    @echo "  compile        Build packages for all languages"
    @echo "  doc            Generate PDF documentation (requires 'pandoc')"
    @echo "  lint           Run code linters (Python, Rust, TypeScript, Java)"
    @echo "  test           Run tests (Python, Rust, TypeScript, Java)"
    @echo "  publish        Generate, Validate, Compile, Test, Lint and Upload"
    @echo "  publish-dry-run  Full pipeline without uploading (local verification)"
    @echo "  public-readiness  Full public exposure gate plus clean worktree check"
    @echo "  all            Run generate, validate, lint, test, and compile"

generate:
    @echo "Generating SDKs..."
    python3 generators/generate_sdks.py

check-version:
    @echo "Checking generated SDK versions..."
    python3 tools/check_generated_versions.py

determinism-check:
    @echo "Checking deterministic generation..."
    python3 tools/check_generation_determinism.py

artifact-hygiene:
    @echo "Checking public artifact hygiene..."
    python3 tools/check_public_artifacts.py

check-clean:
    @echo "Checking repository cleanliness..."
    git diff --quiet
    git diff --cached --quiet
    test -z "$(git ls-files --others --exclude-standard)"

generate-fixtures:
    @echo "Generating static test fixtures..."
    python3 tests/conformance/generate_fixtures.py

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
    @echo "Validating extension schemas..."
    check-jsonschema --check-metaschema schema/extensions/meshsync_geometry.schema.json
    check-jsonschema --check-metaschema schema/extensions/meshsync_content.schema.json
    check-jsonschema --check-metaschema schema/extensions/meshsync_thumbnails.schema.json
    check-jsonschema --check-metaschema schema/extensions/meshsync_printability.schema.json
    check-jsonschema --check-metaschema schema/extensions/meshsync_dependencies.schema.json
    @echo "Validating public sample archive..."
    python3 tools/meshpack_validate.py --strict samples/test-workspace.mpack

compile:
    @echo "Compiling Python..."
    # Ensure build is installed: pip install build
    cd generated/sdks/python && python3 -m build
    @echo "Compiling Rust..."
    command -v cargo >/dev/null 2>&1
    cd generated/sdks/rust/meshpack && CARGO_TARGET_DIR=target/release-build cargo build --release
    @echo "Compiling TypeScript..."
    command -v npm >/dev/null 2>&1
    cd generated/sdks/typescript && npm install && npm run build
    @echo "Compiling Java 17..."
    command -v mvn >/dev/null 2>&1
    cd generated/sdks/java/meshpack && mvn -q clean package

lint:
    @echo "Linting Python..."
    flake8 generators/
    # mypy generators/ # Enable when typed
    @echo "Linting Rust..."
    command -v cargo >/dev/null 2>&1
    cd generated/sdks/rust/meshpack && CARGO_TARGET_DIR=target/clippy cargo clippy --all-targets
    @echo "Linting TypeScript..."
    command -v npm >/dev/null 2>&1
    cd generated/sdks/typescript && npm install && npm run lint
    @echo "Checking Java 17 compile..."
    command -v mvn >/dev/null 2>&1
    cd generated/sdks/java/meshpack && mvn -q -DskipTests compile

test:
    @echo "Running Python tests..."
    pytest tests/ -v --tb=short
    @echo "Testing Rust..."
    command -v cargo >/dev/null 2>&1
    cd generated/sdks/rust/meshpack && CARGO_TARGET_DIR=target/test cargo test
    @echo "Testing TypeScript..."
    command -v npm >/dev/null 2>&1
    cd generated/sdks/typescript && npm install && npm test
    @echo "Testing Java 17..."
    command -v mvn >/dev/null 2>&1
    cd generated/sdks/java/meshpack && mvn -q test

publish: generate check-version validate lint test compile
    @echo "Publishing..."
    @echo "Please configure your registry credentials to publish."
    # Python
    # twine upload dist/*
    # Rust
    # cargo publish
    # TypeScript
    # npm publish

publish-dry-run: generate check-version determinism-check validate lint test compile artifact-hygiene
    @echo "Dry-run: packing artifacts (no upload)..."
    @echo "--- Python ---"
    cd generated/sdks/python && python3 -m build
    @echo "--- TypeScript ---"
    if command -v npm >/dev/null 2>&1; then \
        cd generated/sdks/typescript && npm pack --dry-run; \
    fi
    @echo "--- Rust ---"
    cd generated/sdks/rust/meshpack && cargo package --list
    @echo "--- Java ---"
    cd generated/sdks/java/meshpack && mvn -q clean package
    @echo "Dry-run complete. Review output above before tagging a release."

all: generate check-version determinism-check validate lint test compile

public-readiness: publish-dry-run check-clean

clean:
    rm -rf generated/

# Workspace quality contract. Profiles are monotonic and have no external side effects.
quality-fast: validate test lint

quality-full: quality-fast determinism-check artifact-hygiene check-version

quality-release: quality-full
