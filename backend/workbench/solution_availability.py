"""Feasible recovery availability is separate from an optimality certificate."""


def has_recovered_solution(result):
    if not result:
        return False
    if result.get("status") == "optimal":
        return True
    if result.get("schema_version") == "xma-result-1.0":
        return bool((result.get("independent_audit") or {}).get("valid"))
    return bool(result.get("status") in ("not_converged", "aborted")
                and (result.get("diagnostics") or {}).get("integrated_audit_pass") is True
                and result.get("objective") is not None and result.get("resolved_flights"))
