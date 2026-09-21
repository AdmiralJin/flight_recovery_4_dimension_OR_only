from datetime import timedelta

from backend.application.case_service import load_case
from backend.schemas.workbench import (
    CapacitySemantics,
    DisruptionRule,
    DisruptionRuleType,
)
from backend.workbench.compiler import compile_draft, draft_from_case_payload


def test_typed_capacity_rule_changes_compiled_hash_and_closure_has_priority():
    draft = draft_from_case_payload(load_case("passenger-capacity-relaxed"))
    baseline = draft.scenario["airport_intervals"][0]
    start = baseline["start_time"]
    end = baseline["end_time"]
    draft = draft.model_copy(
        update={
            "capacity_semantics": CapacitySemantics.BASELINE_COMPILED,
            "typed_disruptions": [
                DisruptionRule(
                    rule_id="DELTA",
                    rule_type=DisruptionRuleType.BOTH_CAPACITY_DELTA,
                    airport_id=baseline["airport"],
                    start_time=start,
                    end_time=end,
                    capacity_delta=10,
                ),
                DisruptionRule(
                    rule_id="CLOSE",
                    rule_type=DisruptionRuleType.AIRPORT_CLOSURE,
                    airport_id=baseline["airport"],
                    start_time=start,
                    end_time=end,
                ),
            ],
        }
    )
    preview = compile_draft(draft)
    assert preview.valid
    assert preview.compiled_hash is not None
    changed = [item for item in preview.capacity_changes if "CLOSE" in item.applied_rule_ids]
    assert changed
    assert all(item.effective_arrival == 0 and item.effective_departure == 0 for item in changed)
    assert preview.compiled_hash != compile_draft(
        draft.model_copy(update={"typed_disruptions": []})
    ).compiled_hash


def test_legacy_effective_capacity_rejects_typed_rule_to_prevent_double_application():
    draft = draft_from_case_payload(load_case("passenger-capacity-relaxed"))
    interval = draft.scenario["airport_intervals"][0]
    draft = draft.model_copy(
        update={
            "typed_disruptions": [
                DisruptionRule(
                    rule_id="R1",
                    rule_type=DisruptionRuleType.DEPARTURE_CAPACITY_DELTA,
                    airport_id=interval["airport"],
                    start_time=interval["start_time"],
                    end_time=interval["end_time"],
                    capacity_delta=-1,
                )
            ]
        }
    )
    preview = compile_draft(draft)
    assert not preview.valid
    assert any(item.code == "legacy_capacity_rules_not_applied" for item in preview.issues)
