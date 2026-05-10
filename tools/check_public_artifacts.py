#!/usr/bin/env python3
"""Public exposure guard for samples and generated SDK package roots."""

from __future__ import annotations

import json
import re
import sys
import zipfile
from pathlib import Path


REPO_DIR = Path(__file__).resolve().parents[1]
SAMPLES_DIR = REPO_DIR / "samples"
GENERATED_DIR = REPO_DIR / "generated" / "sdks"

PACKAGE_ROOTS = [
    GENERATED_DIR / "python",
    GENERATED_DIR / "rust" / "meshpack",
    GENERATED_DIR / "typescript",
    GENERATED_DIR / "java" / "meshpack",
]

IGNORED_PARTS = {
    ".mypy_cache",
    ".pytest_cache",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
    "target",
}

SENSITIVE_NAME_RE = re.compile(
    r"(^|[._-])(env|secret|secrets|token|private|credential|credentials|keystore)([._-]|$)|\.(pem|key|p12|pfx|jks|keystore)$",
    re.IGNORECASE,
)
PRIVATE_KEY_RE = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")
TOKEN_RE = re.compile(r"(?i)(api[_-]?key|secret|token|password)\s*[:=]\s*['\"]?[A-Za-z0-9_./+=-]{16,}")
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
ALLOWED_EMAILS = {"contact@meshsync.net"}


def _is_text_file(path: Path) -> bool:
    return path.suffix.lower() in {".json", ".md", ".py", ".rs", ".ts", ".js", ".toml", ".xml", ".txt", ""}


def _scan_text(path: Path, text: str, failures: list[str]) -> None:
    if PRIVATE_KEY_RE.search(text):
        failures.append(f"{path}: private key material found")
    if TOKEN_RE.search(text):
        failures.append(f"{path}: secret-like assignment found")
    for email in EMAIL_RE.findall(text):
        if email.lower() not in ALLOWED_EMAILS:
            failures.append(f"{path}: non-public email address found: {email}")


def _scan_path_tree(root: Path, failures: list[str]) -> None:
    if not root.exists():
        return
    for path in sorted(root.rglob("*")):
        if any(part in IGNORED_PARTS for part in path.relative_to(root).parts):
            continue
        if not path.is_file():
            continue
        relative = path.relative_to(REPO_DIR)
        if SENSITIVE_NAME_RE.search(path.name):
            failures.append(f"{relative}: sensitive filename is not allowed in public artifacts")
        if _is_text_file(path):
            try:
                _scan_text(relative, path.read_text(encoding="utf-8"), failures)
            except UnicodeDecodeError:
                failures.append(f"{relative}: expected text file is not UTF-8 decodable")


def _check_package_roots(failures: list[str]) -> None:
    for root in PACKAGE_ROOTS:
        if not root.exists():
            continue
        for required_name in ("README.md", "LICENSE"):
            if not (root / required_name).exists():
                failures.append(f"{root.relative_to(REPO_DIR)}: missing {required_name}")

    package_json = GENERATED_DIR / "typescript" / "package.json"
    if package_json.exists():
        data = json.loads(package_json.read_text(encoding="utf-8"))
        package_files = set(data.get("files", []))
        if "LICENSE" not in package_files or "README.md" not in package_files:
            failures.append("generated/sdks/typescript/package.json: package files must include README.md and LICENSE")


def _check_public_sample_privacy(failures: list[str]) -> None:
    manifest_paths = [SAMPLES_DIR / "manifest.json"]
    archive = SAMPLES_DIR / "test-workspace.mpack"
    if archive.exists():
        with zipfile.ZipFile(archive) as zip_file:
            manifest = json.loads(zip_file.read("manifest.json"))
        if "email" in manifest.get("creator_info", {}):
            failures.append("samples/test-workspace.mpack: archived manifest creator_info.email must be omitted")
    for manifest_path in manifest_paths:
        if not manifest_path.exists():
            continue
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if "email" in manifest.get("creator_info", {}):
            failures.append(f"{manifest_path.relative_to(REPO_DIR)}: creator_info.email must be omitted")


def main() -> int:
    failures: list[str] = []
    _scan_path_tree(SAMPLES_DIR, failures)
    for root in PACKAGE_ROOTS:
        _scan_path_tree(root, failures)
    _check_package_roots(failures)
    _check_public_sample_privacy(failures)

    if failures:
        print("Public artifact hygiene check failed:", file=sys.stderr)
        for failure in failures:
            print(f"  - {failure}", file=sys.stderr)
        return 1

    print("Public artifact hygiene check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())