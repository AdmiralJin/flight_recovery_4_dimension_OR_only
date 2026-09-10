import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const projectRoot = resolve(dirname(fileURLToPath(import.meta.url)), "../..");
const source = readFileSync(resolve(projectRoot, "frontend/js/visualization.js"), "utf8");
const moduleUrl = `data:text/javascript;base64,${Buffer.from(source).toString("base64")}`;
const visualization = await import(moduleUrl);
const toyCase = JSON.parse(readFileSync(
  resolve(projectRoot, "data/examples/toy_case_001.json"),
  "utf8",
));
const phase1ValidationCase = JSON.parse(readFileSync(
  resolve(projectRoot, "data/examples/phase1_validation_001.json"),
  "utf8",
));

test("classifies supported and unknown disruption types", () => {
  assert.equal(visualization.classifyDisruptionType("departure_capacity_reduction"), "departure");
  assert.equal(visualization.classifyDisruptionType("ARRIVAL_RATE"), "arrival");
  assert.equal(visualization.classifyDisruptionType("airport_closure"), "both");
  assert.equal(visualization.classifyDisruptionType("wind_restriction"), "unknown");
});

test("chooses a readable tick interval for the eight-hour toy horizon", () => {
  assert.equal(visualization.chooseTimeTickMinutes(
    toyCase.recovery_window.start_time,
    toyCase.recovery_window.end_time,
  ), 60);
});

test("derives direct and downstream flight impacts without inventing results", () => {
  const impacts = visualization.deriveFlightImpacts(toyCase);
  const statuses = Object.fromEntries(
    [...impacts.entries()].map(([flightId, impact]) => [flightId, impact.status]),
  );

  assert.deepEqual(statuses, {
    F1: "normal",
    F2: "direct",
    F3: "downstream",
    F4: "normal",
    F5: "direct",
    F6: "downstream",
  });
  assert.deepEqual(
    impacts.get("F3").propagationSources.map(({ type, resourceId, sourceFlightId }) => (
      `${type}:${resourceId}:${sourceFlightId}`
    )),
    ["aircraft:AC1:F2", "crew:C1:F2"],
  );
  assert.deepEqual(
    impacts.get("F6").propagationSources.map(({ type, resourceId, sourceFlightId }) => (
      `${type}:${resourceId}:${sourceFlightId}`
    )),
    ["aircraft:AC2:F5", "crew:C2:F5"],
  );
});

test("retains every upstream direct source along an original resource chain", () => {
  const scenario = structuredClone(toyCase);
  scenario.disruptions.push({
    ...scenario.disruptions[0],
    airport: "A",
    start_time: "2026-01-15T08:00:00Z",
    end_time: "2026-01-15T08:30:00Z",
  });
  const impacts = visualization.deriveFlightImpacts(scenario);

  assert.deepEqual(
    impacts.get("F3").propagationSources
      .filter(({ type }) => type === "aircraft")
      .map(({ sourceFlightId }) => sourceFlightId),
    ["F1", "F2"],
  );
});

test("does not infer exposure for an unknown restriction type", () => {
  const scenario = structuredClone(toyCase);
  scenario.disruptions[0].restriction_type = "wind_restriction";
  const impacts = visualization.deriveFlightImpacts(scenario);

  assert.ok([...impacts.values()].every((impact) => impact.status === "normal"));
});

test("derives passenger risk from operationally flagged itinerary flights", () => {
  const impacts = visualization.deriveFlightImpacts(toyCase);
  const risks = visualization.derivePassengerRisk(toyCase, impacts);

  assert.equal(risks.get("P1").firstAffectedFlightId, "F2");
  assert.equal(risks.get("P2").firstAffectedFlightId, "F5");
  assert.equal(risks.get("P3").firstAffectedFlightId, "F3");
  assert.equal(risks.get("P4").firstAffectedFlightId, "F6");
  assert.ok([...risks.values()].every((risk) => risk.atRisk));
});

test("counts toy-case departure and arrival capacity loads", () => {
  const departure = visualization.deriveCapacityCells(toyCase, "departures")[0];
  const arrival = visualization.deriveCapacityCells(toyCase, "arrivals")[0];

  assert.deepEqual(
    { load: departure.load, capacity: departure.capacity, status: departure.status },
    { load: 2, capacity: 1, status: "over" },
  );
  assert.deepEqual(
    { load: arrival.load, capacity: arrival.capacity, status: arrival.status },
    { load: 2, capacity: 2, status: "at" },
  );
});

test("capacity counting uses half-open interval boundaries", () => {
  const scenario = structuredClone(toyCase);
  scenario.flights.push({
    ...scenario.flights[0],
    flight_id: "BOUNDARY",
    origin: "B",
    sched_dep: "2026-01-15T11:00:00Z",
  });

  const departure = visualization.deriveCapacityCells(scenario, "departures")[0];
  assert.equal(departure.load, 2);
});

test("phase1 validation case has the intended deterministic impacts", () => {
  const impacts = visualization.deriveFlightImpacts(phase1ValidationCase);
  const byStatus = (status) => [...impacts]
    .filter(([, impact]) => impact.status === status)
    .map(([flightId]) => flightId);

  assert.deepEqual(byStatus("direct"), ["F05", "F06"]);
  assert.deepEqual(byStatus("downstream"), ["F09", "F10"]);
  assert.deepEqual(byStatus("normal"), ["F01", "F02", "F03", "F04", "F07", "F08", "F11", "F12"]);

  const risks = visualization.derivePassengerRisk(phase1ValidationCase, impacts);
  assert.deepEqual(
    [...risks].filter(([, risk]) => risk.atRisk).map(([passengerId]) => passengerId),
    ["P01", "P02", "P05", "P06"],
  );

  const constrainedBucket = visualization.deriveCapacityCells(phase1ValidationCase, "departures")
    .find((cell) => cell.airport === "B" && cell.startTime === "2026-01-15T08:00:00Z");
  assert.deepEqual(
    { load: constrainedBucket.load, capacity: constrainedBucket.capacity, status: constrainedBucket.status },
    { load: 2, capacity: 1, status: "over" },
  );
});
