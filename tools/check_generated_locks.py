#!/usr/bin/env python3
"""Fail when generated SDK locks differ from tracked authoritative inputs."""

from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "generators"))

from lock_inputs import lock_drift_errors  # noqa: E402


def main() -> int:
    errors = lock_drift_errors()
    if errors:
        print("Generated SDK lock verification failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        print("Run `just generate` to restore locks from tracked inputs.", file=sys.stderr)
        return 1
    print("Generated SDK locks match tracked authoritative inputs.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
