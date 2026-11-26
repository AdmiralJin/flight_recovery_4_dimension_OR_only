"""Post-process immutable evidence without altering experiments or solving models."""
from __future__ import annotations

from collections import Counter, defaultdict
import csv
from datetime import datetime, timedelta
import json
import math
from pathlib import Path
import statistics

from .common import file_hash, read_json, write_json, utc_now, solver_failure


def _time(value):
    return datetime.fromisoformat(value)


def _options(public, evidence):
    options = {o["option_id"]: o for o in public["recovery_columns"]["flight_options"]}
    return {options[oid]["base_flight_id"]: options[oid] for oid in evidence["selected"]["flight_options"]}


def business_metrics(public, evidence):
    if not (evidence.get("audit") or {}).get("pass"):
        return dict(eligible=False, reason="no_independently_audited_primal")
    options = _options(public, evidence)
    base = {f["flight_id"]: f for f in public["scenario"]["flights"]}
    cancelled = {fid for fid, o in options.items() if o["operation_type"] == "cancel"}
    delayed = {fid for fid, o in options.items() if (o.get("departure_delay_minutes") or 0) > 0}
    selected = evidence["selected"]
    owner = {oid: s["aircraft_id"] for s in evidence["solution_columns"]["aircraft_strings"]
             if s["string_id"] in selected["aircraft_strings"] for oid in s["leg_option_ids"]}
    source = {f["id"]: f for f in public["source"]["records"]}
    boardings = {}
    if public["source"]["dataset"] == "delft2020-derived":
        boardings = {fid: f.get("raw", {}).get("PAX_ECONOMY", 0)+f.get("raw", {}).get("PAX_BUSINESS", 0)
                     for fid, f in source.items()}
    elif public["source"]["dataset"] == "roadef2009":
        keys = {(f["number"], f["day"]): fid for fid, f in source.items()}
        boardings = Counter()
        for row in public["source"]["raw_tables"].get("itineraries.csv", []):
            t = row["tokens"]
            for i in range(4, len(t), 3):
                fid = keys.get((t[i], t[i+1]))
                if fid:
                    boardings[fid] += int(t[3])
    groups = {g["pax_group_id"]: g for g in public["scenario"]["passengers"]}
    itineraries = [p for p in evidence["solution_columns"]["passenger_itineraries"]
                   if p["itinerary_id"] in selected["passenger_itineraries"]]
    return dict(eligible=True, flights=len(base), cancelled_flights=len(cancelled), delayed_flights=len(delayed),
        total_departure_delay_minutes=sum(o.get("departure_delay_minutes") or 0 for o in options.values()),
        reassigned_flights=sum(o["operation_type"] == "operate" and owner.get(o["option_id"]) != base[fid]["original_aircraft"]
                               for fid, o in options.items()),
        original_boardings_on_cancelled_legs=sum(boardings.get(fid, 0) for fid in cancelled),
        original_boardings_on_delayed_legs=sum(boardings.get(fid, 0) for fid in delayed),
        optimized_passenger_groups=len(groups), optimized_passengers=sum(g["count"] for g in groups.values()),
        unserved_optimized_passengers=sum(groups[p["pax_group_id"]]["count"] for p in itineraries if p["status"] == "unserved"),
        optimized_passenger_delay_minutes=sum(groups[p["pax_group_id"]]["count"]*(p.get("arrival_delay_minutes") or 0)
                                             for p in itineraries if p["status"] != "unserved"),
        exposure_unit="original flight-leg boardings; not distinct disrupted or recovered people")


def connection_impact(public, evidence, connections, min_connection):
    """Assess observed connection records; never construct passenger demands."""
    chosen = _options(public, evidence)
    records = public["source"]["records"]+public["fixed_context"]["flights"]
    key = lambda f: (f["number"], _time(f["dep"]), f["origin"], f["destination"])
    lookup = {key(f): f for f in records}
    def times(f, recovered):
        if any(e.get("DISRUPTION_TYPE") != "Delay" for e in f.get("events", [])):
            return None
        if recovered and f["id"] in chosen:
            o = chosen[f["id"]]
            return None if o["operation_type"] == "cancel" else (_time(o["dep_time"]), _time(o["arr_time"]))
        if f.get("cancel_required"):
            return None
        return (_time(f["dep"])+timedelta(minutes=max(0, f["delay"])),
                _time(f["arr"])+timedelta(minutes=f.get("context_arrival_delay", max(0, f["delay"]))))
    rows, counts = [], Counter()
    for connection in connections:
        k1 = (connection["first_flight_no"], _time(connection["planned_departure_time"]),
              connection["planned_origin"], connection["planned_connection"])
        k2 = (connection["second_flight_no"], _time(connection["planned_conn_departure_time"]),
              connection["planned_connection"], connection["planned_destination"])
        first, second = lookup.get(k1), lookup.get(k2)
        if not any(f and f["id"] in chosen for f in (first, second)):
            continue
        row = dict(source_row=connection["_source_row"], passengers=connection["num_passengers"],
                   first_in_window=connection["first_in_window"], second_in_window=connection["second_in_window"])
        mct = min_connection.get(connection["planned_connection"])
        unknown = (first is None or second is None or mct is None or any(
            e.get("DISRUPTION_TYPE") != "Delay" for f in (first, second) if f for e in f.get("events", [])))
        if unknown:
            row.update(status="unknown_missing_fixed_context_mct_or_event_semantics")
            counts["unknown_records"] += 1
        else:
            def protected(recovered):
                a, b = times(first, recovered), times(second, recovered)
                return bool(a and b and b[0]-a[1] >= timedelta(minutes=mct))
            before, after = protected(False), protected(True)
            row.update(status="evaluated", before_protected=before, after_protected=after, mct_minutes=mct)
            counts["evaluated_records"] += 1
            counts["newly_broken_connection_boardings"] += connection["num_passengers"] if before and not after else 0
            counts["restored_connection_boardings"] += connection["num_passengers"] if not before and after else 0
        rows.append(row)
    return dict(counts=dict(counts), records=rows,
        scope="source connection observations touching selected legs; not full OD or distinct passengers",
        baseline="derived positive departure delay and observed arrival delay; outside legs fixed to source context")


def publisher_distributions(path):
    groups = defaultdict(lambda: dict(observations=0, eligible=0, statuses=Counter(), metrics=defaultdict(list)))
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            row = json.loads(line)
            if row["kind"] != "run_observation":
                continue
            group = groups[row["file"], row["sheet"]]
            group["observations"] += 1
            group["statuses"][str(row["publisher_status"])] += 1
            if not row["eligible_reference"]:
                continue
            group["eligible"] += 1
            for name, cell in row["cells"].items():
                normalized = name.lower()
                if normalized in ("cost of disruption", "otp", "flights", "aircraft", "dv", "constraints", "dpc", "xp", "xf", "mcp", "rcp"):
                    value = cell["value"]
                elif cell["seconds"] is not None:
                    normalized, value = normalized+"_seconds", cell["seconds"]
                else:
                    continue
                if isinstance(value, (int, float)) and math.isfinite(value):
                    group["metrics"][normalized].append(value)
    return [dict(file=file, sheet=sheet, observations=g["observations"], eligible=g["eligible"],
        publisher_statuses=dict(g["statuses"]), metrics={name: dict(n=len(v), min=min(v), median=statistics.median(v), max=max(v))
        for name, v in g["metrics"].items()}) for (file, sheet), g in groups.items()]


def analyze(folder, output):
    folder, output = folder.resolve(), output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    manifest, state = read_json(folder / "manifest.json"), read_json(folder / "state.json")
    connections = read_json(folder / "source_connections.json")
    airport_file = Path(manifest["source_roots"]["TU_Delft_370_Disruptions"]) / "extracted/data/Airports.csv"
    with airport_file.open(encoding="utf-8-sig", newline="") as stream:
        mct = {r["airport"]: int(r["min_connection"]) for r in csv.DictReader(stream, delimiter=";")}
    metrics = []
    original_rule_comparisons = []
    from .external import historical_references, historical_comparison
    references = historical_references(Path(manifest["source_roots"]["ROADEF_2009"]))
    for job in manifest["jobs"]:
        directory = folder / "jobs" / job["id"]
        if job["kind"] not in ("solve", "stop") or not (directory / "evidence.json").exists():
            continue
        public, evidence = read_json(directory / "input.json"), read_json(directory / "evidence.json")
        failure = solver_failure(evidence)
        row = dict(job=job["id"], instance=job["instance"], algorithm=job["algorithm"],
                   status=failure["status"] if failure else evidence["status"], raw_status=evidence["status"],
                   input_sha256=file_hash(directory / "input.json"),
                   evidence_sha256=file_hash(directory / "evidence.json"), metrics=business_metrics(public, evidence))
        if row["metrics"]["eligible"] and public["source"]["dataset"] == "delft2020-derived":
            expected = next(r["sha256"] for r in public["source"]["files"] if r["file"] == "extracted/data/Airports.csv")
            if file_hash(airport_file) != expected:
                raise ValueError("published connection-time file changed after experiment freeze")
            impact = connection_impact(public, evidence, connections, mct)
            row["connection_impact"] = {k: v for k, v in impact.items() if k != "records"}
            write_json(output / "connections" / (job["id"]+".json"), impact)
        metrics.append(row)
    for entry in read_json(folder / "registry.json"):
        if entry["source"] != "roadef2009":
            continue
        native_jobs = [j for j in manifest["jobs"] if j["kind"] == "external" and j["instance"] == entry["id"]]
        native = []
        for job in native_jobs:
            path = folder / "jobs" / job["id"] / "native/checker-evidence.json"
            if path.exists():
                result = read_json(path)
                native.append(dict(job=job["id"], evidence_sha256=file_hash(path),
                    passed=result["passed"], historical_comparison=historical_comparison(result, references.get(entry["source_instance"])),
                    violations=list(result.get("violations", {}))))
        eligible = any((n.get("historical_comparison") or {}).get("eligible") for n in native)
        original_rule_comparisons.append(dict(instance=entry["id"], source_instance=entry["source_instance"],
            precheck_ready=entry["precheck"]["ready"], native_evidence=native,
            historical_eligible=eligible,
            no_score_reason=None if eligible else ("native_feasibility_cost_or_mapping_failed" if native
                                                   else "native_evaluation_not_executed_or_no_audited_solution"),
            scheduled_task_verdicts={j["id"]: state["jobs"].get(j["id"], {}).get("verdict", "pending") for j in native_jobs}))
    result = dict(schema_version="public-post-analysis-1.0", created_at=utc_now(), analysis_sha256=file_hash(Path(__file__)),
        analysis_dependencies_sha256={name: file_hash(Path(__file__).with_name(name))
                                    for name in ("analysis.py", "common.py", "external.py")},
        campaign_manifest_sha256=manifest["manifest_sha256"], campaign_status=state["status"],
        source_connections_sha256=file_hash(folder / "source_connections.json"),
        publisher_rows_sha256=file_hash(folder / "reference-2019/rows.jsonl"),
        jobs_with_evidence=len(metrics), audited_business_observations=sum(r["metrics"]["eligible"] for r in metrics),
        publisher_distributions=publisher_distributions(folder / "reference-2019/rows.jsonl"), observations=metrics,
        original_rule_comparisons=original_rule_comparisons,
        historical_references=references,
        limitations=["publisher sheets may overlap; do not pool as independent samples",
                     "only the frozen January 1 connection window is available for connection analysis",
                     "connection and boarding exposures do not establish recovered passenger demand"])
    write_json(output / "analysis.json", result)
    return dict(output=str(output / "analysis.json"), jobs_with_evidence=result["jobs_with_evidence"],
                audited_business_observations=result["audited_business_observations"])
