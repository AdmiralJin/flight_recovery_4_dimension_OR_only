import { lazy, Suspense } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { Shell } from "./components/Shell";

const AuditPage = lazy(() => import("./pages/AuditPage").then((module) => ({ default: module.AuditPage })));
const ComparePage = lazy(() => import("./pages/ComparePage").then((module) => ({ default: module.ComparePage })));
const DataStudio = lazy(() => import("./pages/DataStudio").then((module) => ({ default: module.DataStudio })));
const ImpactPage = lazy(() => import("./pages/ImpactPage").then((module) => ({ default: module.ImpactPage })));
const SolvePage = lazy(() => import("./pages/SolvePage").then((module) => ({ default: module.SolvePage })));

export default function App() {
  return <Suspense fallback={<div className="route-loading" role="status">加载工作视图…</div>}><Routes><Route element={<Shell />}><Route index element={<Navigate to="/data" replace />} /><Route path="data" element={<DataStudio />} /><Route path="impact" element={<ImpactPage />} /><Route path="solve" element={<SolvePage />} /><Route path="compare" element={<ComparePage />} /><Route path="audit" element={<AuditPage />} /></Route><Route path="*" element={<Navigate to="/data" replace />} /></Routes></Suspense>;
}
