"use client";

import { useMemo, useState } from "react";

import { MOCK_TRADES } from "../../../lib/backtest-mock";
import {
  backtestIssues,
  createBacktestDraft,
  deriveKpis,
  draftToExecution,
  type BacktestDraft,
} from "../../../lib/backtest";
import { useWorkspace } from "../../providers/workspace";
import { Button, StatusMessage } from "../ui/Foundation";
import { Icon } from "../ui/Icon";
import { BacktestChart } from "./BacktestChart";
import { BacktestFilters } from "./BacktestFilters";
import { BacktestMetrics } from "./BacktestMetrics";
import { TradeLedger } from "./TradeLedger";
import styles from "./backtest.module.css";

export function BacktestScreen() {
  const {
    marketPairs,
    availableTimeframes,
    selectedMarket,
    experiment,
    result,
    runBacktest,
    openInspector,
    user,
  } = useWorkspace();

  const [draft, setDraft] = useState<BacktestDraft>(() =>
    createBacktestDraft(selectedMarket, "5m"),
  );
  /* Frozen at submit time so the chart title and ledger keep describing the run
     that produced the numbers, even while the user edits the strip again. */
  const [submitted, setSubmitted] = useState<BacktestDraft | null>(null);

  const issues = backtestIssues(draft);
  const running = experiment?.status === "queued" || experiment?.status === "running";
  const completed = experiment?.status === "completed" && result !== null;
  const isMock = !completed;

  const trades = completed ? result.trades : MOCK_TRADES;
  const kpis = useMemo(() => deriveKpis(trades), [trades]);
  const shownDraft = submitted ?? draft;

  function patch(next: Partial<BacktestDraft>) {
    setDraft((current) => ({ ...current, ...next }));
  }

  function submit() {
    setSubmitted(draft);
    void runBacktest(
      [{ strategy_id: draft.strategyId, weight: 1 }],
      draftToExecution(draft),
      draft.timeframe,
    );
  }

  return (
    <section className={styles.screen} aria-label="Không gian backtest và kết quả giao dịch">
      <div className={styles.stack}>
        {issues.length > 0 ? <StatusMessage tone="syncing">{issues[0]}</StatusMessage> : null}
        {experiment && !completed ? (
          <StatusMessage tone={experiment.status === "failed" ? "error" : "syncing"}>
            {statusText(experiment.status)}
          </StatusMessage>
        ) : null}

        <BacktestFilters
          draft={draft}
          pairs={marketPairs}
          timeframes={availableTimeframes}
          disabled={running}
          onChange={patch}
        />

        <div className={styles.resultsRow}>
          <BacktestChart
            draft={shownDraft}
            experiment={completed ? experiment : null}
            candles={completed ? result.candles : []}
            series={completed ? result.series : []}
            markers={completed ? result.signalMarkers : []}
            executionMarkers={completed ? result.executionMarkers : []}
            isMock={isMock}
            onInspect={() => openInspector(completed ? "metrics" : "provenance")}
          />
          <TradeLedger trades={trades} symbol={shownDraft.market.symbol} />
        </div>

        <BacktestMetrics
          metrics={completed ? experiment.metrics : null}
          kpis={kpis}
          equity={completed ? result.equity : []}
          isMock={isMock}
        />

        <div className={styles.runAction}>
          <Button
            variant="primary"
            disabled={!user || running || issues.length > 0}
            onClick={submit}
          >
            <Icon name="play" aria-hidden="true" />
            {running ? "Đang chạy backtest…" : "Chạy backtest"}
          </Button>
        </div>
      </div>
    </section>
  );
}

function statusText(status: string) {
  switch (status) {
    case "queued":
      return "Backtest đã vào hàng đợi. Worker sẽ thực thi snapshot bất biến này.";
    case "running":
      return "Backtest đang chạy trên dataset đã khoá.";
    case "failed":
      return "Backtest thất bại. Kiểm tra lại cấu hình và chạy lại.";
    case "cancelled":
      return "Backtest đã bị huỷ.";
    default:
      return "";
  }
}
