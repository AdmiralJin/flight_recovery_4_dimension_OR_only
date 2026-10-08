import { useEffect, useRef } from "react";
import type { EChartsOption } from "echarts";
import { BarChart, CustomChart, GraphChart, HeatmapChart, LineChart, ScatterChart } from "echarts/charts";
import { AriaComponent, DataZoomComponent, GridComponent, LegendComponent, TooltipComponent, VisualMapComponent } from "echarts/components";
import { init, use as registerECharts } from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import type { ThemeMode } from "../theme";

registerECharts([
  BarChart,
  CustomChart,
  GraphChart,
  HeatmapChart,
  LineChart,
  ScatterChart,
  AriaComponent,
  DataZoomComponent,
  GridComponent,
  LegendComponent,
  TooltipComponent,
  VisualMapComponent,
  CanvasRenderer,
]);

export interface ChartClickEvent {
  data?: { entityId?: string; entityType?: string } | unknown;
  name?: string;
  seriesName?: string;
}

export function Chart({ option, label, theme, height = 360, onClick }: { option: EChartsOption; label: string; theme: ThemeMode; height?: number; onClick?: (event: ChartClickEvent) => void }) {
  const element = useRef<HTMLDivElement>(null);
  const instance = useRef<ReturnType<typeof init> | null>(null);
  const previousTheme = useRef<ThemeMode | null>(null);

  useEffect(() => {
    if (!element.current) return;
    const chart = init(element.current, undefined, { renderer: "canvas" });
    instance.current = chart;
    const resize = new ResizeObserver(() => chart.resize());
    resize.observe(element.current);
    return () => {
      resize.disconnect();
      chart.dispose();
      instance.current = null;
    };
  }, []);

  useEffect(() => {
    const chart = instance.current;
    if (!chart) return;
    const preserveZoom = previousTheme.current !== null && previousTheme.current !== theme;
    const zoom = preserveZoom ? chart.getOption().dataZoom : null;
    chart.setOption(option, { notMerge: true });
    if (Array.isArray(zoom)) zoom.forEach((item, index) => {
      const current = item as { start?: number; end?: number; startValue?: string | number; endValue?: string | number };
      chart.dispatchAction({ type: "dataZoom", dataZoomIndex: index, start: current.start, end: current.end, startValue: current.startValue, endValue: current.endValue });
    });
    previousTheme.current = theme;
  }, [option, theme]);

  useEffect(() => {
    const chart = instance.current;
    if (!chart || !onClick) return;
    const handler = (event: unknown) => onClick(event as ChartClickEvent);
    chart.on("click", handler);
    return () => { chart.off("click", handler); };
  }, [onClick]);

  return <div ref={element} className="chart" style={{ height }} role="img" aria-label={label} />;
}
