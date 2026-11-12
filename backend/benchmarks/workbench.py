from backend.schemas.workbench import DraftDocument, CompilePreview, WorkbenchIssue, FlightImpact
from backend.workbench.storage import content_hash

from .common import digest
from .model import PublicSolveRequest
from .solve import precheck


def make_document(request):
    return DraftDocument(name=request.instance_id, source_case_id=request.instance_id,
        scenario=request.scenario.model_dump(mode="json"), solve_bundle=request.model_dump(mode="json"),
        notes=["Public research model. CRM disabled. Original-rule scoring requires separate native checker evidence.",
               "Frozen candidates/configuration: regenerate the instance via the benchmark CLI to change the problem."])


def compile_document(document):
    draft_hash = content_hash(document.model_dump(mode="json"))
    try:
        request = PublicSolveRequest.model_validate(document.solve_bundle)
        if digest(document.scenario) != digest(request.scenario):
            raise ValueError("display scenario differs from frozen public problem; regenerate the instance via CLI")
        if (document.typed_disruptions or document.manual_flight_options or document.manual_passenger_itineraries
                or document.candidate_policy.regenerate_flight_options):
            raise ValueError("public benchmark snapshots require frozen candidates and source disturbances")
        ready = precheck(request)
        supported = request.algorithm in ("air_bp", "direct_mip", "integrated_oracle")
        if request.algorithm == "integrated_oracle" and len(request.scenario.flights) > 12:
            supported = False
        valid = ready["ready"] and supported
        return CompilePreview(valid=valid, draft_hash=draft_hash,
            compiled_hash=content_hash(request.model_dump(mode="json")) if valid else None,
            effective_scenario=request.scenario.model_dump(mode="json"),
            solve_request=request.model_dump(mode="json") if valid else None,
            readiness={"solve_ready": valid, "missing_inputs": [], "invalid_profiles": [],
                       "semantics": "PUBLIC_RESEARCH_MODEL_NOT_ORIGINAL_RULE_CERTIFICATION"},
            candidate_counts={"flight_options": len(request.recovery_columns.flight_options),
                              "passenger_itineraries": len(request.recovery_columns.passenger_itineraries),
                              "aircraft_strings": 0, "crew_pairings": 0},
            flight_impacts=[FlightImpact(flight_id=f.flight_id,
                status="direct" if f.cancel_required or (f.earliest_departure and f.earliest_departure > f.sched_dep) else "normal")
                for f in request.scenario.flights],
            issues=[WorkbenchIssue(code="public_precheck", message=str(issue), path="solve_bundle") for issue in ready["issues"]]
                   + ([] if supported else [WorkbenchIssue(code="unsupported_public_algorithm",
                       message="请选择直接模型或 AIR 主线；全路径 Oracle 限 12 个航班以内。", path="solve_bundle.algorithm")]))
    except ValueError as exc:
        return CompilePreview(valid=False, draft_hash=draft_hash,
            issues=[WorkbenchIssue(code="invalid_public_problem", message=str(exc), path="solve_bundle")])
