"""ROADEF whitespace grammar, dated occurrences, and lossless source records."""
from __future__ import annotations

import csv
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .common import source_ref


def rows(path):
    if not path.exists():
        return []
    result = []
    for line, text in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        text = text.strip()
        if text.startswith("#"):
            break
        if not text or text.startswith("%"):
            continue
        result.append({"line": line, "tokens": text.split()})
    return result


def timestamp(day, clock):
    match = re.fullmatch(r"(\d{2}):(\d{2})([+-]\d+)?", clock)
    if not match:
        raise ValueError(f"invalid ROADEF clock: {clock}")
    hour, minute, offset = match.groups()
    return datetime.strptime(day, "%d/%m/%y").replace(tzinfo=timezone.utc) + timedelta(
        days=int(offset or 0), hours=int(hour), minutes=int(minute))


def instance_paths(root):
    with (root / "verification/instance_summary.csv").open(encoding="utf-8-sig", newline="") as f:
        return [(x["instance_id"], root / x["directory"]) for x in csv.DictReader(f)]


def load(root: Path, instance_id: str):
    folder = dict(instance_paths(root))[instance_id]
    tables = {p.name: rows(p) for p in sorted(folder.glob("*.csv"))}
    conf = tables["config.csv"][0]["tokens"]
    start, end = timestamp(conf[0], conf[1]), timestamp(conf[2], conf[3])
    definitions = {r["tokens"][0]: r for r in tables["flights.csv"]}
    planes = {}
    for row in tables["aircraft.csv"]:
        t = row["tokens"]
        seats = [int(x) for x in t[3].split("/")]
        planes[t[0]] = {"tail": t[0], "type": t[1], "seats": seats,
                        "turn": int(t[6]), "initial": t[8], "maintenance": t[9], "source": row}
    delays = {(t[0], t[1]): int(t[2]) for r in tables.get("alt_flights.csv", []) for t in [r["tokens"]]}
    flights = []
    for row in tables["rotations.csv"]:
        number, day, tail = row["tokens"]
        t = definitions[number]["tokens"]
        dep, arr = timestamp(day, t[3]), timestamp(day, t[4])
        if arr <= dep:
            raise ValueError(f"arrival must include its explicit day offset: {number}, {day}")
        flight_id = f"R{number}_{dep:%Y%m%d}"
        flights.append({"id": flight_id, "number": number, "day": day, "tail": tail,
                        "origin": t[1], "destination": t[2], "dep": dep, "arr": arr,
                        "link": t[5], "delay": delays.get((number, day), 0),
                        "fixed_delay": delays.get((number, day)) if delays.get((number, day), -1) >= 0 else None,
                        "cancel_required": delays.get((number, day)) == -1,
                        "source": {"file": "rotations.csv", "line": row["line"],
                                   "definition_line": definitions[number]["line"]}})
    unavailable = []
    for row in tables.get("alt_aircraft.csv", []):
        t = row["tokens"]
        if len(t) != 5:
            raise ValueError(f"unsupported alt_aircraft shape at line {row['line']}: {t}")
        unavailable.append({"tail": t[0], "start": timestamp(t[1], t[2]),
                            "end": timestamp(t[3], t[4]), "source": row})
    journeys = []
    by_key = {(f["number"], f["day"]): f for f in flights}
    for row in tables.get("itineraries.csv", []):
        t = row["tokens"]
        legs, missing = [], []
        for i in range(4, len(t), 3):
            f = by_key.get((t[i], t[i+1]))
            (legs if f else missing).append(f["id"] if f else [t[i], t[i+1], t[i+2]])
        journeys.append({"id": f"RP{t[0]}", "count": int(t[3]), "legs": legs,
                         "missing": missing, "raw": row})
    return {"source": "roadef2009", "source_instance": instance_id, "start": start, "end": end,
            "flights": flights, "planes": planes, "unavailable": unavailable, "journeys": journeys,
            "raw_tables": tables, "source_files": [source_ref(p, root) for p in sorted(folder.glob("*.csv"))],
            "reference_kind": "historical_feasible_upper_bound_not_proven_optimum"}
