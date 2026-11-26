"""Safe, chunked decoder for the publisher's pandas 0.15 HDF5 tables."""
from __future__ import annotations

import ast
import csv
import re
from datetime import datetime, timedelta, timezone

import h5py
import numpy as np

from .common import source_ref


def _column_names(value):
    # These attributes contain protocol-0 pickles. Parse string literals only;
    # never unpickle downloaded bytes or execute GLOBAL/REDUCE opcodes.
    raw = bytes(value).decode("ascii")
    names = [ast.literal_eval(x) for x in re.findall(r"(?:^|\n)(?:a)?S([^\n]+)", raw)]
    if not names or not all(isinstance(x, str) for x in names):
        raise ValueError("unsupported HDF column-name metadata")
    return names


def iter_records(path, chunk_size=16384, select=None):
    with h5py.File(path, "r") as h:
        table = h["csv/table"]
        blocks = []
        for block in table.dtype.names:
            if block == "index":
                continue
            cols = _column_names(table.attrs[block + "_kind"])
            dtype = bytes(table.attrs[block + "_dtype"]).decode()
            categories = None
            if bytes(table.attrs.get(block + "_meta", b"")) == b"category":
                meta = h[f"csv/meta/{block}/meta/table"][:]
                categories = {int(r["index"]): r["values"].decode("utf-8") for r in meta}
            blocks.append((block, cols, dtype, categories))
        for offset in range(0, len(table), chunk_size):
            chunk = table[offset:offset+chunk_size]
            indices = range(len(chunk)) if select is None else np.flatnonzero(select(chunk))
            for local in indices:
                row = chunk[local]
                record = {"_source_row": offset+local, "_source_index": int(row["index"])}
                for block, cols, dtype, categories in blocks:
                    for col, value in zip(cols, row[block]):
                        if categories is not None:
                            value = categories.get(int(value))
                        elif dtype == "datetime64":
                            value = datetime.fromtimestamp(int(value) // 10**9, timezone.utc)
                        elif dtype == "timedelta64":
                            value = timedelta(microseconds=int(value)//1000)
                        elif isinstance(value, bytes):
                            value = value.decode("utf-8").strip()
                        else:
                            value = value.item()
                        record[col] = value
                yield record


def _csv(path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f, delimiter=";"))


def flight_key(r):
    return tuple(r[k] for k in ("FLIGHT_NO", "SCHEDULED_DEPARTURE_DATETIME_UTC",
                                "ORIGIN_AIRPORT", "DESTINATION_AIRPORT"))


def load(root, start, hours=12):
    folder = root / "extracted/data"
    end = start + timedelta(hours=hours)
    ac = {r["Tailshort"]: r for r in _csv(folder / "ACType.csv")}
    tat = {r["ACTYPE_SHORT"]: int(float(next(v for k, v in r.items() if k != "ACTYPE_SHORT")))
           for r in _csv(folder / "TAT.csv")}
    schedule = []
    for r in iter_records(folder / "Schedule_Q1_2015_def.h5"):
        dep, arr = r["SCHEDULED_DEPARTURE_DATETIME_UTC"], r["SCHEDULED_ARRIVAL_DATETIME_UTC"]
        if dep < end + timedelta(days=1) and arr > start - timedelta(days=1):
            schedule.append(r)
    events = {}
    raw_events = []
    for r in iter_records(folder / "Disruptions_Q1_2015_def.h5"):
        if start - timedelta(days=1) <= r["SCHEDULED_DEPARTURE_DATETIME_UTC"] < end+timedelta(days=1):
            raw_events.append(r)
            events.setdefault(flight_key(r), []).append(r)
    flights, planes, unsupported = [], {}, []
    seen = set()
    for r in schedule:
        key = flight_key(r)
        if key in seen:
            raise ValueError(f"duplicate schedule composite key {key}")
        seen.add(key)
        tail = r["TAIL_NUMBER"]
        spec = ac[tail]
        typ = spec["ACtypeshort"]
        planes[tail] = {"tail": tail, "type": typ, "seats": [0, int(spec["Business"]), int(spec["Economy"])],
                        "turn": tat[typ], "maintenance": "NULL", "source": spec}
        matches = events.get(key, [])
        delay = 0
        arrival_delay = 0
        for event in matches:
            if event["TAIL_NUMBER"] != tail:
                unsupported.append({"reason": "disruption_tail_mismatch", "event": event, "tail": tail})
            elif event["DISRUPTION_TYPE"] == "Delay":
                # Explicit derived static scenario: observed positive departure delay
                # is a lower bound, not a claim to reproduce the dynamic paper model.
                value = float(event["DEPARTURE_DELAY"])
                if value != value or not value.is_integer():
                    unsupported.append({"reason": "non_integer_or_missing_departure_delay", "event": event, "tail": tail})
                else:
                    delay = max(delay, int(value), 0)
                    arr_value = float(event["ARRIVAL_DELAY"])
                    if arr_value == arr_value and arr_value.is_integer():
                        arrival_delay = int(arr_value)
            else:
                unsupported.append({"reason": "AC_Unavailable_interval_semantics_not_documented", "event": event, "tail": tail})
        flights.append({"id": f"D{r['_source_row']}", "number": r["FLIGHT_NO"], "tail": tail,
                        "origin": r["ORIGIN_AIRPORT"], "destination": r["DESTINATION_AIRPORT"],
                        "dep": r["SCHEDULED_DEPARTURE_DATETIME_UTC"],
                        "arr": r["SCHEDULED_ARRIVAL_DATETIME_UTC"], "delay": delay,
                        "context_arrival_delay": arrival_delay,
                        "source": {"file": "Schedule_Q1_2015_def.h5", "dataset": "/csv/table",
                                   "row": r["_source_row"]}, "raw": r, "events": matches})
    return {"source": "delft2020-derived", "source_instance": start.isoformat(), "start": start, "end": end,
            "flights": flights, "planes": planes, "unavailable": [], "journeys": [],
            "raw_tables": {"events": raw_events}, "unsupported": unsupported,
            "source_files": [source_ref(p, root) for p in sorted(folder.iterdir()) if p.is_file()],
            "reference_kind": "no_paired_answers_no_original_370_partition",
            "delay_semantics": "static_observed_positive_departure_delay_lower_bound"}


def connection_records(root, flight_records):
    """Keep raw connection observations touching the window, including outside legs."""
    keys = {(f["number"], f["dep"], f["origin"], f["destination"]) for f in flight_records}
    numbers = np.array(sorted({f["number"].encode() for f in flight_records}), dtype="S9")
    def select(chunk):
        return np.isin(chunk["values_block_6"][:, 0], numbers) | np.isin(chunk["values_block_6"][:, 1], numbers)
    for r in iter_records(root / "extracted/data/Connections_Q1_2015_def.h5", select=select):
        first = (r["first_flight_no"], r["planned_departure_time"], r["planned_origin"], r["planned_connection"])
        second = (r["second_flight_no"], r["planned_conn_departure_time"], r["planned_connection"], r["planned_destination"])
        if first in keys or second in keys:
            yield {**r, "first_in_window": first in keys, "second_in_window": second in keys}
