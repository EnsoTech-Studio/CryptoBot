"use client";

import { BacktestPanel, SearchPanel } from "./components/Operations";
import { ChartWorkspace } from "./components/ChartWorkspace";

export default function DashboardPage() {
  return (
    <>
      <ChartWorkspace />
      <section className="operation-grid">
        <BacktestPanel />
        <SearchPanel />
      </section>
    </>
  );
}
