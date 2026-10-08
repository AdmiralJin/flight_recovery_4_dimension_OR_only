/* eslint-disable react-refresh/only-export-components */
import { PanelRightClose, PanelRightOpen } from "lucide-react";
import { useEffect, useState } from "react";

export function useDetailPanel() {
  const query = window.matchMedia("(max-width: 768px)");
  const [open, setOpen] = useState(() => !query.matches);

  useEffect(() => {
    const update = (event: MediaQueryListEvent) => setOpen(!event.matches);
    query.addEventListener("change", update);
    return () => query.removeEventListener("change", update);
  }, []);

  return { open, setOpen };
}

export function PanelToggle({ open, onToggle, label = "详情栏" }: { open: boolean; onToggle: () => void; label?: string }) {
  const action = open ? "收起" : "展开";
  return <button className="panel-toggle" type="button" onClick={onToggle} aria-expanded={open} aria-label={`${action}${label}`} title={`${action}${label}`}>
    {open ? <PanelRightClose aria-hidden="true" /> : <PanelRightOpen aria-hidden="true" />}
    <span>{action}{label}</span>
  </button>;
}
