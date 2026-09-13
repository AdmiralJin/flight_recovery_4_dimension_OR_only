import re

from backend.core import arm, crm, prm, srm
from backend.core.constraint_registry import (
    CONSTRAINT_REGISTRY,
    ConstraintKind,
    ConstraintImplementationStatus,
    list_constraint_metadata,
)


def _actual_constraint_ids():
    modules = (srm, arm, crm, prm)
    return {
        value
        for module in modules
        for name, value in vars(module).items()
        if re.fullmatch(r"(?:SRM|ARM|CRM|PRM)_C\d+_[A-Z_]+", name)
    }


def test_registry_has_one_metadata_record_for_every_actual_constraint_id():
    records = list_constraint_metadata()

    assert len(records) == 20
    assert len(CONSTRAINT_REGISTRY) == len(records)
    assert set(CONSTRAINT_REGISTRY) == _actual_constraint_ids()


def test_registry_metadata_is_complete_and_assumption_refs_are_well_formed():
    for item in list_constraint_metadata():
        assert item.model == item.constraint_id.split("-")[0]
        assert item.formula_summary
        assert item.input_dependencies
        assert item.provenance_detail
        assert item.notes
        assert all(re.fullmatch(r"A-\d{3}", ref) for ref in item.assumption_refs)
        if item.kind is ConstraintKind.PAPER_CONSTRAINT:
            assert item.paper_equation is not None


def test_registry_marks_provisional_constraints_as_proxies():
    assert CONSTRAINT_REGISTRY[srm.SRM_C05_GATE_INVENTORY].implementation_status is ConstraintImplementationStatus.PROXY
    assert CONSTRAINT_REGISTRY[srm.SRM_C06_MARKET_SEAT].implementation_status is ConstraintImplementationStatus.PROXY
    assert "not physical aircraft capacity" in CONSTRAINT_REGISTRY[prm.PRM_C03_SEAT_CAPACITY].notes.lower()
