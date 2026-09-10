import copy
import json
from pathlib import Path

import pytest


@pytest.fixture
def toy_case() -> dict:
    path = Path(__file__).parents[1] / "data" / "examples" / "toy_case_001.json"
    return copy.deepcopy(json.loads(path.read_text(encoding="utf-8")))


def _phase1_json(*parts: str) -> dict:
    path = Path(__file__).parents[1].joinpath("data", *parts)
    return copy.deepcopy(json.loads(path.read_text(encoding="utf-8")))


@pytest.fixture
def phase1_benchmark_001_data() -> dict:
    return _phase1_json("examples", "phase1_benchmark_001.json")


@pytest.fixture
def phase1_columns_001_data() -> dict:
    return _phase1_json("columns", "phase1_benchmark_001_columns.json")


@pytest.fixture
def phase1_expected_001_data() -> dict:
    return _phase1_json("expected", "phase1_benchmark_001_expected.json")
