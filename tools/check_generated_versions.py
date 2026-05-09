#!/usr/bin/env python3
"""Verify all generated SDK package versions match the repository VERSION file."""

import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


REPO_DIR = Path(__file__).resolve().parents[1]
EXPECTED_VERSION = (REPO_DIR / "VERSION").read_text(encoding="utf-8").strip()
GENERATED_DIR = REPO_DIR / "generated" / "sdks"


def read_python_version() -> str:
    return read_toml_project_version(GENERATED_DIR / "python" / "pyproject.toml")


def read_rust_version() -> str:
    return read_toml_project_version(GENERATED_DIR / "rust" / "meshpack" / "Cargo.toml")


def read_toml_project_version(path: Path) -> str:
    match = re.search(
        r'^version\s*=\s*"([^"]+)"',
        path.read_text(encoding="utf-8"),
        flags=re.MULTILINE,
    )
    if match is None:
        raise ValueError(f"{path} is missing a version field")
    return match.group(1)


def read_typescript_version() -> str:
    data = json.loads((GENERATED_DIR / "typescript" / "package.json").read_text(encoding="utf-8"))
    return data["version"]


def read_java_version() -> str:
    root = ET.fromstring((GENERATED_DIR / "java" / "meshpack" / "pom.xml").read_text(encoding="utf-8"))
    namespace = {"m": "http://maven.apache.org/POM/4.0.0"}
    version = root.findtext("m:version", namespaces=namespace)
    if version is None:
        raise ValueError("Java pom.xml is missing a project version")
    return version


CHECKS = {
    "python": read_python_version,
    "rust": read_rust_version,
    "typescript": read_typescript_version,
    "java": read_java_version,
}


def main() -> int:
    failures = []
    for name, read_version in CHECKS.items():
        actual = read_version()
        if actual != EXPECTED_VERSION:
            failures.append(f"{name}: expected {EXPECTED_VERSION}, got {actual}")
        else:
            print(f"{name}: {actual}")

    if failures:
        print("Generated SDK version mismatch:", file=sys.stderr)
        for failure in failures:
            print(f"  - {failure}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
