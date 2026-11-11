// Copy only the edited branch. Unchanged resources and undo entries share data.
export function setPath<T>(source: T, path: readonly (string | number)[], value: unknown): T {
  if (!path.length) return value as T;
  const [key, ...rest] = path;
  if (["__proto__", "prototype", "constructor"].includes(String(key))) throw new Error("不支持此字段路径。");
  const record = source as Record<string | number, unknown>;
  const next = setPath(record?.[key], rest, value);
  if (Object.is(record?.[key], next)) return source;
  const copy = Array.isArray(source) ? source.slice() : { ...record };
  (copy as Record<string | number, unknown>)[key] = next;
  return copy as T;
}
