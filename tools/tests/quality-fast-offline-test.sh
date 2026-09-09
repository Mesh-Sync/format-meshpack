#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
dry_run="$(cd "$repo_root" && just --dry-run quality-fast 2>&1)"

fail() {
    printf 'quality-fast offline contract failed: %s\n' "$1" >&2
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

printf 'quality-fast is offline, non-provisioning, locked, and covers Python, Rust, TypeScript, and Java 17\n'
