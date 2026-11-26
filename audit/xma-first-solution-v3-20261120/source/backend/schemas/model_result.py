from __future__ import annotations

from typing import Any

from pydantic import Field, FiniteFloat, model_validator

from backend.solver.base import SolverOutcome, SolverStatus

from .common import SchemaModel


class ModelSolveResult(SchemaModel):
    """Model-neutral solver result; distinct from an oracle/reference fixture."""

    model_name: str = Field(min_length=1)
    scenario_id: str = Field(min_length=1)
    status: SolverStatus

    objective_value: FiniteFloat | None
    best_bound: FiniteFloat | None
    mip_gap: FiniteFloat | None = Field(ge=0)
    runtime_seconds: FiniteFloat = Field(ge=0)

    selected_variables: dict[str, FiniteFloat] = Field(default_factory=dict)
    continuous_variables: dict[str, FiniteFloat] = Field(default_factory=dict)

    solver_name: str = Field(min_length=1)
    solver_version: str = Field(min_length=1)
    raw_status: int | str | None
    termination_reason: str = Field(min_length=1)
    diagnostics: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_solution_shape(self):
        has_solution = self.status in {SolverStatus.OPTIMAL, SolverStatus.FEASIBLE}
        if has_solution and self.objective_value is None:
            raise ValueError(
                "optimal/feasible result requires an objective_value"
            )
        if not has_solution:
            if self.objective_value is not None:
                raise ValueError(
                    "result without a solution requires objective_value=null"
                )
            if self.selected_variables or self.continuous_variables:
                raise ValueError(
                    "result without a solution cannot contain variable values"
                )
            if self.mip_gap is not None:
                raise ValueError("result without a solution requires mip_gap=null")
        if self.status in {
            SolverStatus.INFEASIBLE,
            SolverStatus.UNBOUNDED,
            SolverStatus.INFEASIBLE_OR_UNBOUNDED,
            SolverStatus.ERROR,
        } and self.best_bound is not None:
            raise ValueError(
                f"{self.status.value} result requires best_bound=null"
            )
        return self

    @classmethod
    def from_solver_outcome(
        cls,
        *,
        scenario_id: str,
        outcome: SolverOutcome,
        solver_name: str,
        solver_version: str,
        selected_variables: dict[str, float] | None = None,
        continuous_variables: dict[str, float] | None = None,
    ) -> ModelSolveResult:
        return cls(
            model_name=outcome.model_name,
            scenario_id=scenario_id,
            status=outcome.status,
            objective_value=outcome.objective_value,
            best_bound=outcome.best_bound,
            mip_gap=outcome.mip_gap,
            runtime_seconds=outcome.runtime_seconds,
            selected_variables=selected_variables or {},
            continuous_variables=continuous_variables or {},
            solver_name=solver_name,
            solver_version=solver_version,
            raw_status=outcome.raw_status,
            termination_reason=outcome.termination_reason,
            diagnostics=dict(outcome.diagnostics),
        )
