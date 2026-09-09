default:
    @just --list

# Justfile for standard-meshpack

# Environment variables for publishing (Optional)
# NEXUS_URL := env_var("NEXUS_URL")
# NEXUS_USER := env_var("NEXUS_USER")
# NEXUS_PASS := env_var("NEXUS_PASS")

venv_python := justfile_directory() / ".venv" / "bin" / "python"

generate:
    @echo "Generating SDKs..."
    {{venv_python}} generators/generate_sdks.py

check-version:
    @echo "Checking generated SDK versions..."
    python3 tools/check_generated_versions.py

check-locks:
    @echo "Checking generated SDK locks..."
    python3 tools/check_generated_locks.py

determinism-check:
    @echo "Checking deterministic generation..."
    {{venv_python}} tools/check_generation_determinism.py

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
    # Requires the pre-provisioned repository-local Python environment.
    {{venv_python}} -m check_jsonschema --check-metaschema schema/manifest.schema.json
    {{venv_python}} -m check_jsonschema --check-metaschema schema/shard.schema.json
    {{venv_python}} -m check_jsonschema --check-metaschema schema/sidecar.schema.json
    {{venv_python}} -m check_jsonschema --check-metaschema schema/common.schema.json
    @echo "Validating extension schemas..."
    {{venv_python}} -m check_jsonschema --check-metaschema schema/extensions/meshsync_geometry.schema.json
    {{venv_python}} -m check_jsonschema --check-metaschema schema/extensions/meshsync_content.schema.json
    {{venv_python}} -m check_jsonschema --check-metaschema schema/extensions/meshsync_thumbnails.schema.json
    {{venv_python}} -m check_jsonschema --check-metaschema schema/extensions/meshsync_printability.schema.json
    {{venv_python}} -m check_jsonschema --check-metaschema schema/extensions/meshsync_dependencies.schema.json
    @echo "Validating public sample archive..."
    {{venv_python}} tools/meshpack_validate.py --strict samples/test-workspace.mpack

# Explicit, network-capable root tooling provisioning. Python dependencies in
# requirements.txt are the only repository-owned development/tool dependencies;
# Rust, npm, and Maven dependencies belong to generated SDKs.
# Install only the repository-root development/tool dependency manifest.
install-deps:
    @echo "Installing repository Python development/tool dependencies..."
    python3 -m venv .venv
    {{venv_python}} -m pip install --requirement requirements.txt

# Bootstrap generated SDKs and their dependencies. Quality profiles never
# depend on this recipe; they consume only already-installed tools and caches.
# Generate SDKs before provisioning their language-specific dependencies.
provision: install-deps
    @echo "Generating SDK manifests and authoritative lock copies..."
    {{venv_python}} generators/generate_sdks.py
    @echo "Provisioning Rust dependencies..."
    cd generated/sdks/rust/meshpack && cargo fetch --locked
    @echo "Provisioning TypeScript dependencies..."
    cd generated/sdks/typescript && npm ci
    @echo "Provisioning Java 17 dependencies..."
    cd generated/sdks/java/meshpack && mvn -q dependency:go-offline
    # Surefire discovers its provider at runtime; execute the lifecycle once to
    # cache provider and packaging dependencies before offline quality checks.
    cd generated/sdks/java/meshpack && mvn -q clean package

build:
    @echo "Compiling Python..."
    cd generated/sdks/python && {{venv_python}} -m build --no-isolation
    @echo "Compiling Rust..."
    command -v cargo >/dev/null 2>&1
    cd generated/sdks/rust/meshpack && CARGO_TARGET_DIR=target/release-build cargo build --release --locked --offline
    @echo "Compiling TypeScript..."
    command -v npm >/dev/null 2>&1
    cd generated/sdks/typescript && npm --offline run build
    @echo "Compiling Java 17..."
    command -v mvn >/dev/null 2>&1
    cd generated/sdks/java/meshpack && mvn --offline -q package

lint:
    @echo "Linting Python..."
    {{venv_python}} -m flake8 generators/
    # mypy generators/ # Enable when typed
    @echo "Linting Rust..."
    command -v cargo >/dev/null 2>&1
    cd generated/sdks/rust/meshpack && CARGO_TARGET_DIR=target/clippy cargo clippy --all-targets --locked --offline
    @echo "Linting TypeScript..."
    command -v npm >/dev/null 2>&1
    cd generated/sdks/typescript && npm --offline run lint
    @echo "Checking Java 17 compile..."
    command -v mvn >/dev/null 2>&1
    cd generated/sdks/java/meshpack && mvn --offline -q -DskipTests compile

test:
    @echo "Running Python tests..."
    {{venv_python}} -m pytest tests/ -v --tb=short
    @echo "Testing Rust..."
    command -v cargo >/dev/null 2>&1
    cd generated/sdks/rust/meshpack && CARGO_TARGET_DIR=target/test cargo test --locked --offline
    @echo "Testing TypeScript..."
    command -v npm >/dev/null 2>&1
    cd generated/sdks/typescript && npm --offline test
    @echo "Testing Java 17..."
    command -v mvn >/dev/null 2>&1
    cd generated/sdks/java/meshpack && mvn --offline -q test

publish: generate check-version validate lint test build
    @echo "Publishing..."
    @echo "Please configure your registry credentials to publish."
    # Python
    # twine upload dist/*
    # Rust
    # cargo publish
    # TypeScript
    # npm publish

# Validate and build once, then inspect packages without uploading.
publish-dry-run: quality-release
    @echo "Dry-run complete. No packages uploaded."

# Materialize the npm/Cargo archives after publish-dry-run. Python and Java
# archives are already built by build; this recipe never publishes.
package-artifacts:
    cd generated/sdks/typescript && npm --offline pack
    cd generated/sdks/rust/meshpack && cargo package --allow-dirty --locked --offline

package-check:
    {{venv_python}} -m twine check generated/sdks/python/dist/*
    cd generated/sdks/typescript && npm --offline pack --dry-run
    cd generated/sdks/rust/meshpack && cargo package --list --locked --offline

all: generate check-version determinism-check validate lint test build

public-readiness: publish-dry-run check-clean

# Workspace quality contract. Profiles are monotonic, consume pre-provisioned
# local dependencies only, and have no external side effects.
quality-fast: check-locks validate test lint
    bash tools/tests/quality-fast-offline-test.sh
    {{venv_python}} tools/tests/generated-locks-test.py

quality-full: quality-fast determinism-check artifact-hygiene check-version

quality-release: quality-full build package-check
    bash tools/tests/quality-fast-offline-test.sh quality-release

# Standard workspace operations; implementations remain repository-owned.
check: quality-fast

clean:
    git clean -ndX -- generated/sdks/python/dist/ generated/sdks/rust/meshpack/target/ generated/sdks/typescript/dist/ generated/sdks/java/meshpack/target/
    git clean -fdX -- generated/sdks/python/dist/ generated/sdks/rust/meshpack/target/ generated/sdks/typescript/dist/ generated/sdks/java/meshpack/target/
