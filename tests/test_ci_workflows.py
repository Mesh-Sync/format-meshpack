"""Regression checks for clean-runner and untrusted-PR workflow failures."""
from pathlib import Path

import pytest
from ruamel.yaml import YAML  # Installed by check-jsonschema.


WORKFLOWS = Path(__file__).resolve().parents[1] / ".github" / "workflows"


def workflow(name):
    return YAML(typ="safe").load((WORKFLOWS / name).read_text())


@pytest.mark.parametrize("filename,job", [
    ("ci.yml", "build-and-test"),
    ("ci.yml", "publish"),
    ("security.yml", "sbom-and-provenance"),
])
def test_package_jobs_provision_before_validation(filename, job):
    steps = workflow(filename)["jobs"][job]["steps"]
    commands = "\n".join(step.get("run", "") for step in steps)
    provision = commands.index("just provision")
    gates = [commands.index(gate) for gate in
             ("just public-readiness", "just publish-dry-run") if gate in commands]
    assert gates and provision < min(gates)
    rust = next(step for step in steps if "dtolnay/rust-toolchain@" in step.get("uses", ""))
    assert "clippy" in rust["with"]["components"]


def test_codeql_actions_use_the_same_revision():
    steps = workflow("security.yml")["jobs"]["codeql"]["steps"]
    revisions = [step["uses"].split("@", 1)[1] for step in steps
                 if step.get("uses", "").startswith("github/codeql-action/")]
    assert len(revisions) == 2
    assert len(set(revisions)) == 1


def test_pr_artifacts_remain_available_without_attestation_permissions():
    security = workflow("security.yml")
    assert security["permissions"] == {"contents": "read"}
    steps = security["jobs"]["sbom-and-provenance"]["steps"]
    attest = next(step for step in steps if "attest-build-provenance@" in step.get("uses", ""))
    assert "github.event_name != 'pull_request'" in attest["if"]
    assert "github.actor != 'dependabot[bot]'" in attest["if"]
    upload = next(step for step in steps if "actions/upload-artifact@" in step.get("uses", ""))
    assert "if" not in upload
    assert upload["with"]["if-no-files-found"] == "error"


def test_release_prepares_and_attests_before_any_registry_upload():
    job = workflow("ci.yml")["jobs"]["publish"]
    assert "github.event_name == 'push'" in job["if"]
    assert job["environment"] == "release"
    steps = job["steps"]
    publish = [i for i, step in enumerate(steps)
               if any(command in step.get("run", "") for command in
                      ("twine upload", "npm publish", "cargo publish"))]
    assert len(publish) == 3
    for name in ("Verify Release Tag Version", "Build Release Artifacts",
                 "Verify Release Worktree Cleanliness", "Create Attestable Package Artifacts",
                 "Upload Release Artifacts", "Attest Release Artifacts"):
        assert next(i for i, step in enumerate(steps) if step.get("name") == name) < min(publish)
    verification = next(step["run"] for step in steps if step.get("name") == "Verify Published Packages")
    assert "|| echo" not in verification
    assert 'https://pypi.org/pypi/meshpack/$PKG_VERSION/json' in verification
