from __future__ import annotations

from collections.abc import Mapping

from backend.schemas.columns import FlightOperationType, RecoveryColumns
from backend.schemas.model_result import ModelSolveResult
from backend.solver import SolverStatus


class RecoveryHandoffError(ValueError):
    """An SRM result cannot be safely handed to resource recovery models."""


def extract_required_operated_option_ids(
    srm_result: ModelSolveResult,
    columns: RecoveryColumns,
) -> tuple[str, ...]:
    """Validate an SRM schedule and retain only operated revenue options.

    Legal cancellation selections are intentionally filtered. Unknown, ferry,
    duplicate, mismatched, extra, or missing schedule selections fail fast.
    The deterministic result is shared by ARM and CRM.
    """

    if srm_result.model_name != "fixed_column_srm":
        raise RecoveryHandoffError(
            f"expected fixed_column_srm result, got {srm_result.model_name!r}"
        )
    if srm_result.status not in {SolverStatus.OPTIMAL, SolverStatus.FEASIBLE}:
        raise RecoveryHandoffError(
            f"SRM result has no schedule solution: {srm_result.status.value}"
        )
    if srm_result.scenario_id != columns.scenario_id:
        raise RecoveryHandoffError(
            "SRM result scenario_id differs from RecoveryColumns: "
            f"{srm_result.scenario_id!r} != {columns.scenario_id!r}"
        )

    raw_mapping = srm_result.diagnostics.get("selected_option_by_flight")
    if not isinstance(raw_mapping, Mapping):
        raise RecoveryHandoffError(
            "SRM diagnostics.selected_option_by_flight must be a mapping"
        )

    option_ids = [option.option_id for option in columns.flight_options]
    if len(option_ids) != len(set(option_ids)):
        raise RecoveryHandoffError("RecoveryColumns contains duplicate option IDs")
    options = {option.option_id: option for option in columns.flight_options}
    expected_flights = tuple(
        dict.fromkeys(
            option.base_flight_id
            for option in columns.flight_options
            if option.base_flight_id is not None
        )
    )
    mapping_keys = set(raw_mapping)
    expected_set = set(expected_flights)
    missing = [
        flight_id for flight_id in expected_flights if flight_id not in mapping_keys
    ]
    extra = sorted(str(item) for item in mapping_keys - expected_set)
    if missing or extra:
        raise RecoveryHandoffError(
            f"SRM schedule selection keys mismatch: missing={missing}, extra={extra}"
        )

    selected_ids = list(raw_mapping.values())
    if any(not isinstance(option_id, str) for option_id in selected_ids):
        raise RecoveryHandoffError("SRM selected option IDs must be strings")
    if len(selected_ids) != len(set(selected_ids)):
        raise RecoveryHandoffError(
            "SRM schedule contains duplicate selected option IDs"
        )

    required: list[str] = []
    for flight_id in expected_flights:
        option_id = raw_mapping[flight_id]
        option = options.get(option_id)
        if option is None:
            raise RecoveryHandoffError(
                f"SRM schedule references unknown option {option_id!r} for {flight_id!r}"
            )
        if option.operation_type is FlightOperationType.FERRY:
            raise RecoveryHandoffError(
                f"SRM schedule cannot select ferry option {option_id!r}"
            )
        if option.base_flight_id != flight_id:
            raise RecoveryHandoffError(
                f"SRM mapping {flight_id!r} -> {option_id!r} has base flight "
                f"{option.base_flight_id!r}"
            )
        if option.operation_type is FlightOperationType.CANCEL:
            continue
        if option.operation_type is not FlightOperationType.OPERATE:
            raise RecoveryHandoffError(
                f"SRM selected option {option_id!r} has unsupported operation type"
            )
        required.append(option_id)

    return tuple(required)
