#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
profile="${1:-quality-fast}"
case "$profile" in
    quality-fast|quality-full|quality-release) ;;
    *) printf 'Unsupported quality profile: %s\n' "$profile" >&2; exit 1 ;;
esac
dry_run="$(cd "$repo_root" && just --dry-run "$profile" 2>&1)"

fail() {
    printf 'quality profile offline contract failed: %s\n' "$1" >&2
    exit 1
}

if grep -Eq '(^|[[:space:]])(npm (ci|install)|pip(3)? install|python3 -m pip install|cargo fetch|mvn[^[:cntrl:]]*dependency:go-offline)([[:space:]]|$)' <<<"$dry_run"; then
    fail "dependency provisioning is reachable from quality-fast"
fi

grep -Fq 'cargo test --locked --offline' <<<"$dry_run" || fail "Rust tests are not locked and offline"
grep -Fq 'cargo clippy --all-targets --locked --offline' <<<"$dry_run" || fail "Rust lint is not locked and offline"
grep -Fq 'npm --offline test' <<<"$dry_run" || fail "TypeScript tests are not offline"
grep -Fq 'npm --offline run lint' <<<"$dry_run" || fail "TypeScript lint is not offline"
grep -Fq 'mvn --offline -q test' <<<"$dry_run" || fail "Java tests are not offline"
grep -Fq 'mvn --offline -q -DskipTests compile' <<<"$dry_run" || fail "Java compile check is not offline"
grep -Fq 'pytest tests/' <<<"$dry_run" || fail "Python tests are missing"
grep -Fq 'flake8 generators/' <<<"$dry_run" || fail "Python lint is missing"
grep -Fq 'python3 tools/check_generated_locks.py' <<<"$dry_run" || fail "generated lock drift check is missing"

pom="$repo_root/generated/sdks/java/meshpack/pom.xml"
grep -Fq '<maven.compiler.release>17</maven.compiler.release>' "$pom" || fail "Java 17 compiler release is not preserved"

if [[ "$profile" == quality-release ]]; then
    grep -Fq ' -m build --no-isolation' <<<"$dry_run" || fail "Python packaging is not using provisioned build tools"
    grep -Fq 'cargo build --release --locked --offline' <<<"$dry_run" || fail "Rust packaging is not locked and offline"
    grep -Fq 'npm --offline pack --dry-run' <<<"$dry_run" || fail "npm packaging is not offline"
    grep -Fq 'mvn --offline -q package' <<<"$dry_run" || fail "Java packaging is not offline"
    grep -Fq 'cargo package --list --locked --offline' <<<"$dry_run" || fail "Cargo package inspection is not offline"
    if grep -Eq '(twine upload|npm publish|cargo publish| -m build$)' <<<"$dry_run"; then
        fail "release validation can publish or provision an isolated build environment"
    fi
fi

printf 'quality profile is offline, non-provisioning, locked, and covers Python, Rust, TypeScript, and Java 17\n'
