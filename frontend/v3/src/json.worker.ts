import type { JsonTask } from "./json";

const channel = globalThis as unknown as {
  onmessage: (event: MessageEvent<JsonTask>) => void;
  postMessage: (reply: { id: number; value?: unknown; error?: string }) => void;
};
channel.onmessage = ({ data }) => {
  try {
    const value: unknown = data.kind === "parse" ? JSON.parse(data.value as string) : JSON.stringify(data.value, null, data.space);
    channel.postMessage({ id: data.id, value });
  } catch (error) {
    channel.postMessage({ id: data.id, error: error instanceof Error ? error.message : "JSON 处理失败" });
  }
};
