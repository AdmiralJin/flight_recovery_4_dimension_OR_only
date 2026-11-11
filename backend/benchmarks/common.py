from __future__ import annotations

import hashlib
import json
import math
import os
import tempfile
from collections.abc import Mapping
from dataclasses import asdict, is_dataclass
from datetime import date, datetime, time, timedelta, timezone
from enum import Enum
from pathlib import Path

BASELINE = "fa293d3ba556f1e5ae621e1eee0bcb8dadab00b2"
CONVERTER = "public-v3.2"
ROOT = Path(__file__).resolve().parents[2]


def clean(value):
    if hasattr(value, "model_dump"):
        return clean(value.model_dump(mode="json"))
    if is_dataclass(value):
        return {k: clean(getattr(value, k)) for k in value.__dataclass_fields__}
    if isinstance(value, Mapping):
        return {str(k): clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [clean(v) for v in value]
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, timedelta):
        return value.total_seconds()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if hasattr(value, "item"):
        return clean(value.item())
    return value


def digest(value):
    return hashlib.sha256(json.dumps(clean(value), sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def file_hash(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                     delete=False, suffix=".tmp") as f:
        json.dump(clean(value), f, ensure_ascii=False, indent=2, allow_nan=False)
        name = f.name
    os.replace(name, path)


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def discover(root=None):
    if root:
        base = Path(root).resolve()
    else:
        found = list((ROOT / "data").glob("*_3*"))
        if len(found) != 1:
            raise ValueError("specify --data-root; expected one downloaded public-data folder")
        base = found[0]
    result = {}
    for name in ("ROADEF_2009", "TU_Delft_2019_Results", "TU_Delft_370_Disruptions"):
        matches = list(base.rglob(name)) if base.name != name else [base]
        if len(matches) != 1:
            raise ValueError(f"expected exactly one {name} under {base}")
        result[name] = matches[0]
    return result


def source_ref(path, root, **extra):
    return {"file": Path(path).relative_to(root).as_posix(), "sha256": file_hash(path), **extra}
