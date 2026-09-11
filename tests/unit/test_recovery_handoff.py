import copy

import pytest

from backend.core import (
    AircraftRecoveryRequest,
    CrewRecoveryRequest,
    RecoveryHandoffError,
    extract_required_operated_option_ids,
)
from backend.schemas.columns import RecoveryColumns
from backend.schemas.model_result import ModelSolveResult
from backend.solver import SolverStatus


def _handoff_columns(phase1_columns_001_data):
    source = copy.deepcopy(phase1_columns_001_data)
    by_id = {item["option_id"]: item for item in source["flight_options"]}
    f2_cancel = copy.deepcopy(by_id["FO_F3_CANCEL"])
    f2_cancel.update(option_id="FO_F2_CANCEL", base_flight_id="F2")
    ferry = copy.deepcopy(by_id["FO_FERRY_CA_1140"])
    ferry["option_id"] = "FO_FERRY_TEST"
    return RecoveryColumns.model_validate(
        {
            "schema_version": "1.0.0",
            "scenario_id": source["scenario_id"],
            "time_unit": "minute",
            "notes": [],
            "flight_options": [
                by_id["FO_F1_ORIG"],
                f2_cancel,
                by_id["FO_F3_D30"],
                ferry,
            ],
            "aircraft_strings": [],
            "crew_pairings": [],
            "passenger_itineraries": [],
        }
    )


def _srm_result(scenario_id, selected):
    return ModelSolveResult(
        model_name="fixed_column_srm",
        scenario_id=scenario_id,
        status=SolverStatus.OPTIMAL,
        objective_value=0,
        best_bound=0,
        mip_gap=0,
        runtime_seconds=0,
        selected_variables={},
        continuous_variables={},
        solver_name="test",
        solver_version="test",
        raw_status=2,
        termination_reason="optimal",
        diagnostics={"selected_option_by_flight": selected},
    )


def test_handoff_excludes_cancel_and_retains_original_and_delayed_operate(
    phase1_columns_001_data,
):
    columns = _handoff_columns(phase1_columns_001_data)
    result = _srm_result(
        columns.scenario_id,
        {
            "F1": "FO_F1_ORIG",
            "F2": "FO_F2_CANCEL",
            "F3": "FO_F3_D30",
        },
    )

    required = extract_required_operated_option_ids(result, columns)
    assert required == (
        "FO_F1_ORIG",
        "FO_F3_D30",
    )
    assert AircraftRecoveryRequest(columns.scenario_id, required)
    assert CrewRecoveryRequest(columns.scenario_id, required)


@pytest.mark.parametrize(
    ("selected", "message"),
    [
        (
            {"F1": "UNKNOWN", "F2": "FO_F2_CANCEL", "F3": "FO_F3_D30"},
            "unknown option",
        ),
        (
            {
                "F1": "FO_FERRY_TEST",
                "F2": "FO_F2_CANCEL",
                "F3": "FO_F3_D30",
            },
            "ferry option",
        ),
        (
            {
                "F1": "FO_F3_D30",
                "F2": "FO_F2_CANCEL",
                "F3": "FO_F1_ORIG",
            },
            "base flight",
        ),
        (
            {"F1": "FO_F1_ORIG", "F2": "FO_F2_CANCEL"},
            "missing=",
        ),
        (
            {
                "F1": "FO_F1_ORIG",
                "F2": "FO_F1_ORIG",
                "F3": "FO_F3_D30",
            },
            "duplicate selected",
        ),
    ],
)
def test_handoff_invalid_schedule_fails_fast(
    phase1_columns_001_data, selected, message
):
    columns = _handoff_columns(phase1_columns_001_data)

    with pytest.raises(RecoveryHandoffError, match=message):
        extract_required_operated_option_ids(
            _srm_result(columns.scenario_id, selected), columns
        )


def test_handoff_requires_a_solved_srm_result(phase1_columns_001_data):
    columns = _handoff_columns(phase1_columns_001_data)
    result = _srm_result(
        columns.scenario_id,
        {"F1": "FO_F1_ORIG", "F2": "FO_F2_CANCEL", "F3": "FO_F3_D30"},
    ).model_copy(
        update={
            "status": SolverStatus.INFEASIBLE,
            "objective_value": None,
            "best_bound": None,
            "mip_gap": None,
        }
    )

    with pytest.raises(RecoveryHandoffError, match="has no schedule solution"):
        extract_required_operated_option_ids(result, columns)
