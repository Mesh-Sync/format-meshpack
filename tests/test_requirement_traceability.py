"""Guard requirement-marker traceability against stale or invented IDs."""

from __future__ import annotations

import re
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
REQUIREMENTS_DIR = REPO_ROOT / "definition" / "requirements"
CONFORMANCE_DIR = REPO_ROOT / "tests" / "conformance"
REQUIREMENT_COVERAGE_FILE = REPO_ROOT / "tests" / "requirement_coverage.json"


def _requirement_ids() -> dict[str, str]:
    requirements: dict[str, str] = {}
    for path in sorted(REQUIREMENTS_DIR.glob("L*.md")):
        text = path.read_text(encoding="utf-8")
        for requirement_id, title in re.findall(r"### (REQ-L\d-\d{3}):\s*(.+)", text):
            requirements[requirement_id.replace("-", "_")] = title.strip()
    return requirements


def _requirement_records() -> dict[str, dict[str, str]]:
    requirements: dict[str, dict[str, str]] = {}
    for path in sorted(REQUIREMENTS_DIR.glob("L*.md")):
        text = path.read_text(encoding="utf-8")
        sections = re.split(r"(?=### REQ-L\d-\d{3}:)", text)
        for section in sections:
            heading = re.match(r"### (REQ-L\d-\d{3}):\s*(.+)", section)
            if heading is None:
                continue
            type_match = re.search(r"\*\*Type\*\*:\s*(.+)", section)
            requirements[heading.group(1)] = {
                "title": heading.group(2).strip(),
                "type": type_match.group(1).strip() if type_match else "",
                "path": str(path.relative_to(REPO_ROOT)),
            }
    return requirements


def _used_markers() -> dict[str, list[str]]:
    markers: dict[str, list[str]] = {}
    for path in sorted(CONFORMANCE_DIR.glob("test_*.py")):
        text = path.read_text(encoding="utf-8")
        for marker in re.findall(r"@pytest\.mark\.(REQ_L\d_\d{3})", text):
            markers.setdefault(marker, []).append(str(path.relative_to(REPO_ROOT)))
    return markers


def _requirement_coverage() -> dict[str, dict[str, object]]:
    with open(REQUIREMENT_COVERAGE_FILE, "r", encoding="utf-8") as coverage_file:
        data = json.load(coverage_file)
    return data["coverage"]


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


def test_all_must_requirements_have_coverage_records() -> None:
    records = _requirement_records()
    coverage = _requirement_coverage()
    must_ids = {
        requirement_id
        for requirement_id, record in records.items()
        if record["type"].startswith("MUST")
    }

    missing = sorted(must_ids - set(coverage))

    assert not missing, "MUST requirements missing coverage records: " + ", ".join(missing)


def test_coverage_records_reference_documented_requirements() -> None:
    records = _requirement_records()
    coverage = _requirement_coverage()

    unknown = sorted(set(coverage) - set(records))

    assert not unknown, "Coverage records reference unknown requirements: " + ", ".join(unknown)


def test_tested_coverage_records_have_pytest_markers() -> None:
    markers = _used_markers()
    coverage = _requirement_coverage()
    missing = []
    for requirement_id, record in coverage.items():
        if record.get("status") != "tested":
            continue
        marker = requirement_id.replace("-", "_")
        if marker not in markers:
            missing.append(f"{requirement_id} ({marker})")

    assert not missing, "Tested coverage records without pytest markers: " + ", ".join(sorted(missing))


def test_non_tested_coverage_records_have_rationale() -> None:
    coverage = _requirement_coverage()
    missing = sorted(
        requirement_id
        for requirement_id, record in coverage.items()
        if record.get("status") != "tested" and not record.get("rationale")
    )

    assert not missing, "Non-tested coverage records missing rationale: " + ", ".join(missing)


def test_coverage_evidence_paths_exist() -> None:
    coverage = _requirement_coverage()
    missing = []
    for requirement_id, record in coverage.items():
        for evidence_path in record.get("evidence", []):
            if not (REPO_ROOT / str(evidence_path)).exists():
                missing.append(f"{requirement_id}: {evidence_path}")

    assert not missing, "Coverage evidence paths do not exist: " + ", ".join(sorted(missing))