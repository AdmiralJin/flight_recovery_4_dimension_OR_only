import json
from copy import deepcopy
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError as JsonSchemaValidationError
from pydantic import ValidationError as PydanticValidationError

from backend.schemas import RecoveryColumns, RecoveryExpected


PROJECT_ROOT = Path(__file__).parents[2]


def _schema(name: str) -> dict:
    return json.loads((PROJECT_ROOT / "schemas" / name).read_text(encoding="utf-8"))


def _object_nodes(value, path=()):
    if isinstance(value, dict):
        node_type = value.get("type")
        if node_type == "object" or (
            isinstance(node_type, list) and "object" in node_type
        ):
            yield path, value
        for key, child in value.items():
            yield from _object_nodes(child, (*path, key))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _object_nodes(child, (*path, index))


@pytest.mark.parametrize(
    "schema_name",
    ["recovery_columns_v1.schema.json", "recovery_expected_v1.schema.json"],
)
def test_every_structured_json_schema_object_is_closed(schema_name):
    free_maps = {
        "cost_components",
        "selected_flight_option_by_flight",
        "selected_aircraft_string_by_aircraft",
        "selected_crew_pairing_by_crew",
        "selected_passenger_itinerary_by_group",
        "required_flight_option_by_flight",
        "from",
        "to",
        "components",
    }

    missing = [
        "/".join(map(str, path))
        for path, node in _object_nodes(_schema(schema_name))
        if node.get("additionalProperties") is not False
        and (not path or path[-1] not in free_maps)
    ]

    assert missing == []


@pytest.mark.parametrize(
    ("schema_name", "fixture_name", "model", "mutation"),
    [
        (
            "recovery_columns_v1.schema.json",
            "phase1_columns_001_data",
            RecoveryColumns,
            lambda data: data.update(unexpected=True),
        ),
        (
            "recovery_columns_v1.schema.json",
            "phase1_columns_001_data",
            RecoveryColumns,
            lambda data: data["flight_options"][0].update(unexpected=True),
        ),
        (
            "recovery_columns_v1.schema.json",
            "phase1_columns_001_data",
            RecoveryColumns,
            lambda data: data["crew_pairings"][0]["duties"][0].update(unexpected=True),
        ),
        (
            "recovery_expected_v1.schema.json",
            "phase1_expected_001_data",
            RecoveryExpected,
            lambda data: data.update(unexpected=True),
        ),
        (
            "recovery_expected_v1.schema.json",
            "phase1_expected_001_data",
            RecoveryExpected,
            lambda data: data["reference_solution"]["metrics"].update(unexpected=1),
        ),
        (
            "recovery_expected_v1.schema.json",
            "phase1_expected_001_data",
            RecoveryExpected,
            lambda data: data["known_equivalent_patterns"][0].update(unexpected=True),
        ),
    ],
)
def test_json_schema_and_pydantic_both_reject_structured_extra_fields(
    request, schema_name, fixture_name, model, mutation
):
    data = request.getfixturevalue(fixture_name)
    mutation(data)

    with pytest.raises(JsonSchemaValidationError, match="Additional properties"):
        Draft202012Validator(_schema(schema_name)).validate(data)
    with pytest.raises(PydanticValidationError, match="Extra inputs are not permitted"):
        model.model_validate(data)


def test_columns_cost_components_remains_a_free_key_value_map(phase1_columns_001_data):
    data = deepcopy(phase1_columns_001_data)
    data["aircraft_strings"][0]["cost_components"]["future_cost"] = 12.5

    Draft202012Validator(_schema("recovery_columns_v1.schema.json")).validate(data)
    assert RecoveryColumns.model_validate(data).aircraft_strings[0].cost_components["future_cost"] == 12.5


def test_expected_selection_and_action_maps_remain_free_key_value_maps(
    phase1_expected_001_data,
):
    data = deepcopy(phase1_expected_001_data)
    data["reference_solution"]["selected_flight_option_by_flight"]["FUTURE"] = "FO_FUTURE"
    data["reference_solution"]["recovery_actions"][0]["from"]["future_field"] = {
        "nested": True
    }

    Draft202012Validator(_schema("recovery_expected_v1.schema.json")).validate(data)
    expected = RecoveryExpected.model_validate(data)
    assert expected.reference_solution.selected_flight_option_by_flight["FUTURE"] == "FO_FUTURE"
    assert expected.reference_solution.recovery_actions[0].from_["future_field"] == {
        "nested": True
    }
