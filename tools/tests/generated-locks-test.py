#!/usr/bin/env python3
"""Static regression coverage for clean-checkout lock reproduction and drift."""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "generators"))

from lock_inputs import LOCK_INPUTS, copy_lock_inputs, lock_drift_errors  # noqa: E402


def fail(message: str) -> None:
    raise AssertionError(message)


def main() -> None:
    for language, (source, _) in LOCK_INPUTS.items():
        if not source.is_file():
            fail(f"{language} authoritative lock is missing: {source}")
        ignored = subprocess.run(
            ["git", "check-ignore", "--quiet", "--no-index", str(source)],
            cwd=REPO_ROOT,
            check=False,
        )
        if ignored.returncode == 0:
            fail(f"{language} authoritative lock is ignored: {source}")
        if ignored.returncode not in (0, 1):
            fail(f"git check-ignore failed for {source}")

    install_deps = subprocess.run(
        ["just", "--dry-run", "install-deps"],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    ).stdout
    root_dependency_steps = (
        "python3 -m venv .venv",
        ".venv/bin/python -m pip install --requirement requirements.txt",
    )
    if any(step not in install_deps for step in root_dependency_steps):
        fail("install-deps does not create and use the repository-local venv")
    if "generators/generate_sdks.py" in install_deps:
        fail("install-deps must not generate SDKs")

    provision = subprocess.run(
        ["just", "--dry-run", "provision"],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    ).stdout
    bootstrap_steps = (
        *root_dependency_steps,
        ".venv/bin/python generators/generate_sdks.py",
        "cargo fetch --locked",
        "npm ci",
        "mvn -q dependency:go-offline",
    )
    positions = [provision.find(step) for step in bootstrap_steps]
    if any(position < 0 for position in positions):
        fail("provision dry-run is missing a clean-checkout bootstrap step")
    if positions != sorted(positions):
        fail("provision does not install root tools, generate locks, then provision SDKs in order")

    with tempfile.TemporaryDirectory(prefix="meshpack-lock-test-") as temp_dir:
        clean_output = Path(temp_dir) / "generated" / "sdks"
        if clean_output.exists():
            fail("clean-checkout simulation unexpectedly has generated output")

        copy_lock_inputs(clean_output)
        errors = lock_drift_errors(clean_output)
        if errors:
            fail("clean-checkout lock reproduction failed: " + "; ".join(errors))

        rust_lock = clean_output / LOCK_INPUTS["rust"][1]
        rust_lock.write_bytes(rust_lock.read_bytes() + b"\n# drift\n")
        errors = lock_drift_errors(clean_output)
        if not any(error.startswith("rust: generated lock drifted") for error in errors):
            fail("Rust lock drift was not detected")

        rust_lock.unlink()
        errors = lock_drift_errors(clean_output)
        if not any(error.startswith("rust: generated lock is missing") for error in errors):
            fail("missing Rust lock was not detected")

    print("tracked locks reproduce a clean output tree and drift is detected")


if __name__ == "__main__":
    main()
