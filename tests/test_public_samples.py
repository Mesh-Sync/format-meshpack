"""Public sample archive release guards."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLES_DIR = REPO_ROOT / "samples"
PUBLIC_SAMPLE = SAMPLES_DIR / "test-workspace.mpack"
PUBLIC_SAMPLE_SIDECAR = SAMPLES_DIR / "test-workspace.mpack.integrity"


def _archived_manifest() -> dict:
    with zipfile.ZipFile(PUBLIC_SAMPLE) as archive:
        return json.loads(archive.read("manifest.json"))


def test_public_sample_sidecar_size_matches_archive_bytes() -> None:
    sidecar = json.loads(PUBLIC_SAMPLE_SIDECAR.read_text(encoding="utf-8"))

    assert sidecar["pack_size_bytes"] == PUBLIC_SAMPLE.stat().st_size


def test_public_sample_index_total_is_not_archive_byte_size() -> None:
    manifest = _archived_manifest()

    assert manifest["index_summary"]["total_size_bytes"] != PUBLIC_SAMPLE.stat().st_size


def test_public_sample_manifests_do_not_include_creator_email() -> None:
    manifests = [
        json.loads((SAMPLES_DIR / "manifest.json").read_text(encoding="utf-8")),
        _archived_manifest(),
    ]

    offenders = [manifest for manifest in manifests if "email" in manifest.get("creator_info", {})]

    assert not offenders