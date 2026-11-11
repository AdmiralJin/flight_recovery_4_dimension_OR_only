"""ROADEF native export/checker gate. Exit code alone never proves feasibility."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import re
import subprocess
import csv
import math
from html.parser import HTMLParser

from backend.schemas.columns import RecoveryColumns, FlightOperationType, PassengerItineraryStatus

from .common import file_hash, write_json
from .roadef import timestamp

CHECK_FILES = ["checkItinerary.txt", "checkPassengerReac.txt", "checkRotation.txt", "checkFlight.txt",
               "checkAircraftBreakdownPeriod.txt", "checkAircraftCreation.txt", "checkAircraftCapacity.txt",
               "checkAircraftSwap.txt", "checkCancellationofCreatedRotation.txt", "checkAirportCapacity.txt",
               "checkFixedFlights.txt"]


class _ReferenceTables(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables, self.rows, self.row, self.cell = [], None, None, None

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self.rows = []
            self.tables.append(self.rows)
        elif tag == "tr" and self.rows is not None:
            self.row = []
        elif tag in ("td", "th") and self.row is not None:
            self.cell = []

    def handle_data(self, data):
        if self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self.cell is not None:
            self.row.append("".join(self.cell).strip())
            self.cell = None
        elif tag == "tr" and self.row is not None:
            self.rows.append(self.row)
            self.row = None
        elif tag == "table":
            self.rows = None


def historical_references(root):
    """Published feasible upper bounds, never certificates of global optimality."""
    result = {}
    def add(case, text, path, row_number, team, table=None):
        if not re.fullmatch(r"(?:A|B|X|XA|XB)\d{2}", case or ""):
            return
        try:
            value = float("".join((text or "").split()).replace(",", "."))
        except ValueError:
            return
        if not math.isfinite(value):
            return
        record = dict(value=value, team=team, file=path.relative_to(root).as_posix(), row=row_number,
                      sha256=file_hash(path), reference_kind="historical_upper_bound", table=table,
                      competition_scored=case not in ("X01", "X02", "X03", "X04"))
        if case not in result or value < result[case]["value"]:
            result[case] = record
    for path in sorted((root / "verification").glob("official_results_table_*.csv")):
        with path.open(encoding="utf-8-sig", newline="") as stream:
            for row_number, row in enumerate(csv.DictReader(stream), 2):
                for case, text in row.items():
                    add(case, text, path, row_number, row.get("Equipe"))
    # Qualification A-instance values are in a separate publisher page, not
    # the downloaded final-results CSV tables (which contain rankings/B/X).
    path = root / "documentation/resultat_qualif.php.html"
    if path.exists():
        parser = _ReferenceTables()
        parser.feed(path.read_text(encoding="utf-8", errors="replace"))
        for table_number, rows in enumerate(parser.tables, 1):
            if not rows:
                continue
            for row_number, row in enumerate(rows[1:], 2):
                for case, text in zip(rows[0][1:], row[1:]):
                    add(case, text, path, row_number, row[0], table_number)
    return result


def historical_comparison(checker, reference):
    if not checker.get("historical_comparison_eligible") or reference is None:
        return dict(eligible=False, reason="native_feasibility_cost_or_reference_missing")
    value, baseline = checker["cost"]["total"], reference["value"]
    return dict(eligible=True, original_cost=value, reference=reference, absolute_difference=value-baseline,
                relative_difference=(value-baseline)/abs(baseline) if baseline else None,
                interpretation="difference_to_historical_upper_bound_not_optimality_gap")


def _clock(day, at):
    midnight = datetime.strptime(day, "%d/%m/%y").replace(tzinfo=timezone.utc)
    days = (at.date()-midnight.date()).days
    return at.strftime("%H:%M") + (f"{days:+d}" if days else "")


def export(public, evidence, folder):
    if public.source["dataset"] != "roadef2009":
        raise ValueError("original-rule export is only defined for ROADEF")
    folder.mkdir(parents=True, exist_ok=False)
    tables = public.source["raw_tables"]
    for filename, records in tables.items():
        (folder / filename).write_text("\n".join(" ".join(r["tokens"]) for r in records)+"\n#\n", encoding="ascii")
    for alias in ("position.csv", "positions.csv"):
        if alias in tables:
            other = "positions.csv" if alias == "position.csv" else "position.csv"
            (folder / other).write_bytes((folder / alias).read_bytes())
    columns = RecoveryColumns.model_validate(evidence["solution_columns"]) if evidence else None
    options = {o.option_id: o for o in columns.flight_options} if columns else {}
    selected = evidence.get("selected") or {} if evidence else {}
    selected_opts = {options[oid].base_flight_id: options[oid] for oid in selected.get("flight_options", [])}
    records = {f["id"]: f for f in public.source["records"]}
    owner = {}
    if columns:
        for path in columns.aircraft_strings:
            if path.string_id in selected.get("aircraft_strings", []):
                owner.update({oid: path.aircraft_id for oid in path.leg_option_ids})
    definitions = {r["tokens"][0]: r["tokens"] for r in tables["flights.csv"]}
    rotations = []
    for row in tables["rotations.csv"]:
        number, day, tail = row["tokens"]
        t = definitions[number]
        dep, arr = timestamp(day, t[3]), timestamp(day, t[4])
        fid = f"R{number}_{dep:%Y%m%d}"
        if fid in selected_opts:
            option = selected_opts[fid]
            if option.operation_type == FlightOperationType.CANCEL:
                tail = "cancelled"
            else:
                dep, arr, tail = option.dep_time, option.arr_time, owner[option.option_id]
        elif evidence:
            # Fixed observed flight disruptions are input context, not new recovery decisions.
            alt = next((r["tokens"] for r in tables.get("alt_flights.csv", [])
                        if r["tokens"][:2] == [number, day]), None)
            if alt:
                from datetime import timedelta
                if int(alt[2]) == -1:
                    tail = "cancelled"
                else:
                    dep, arr = dep+timedelta(minutes=int(alt[2])), arr+timedelta(minutes=int(alt[2]))
        rotations.append(" ".join([number, t[1], t[2], _clock(day, dep), _clock(day, arr), t[5], day, tail]))
    (folder / "sol_rotations.csv").write_text("\n".join(rotations)+"\n#\n", encoding="ascii")
    mapping_issues, result_journeys = [], []
    choices = {p.pax_group_id: p for p in columns.passenger_itineraries
               if p.itinerary_id in selected.get("passenger_itineraries", [])} if columns else {}
    for row in tables["itineraries.csv"]:
        t = row["tokens"]
        choice = choices.get("RP"+t[0])
        if choice is None:
            result_journeys.append(" ".join(t))
        elif choice.status == PassengerItineraryStatus.UNSERVED:
            result_journeys.append(" ".join(t[:4]+["cancelled"]))
        else:
            cabins = {(t[i], t[i+1]): t[i+2] for i in range(4, len(t), 3)}
            new_legs = []
            for segment in choice.segments:
                o = options[segment.flight_option_id]
                source = records.get(o.base_flight_id)
                cabin = cabins.get((source["number"], source["day"])) if source else None
                if cabin is None:
                    mapping_issues.append({"code": "unknown_cabin_on_rerouted_passenger_leg", "reservation": t[0]})
                    break
                new_legs.extend([source["number"], source["day"], cabin])
            result_journeys.append(" ".join(t[:4]+new_legs) if new_legs else " ".join(t))
    (folder / "sol_itineraries.csv").write_text("\n".join(result_journeys)+"\n#\n", encoding="ascii")
    info = {"schema_version": "roadef-export-1.0", "problem_sha256": public.problem_sha256,
            "source_instance": public.source["source_instance"],
            "mapping_issues": mapping_issues, "raw_rule_gaps": public.rule_mapping,
            "files": {p.name: file_hash(p) for p in folder.glob("*.csv")},
            "note": "Native checker required. Research objective is never used as ROADEF score."}
    write_json(folder / "export.json", info)
    return info


def check(root, folder, *, timeout=120):
    if (folder / "results").exists():
        raise ValueError("checker requires a fresh folder; stale results must not certify a run")
    exe = root / "extracted/Checker-B-2/solutionChecker-win32.exe"
    try:
        process = subprocess.run([str(exe.resolve()), str(folder.resolve())], cwd=folder,
            capture_output=True, timeout=timeout, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        (folder / "checker.stdout.txt").write_bytes(process.stdout)
        (folder / "checker.stderr.txt").write_bytes(process.stderr)
        actual = {p.name: p for p in (folder / "results").glob("*") if p.is_file()}
        # Match case-insensitively; the publisher has used variant capitalization.
        named = {name.lower(): p for name, p in actual.items()}
        missing = [name for name in CHECK_FILES if name.lower() not in named]
        nonempty = {name: p.read_text(errors="replace") for name, p in actual.items()
                    if name.lower() in {s.lower() for s in CHECK_FILES} and p.read_bytes().strip()}
        passed = process.returncode == 0 and not missing and not nonempty
        result = {"checker_sha256": file_hash(exe), "returncode": process.returncode,
                  "passed": passed, "missing_reports": missing, "violations": nonempty,
                  "output_files": {name: file_hash(p) for name, p in actual.items()}}
    except (OSError, subprocess.TimeoutExpired) as exc:
        result = {"passed": False, "status": "checker_unavailable_or_timeout", "error": str(exc)}
    # Cost execution remains useful for diagnostics even if infeasible, but its
    # total is forbidden from entering the historical-quality table in that case.
    cost_exe = root / "extracted/CostChecker-B-1/costChecker-win32.exe"
    if result["passed"]:
        try:
            cp = subprocess.run([str(cost_exe.resolve()), str(folder.resolve())], cwd=folder,
                capture_output=True, timeout=timeout, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            (folder / "cost.stdout.txt").write_bytes(cp.stdout)
            (folder / "cost.stderr.txt").write_bytes(cp.stderr)
            total = re.search(rb"Total Cost:\s*([-+\d.eE]+)", cp.stdout)
            result["cost"] = {"checker_sha256": file_hash(cost_exe), "returncode": cp.returncode,
                              "total": float(total.group(1)) if total and cp.returncode == 0 else None}
        except (OSError, subprocess.TimeoutExpired) as exc:
            result["cost"] = {"total": None, "error": str(exc)}
    result["historical_comparison_eligible"] = bool(result["passed"] and result.get("cost", {}).get("total") is not None)
    if (folder / "export.json").exists():
        from .common import read_json
        if read_json(folder / "export.json").get("mapping_issues"):
            result["historical_comparison_eligible"] = False
    # Export retains the source instance explicitly; never infer it from an output directory name.
    if (folder / "export.json").exists():
        source_case = read_json(folder / "export.json").get("source_instance")
        result["historical_comparison"] = historical_comparison(result, historical_references(root).get(source_case))
    write_json(folder / "checker-evidence.json", result)
    return result
