from pydantic import ValidationError
import pytest

from backend.schemas import Scenario


def test_toy_case_schema_and_json_round_trip(toy_case):
    scenario = Scenario.model_validate(toy_case)
    restored = Scenario.model_validate_json(scenario.model_dump_json())

    assert restored == scenario
    assert len(restored.airports) == 3
    assert len(restored.flights) == 6
    assert len(restored.aircraft) == 2
    assert len(restored.crew) == 2
    assert len(restored.passengers) == 4


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda data: data["flights"][0].update(max_delay=-1), "greater than or equal to 0"),
        (lambda data: data["flights"][0].update(duration=61), "duration must equal"),
        (lambda data: data["flights"][0].update(sched_arr=data["flights"][0]["sched_dep"]), "sched_dep must be before"),
        (lambda data: data["flights"][0].update(sched_dep="2026-01-15T08:00:00"), "timezone"),
        (lambda data: data["crew"][0].update(original_pairing=["F1"]), "must equal original_duties"),
        (lambda data: data["disruptions"][0].update(capacity_change=0), "must be non-zero"),
    ],
)
def test_structural_schema_rejects_invalid_values(toy_case, mutation, message):
    mutation(toy_case)
    with pytest.raises(ValidationError, match=message):
        Scenario.model_validate(toy_case)


def test_schema_forbids_undeclared_fields(toy_case):
    toy_case["flights"][0]["mystery"] = "not in contract"
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        Scenario.model_validate(toy_case)
