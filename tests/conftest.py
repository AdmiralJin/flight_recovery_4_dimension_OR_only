import copy
import json
from pathlib import Path

import pytest


@pytest.fixture
def toy_case() -> dict:
    path = Path(__file__).parents[1] / "data" / "examples" / "toy_case_001.json"
    return copy.deepcopy(json.loads(path.read_text(encoding="utf-8")))

