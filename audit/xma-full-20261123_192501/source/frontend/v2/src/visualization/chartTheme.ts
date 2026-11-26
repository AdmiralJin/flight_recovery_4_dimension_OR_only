import type { ThemeMode } from "../theme";

export const CHART_FONT_FAMILY = 'Inter, "Segoe UI", "Microsoft YaHei", system-ui, sans-serif';
export const CHART_FONT_SIZE = 12;

export interface ChartPalette {
  text: string;
  muted: string;
  axis: string;
  grid: string;
  minorGrid: string;
  laneA: string;
  laneB: string;
  panel: string;
  border: string;
  tooltip: string;
  tooltipBorder: string;
  normal: string;
  direct: string;
  downstream: string;
  cancelled: string;
  od_changed: string;
  time_changed: string;
  aircraft_reassigned: string;
  crew_reassigned: string;
  unchanged: string;
  ghost: string;
  ground: string;
  ferry: string;
  operate: string;
  deadhead: string;
  rest: string;
  ground_transfer: string;
  surface: string;
  flight: string;
}

const light: ChartPalette = {
  text: "#17242b", muted: "#526873", axis: "#6f858f", grid: "rgba(83, 109, 121, .24)", minorGrid: "rgba(83, 109, 121, .10)",
  laneA: "rgba(8, 127, 109, .045)", laneB: "rgba(82, 104, 115, .025)", panel: "#ffffff", border: "#c7d4da",
  tooltip: "#ffffff", tooltipBorder: "#9eb0b9", normal: "#066f60", direct: "#b4232d", downstream: "#936000",
  cancelled: "#b4232d", od_changed: "#7442b7", time_changed: "#936000", aircraft_reassigned: "#2868ad",
  crew_reassigned: "#19758a", unchanged: "#066f60", ghost: "#697d86", ground: "#6d7e86", ferry: "#7442b7",
  operate: "#066f60", deadhead: "#2868ad", rest: "#697d86", ground_transfer: "#936000", surface: "#936000", flight: "#066f60",
};

const dark: ChartPalette = {
  text: "#e7f1f4", muted: "#a5b8c2", axis: "#7e99a5", grid: "rgba(139, 170, 182, .28)", minorGrid: "rgba(139, 170, 182, .11)",
  laneA: "rgba(45, 212, 179, .055)", laneB: "rgba(126, 153, 165, .025)", panel: "#0c2230", border: "#34505e",
  tooltip: "#102b3a", tooltipBorder: "#587480", normal: "#2dd4b3", direct: "#ff7b82", downstream: "#f4c65d",
  cancelled: "#ff7b82", od_changed: "#d394ff", time_changed: "#f4c65d", aircraft_reassigned: "#6aa9ed",
  crew_reassigned: "#72d4e5", unchanged: "#2dd4b3", ghost: "#91a7b1", ground: "#58717d", ferry: "#d394ff",
  operate: "#2dd4b3", deadhead: "#6aa9ed", rest: "#91a7b1", ground_transfer: "#f4c65d", surface: "#f4c65d", flight: "#2dd4b3",
};

export function chartPalette(theme: ThemeMode): ChartPalette {
  return theme === "dark" ? dark : light;
}

export function chartBase(theme: ThemeMode) {
  const palette = chartPalette(theme);
  return {
    backgroundColor: "transparent",
    textStyle: { color: palette.text, fontFamily: CHART_FONT_FAMILY, fontSize: CHART_FONT_SIZE },
  };
}

export function tooltipStyle(theme: ThemeMode) {
  const palette = chartPalette(theme);
  return {
    backgroundColor: palette.tooltip,
    borderColor: palette.tooltipBorder,
    borderWidth: 1,
    textStyle: { color: palette.text, fontFamily: CHART_FONT_FAMILY, fontSize: CHART_FONT_SIZE },
  };
}

export function legendStyle(theme: ThemeMode) {
  const palette = chartPalette(theme);
  return { textStyle: { color: palette.muted, fontFamily: CHART_FONT_FAMILY, fontSize: CHART_FONT_SIZE } };
}

export function timeAxis(theme: ThemeMode) {
  const palette = chartPalette(theme);
  return {
    type: "time" as const,
    name: "时间（UTC）",
    nameLocation: "end" as const,
    nameGap: 12,
    nameTextStyle: { color: palette.text, fontSize: CHART_FONT_SIZE, fontWeight: 600 },
    splitNumber: 8,
    minInterval: 10 * 60 * 1_000,
    axisLine: { show: true, lineStyle: { color: palette.axis, width: 1.2 } },
    axisTick: { show: true, length: 6, lineStyle: { color: palette.axis } },
    axisLabel: { show: true, color: palette.muted, fontSize: CHART_FONT_SIZE, margin: 12, hideOverlap: true },
    splitLine: { show: true, lineStyle: { color: palette.grid, width: 1, type: "dashed" as const } },
    minorTick: { show: true, splitNumber: 2, lineStyle: { color: palette.axis } },
    minorSplitLine: { show: true, lineStyle: { color: palette.minorGrid, width: 1 } },
  };
}

export function categoryAxis(theme: ThemeMode, lane = false) {
  const palette = chartPalette(theme);
  return {
    type: "category" as const,
    axisLine: { show: true, lineStyle: { color: palette.axis, width: 1.2 } },
    axisTick: { show: true, alignWithLabel: true, length: 6, lineStyle: { color: palette.axis } },
    axisLabel: { show: true, color: palette.muted, fontSize: CHART_FONT_SIZE, margin: 12, hideOverlap: true },
    splitLine: { show: true, lineStyle: { color: palette.grid, width: 1 } },
    ...(lane ? { splitArea: { show: true, areaStyle: { color: [palette.laneA, palette.laneB] } } } : {}),
  };
}

export function valueAxis(theme: ThemeMode) {
  const palette = chartPalette(theme);
  return {
    type: "value" as const,
    nameTextStyle: { color: palette.text, fontSize: CHART_FONT_SIZE, fontWeight: 600 },
    axisLine: { show: true, lineStyle: { color: palette.axis, width: 1.2 } },
    axisTick: { show: true, lineStyle: { color: palette.axis } },
    axisLabel: { color: palette.muted, fontSize: CHART_FONT_SIZE },
    splitLine: { show: true, lineStyle: { color: palette.grid, width: 1, type: "dashed" as const } },
  };
}

export function sliderZoom(theme: ThemeMode, bottom = 16, height = 22) {
  const palette = chartPalette(theme);
  return {
    type: "slider" as const,
    bottom,
    height,
    borderColor: palette.border,
    backgroundColor: palette.panel,
    fillerColor: theme === "dark" ? "rgba(106, 169, 237, .22)" : "rgba(40, 104, 173, .16)",
    dataBackground: { lineStyle: { color: palette.muted }, areaStyle: { color: palette.laneA } },
    selectedDataBackground: { lineStyle: { color: palette.normal }, areaStyle: { color: palette.laneA } },
    textStyle: { color: palette.muted, fontSize: CHART_FONT_SIZE },
  };
}
