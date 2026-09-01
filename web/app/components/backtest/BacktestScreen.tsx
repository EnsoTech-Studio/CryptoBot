"use client";

import { useEffect, useMemo, useState } from "react";

import { api, apiUrl } from "../../../lib/api";
import { MOCK_TRADES } from "../../../lib/backtest-mock";
import { STRATEGIES_MOCK } from "../../../lib/discovery-mock";
import { marketKey } from "../../../lib/market";
import {
  backtestIssues,
  createBacktestDraft,
  defaultBacktestStrategyId,
  defaultBacktestTimeframe,
  deriveKpis,
  draftToExecution,
  type BacktestDraft,
} from "../../../lib/backtest";
import { useWorkspace } from "../../providers/workspace";
import { StatusMessage } from "../ui/Foundation";
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
    strategies,
    experiment,
    result,
    runBacktest,
    openInspector,
    user,
    dataMode,
  } = useWorkspace();

  const [draft, setDraft] = useState<BacktestDraft>(() =>
    createBacktestDraft(selectedMarket, "5m"),
  );
  /* Frozen at submit time so the chart title and ledger keep describing the run
     that produced the numbers, even while the user edits the strip again. */
  const [submitted, setSubmitted] = useState<BacktestDraft | null>(null);
  const [selectedTradeSequence, setSelectedTradeSequence] = useState<number | null>(null);
  const backtestStrategies = useMemo(
    () => (dataMode === "mock" ? STRATEGIES_MOCK : strategies).filter((strategy) => !strategy.is_composite),
    [dataMode, strategies],
  );
  const market = draft.market;
  const backtestTimeframes = useMemo(
    () => marketPairs.find((pair) => marketKey(pair) === marketKey(market))?.timeframes.filter(Boolean) ?? availableTimeframes,
    [availableTimeframes, market, marketPairs],
  );
  const defaultStrategyId = defaultBacktestStrategyId(backtestStrategies);
  const effectiveStrategyId = backtestStrategies.some((strategy) => strategy.strategy_id === draft.strategyId)
    ? draft.strategyId
    : defaultStrategyId || draft.strategyId;
  const effectiveTimeframe = defaultBacktestTimeframe(backtestTimeframes, draft.timeframe);
  const effectiveDraft = effectiveStrategyId === draft.strategyId && effectiveTimeframe === draft.timeframe
    ? draft
    : { ...draft, strategyId: effectiveStrategyId, timeframe: effectiveTimeframe };

  useEffect(() => {
    let cancelled = false;
    void api.datasets(market, effectiveTimeframe).then(({ datasets }) => {
      const dataset = datasets[0];
      if (!dataset || cancelled) return;
      const rangeFrom = dataset.range_from.slice(0, 10);
      const rangeTo = new Date(new Date(dataset.range_to).getTime() - 1).toISOString().slice(0, 10);
      setDraft((current) => ({ ...current, rangeFrom, rangeTo }));
    }).catch(() => undefined);
    return () => { cancelled = true; };
  }, [effectiveTimeframe, market]);

  const issues = backtestIssues(effectiveDraft);
  const running = experiment?.status === "queued" || experiment?.status === "running";
  const completed = experiment?.status === "completed" && result !== null;
  const isMock = dataMode === "mock" && !completed;
  const noStrategies = backtestStrategies.length === 0;

  const trades = useMemo(
    () => completed && result ? result.trades : isMock ? MOCK_TRADES : [],
    [completed, isMock, result],
  );
  const kpis = useMemo(() => deriveKpis(trades), [trades]);
  const shownDraft = submitted ?? effectiveDraft;

  function patch(next: Partial<BacktestDraft>) {
    setDraft((current) => ({ ...current, ...next }));
  }

  function submit() {
    if (noStrategies) return;
    setSubmitted(effectiveDraft);
    void runBacktest(
      [{ strategy_id: effectiveDraft.strategyId, weight: 1 }],
      draftToExecution(effectiveDraft),
      effectiveDraft.timeframe,
      { from: effectiveDraft.rangeFrom, to: effectiveDraft.rangeTo },
      effectiveDraft.market,
    );
  }

  return (
    <section className={styles.screen} aria-label="Không gian backtest và kết quả giao dịch">
      <div className={styles.stack}>
        {issues.length > 0 ? <StatusMessage tone="syncing">{issues[0]}</StatusMessage> : null}
        {noStrategies ? <StatusMessage tone="syncing">Chưa có strategy nào trong registry để chạy backtest.</StatusMessage> : null}
        {experiment && !completed ? (
          <StatusMessage tone={experiment.status === "failed" ? "error" : "syncing"}>
            {statusText(experiment.status)}
          </StatusMessage>
        ) : null}

        <BacktestFilters
          draft={effectiveDraft}
          pairs={marketPairs}
          timeframes={backtestTimeframes}
          strategies={backtestStrategies}
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
            empty={!completed && !isMock}
            onInspect={() => openInspector(completed ? "metrics" : "provenance")}
            onRun={submit}
            runDisabled={!user || running || noStrategies || issues.length > 0}
            runLabel={running ? "Đang chạy backtest…" : "Chạy backtest"}
            selectedTradeSequence={selectedTradeSequence}
          />
          <TradeLedger
            key={completed && experiment ? experiment.id : `${dataMode}-pending`}
            trades={trades}
            symbol={shownDraft.market.symbol}
            csvExportUrl={completed && experiment ? `${apiUrl}/api/v1/experiments/${experiment.id}/trades?format=csv` : undefined}
            selectedTradeSequence={selectedTradeSequence}
            onSelectTrade={setSelectedTradeSequence}
            experimentId={completed ? experiment?.id : undefined}
            nextTradeCursor={completed && result ? result.nextTradeCursor : null}
            totalTrades={completed ? experiment?.metrics?.trade_count : undefined}
          />
        </div>

        <BacktestMetrics
          metrics={completed ? experiment.metrics : null}
          kpis={kpis}
          equity={completed ? result.equity : []}
          isMock={isMock}
        />
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
