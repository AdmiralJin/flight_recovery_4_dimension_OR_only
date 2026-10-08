import type { ComparisonFlight, FlightImpact, JsonObject } from "../types";

interface NetworkFlight {
  flight_id: string;
  origin: string;
  destination: string;
  dep: string;
  arr: string;
  state: string;
  ghost?: boolean;
}

function time(value: unknown) {
  const parsed = Date.parse(String(value ?? ""));
  return Number.isFinite(parsed) ? parsed : 0;
}

export function TimeSpaceNetwork({
  flights,
  impacts = [],
  selectedId,
  onSelect,
  label,
}: {
  flights: JsonObject[] | ComparisonFlight[];
  impacts?: FlightImpact[];
  selectedId?: string | null;
  onSelect?: (id: string) => void;
  label: string;
}) {
  const impactById = new Map(impacts.map((item) => [item.flight_id, item.status]));
  const normalized: NetworkFlight[] = flights.flatMap((item) => {
    const compared = item as ComparisonFlight;
    if (compared.original && typeof compared.original === "object") {
      const original = compared.original;
      const recovered = compared.recovered;
      const values: NetworkFlight[] = [{
        flight_id: compared.flight_id,
        origin: String(original.origin), destination: String(original.destination),
        dep: String(original.sched_dep), arr: String(original.sched_arr), state: "ghost", ghost: true,
      }];
      if (recovered && recovered.status !== "cancelled") values.push({
        flight_id: compared.flight_id,
        origin: String(recovered.recovered_origin), destination: String(recovered.recovered_destination),
        dep: String(recovered.recovered_dep), arr: String(recovered.recovered_arr), state: compared.primary_change,
      });
      if (recovered?.status === "cancelled") values.push({ ...values[0], state: "cancelled", ghost: false });
      return values;
    }
    const raw = item as JsonObject;
    return [{
      flight_id: String(raw.flight_id), origin: String(raw.origin), destination: String(raw.destination),
      dep: String(raw.sched_dep), arr: String(raw.sched_arr), state: impactById.get(String(raw.flight_id)) ?? "normal",
    }];
  });
  if (!normalized.length) return <div className="empty-state">没有可绘制的航班。</div>;
  const airports = [...new Set(normalized.flatMap((item) => [item.origin, item.destination]))];
  const min = Math.min(...normalized.map((item) => time(item.dep)));
  const max = Math.max(...normalized.map((item) => time(item.arr)));
  const width = 1120;
  const height = Math.max(360, airports.length * 74 + 72);
  const left = 92;
  const right = 32;
  const top = 44;
  const lane = (airport: string) => top + airports.indexOf(airport) * 74;
  const x = (value: string) => left + ((time(value) - min) / Math.max(max - min, 1)) * (width - left - right);
  const plotTop = top - 32;
  const plotBottom = top + Math.max(airports.length - 1, 0) * 74 + 32;
  const axisY = plotBottom + 28;
  const hour = 60 * 60 * 1_000;
  const step = Math.max(1, Math.ceil((max - min) / hour / 8)) * hour;
  const firstTick = Math.ceil(min / step) * step;
  const ticks: number[] = [];
  for (let value = firstTick; value <= max; value += step) ticks.push(value);
  if (!ticks.length) ticks.push(min);
  const tickX = (value: number) => left + ((value - min) / Math.max(max - min, 1)) * (width - left - right);

  return (
    <div className="network-scroll">
      <svg className="network" viewBox={`0 0 ${width} ${height}`} role="group" aria-label={label}>
        <title>{label}</title>
        <text className="axis-title" x={12} y={18}>机场</text>
        {airports.map((airport, index) => <g key={airport}><rect className={`lane-band ${index % 2 ? "is-alt" : ""}`} x={left} y={lane(airport) - 36} width={width - left - right} height={72} /><text x={12} y={lane(airport) + 4}>{airport}</text><line x1={left} y1={lane(airport)} x2={width - right} y2={lane(airport)} className="lane" /></g>)}
        <g className="time-axis" aria-hidden="true">
          {ticks.map((value) => <g key={value}><line className="time-grid" x1={tickX(value)} y1={plotTop} x2={tickX(value)} y2={plotBottom} /><line className="time-tick" x1={tickX(value)} y1={plotBottom} x2={tickX(value)} y2={plotBottom + 6} /><text x={tickX(value)} y={axisY} textAnchor="middle">{formatTick(value)}</text></g>)}
          <text className="axis-title" x={width - right} y={axisY + 24} textAnchor="end">时间（UTC）</text>
        </g>
        {normalized.map((flight, index) => {
          const key = `${flight.flight_id}-${index}`;
          return <g key={key} className={`flight-line state-${flight.state} ${flight.ghost ? "is-ghost" : ""} ${flight.flight_id === selectedId ? "is-selected" : ""}`} role="button" aria-label={`${flight.flight_id} ${flight.origin} 到 ${flight.destination}`} tabIndex={0} onClick={() => onSelect?.(flight.flight_id)} onKeyDown={(event) => event.key === "Enter" && onSelect?.(flight.flight_id)}>
            <line x1={x(flight.dep)} y1={lane(flight.origin)} x2={x(flight.arr)} y2={lane(flight.destination)} />
            <circle cx={x(flight.dep)} cy={lane(flight.origin)} r="4" />
            <text x={(x(flight.dep) + x(flight.arr)) / 2} y={(lane(flight.origin) + lane(flight.destination)) / 2 - 7}>{flight.flight_id}</text>
          </g>;
        })}
      </svg>
    </div>
  );
}

function formatTick(value: number) {
  const text = new Date(value).toISOString();
  return text.slice(11, 16) === "00:00" ? text.slice(5, 16).replace("T", " ") : text.slice(11, 16);
}
