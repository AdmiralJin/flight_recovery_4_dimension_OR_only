export type JsonTask = { id: number; kind: "parse" | "stringify"; value: unknown; space?: number };
type Reply = { id: number; value?: unknown; error?: string };
type Pending = { resolve: (value: unknown) => void; reject: (error: Error) => void; timer: ReturnType<typeof setTimeout> };
let worker: Worker | null = null;
let unavailable = false;
let sequence = 0;
const pending = new Map<number, Pending>();

function disableWorker(error: Error) {
  unavailable = true;
  worker?.terminate();
  worker = null;
  for (const entry of pending.values()) { clearTimeout(entry.timer); entry.reject(error); }
  pending.clear();
}
function getWorker() {
  if (unavailable || typeof Worker === "undefined") return null;
  if (!worker) {
    try {
      worker = new Worker(new URL("./json.worker.ts", import.meta.url), { type: "module", name: "wb3-json" });
      worker.onmessage = ({ data }: MessageEvent<Reply>) => {
        const entry = pending.get(data.id);
        if (!entry) return;
        clearTimeout(entry.timer); pending.delete(data.id);
        if (data.error) entry.reject(new SyntaxError(data.error)); else entry.resolve(data.value);
      };
      worker.onerror = () => disableWorker(new Error("后台数据处理不可用，已恢复兼容模式。"));
      worker.onmessageerror = () => disableWorker(new Error("后台数据传输失败。"));
    } catch { unavailable = true; worker = null; }
  }
  return worker;
}
async function transform(kind: JsonTask["kind"], value: unknown, space?: number): Promise<unknown> {
  const engine = getWorker();
  if (engine) {
    try {
      return await new Promise((resolve, reject) => {
        const id = ++sequence;
        const timer = setTimeout(() => disableWorker(new Error("后台数据处理超时。")), 60000);
        pending.set(id, { resolve, reject, timer });
        try { engine.postMessage({ id, kind, value, space } satisfies JsonTask); }
        catch (error) { clearTimeout(timer); pending.delete(id); reject(error); }
      });
    } catch (error) {
      // Invalid JSON is still an input error; only an unavailable worker uses fallback.
      if (!unavailable) throw error;
    }
  }
  await new Promise(resolve => setTimeout(resolve, 0));
  return kind === "parse" ? JSON.parse(value as string) : JSON.stringify(value, null, space);
}
export async function stringifyJson(value: unknown, space?: number): Promise<string> {
  return await transform("stringify", value, space) as string;
}
export async function parseJson<T>(text: string): Promise<T> {
  return text.length < 131072 ? JSON.parse(text) as T : await transform("parse", text) as T;
}
