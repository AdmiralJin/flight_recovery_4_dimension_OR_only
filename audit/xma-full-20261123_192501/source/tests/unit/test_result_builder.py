from dataclasses import dataclass

import pytest
from pydantic import ValidationError

from backend.application.result_builder import ResultBuildError, _selected_map
from backend.schemas.result import RecoveredObjective


@dataclass(frozen=True)
class Candidate:
    owner: str


def test_selected_map_rejects_unknown_duplicate_and_missing_owners():
    candidates = {
        "a1": Candidate("a"),
        "a2": Candidate("a"),
        "b1": Candidate("b"),
    }
    with pytest.raises(ResultBuildError, match="no generated column"):
        _selected_map(("absent",), candidates, {"a"}, "owner")
    with pytest.raises(ResultBuildError, match="duplicate selected owner"):
        _selected_map(("a1", "a2"), candidates, {"a"}, "owner")
    with pytest.raises(ResultBuildError, match="selection ownership mismatch"):
        _selected_map(("a1",), candidates, {"a", "b"}, "owner")
    assert _selected_map(("a1", "b1"), candidates, {"a", "b"}, "owner") == {
        "a": candidates["a1"],
        "b": candidates["b1"],
    }


def test_recovered_objective_rejects_component_mismatch():
    with pytest.raises(ValidationError, match="do not sum to total"):
        RecoveredObjective(total=5, schedule=1, aircraft=1, crew=1, passenger=1)
