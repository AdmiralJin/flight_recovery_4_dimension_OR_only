const clone = (value) => structuredClone(value);

export function buildCurrentSolveBundle(state) {
  if (!state.solveBundle) return null;
  return {
    ...clone(state.solveBundle),
    scenario: clone(state.scenario),
    recovery_columns: clone(state.recoveryColumns),
    capacity_profile: clone(state.passengerCapacityProfile),
    cost_overrides: clone(state.costOverrides),
  };
}

export function beginSolve(state) {
  if (state.solving) return null;
  state.solving = true;
  return {
    revision: state.revision,
    bundle: buildCurrentSolveBundle(state),
  };
}

export function acceptSolveResult(state, request, result) {
  if (!request || request.revision !== state.revision) return false;
  state.recoveredResult = result;
  state.recoveredResultRevision = request.revision;
  state.resultStale = false;
  return true;
}

export function finishSolve(state) {
  state.solving = false;
}

export function snapshotCaseBaseline(state) {
  return clone({
    scenario: state.scenario,
    solveBundle: state.solveBundle,
    recoveryColumns: state.recoveryColumns,
    passengerCapacityProfile: state.passengerCapacityProfile,
    costOverrides: state.costOverrides,
    caseId: state.caseId,
    source: state.source,
  });
}

export function restoreCaseBaseline(state) {
  if (!state.baseline) return false;
  Object.assign(state, clone(state.baseline));
  state.revision += 1;
  state.dirty = false;
  state.recoveredResult = null;
  state.recoveredResultRevision = null;
  state.resultStale = false;
  return true;
}
