import { useEffect, useRef } from "react";
import type { EChartsOption } from "echarts";
import { BarChart, CustomChart, GraphChart, HeatmapChart, LineChart, ScatterChart } from "echarts/charts";
import { AriaComponent, DataZoomComponent, GridComponent, LegendComponent, TooltipComponent, VisualMapComponent } from "echarts/components";
import { init, use as registerECharts } from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";

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

export function Chart({ option, label, height = 360, onClick }: { option: EChartsOption; label: string; height?: number; onClick?: (event: ChartClickEvent) => void }) {
  const element = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!element.current) return;
    const chart = init(element.current, undefined, { renderer: "canvas" });
    chart.setOption(option, { notMerge: true });
    if (onClick) chart.on("click", (event) => onClick(event as ChartClickEvent));
    const resize = new ResizeObserver(() => chart.resize());
    resize.observe(element.current);
    return () => {
      resize.disconnect();
      chart.dispose();
    };
  }, [option, onClick]);

  return <div ref={element} className="chart" style={{ height }} role="img" aria-label={label} />;
}
