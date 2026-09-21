import { useMemo, useRef, useState } from "react";
import { createColumnHelper, flexRender, getCoreRowModel, useReactTable } from "@tanstack/react-table";
import { useVirtualizer } from "@tanstack/react-virtual";
import type { JsonObject } from "../types";

function display(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

export function VirtualTable({
  rows,
  onSelect,
  selectedId,
  idKey,
}: {
  rows: JsonObject[];
  onSelect?: (row: JsonObject) => void;
  selectedId?: string | null;
  idKey?: string;
}) {
  const [filter, setFilter] = useState("");
  const viewport = useRef<HTMLDivElement>(null);
  const filtered = useMemo(() => {
    const needle = filter.trim().toLowerCase();
    return needle ? rows.filter((row) => JSON.stringify(row).toLowerCase().includes(needle)) : rows;
  }, [filter, rows]);
  const keys = useMemo(() => {
    const found: string[] = [];
    for (const row of filtered.slice(0, 25)) {
      for (const key of Object.keys(row)) if (!found.includes(key)) found.push(key);
    }
    return found.slice(0, 10);
  }, [filtered]);
  const helper = createColumnHelper<JsonObject>();
  const columns = useMemo(
    () => keys.map((key) => helper.accessor((row) => row[key], { id: key, header: key, cell: (info) => display(info.getValue()) })),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [keys.join("|")],
  );
  const table = useReactTable({ data: filtered, columns, getCoreRowModel: getCoreRowModel() });
  const model = table.getRowModel().rows;
  const virtualizer = useVirtualizer({ count: model.length, getScrollElement: () => viewport.current, estimateSize: () => 42, overscan: 10 });

  return (
    <section className="data-grid" aria-label="数据表格">
      <div className="table-tools">
        <label className="search-field">
          <span className="sr-only">搜索当前表</span>
          <input value={filter} onChange={(event) => setFilter(event.target.value)} placeholder="搜索或筛选…" />
        </label>
        <span>{filtered.length.toLocaleString()} 行</span>
      </div>
      <div className="table-head" style={{ gridTemplateColumns: `repeat(${Math.max(keys.length, 1)}, minmax(140px, 1fr))` }}>
        {table.getHeaderGroups().flatMap((group) => group.headers.map((header) => <div key={header.id}>{flexRender(header.column.columnDef.header, header.getContext())}</div>))}
      </div>
      <div ref={viewport} className="table-viewport" tabIndex={0}>
        <div style={{ height: virtualizer.getTotalSize(), position: "relative" }}>
          {virtualizer.getVirtualItems().map((virtual) => {
            const row = model[virtual.index];
            const rowId = idKey ? String(row.original[idKey] ?? "") : "";
            return (
              <button
                type="button"
                key={row.id}
                className={`table-row ${rowId && rowId === selectedId ? "is-selected" : ""}`}
                style={{ transform: `translateY(${virtual.start}px)`, gridTemplateColumns: `repeat(${Math.max(keys.length, 1)}, minmax(140px, 1fr))` }}
                onClick={() => onSelect?.(row.original)}
              >
                {row.getVisibleCells().map((cell) => <span key={cell.id} title={display(cell.getValue())}>{flexRender(cell.column.columnDef.cell, cell.getContext())}</span>)}
              </button>
            );
          })}
        </div>
      </div>
    </section>
  );
}
