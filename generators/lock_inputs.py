"""Authoritative tracked lock inputs for generated MeshPack SDKs."""

from __future__ import annotations

import filecmp
import os
import shutil
from pathlib import Path
from typing import Iterable


GENERATORS_DIR = Path(__file__).resolve().parent
DEFAULT_OUTPUT_DIR = GENERATORS_DIR.parent / "generated" / "sdks"

LOCK_INPUTS = {
    "rust": (
        GENERATORS_DIR / "locks" / "rust" / "Cargo.lock",
        Path("rust") / "meshpack" / "Cargo.lock",
    ),
    "typescript": (
        GENERATORS_DIR / "locks" / "typescript" / "package-lock.json",
        Path("typescript") / "package-lock.json",
    ),
}


def _selected_languages(languages: Iterable[str] | None) -> tuple[str, ...]:
    selected = tuple(LOCK_INPUTS) if languages is None else tuple(languages)
    unknown = sorted(set(selected) - set(LOCK_INPUTS))
    if unknown:
        raise ValueError(f"Unknown lock language(s): {', '.join(unknown)}")
    return selected


def copy_lock_inputs(
    output_dir: str | os.PathLike[str] = DEFAULT_OUTPUT_DIR,
    *,
    languages: Iterable[str] | None = None,
) -> None:
    """Copy tracked authoritative locks into an SDK output tree byte-for-byte."""
    output_root = Path(output_dir)
    for language in _selected_languages(languages):
        source, relative_destination = LOCK_INPUTS[language]
        destination = output_root / relative_destination
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        print(f"Generated: {destination}")


def lock_drift_errors(
    output_dir: str | os.PathLike[str] = DEFAULT_OUTPUT_DIR,
    *,
    languages: Iterable[str] | None = None,
) -> list[str]:
    """Return missing or byte-drifted generated lock diagnostics."""
    output_root = Path(output_dir)
    errors: list[str] = []
    for language in _selected_languages(languages):
        source, relative_destination = LOCK_INPUTS[language]
        destination = output_root / relative_destination
        if not destination.is_file():
            errors.append(f"{language}: generated lock is missing: {destination}")
        elif not filecmp.cmp(source, destination, shallow=False):
            errors.append(
                f"{language}: generated lock drifted from authoritative input "
                f"{source}: {destination}"
            )
    return errors
