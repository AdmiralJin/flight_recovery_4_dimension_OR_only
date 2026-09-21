from __future__ import annotations

import json
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any

from backend.config import load_passenger_itinerary_generation_config
from backend.core import generate_passenger_itineraries
from backend.schemas.columns import RecoveryColumns
from backend.schemas.result import SolveRequest
from backend.schemas.scenario import Scenario

from .solve_service import ALGORITHM, ROOT, default_profile_ids


CATALOG_PATH = ROOT / "data" / "cases" / "catalog.json"
DATA_ROOT = (ROOT / "data").resolve()


class CaseCatalogError(ValueError):
    pass


def _data_path(relative_path: str) -> Path:
    path = (DATA_ROOT / relative_path).resolve()
    if DATA_ROOT not in path.parents or not path.is_file():
        raise CaseCatalogError(f"invalid_case_artifact:{relative_path}")
    return path


def _read_json(relative_path: str) -> Any:
    return json.loads(_data_path(relative_path).read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _catalog() -> dict[str, Any]:
    data = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    cases = data.get("cases")
    if data.get("schema_version") != "1.0.0" or not isinstance(cases, list):
        raise CaseCatalogError("invalid_case_catalog")
    ids = [item.get("case_id") for item in cases]
    if any(not isinstance(case_id, str) or not case_id for case_id in ids):
        raise CaseCatalogError("invalid_case_id")
    if len(ids) != len(set(ids)):
        raise CaseCatalogError("duplicate_case_id")
    if data.get("default_case_id") not in ids:
        raise CaseCatalogError("unknown_default_case")
    return data


def _public_metadata(item: dict[str, Any]) -> dict[str, Any]:
    return {
        key: deepcopy(item[key])
        for key in ("case_id", "label", "category", "description", "tags", "mode", "expected")
    }


def list_cases() -> dict[str, Any]:
    catalog = _catalog()
    return {
        "schema_version": catalog["schema_version"],
        "default_case_id": catalog["default_case_id"],
        "cases": [_public_metadata(item) for item in catalog["cases"]],
    }


def _manifest(case_id: str) -> dict[str, Any]:
    for item in _catalog()["cases"]:
        if item["case_id"] == case_id:
            return item
    raise CaseCatalogError("unknown_case")


def _complete_bundle(item: dict[str, Any], scenario_data: dict[str, Any]) -> dict[str, Any]:
    scenario = Scenario.model_validate(scenario_data)
    columns_data = _read_json(item["columns_file"])
    columns_data["aircraft_strings"] = []
    columns_data["crew_pairings"] = []
    columns = RecoveryColumns.model_validate(columns_data)
    if item.get("generate_passenger_itineraries"):
        profile = load_passenger_itinerary_generation_config(
            ROOT / "data" / "config" / "phase7_test_itinerary_generation_v1.json"
        )
        columns = columns.model_copy(
            update={
                "passenger_itineraries": list(
                    generate_passenger_itineraries(
                        scenario, columns.flight_options, None, profile
                    )
                )
            }
        )

    allowed = item.get("allowed_flight_option_ids")
    if allowed is not None:
        allowed_ids = set(allowed)
        columns = columns.model_copy(
            update={
                "flight_options": [
                    option
                    for option in columns.flight_options
                    if option.option_id in allowed_ids
                ],
                "passenger_itineraries": [
                    itinerary
                    for itinerary in columns.passenger_itineraries
                    if all(
                        segment.flight_option_id in allowed_ids
                        for segment in itinerary.segments
                        if segment.flight_option_id is not None
                    )
                ],
            }
        )

    capacity = _read_json(item["capacity_file"])
    if item.get("capacity_profile_id"):
        capacity["capacity_profile_id"] = item["capacity_profile_id"]
    capacity["seat_capacity_by_option_id"].update(item.get("capacity_overrides", {}))
    if allowed is not None:
        capacity["seat_capacity_by_option_id"] = {
            key: value
            for key, value in capacity["seat_capacity_by_option_id"].items()
            if key in allowed_ids
        }

    return SolveRequest(
        schema_version="1.0.0",
        scenario=scenario.model_dump(mode="json"),
        recovery_columns=columns.model_dump(mode="json"),
        capacity_profile=capacity,
        cost_profile_id="phase2_test_v1",
        cost_overrides=item.get("cost_overrides", {}),
        algorithm=ALGORITHM,
        profile_ids=default_profile_ids(),
    ).model_dump(mode="json")


def load_case(case_id: str) -> dict[str, Any]:
    item = _manifest(case_id)
    scenario = _read_json(item["scenario_file"])
    bundle = (
        _complete_bundle(item, scenario)
        if item["mode"] == "solve_bundle"
        else None
    )
    return {
        "schema_version": "1.0.0",
        "case": _public_metadata(item),
        "scenario": deepcopy(bundle["scenario"] if bundle else scenario),
        "solve_bundle": bundle,
    }
