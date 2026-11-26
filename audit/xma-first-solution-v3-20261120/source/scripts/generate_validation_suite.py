from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.data_generation.validation_suite import generate_validation_suite


if __name__ == "__main__":
    root = PROJECT_ROOT / "data" / "validation_suite"
    manifest = generate_validation_suite(root)
    print(f"generated {len(manifest['entries'])} validation artifacts in {root}")
