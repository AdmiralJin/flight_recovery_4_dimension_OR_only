export type JsonObject = Record<string, unknown>;

export interface CaseSummary {
  case_id: string;
  label: string;
  category: string;
  description: string;
  mode: string;
  tags: string[];
  expected?: JsonObject;
}

export interface DraftDocument {
  schema_version: "2.0.0";
  name: string;
  source_case_id?: string | null;
  capacity_semantics: "effective_legacy" | "baseline_compiled";
  scenario: JsonObject;
  solve_bundle?: JsonObject | null;
  typed_disruptions: JsonObject[];
  candidate_policy: JsonObject;
  manual_flight_options: JsonObject[];
  manual_passenger_itineraries: JsonObject[];
  expected?: JsonObject | null;
  notes: string[];
}

export interface Draft {
  draft_id: string;
  name: string;
  source_case_id?: string | null;
  working_hash: string;
  revision_count: number;
  created_at: string;
  updated_at: string;
  document: DraftDocument;
}

export interface Issue {
  code: string;
  message: string;
  severity: "error" | "warning" | "info";
  path: string;
  entity_id?: string | null;
}

export interface FlightImpact {
  flight_id: string;
  status: "normal" | "direct" | "downstream";
  direct_rule_ids: string[];
  propagation_sources: JsonObject[];
}

export interface CompilePreview {
  valid: boolean;
  draft_hash: string;
  compiled_hash?: string | null;
  issues: Issue[];
  effective_scenario?: JsonObject | null;
  solve_request?: JsonObject | null;
  capacity_changes: JsonObject[];
  flight_impacts: FlightImpact[];
  candidate_counts: Record<string, number>;
  readiness?: JsonObject | null;
}

export interface Snapshot {
  snapshot_id: string;
  draft_id: string;
  revision_id: string;
  content_hash: string;
  created_at: string;
  solve_request: JsonObject;
  compile_preview: CompilePreview;
  draft_document: DraftDocument;
  environment: JsonObject;
}

export type JobStatus =
  | "queued"
  | "preparing"
  | "running"
  | "completed"
  | "failed"
  | "cancelled"
  | "interrupted";

export interface RunRecord {
  run_id: string;
  snapshot_id: string;
  draft_id: string;
  input_hash: string;
  job_status: JobStatus;
  optimization_status?: string | null;
  trace_level: "summary" | "detailed";
  runtime_profile_id: string;
  cancel_requested: boolean;
  created_at: string;
  started_at?: string | null;
  finished_at?: string | null;
  result?: JsonObject | null;
  error?: JsonObject | null;
}

export interface RunEvent {
  run_id: string;
  seq: number;
  emitted_at: string;
  elapsed_seconds: number;
  stage: string;
  event_type: string;
  message: string;
  lower_bound?: number | null;
  upper_bound?: number | null;
  absolute_gap?: number | null;
  relative_gap?: number | null;
  metrics: JsonObject;
  artifact_refs: string[];
}

export interface ComparisonFlight {
  flight_id: string;
  original: JsonObject;
  effective: JsonObject;
  impact: FlightImpact;
  recovered?: JsonObject | null;
  changed: boolean;
  change_flags: string[];
  primary_change: string;
}

export interface Comparison {
  schema_version: string;
  snapshot_id: string;
  input_hash: string;
  optimization_status?: string | null;
  recovered_available: boolean;
  mode_semantics: Record<string, string>;
  counts: {
    total_flights: number;
    changed_flights: number;
    unchanged_flights: number;
    change_flags: Record<string, number>;
  };
  flights: ComparisonFlight[];
  aircraft: JsonObject[];
  crew: JsonObject[];
  passengers: JsonObject[];
  capacity: Record<string, JsonObject[]>;
  objective?: JsonObject | null;
  delay_distribution: JsonObject[];
}

export interface Capabilities {
  solver: { name: string; available: boolean; reason?: string | null; max_concurrent_runs: number };
  algorithm: string;
  full_scope_only: boolean;
  candidate_generation: Record<string, boolean>;
  profiles: Record<string, string>;
  runtime_profiles: Array<{
    profile_id: string;
    name: string;
    builtin: boolean;
    parameters: JsonObject;
  }>;
}
