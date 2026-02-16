# MeshPack Conformance Test Suite

Automated tests that verify implementations against the MeshPack specification.

## Structure

```
tests/conformance/
├── README.md              # This file
├── conftest.py            # Shared pytest fixtures & helpers
├── test_l1_minimal.py     # L1 (Minimal Reader) conformance
├── test_l2_standard.py    # L2 (Standard Reader/Writer) conformance
├── test_l3_full.py        # L3 (Full MeshSync Ecosystem) conformance
└── fixtures/              # Test data
    ├── valid/             # Known-good archives
    └── invalid/           # Intentionally broken archives
```

## Running

```bash
# All conformance tests
pytest tests/conformance/ -v

# Single conformance level
pytest tests/conformance/test_l1_minimal.py -v

# With requirement-ID markers
pytest tests/conformance/ -m "REQ_L1" -v
```

## Requirement Traceability

Every test function is decorated with `@pytest.mark.REQ_xxx` linking it to
the requirement ID from `definition/requirements/`. This enables:

- Coverage reports per requirement level
- Gap analysis (requirements without tests)
- Regression tracking

## Adding New Tests

1. Identify the requirement ID (e.g., `REQ-L2-005`)
2. Add a test in the appropriate file (`test_l2_standard.py`)
3. Decorate with `@pytest.mark.REQ_L2_005`
4. Add or reuse a fixture from `fixtures/`
5. Run `pytest --co -q` to verify the test is discovered
