"use client";

import { BacktestPanel } from "../components/Operations";
import { ResultChart } from "../components/ResultChart";

export default function BacktestsPage() {
  return (
    <>
      <section className="operation-grid single">
        <BacktestPanel />
      </section>
      <ResultChart />
    </>
  );
}
