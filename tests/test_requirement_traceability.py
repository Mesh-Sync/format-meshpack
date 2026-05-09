"""Guard requirement-marker traceability against stale or invented IDs."""

from __future__ import annotations

import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
REQUIREMENTS_DIR = REPO_ROOT / "definition" / "requirements"
CONFORMANCE_DIR = REPO_ROOT / "tests" / "conformance"


def _requirement_ids() -> dict[str, str]:
    requirements: dict[str, str] = {}
    for path in sorted(REQUIREMENTS_DIR.glob("L*.md")):
        text = path.read_text(encoding="utf-8")
        for requirement_id, title in re.findall(r"### (REQ-L\d-\d{3}):\s*(.+)", text):
            requirements[requirement_id.replace("-", "_")] = title.strip()
    return requirements


def _used_markers() -> dict[str, list[str]]:
    markers: dict[str, list[str]] = {}
    for path in sorted(CONFORMANCE_DIR.glob("test_*.py")):
        text = path.read_text(encoding="utf-8")
        for marker in re.findall(r"@pytest\.mark\.(REQ_L\d_\d{3})", text):
            markers.setdefault(marker, []).append(str(path.relative_to(REPO_ROOT)))
    return markers


def test_all_requirement_markers_exist_in_requirement_docs() -> None:
    requirements = _requirement_ids()
    markers = _used_markers()

    unknown = sorted(set(markers) - set(requirements))

    assert not unknown, "Unknown requirement markers: " + ", ".join(
        f"{marker} in {', '.join(markers[marker])}" for marker in unknown
    )


def test_conformance_markers_cover_multiple_spec_levels() -> None:
    markers = set(_used_markers())

    assert any(marker.startswith("REQ_L1_") for marker in markers)
    assert any(marker.startswith("REQ_L2_") for marker in markers)
    assert any(marker.startswith("REQ_L3_") for marker in markers)