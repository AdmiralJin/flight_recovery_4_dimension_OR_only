import pytest
from pydantic import ValidationError

from backend.schemas.expected import RecoveryExpected


def test_expected_schema_accepts_benchmark_and_preserves_from_alias(phase1_expected_001_data):
    expected = RecoveryExpected.model_validate(phase1_expected_001_data)
    dumped = expected.model_dump(mode="json", by_alias=True)
    action = dumped["reference_solution"]["recovery_actions"][0]
    assert "from" in action
    assert "from_" not in action


def test_expected_schema_forbids_unknown_fields(phase1_expected_001_data):
    phase1_expected_001_data["reference_solution"]["metrics"]["mystery"] = 1
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        RecoveryExpected.model_validate(phase1_expected_001_data)


def test_expected_schema_rejects_unknown_enum(phase1_expected_001_data):
    phase1_expected_001_data["solution_status"] = "mostly_feasible"
    with pytest.raises(ValidationError, match="feasible"):
        RecoveryExpected.model_validate(phase1_expected_001_data)


def test_undefined_objective_must_have_null_value(phase1_expected_001_data):
    phase1_expected_001_data["objective"]["value"] = 80
    with pytest.raises(ValidationError, match="must be null"):
        RecoveryExpected.model_validate(phase1_expected_001_data)
