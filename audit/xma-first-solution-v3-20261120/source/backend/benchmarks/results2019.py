"""Read publisher workbooks; formulas and cached values are never conflated."""
from __future__ import annotations

from collections import Counter
from datetime import time, timedelta
from itertools import zip_longest
import openpyxl

from .common import clean, source_ref, write_json


def time_seconds(value):
    if isinstance(value, time):
        return value.hour*3600 + value.minute*60 + value.second + value.microsecond/1e6
    if isinstance(value, timedelta):
        return value.total_seconds()
    return None


def extract(root, output):
    output.mkdir(parents=True, exist_ok=True)
    counts, sheets, refs = Counter(), [], []
    with (output / "rows.jsonl").open("w", encoding="utf-8") as sink:
        import json
        for path in sorted((root / "extracted/data").glob("*.xlsx")):
            ref = source_ref(path, root)
            refs.append(ref)
            values = openpyxl.load_workbook(path, data_only=True, read_only=True)
            formulas = openpyxl.load_workbook(path, data_only=False, read_only=True)
            try:
                for v_sheet, f_sheet in zip(values, formulas):
                    header = next(f_sheet.iter_rows(max_row=1, values_only=True), ())
                    names = [str(v).strip() if v is not None else f"unnamed_{i}" for i, v in enumerate(header)]
                    sheet_counts = Counter()
                    for rownum, (vr, fr) in enumerate(zip(v_sheet.iter_rows(min_row=2), f_sheet.iter_rows(min_row=2)), 2):
                        if all(v.value is None and f.value is None for v, f in zip(vr, fr)):
                            continue
                        cells = {name: {"value": clean(v.value), "formula": f.value if f.data_type == "f" else None,
                                        "error": v.value if v.data_type == "e" else
                                            "formula_reference_error" if f.data_type == "f" and "#REF!" in str(f.value) else None,
                                        "cache_missing": f.data_type == "f" and v.value is None,
                                        "seconds": time_seconds(v.value), "cell": f"{openpyxl.utils.get_column_letter(col)}{rownum}"}
                                 for col, (name, v, f) in enumerate(zip(names, vr, fr), 1)}
                        normalized = {name.lower(): v.value for name, v in zip(names, vr)}
                        iteration, run = normalized.get("iteration"), normalized.get("run")
                        is_observation = isinstance(iteration, (int, float)) and run is not None and "cplex status" in normalized
                        cv = normalized.get("cv")
                        errors = [c["cell"] for c in cells.values() if c["error"] is not None]
                        # A publisher status is not our independently audited proof.
                        uncached = [c["cell"] for c in cells.values() if c["cache_missing"]]
                        legal_reference = bool(is_observation and isinstance(cv, (int, float)) and cv == 0 and not errors and not uncached)
                        record = {"file": ref["file"], "sha256": ref["sha256"], "sheet": v_sheet.title,
                                  "row": rownum, "iteration": clean(iteration), "run": clean(run),
                                  "kind": "run_observation" if is_observation else "summary_or_auxiliary",
                                  "publisher_status": normalized.get("cplex status"), "cv": clean(cv),
                                  "eligible_reference": legal_reference, "independent_audit": False,
                                  "formula_errors": errors, "uncached_formulas": uncached, "cells": cells}
                        sink.write(json.dumps(record, ensure_ascii=False, allow_nan=False)+"\n")
                        sheet_counts[record["kind"]] += 1
                        sheet_counts["eligible_reference"] += legal_reference
                        sheet_counts["nonzero_cv"] += bool(is_observation and isinstance(cv, (int, float)) and cv != 0)
                        sheet_counts["publisher_101"] += normalized.get("cplex status") == 101
                        sheet_counts["formula_errors"] += len(errors)
                    counts.update(sheet_counts)
                    sheets.append({"file": ref["file"], "sheet": v_sheet.title, "counts": dict(sheet_counts)})
            finally:
                values.close()
                formulas.close()
    summary = {"dataset": "TU_Delft_2019_Results", "source_files": refs, "sheets": sheets,
               "counts": dict(counts), "answer_kind": "publisher_results_without_rerunnable_inputs",
               "paired_with_2020": False, "status_101_is_not_our_optimality_proof": True}
    write_json(output / "summary.json", summary)
    return summary
