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


@pytest.fixture
def toy_case_003_data() -> dict:
    return _phase1_json("examples", "toy_case_003.json")


@pytest.fixture
def toy_case_003_columns_data() -> dict:
    return _phase1_json("columns", "toy_case_003_columns.json")


@pytest.fixture
def toy_case_004_data() -> dict:
    return _phase1_json("examples", "toy_case_004.json")


@pytest.fixture
def toy_case_004_columns_data() -> dict:
    return _phase1_json("columns", "toy_case_004_columns.json")


@pytest.fixture
def toy_case_005_data() -> dict:
    return _phase1_json("examples", "toy_case_005.json")


@pytest.fixture
def toy_case_005_columns_data() -> dict:
    return _phase1_json("columns", "toy_case_005_columns.json")


@pytest.fixture
def toy_case_006_scope_data() -> dict:
    return _phase1_json("examples", "toy_case_006_scope.json")


@pytest.fixture
def toy_case_006_scope_columns_data() -> dict:
    return _phase1_json("columns", "toy_case_006_scope_columns.json")


@pytest.fixture
def toy_case_007_string_generator_data() -> dict:
    return _phase1_json("examples", "toy_case_007_string_generator.json")


@pytest.fixture
def toy_case_007_string_generator_columns_data() -> dict:
    return _phase1_json("columns", "toy_case_007_string_generator_columns.json")


@pytest.fixture
def toy_case_008_crew_pairing_generator_data() -> dict:
    return _phase1_json("examples", "toy_case_008_crew_pairing_generator.json")


@pytest.fixture
def toy_case_008_crew_pairing_generator_columns_data() -> dict:
    return _phase1_json("columns", "toy_case_008_crew_pairing_generator_columns.json")


@pytest.fixture
def toy_case_009_passenger_itinerary_generator_data() -> dict:
    return _phase1_json("examples", "toy_case_009_passenger_itinerary_generator.json")


@pytest.fixture
def toy_case_009_passenger_itinerary_generator_columns_data() -> dict:
    return _phase1_json(
        "columns", "toy_case_009_passenger_itinerary_generator_columns.json"
    )


@pytest.fixture
def toy_case_010_fixed_column_benders_data() -> dict:
    return _phase1_json("examples", "toy_case_010_fixed_column_benders.json")


@pytest.fixture
def toy_case_010_fixed_column_benders_columns_data() -> dict:
    return _phase1_json("columns", "toy_case_010_fixed_column_benders_columns.json")


@pytest.fixture
def toy_case_011_aircraft_string_column_generation_data() -> dict:
    return _phase1_json(
        "examples", "toy_case_011_aircraft_string_column_generation.json"
    )


@pytest.fixture
def toy_case_011_aircraft_string_column_generation_columns_data() -> dict:
    return _phase1_json(
        "columns", "toy_case_011_aircraft_string_column_generation_columns.json"
    )


@pytest.fixture
def toy_case_012_crew_pairing_column_generation_data() -> dict:
    return _phase1_json("examples", "toy_case_012_crew_pairing_column_generation.json")


@pytest.fixture
def toy_case_012_crew_pairing_column_generation_columns_data() -> dict:
    return _phase1_json(
        "columns", "toy_case_012_crew_pairing_column_generation_columns.json"
    )


@pytest.fixture
def toy_case_013_benders_column_generation_data() -> dict:
    return _phase1_json("examples", "toy_case_013_benders_column_generation.json")


@pytest.fixture
def toy_case_013_benders_column_generation_columns_data() -> dict:
    return _phase1_json(
        "columns", "toy_case_013_benders_column_generation_columns.json"
    )
