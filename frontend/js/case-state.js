const clone = (value) => structuredClone(value);

export function createCurrentCase(payload) {
  const bundle = payload.solve_bundle ? clone(payload.solve_bundle) : null;
  const scenario = clone(payload.scenario);
  return {
    metadata: clone(payload.case),
    scenario,
    scenarioBaseline: clone(scenario),
    solveBundle: bundle,
    recoveryColumns: bundle ? clone(bundle.recovery_columns) : null,
    recoveryColumnsBaseline: bundle ? clone(bundle.recovery_columns) : null,
    capacityProfile: bundle ? clone(bundle.capacity_profile) : null,
    capacityProfileBaseline: bundle ? clone(bundle.capacity_profile) : null,
    costOverrides: bundle ? clone(bundle.cost_overrides || {}) : {},
    costOverridesBaseline: bundle ? clone(bundle.cost_overrides || {}) : {},
    inputRevision: 0,
    resultRevision: null,
    resultState: "none",
  };
}

export function buildCurrentSolveBundle(state) {
  if (!state.solveBundle) return null;
  return {
    ...clone(state.solveBundle),
    scenario: clone(state.scenario),
    recovery_columns: clone(state.recoveryColumns),
    capacity_profile: clone(state.capacityProfile),
    cost_overrides: clone(state.costOverrides),
  };
}

export function advanceInputRevision(state) {
  state.inputRevision += 1;
  if (state.resultRevision !== null) state.resultState = "stale";
  return state.inputRevision;
}

export function recordSolvedRevision(state) {
  state.resultRevision = state.inputRevision;
  state.resultState = "current";
}

export function resetCurrentCaseInputs(state) {
  state.scenario = clone(state.scenarioBaseline);
  state.recoveryColumns = clone(state.recoveryColumnsBaseline);
  state.capacityProfile = clone(state.capacityProfileBaseline);
  state.costOverrides = clone(state.costOverridesBaseline);
  advanceInputRevision(state);
  return state;
}

export function capacityProfileSummary(profile) {
  if (!profile) {
    return {
      display_label: "未加载容量配置",
      capacity_profile_id: "not-loaded",
      source: "scenario_only",
      units: "座位",
      seat_capacity_by_option_id: {},
      notes: ["当前 Case 为 Scenario-only，不包含旅客容量输入。"],
    };
  }
  return {
    display_label: "当前 CASE / 剩余容量",
    capacity_profile_id: profile.capacity_profile_id,
    source: profile.source,
    units: profile.units,
    seat_capacity_by_option_id: clone(profile.seat_capacity_by_option_id),
    notes: clone(profile.notes || []),
  };
}
