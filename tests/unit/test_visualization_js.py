from pathlib import Path
import shutil
import subprocess

import pytest


def test_visualization_pure_functions_with_node():
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is not available for the dependency-free frontend tests")

    test_file = Path(__file__).parents[1] / "frontend" / "visualization.test.mjs"
    result = subprocess.run(
        [node, "--test", str(test_file)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
