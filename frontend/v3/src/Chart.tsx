import { memo, useEffect, useRef, useState } from "react";
import type { EChartsOption } from "echarts";
import { BarChart, CustomChart, GraphChart, HeatmapChart, LineChart, ScatterChart } from "echarts/charts";
import { AriaComponent, DataZoomComponent, GridComponent, LegendComponent, TooltipComponent, VisualMapComponent } from "echarts/components";
import { init, use as register } from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import { useWb } from "./state";
import { object, rows } from "./state";
import { Button } from "./components";
import { Minus, Plus, RotateCcw } from "lucide-react";
import { Help } from "./Help";

register([BarChart, CustomChart, GraphChart, HeatmapChart, LineChart, ScatterChart, AriaComponent, DataZoomComponent, GridComponent, LegendComponent, TooltipComponent, VisualMapComponent, CanvasRenderer]);
export const Chart = memo(function Chart({ option, label, viewportKey, onSelect, height = 340 }: { option: EChartsOption; label: string; viewportKey?: string; onSelect?: (id: string) => void; height?: number }) {
  const el = useRef<HTMLDivElement>(null);
  const instance = useRef<ReturnType<typeof init> | null>(null);
  const previousLabel = useRef<string | null>(null);
  const ranges = useRef(new Map<string, unknown>());
  const [axis, setAxis] = useState("x");
  const theme = useWb(s => s.theme);
  useEffect(() => {
    const chart = init(el.current!, undefined, { renderer: "canvas" }); instance.current = chart;
    let frame = 0;
    const observer = new ResizeObserver(() => { cancelAnimationFrame(frame); frame = requestAnimationFrame(() => chart.resize()); }); observer.observe(el.current!);
    return () => { cancelAnimationFrame(frame); observer.disconnect(); chart.dispose(); instance.current = null; };
  }, []);
  useEffect(() => {
    const chart = instance.current;
    if (!chart) return;
    const key = viewportKey ?? label;
    if (previousLabel.current) ranges.current.set(previousLabel.current, chart.getOption()?.dataZoom);
    const zoom = ranges.current.get(key);
    chart.setOption(refinedOption(option), { notMerge: true, lazyUpdate: true });
    if (Array.isArray(zoom)) zoom.forEach((item, index) => {
      const current = item as { id?: string; start?: number; end?: number };
      chart.dispatchAction({ type: "dataZoom", ...(current.id ? { dataZoomId: current.id } : { dataZoomIndex: index }), start: current.start, end: current.end });
    });
    previousLabel.current = key;
  }, [option, theme, label, viewportKey]);
  useEffect(() => {
    const chart = instance.current; if (!chart || !onSelect) return;
    const handler = (event: unknown) => { const value = event as { data?: { entityId?: string }; name?: string }; const id = value.data?.entityId ?? value.name; if (id) onSelect(id); };
    chart.on("click", handler); return () => { chart.off("click", handler); };
  }, [onSelect]);
  const zoom = (direction: number) => {
    const chart = instance.current;
    if (!chart) return;
    const zooms = rows(chart.getOption()?.dataZoom);
    const current = zooms.find(item => item.id === (axis === "y" ? "wb3-y-slider" : "wb3-x-inside")) ?? zooms[0] ?? {};
    const start = Number(current.start ?? 0); const end = Number(current.end ?? 100);
    const center = (start + end) / 2;
    const size = direction === 0 ? 100 : Math.max(5, Math.min(100, (end - start) * (direction > 0 ? .65 : 1.5)));
    const next = Math.max(0, Math.min(100 - size, center - size / 2));
    chart.dispatchAction({ type: "dataZoom", dataZoomIndex: zooms.indexOf(current), start: next, end: next + size });
  };
  const twoAxes = rows(option.dataZoom).some(item => item.yAxisIndex != null);
  return <><div className="chart-frame" tabIndex={0} role="region" aria-label={`${label}，可缩放坐标`}><div className="chart" ref={el} role="img" aria-label={label} style={{ height }}/></div>{option.dataZoom && <div className="chart-controls"><span>{twoAxes ? "筛选保持坐标 · 拖动滑块调整范围" : "可缩放 · 详细数值见数据表"}</span>{twoAxes && <label>缩放坐标<select aria-label={`${label} 缩放坐标`} value={axis} onChange={event => setAxis(event.target.value)}><option value="x">横轴</option><option value="y">纵轴</option></select></label>}<Help term="坐标缩放" text="选择横轴或纵轴后使用放大、缩小及复位；也可拖动底部或右侧滑块调整范围。筛选、主题和方案模式切换保留手动范围，切换数据来源时重新取完整范围。"/><Button variant="quiet" aria-label="放大图表" onClick={() => zoom(1)}><Plus size={16}/></Button><Button variant="quiet" aria-label="缩小图表" onClick={() => zoom(-1)}><Minus size={16}/></Button><Button variant="quiet" aria-label="重置图表范围" onClick={() => zoom(0)}><RotateCcw size={16}/></Button></div>}</>;
});

function refinedOption(option: EChartsOption): EChartsOption {
  const css = getComputedStyle(document.documentElement);
  const token = (name: string) => css.getPropertyValue(name).trim();
  const axis = (value: unknown) => ({ ...object(value), axisLabel: { ...object(object(value).axisLabel), color: token("--muted"), fontSize: 12 }, nameTextStyle: { ...object(object(value).nameTextStyle), color: token("--muted"), fontSize: 12 } });
  const result = { ...option, textStyle: { ...object(option.textStyle), fontFamily: token("--font-ui"), fontSize: 13, color: token("--text") } } as EChartsOption;
  for (const key of ["xAxis", "yAxis"] as const) if (option[key]) result[key] = (Array.isArray(option[key]) ? option[key] as unknown[] : [option[key]]).map(axis) as never;
  if (Array.isArray(option.series)) result.series = option.series.map((series, index) => {
    if (series.name === "Lower bound" || series.name === "Incumbent UB") {
      const lower = series.name === "Lower bound";
      const color = token(lower ? "--chart-bound" : "--chart-incumbent");
      return { ...series, name: lower ? "全局下界 LB" : "全局可行解 UB", symbol: lower ? "emptyCircle" : "diamond", symbolSize: 6, lineStyle: { color, width: 2.5, type: lower ? "dashed" : "solid" }, itemStyle: { color } };
    }
    if (series.type === "bar" && index > 0 && object(series.itemStyle).color !== "transparent" && String(series.name).includes("成本")) return { ...series, itemStyle: { ...object(series.itemStyle), color: token("--chart-bound") } };
    return series;
  }) as never;
  const x = object(Array.isArray(result.xAxis) ? result.xAxis[0] : result.xAxis);
  if (Array.isArray(x.data) && x.data.join(",") === "schedule,aircraft,crew,passenger") x.data = ["航班计划", "飞机资源", "机组资源", "旅客恢复"];
  return result;
}
