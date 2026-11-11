import { Children, cloneElement, createContext, isValidElement, memo, useContext, useDeferredValue, useEffect, useId, useMemo, useRef, useState } from "react";
import type { ButtonHTMLAttributes, ReactElement, ReactNode } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import { AlertCircle, CheckCircle2, FileSearch, LoaderCircle, Search, X } from "lucide-react";
import { discardEdits, download, execute, isDirty, saveOnly, useWb } from "./state";
import { useShallow } from "zustand/react/shallow";
import { stringifyJson } from "./json";
import type { JsonObject } from "./types";
import { Help, Term } from "./Help";

export function Button({ variant = "secondary", loading = false, children, ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "secondary" | "quiet" | "danger"; loading?: boolean }) {
  const content = Children.map(children, child => isValidElement(child) && "size" in (child.props as object) ? cloneElement(child as ReactElement<Record<string, unknown>>, { "aria-hidden": true, focusable: false }) : child);
  return <button type="button" className={`button ${variant}`} {...props} disabled={loading || props.disabled} aria-busy={loading || undefined}>{loading && <LoaderCircle size={16} className="loading-icon" aria-hidden="true"/>}{content}</button>;
}
export function Card({ title, note, actions, children, className = "" }: { title?: string; note?: string; actions?: ReactNode; children: ReactNode; className?: string }) {
  return <section className={`card ${className}`}>{(title || actions) && <div className="card-head"><div><h2>{title && <Term>{title}</Term>}</h2>{note && <p>{note}</p>}</div>{actions}</div>}{children}</section>;
}
export function Empty({ title, children, action }: { title: string; children?: ReactNode; action?: ReactNode }) {
  return <div className="empty"><FileSearch size={34} strokeWidth={1.4} aria-hidden="true"/><h2>{title}</h2><p>{children}</p>{action}</div>;
}
export function LazyDetails({ summary, children, className, onOpen }: { summary: ReactNode; children: () => ReactNode; className?: string; onOpen?: () => void }) {
  const [open, setOpen] = useState(false);
  return <details className={className} onToggle={event => {
    if (event.target !== event.currentTarget) return;
    const next = event.currentTarget.open;
    setOpen(next);
    if (next) onOpen?.();
  }}><summary>{summary}</summary>{open && children()}</details>;
}
export function JsonView({ value }: { value: unknown }) {
  const [result, setResult] = useState<{ value: unknown; text: string; error?: boolean } | null>(null);
  useEffect(() => {
    let disposed = false;
    void stringifyJson(value ?? {}, 2).then(text => { if (!disposed) setResult({ value, text }); }, error => { if (!disposed) setResult({ value, text: String(error), error: true }); });
    return () => { disposed = true; };
  }, [value]);
  if (!result || result.value !== value) return <p className="muted" role="status">正在整理详情…</p>;
  return <>{result.error ? <Message tone="error">{result.text}</Message> : <pre>{result.text.slice(0, 120000)}</pre>}{result.text.length > 120000 && <div className="actions"><span className="muted">当前预览显示前 12 万字符；完整数据可导出。</span><Button onClick={() => download("details.json", result.text)}>导出完整 JSON</Button></div>}</>;
}
export function JsonDetails({ summary, value, children }: { summary: ReactNode; value: unknown; children?: ReactNode }) {
  return <LazyDetails summary={summary}>{() => <><JsonView value={value}/>{children}</>}</LazyDetails>;
}
export function OperationProgress() {
  const { busy, stage, started } = useWb(useShallow(s => ({ busy: s.busy, stage: s.busyStage, started: s.busyStartedAt })));
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    if (!busy) return;
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, [busy]);
  if (!busy) return null;
  return <div className="operation-progress"><LoaderCircle size={18} className="loading-icon" aria-hidden="true"/><div><strong role="status">{stage || busy}</strong><small>可以切换工作区查看其他内容，请等待当前操作完成。</small></div><span>{Math.max(0, Math.floor((now - (started ?? now)) / 1000))} 秒</span></div>;
}
export function Field({ label, hint, help, error, children }: { label: string; hint?: string; help?: string; error?: string; children: ReactNode }) {
  const id = useId();
  const control = isValidElement(children) ? cloneElement(children as ReactElement<Record<string, unknown>>, { id: `${id}-control`, "aria-labelledby": `${id}-label`, "aria-describedby": hint || error ? `${id}-hint` : undefined, "aria-invalid": error ? true : undefined }) : children;
  return <div className={`field ${error ? "invalid" : ""}`}><div className="field-label"><label id={`${id}-label`} htmlFor={`${id}-control`}>{label}</label><Help term={label} text={help}/></div>{control}{error ? <small id={`${id}-hint`} role="alert">{error}</small> : hint && <small id={`${id}-hint`}>{hint}</small>}</div>;
}
export function Message({ tone = "info", children }: { tone?: "info" | "success" | "error" | "warning"; children: ReactNode }) {
  const ref = useRef<HTMLDivElement>(null);
  const text = typeof children === "string" ? children : null;
  useEffect(() => {
    if (tone !== "error") return;
    const dialog = [...document.querySelectorAll("dialog[open]")].at(-1);
    if (dialog && !dialog.contains(ref.current)) return;
    ref.current?.focus({ preventScroll: false });
  }, [tone, text]);
  return <div ref={ref} tabIndex={tone === "error" ? -1 : undefined} className={`message ${tone}`} role={tone === "error" ? "alert" : "status"}>{tone === "success" ? <CheckCircle2 size={18} aria-hidden="true"/> : <AlertCircle size={18} aria-hidden="true"/>}<div>{children}</div></div>;
}
export function Modal({ title, children, onClose, wide = false }: { title: string; children: ReactNode; onClose: () => void; wide?: boolean }) {
  const ref = useRef<HTMLDialogElement>(null);
  const trigger = useRef<HTMLElement | null>(null);
  const notice = useWb(s => s.notice);
  const openingNotice = useRef(notice);
  const titleId = useId();
  useEffect(() => {
    const el = ref.current;
    if (!trigger.current) trigger.current = document.activeElement as HTMLElement;
    el?.showModal();
    return () => { el?.close(); queueMicrotask(() => { if (!el?.isConnected && trigger.current?.isConnected) trigger.current.focus(); }); };
  }, []);
  return <dialog ref={ref} className={`modal ${wide ? "wide" : ""}`} aria-labelledby={titleId} onCancel={event => { event.preventDefault(); onClose(); }}>
    <div className="modal-head"><h2 id={titleId}>{title}</h2><Button variant="quiet" aria-label="关闭对话框" onClick={onClose}><X size={20}/></Button></div>
    <div className="modal-body">{notice?.tone === "error" && notice !== openingNotice.current && <Message tone="error">{notice.text}</Message>}{children}</div>
  </dialog>;
}
const GuardContext = createContext<(action: () => void) => void>(action => action());
export function useGuard() { return useContext(GuardContext); }
export function DirtyGuard({ children }: { children: ReactNode }) {
  const [pending, setPending] = useState<(() => void) | null>(null);
  const busy = useWb(s => s.busy);
  const guard = (action: () => void) => { if (isDirty()) setPending(() => action); else action(); };
  useEffect(() => {
    const handler = (event: BeforeUnloadEvent) => { if (isDirty()) { event.preventDefault(); event.returnValue = ""; } };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, []);
  const proceed = () => { setPending(null); pending?.(); };
  return <GuardContext.Provider value={guard}>{children}{pending && <Modal title="保留未保存的修改？" onClose={() => !busy && setPending(null)}>
    <p>数据或求解配置已有修改。保存会保留整个草稿的编辑内容；放弃会恢复最近保存的版本。</p>
    <div className="dialog-actions"><Button disabled={!!busy} onClick={() => setPending(null)}>取消</Button><Button variant="danger" disabled={!!busy} onClick={() => { discardEdits(); proceed(); }}>放弃修改</Button><Button variant="primary" disabled={!!busy} onClick={async () => { if (await execute("正在保存草稿", saveOnly) && !isDirty()) proceed(); }}>保存后继续</Button></div>
  </Modal>}</GuardContext.Provider>;
}
export const labels: Record<string, string> = {
  flight_id: "航班 ID", flight_no: "航班号", origin: "出发机场", destination: "到达机场", sched_dep: "计划起飞", sched_arr: "计划到达",
  departure: "起飞时间", arrival: "到达时间", scheduled_departure: "计划起飞", scheduled_arrival: "计划到达", tail_id: "机尾 ID", aircraft_id: "飞机 ID",
  airport_id: "机场 ID", crew_id: "机组 ID", pax_group_id: "旅客组 ID", rule_id: "规则 ID", disruption_id: "扰动 ID", option_id: "候选 ID", itinerary_id: "行程 ID",
  aircraft_type: "机型", capacity: "容量", seats: "座位数（座）", residual_seats: "剩余座位（座）", physical_seats: "实际座位（座）", occupied_seats: "已占座位（座）",
  key: "参数", value: "取值", name: "名称", count: "人数（人）", size: "人数（人）", passengers: "旅客数（人）", demand: "需求（人）",
  start_time: "开始时间", end_time: "结束时间", rule_type: "扰动类型", direction: "起降方向", status: "状态", primary_change: "主要变化",
  resident: "原旅客驻留", sign_out: "改签送出", sign_in: "改签接收", unserved: "未服务", cancelled_in: "进港取消", failed_in: "中转失败",
  changed: "是否变化", operating_cost: "运行成本", cancellation_cost: "取消成本", delay_minutes: "延误（分钟）", min_turn_minutes: "最短过站（分钟）",
  max_delay: "最大延误（分钟）", min_seats: "最少座位（座）", duration: "飞行时长（分钟）", original_aircraft: "原机尾", original_crew: "原机组", original_equipment: "原机型",
  equipment_type: "机型", initial_station_at_t: "初始机场", required_station_at_T_end: "期末要求机场", maintenance_required: "需要维修", rating: "机组资质", start_station_at_t: "机组初始机场",
  airport: "机场", restriction_type: "限制类型", capacity_change: "容量变化", strategic_flag: "战略航班", market_flag: "市场类别", equipment: "机型", initial_station: "初始机场", original_terminal: "原期末机场",
  date: "运营日期", domestic: "国内航班", importance: "航班重要系数", through_passengers: "联程旅客（人）", kind: "事件类型", parking_limit: "停机容量（架）", start: "开始时间", end: "结束时间", source: "来源", original_departure: "原计划出发", recovered_dep: "恢复起飞", recovered_arr: "恢复到达", departure_delay_minutes: "起飞延误（分钟）", arrival_delay_minutes: "到达延误（分钟）", original_dep: "原计划起飞", original_tail: "原机尾", recovered_tail: "恢复机尾",
};
export const labelFor = (key: string) => labels[key] ?? key.replaceAll("_", " ");
export const display = (value: unknown) => value === null || value === undefined ? "—" : typeof value === "boolean" ? value ? "是" : "否" : typeof value === "object" ? JSON.stringify(value) : typeof value === "string" && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/.test(value) ? value.slice(5, 16).replace("T", " ") : String(value);
export const DataTable = memo(function DataTable({ rows, onSelect, selectedId, idKey = "flight_id", columns, search = true }: { rows: JsonObject[]; onSelect?: (row: JsonObject, index: number) => void; selectedId?: string | null; idKey?: string; columns?: string[]; search?: boolean }) {
  const parent = useRef<HTMLDivElement>(null);
  const [filter, setFilter] = useState("");
  const query = useDeferredValue(filter.trim().toLowerCase());
  const searchCache = useRef(new WeakMap<JsonObject, string>());
  const indexed = useMemo(() => rows.map((row, index) => ({ row, index })), [rows]);
  const filtered = useMemo(() => !query ? indexed : indexed.filter(({ row }) => {
    let text = searchCache.current.get(row);
    if (text === undefined) { text = JSON.stringify(row).toLowerCase(); searchCache.current.set(row, text); }
    return text.includes(query);
  }), [indexed, query]);
  const keys = useMemo(() => {
    const available = [...new Set(rows.slice(0, 20).flatMap(Object.keys))].filter(key => rows.slice(0, 5).some(row => typeof row[key] !== "object"));
    return columns ?? [...new Set([idKey, "flight_no", "origin", "destination", "sched_dep", "sched_arr", "original_aircraft", "name", ...available])].filter(key => available.includes(key)).slice(0, 7);
  }, [rows, idKey, columns]);
  const virtual = useVirtualizer({ count: filtered.length, getScrollElement: () => parent.current, estimateSize: () => 48, overscan: 8 });
  const width = Math.max(560, keys.length * 145);
  return <div className="data-table" aria-busy={query !== filter.trim().toLowerCase()}>
    {search && <div className="table-tools"><label className="search"><Search size={16} aria-hidden="true"/><input aria-label="筛选表格" placeholder="搜索当前表格…" value={filter} onChange={e => setFilter(e.target.value)}/></label><span>{query !== filter.trim().toLowerCase() ? "筛选中…" : `${filtered.length.toLocaleString("zh-CN")} 条记录`}</span></div>}
    {!filtered.length ? <div className="table-empty">{filter ? "没有匹配的记录" : "暂无记录；可在高级数据中补充。"}</div> : <div ref={parent} className="table-scroll" role="table" aria-label="数据记录" aria-rowcount={filtered.length + 1} aria-colcount={keys.length} tabIndex={0}>
      <div style={{ minWidth: width }}><div className="table-row table-header" role="row" style={{ gridTemplateColumns: `repeat(${keys.length}, minmax(0, 1fr))` }}>{keys.map(key => <div role="columnheader" key={key}><Term>{labelFor(key)}</Term></div>)}</div>
      <div role="rowgroup" style={{ height: virtual.getTotalSize(), position: "relative" }}>{virtual.getVirtualItems().map(item => {
        const { row, index } = filtered[item.index];
        return <div role="row" aria-rowindex={item.index + 2} className={`table-row ${selectedId && String(row[idKey]) === selectedId ? "selected" : ""}`} key={`${String(row[idKey] ?? index)}-${index}`} style={{ position: "absolute", top: 0, left: 0, width: "100%", height: item.size, transform: `translateY(${item.start}px)`, gridTemplateColumns: `repeat(${keys.length}, minmax(0, 1fr))` }}>
          {keys.map((key, column) => <div role="cell" key={key} title={display(row[key])}>{column === 0 && onSelect ? <button className="text-button" onClick={() => onSelect(row, index)} aria-label={`编辑记录 ${display(row[idKey] ?? row[key])}`}>{display(row[key])}</button> : display(row[key])}</div>)}
        </div>;
      })}</div></div>
    </div>}
  </div>;
});
