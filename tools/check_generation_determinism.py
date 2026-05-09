#!/usr/bin/env python3
"""Run SDK generation twice and verify generated source output is byte-identical."""

from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path


REPO_DIR = Path(__file__).resolve().parents[1]
GENERATED_DIR = REPO_DIR / "generated" / "sdks"
IGNORED_PARTS = {
    "node_modules",
    "dist",
    "target",
    "build",
    ".pytest_cache",
    ".mypy_cache",
    "__pycache__",
}


def run_generator() -> None:
    subprocess.run([sys.executable, "generators/generate_sdks.py"], cwd=REPO_DIR, check=True)


def snapshot() -> dict[str, str]:
    files: dict[str, str] = {}
    for path in sorted(GENERATED_DIR.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(GENERATED_DIR)
        if any(part in IGNORED_PARTS for part in rel.parts):
            continue
        files[str(rel)] = hashlib.sha256(path.read_bytes()).hexdigest()
    return files


def main() -> int:
    run_generator()
    first = snapshot()
    run_generator()
    second = snapshot()

    if first != second:
        first_keys = set(first)
        second_keys = set(second)
        print("Generated SDK output is not deterministic", file=sys.stderr)
        for name in sorted(first_keys ^ second_keys):
            print(f"  file set changed: {name}", file=sys.stderr)
        for name in sorted(first_keys & second_keys):
            if first[name] != second[name]:
                print(f"  content changed: {name}", file=sys.stderr)
        return 1

    print(f"Deterministic generation verified for {len(first)} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
