import type { DraftDocument, JsonObject } from "./types";
import { object, rows } from "./state";
import { setPath } from "./immutable";

export const isXma = (doc: DraftDocument | null) => doc?.solve_bundle?.schema_version === "xma-solve-1.0";
export const entityGroups = [
  { id: "resources", name: "数据资源", note: "航班、飞机与旅客", entities: [["flights", "航班计划", "flight_id"], ["airports", "机场", "airport_id"], ["aircraft", "飞机", "tail_id"], ["crew", "机组", "crew_id"], ["passengers", "旅客组", "pax_group_id"]] },
  { id: "impact", name: "扰动与容量", note: "运行约束与可用资源", entities: [["typed_disruptions", "类型化扰动", "rule_id"], ["disruptions", "来源扰动", "disruption_id"], ["capacity", "余座容量", "option_id"]] },
  { id: "validation", name: "校验预览", note: "问题、影响与候选计数", entities: [] },
  { id: "advanced", name: "高级数据", note: "候选、成本与完整 JSON", entities: [["flight_options", "航班候选", "option_id"], ["passenger_itineraries", "旅客行程", "itinerary_id"], ["costs", "成本参数", "key"]] },
];
export function entityRows(doc: DraftDocument, key: string): JsonObject[] {
  const bundle = object(doc.solve_bundle);
  if (isXma(doc)) {
    const dataset = object(bundle.dataset);
    if (["flights", "aircraft"].includes(key)) return rows(dataset[key]);
    if (["disruptions", "typed_disruptions"].includes(key)) return key === "disruptions" ? rows(dataset.scenes) : [];
    if (key === "costs") return Object.entries(object(bundle.air_objective)).map(([key, value]) => ({ key, value }));
    return [];
  }
  if (["flights", "airports", "aircraft", "crew", "passengers", "disruptions"].includes(key)) return rows(doc.scenario[key]);
  if (key === "typed_disruptions") return doc.typed_disruptions;
  if (["flight_options", "passenger_itineraries"].includes(key)) return rows(object(bundle.recovery_columns)[key]);
  if (key === "capacity") return Object.entries(object(object(bundle.capacity_profile).seat_capacity_by_option_id)).map(([option_id, residual_seats]) => ({ option_id, residual_seats }));
  if (key === "costs") return Object.entries(object(bundle.cost_overrides)).map(([key, value]) => ({ key, value }));
  return [];
}
export function replaceRow(doc: DraftDocument, key: string, index: number, row: JsonObject) {
  const bundle = doc.solve_bundle;
  if (isXma(doc) && bundle) {
    if (["flights", "aircraft"].includes(key)) rows(object(bundle.dataset)[key])[index] = row;
    else if (key === "disruptions") rows(object(bundle.dataset).scenes)[index] = row;
    else if (key === "costs") object(bundle.air_objective)[String(row.key)] = row.value;
    else throw new Error("该数据通过完整 JSON 编辑。");
  } else if (["flights", "airports", "aircraft", "crew", "passengers", "disruptions"].includes(key)) rows(doc.scenario[key])[index] = row;
  else if (key === "typed_disruptions") doc.typed_disruptions[index] = row;
  else if (["flight_options", "passenger_itineraries"].includes(key) && bundle) rows(object(bundle.recovery_columns)[key])[index] = row;
  else if (key === "capacity" && bundle) object(object(bundle.capacity_profile).seat_capacity_by_option_id)[String(row.option_id)] = row.residual_seats;
  else if (key === "costs" && bundle) object(bundle.cost_overrides)[String(row.key)] = row.value;
}
export function replaceRowImmutable(doc: DraftDocument, key: string, index: number, row: JsonObject): DraftDocument {
  let path: (string | number)[];
  let value: unknown = row;
  if (isXma(doc)) {
    if (["flights", "aircraft", "disruptions"].includes(key)) path = ["solve_bundle", "dataset", key === "disruptions" ? "scenes" : key, index];
    else if (key === "costs") { path = ["solve_bundle", "air_objective", String(row.key)]; value = row.value; }
    else throw new Error("该数据通过完整 JSON 编辑。");
  } else if (["flights", "airports", "aircraft", "crew", "passengers", "disruptions"].includes(key)) path = ["scenario", key, index];
  else if (key === "typed_disruptions") path = [key, index];
  else if (["flight_options", "passenger_itineraries"].includes(key)) path = ["solve_bundle", "recovery_columns", key, index];
  else if (key === "capacity") { path = ["solve_bundle", "capacity_profile", "seat_capacity_by_option_id", String(row.option_id)]; value = row.residual_seats; }
  else if (key === "costs") { path = ["solve_bundle", "cost_overrides", String(row.key)]; value = row.value; }
  else throw new Error("该数据通过完整 JSON 编辑。");
  return setPath(doc, path, value);
}
export function blankDocument(): DraftDocument {
  return { schema_version: "2.0.0", name: "未命名研究草稿", capacity_semantics: "baseline_compiled", scenario: { schema_version: "1.0.0", scenario_id: "new-study", name: "新研究", airports: [], aircraft: [], crew: [], flights: [], passengers: [], disruptions: [] }, solve_bundle: null,
    typed_disruptions: [], candidate_policy: {}, manual_flight_options: [], manual_passenger_itineraries: [], notes: [] };
}
