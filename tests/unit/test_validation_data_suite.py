import hashlib
import json
from pathlib import Path

import pytest

from backend.application.solve_service import solve_readiness, solve_request
from backend.data_generation.validation_suite import (
    CONSTRAINT_IDS,
    SCALE_PROFILES,
    build_stress_bundle,
)
from backend.schemas.result import SolveRequest
from backend.services.validator import validate_scenario
from backend.solver import GurobiAdapter


ROOT = Path(__file__).parents[2]
SUITE = ROOT / "data" / "validation_suite"


def _json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_manifest_has_twenty_micro_cases_five_stress_cases_and_complete_constraint_coverage():
    manifest = _json(SUITE / "manifest.json")
    entries = manifest["entries"]

    assert len([item for item in entries if item["category"] != "压力数据"]) == 20
    assert len([item for item in entries if item["category"] == "压力数据"]) == 5

    coverage = _json(SUITE / "constraint_coverage.json")
    assert set(coverage) == set(CONSTRAINT_IDS)
    assert all(coverage[constraint_id] for constraint_id in CONSTRAINT_IDS)

    for entry in entries:
        artifact = SUITE / entry["relative_path"]
        assert artifact.is_file()
        assert _sha256(artifact) == entry["sha256"]


def test_all_frozen_micro_artifacts_match_their_import_contracts():
    manifest = _json(SUITE / "manifest.json")
    micro_entries = [item for item in manifest["entries"] if item["category"] != "压力数据"]

    for entry in micro_entries:
        data = _json(SUITE / entry["relative_path"])
        expected = entry["expected"]
        if entry["import_kind"] == "scenario":
            scenario, issues = validate_scenario(data)
            assert (scenario is not None and not issues) is expected["scenario_valid"], entry["case_id"]
        else:
            request = SolveRequest.model_validate(data)
            readiness = solve_readiness(request.model_dump(mode="json"))
            assert readiness["solve_ready"], (entry["case_id"], readiness)


def test_all_stress_bundles_are_solve_ready_and_counts_match_profiles():
    manifest = _json(SUITE / "manifest.json")
    stress_entries = [item for item in manifest["entries"] if item["category"] == "压力数据"]

    for entry in stress_entries:
        data = _json(SUITE / entry["relative_path"])
        request = SolveRequest.model_validate(data)
        readiness = solve_readiness(request.model_dump(mode="json"))
        assert readiness["solve_ready"], (entry["case_id"], readiness)
        assert len(data["scenario"]["flights"]) == entry["counts"]["flights"]
        assert len(data["recovery_columns"]["flight_options"]) == entry["counts"]["flight_options"]
        assert len(data["recovery_columns"]["passenger_itineraries"]) == entry["counts"]["passenger_itineraries"]


def test_stress_generator_is_deterministic_for_parameterized_profile():
    profile = next(item for item in SCALE_PROFILES if item.profile_id == "P2-tens-seconds")
    first = build_stress_bundle(profile)
    second = build_stress_bundle(profile)
    assert first == second
    assert first == _json(SUITE / "frozen" / "stress" / "P2-tens-seconds.json")


def test_frozen_p1_reference_solves_to_audited_optimum():
    available, reason = GurobiAdapter.availability()
    if not available:
        pytest.skip(reason or "Gurobi is required for the frozen P1 solve smoke test")

    request = SolveRequest.model_validate(
        _json(SUITE / "frozen" / "stress" / "P1-seconds.json")
    )
    result = solve_request(request)

    assert result.status.value == "optimal"
    assert result.objective is not None
    assert result.objective.total == pytest.approx(18080.0)
    assert result.diagnostics.integrated_audit_pass is True
