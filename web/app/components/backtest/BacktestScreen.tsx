"use client";

import { useEffect, useMemo, useState } from "react";

import { api, apiUrl, type MarketDataset } from "../../../lib/api";
import { MOCK_DATASETS, MOCK_TRADES } from "../../../lib/backtest-mock";
import { STRATEGIES_MOCK } from "../../../lib/discovery-mock";
import { marketKey } from "../../../lib/market";
import {
  backtestIssues,
  buildBacktestChildren,
  canRunBacktest,
  createBacktestDraft,
  defaultBacktestStrategyId,
  defaultBacktestTimeframe,
  deriveKpis,
  draftToExecution,
  pickBacktestDataset,
  type BacktestDraft,
} from "../../../lib/backtest";
import { useWorkspace } from "../../providers/workspace";
import { StatusMessage } from "../ui/Foundation";
import { BacktestChart } from "./BacktestChart";
import { BacktestFilters } from "./BacktestFilters";
import { BacktestMetrics } from "./BacktestMetrics";
import { ExperimentHistory, type ExperimentHistoryRecord } from "./ExperimentHistory";
import { TradeLedger } from "./TradeLedger";
import styles from "./backtest.module.css";

type DatasetLoadState = "loading" | "ready" | "empty" | "error";

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
  const [datasets, setDatasets] = useState<MarketDataset[]>([]);
  const [datasetLoadState, setDatasetLoadState] = useState<DatasetLoadState>("loading");
  const [selectedTradeSequence, setSelectedTradeSequence] = useState<number | null>(null);
  const [history, setHistory] = useState<ExperimentHistoryRecord[]>([]);
  const [comparisonIds, setComparisonIds] = useState<string[]>([]);
  const [uiCancelled, setUiCancelled] = useState(false);
  const [mockRunState, setMockRunState] = useState<"idle" | "running" | "completed">("idle");
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
    if (dataMode === "mock") {
      const dataset = MOCK_DATASETS[0];
      const frame = window.requestAnimationFrame(() => {
        if (!dataset) return;
        setDatasets(MOCK_DATASETS);
        setDatasetLoadState("ready");
        setDraft((current) => ({
          ...current,
          datasetVersion: dataset.dataset_version,
          rangeFrom: dataset.range_from.slice(0, 10),
          rangeTo: new Date(new Date(dataset.range_to).getTime() - 1).toISOString().slice(0, 10),
        }));
      });
      return () => window.cancelAnimationFrame(frame);
    }
    let cancelled = false;
    let settled = false;
    const controller = new AbortController();
    const loadingFrame = window.requestAnimationFrame(() => {
      if (cancelled || settled) return;
      setDatasets([]);
      setDatasetLoadState("loading");
    });
    void api.datasets(market, effectiveTimeframe, controller.signal).then(({ datasets: availableDatasets }) => {
      if (cancelled) return;
      settled = true;
      setDatasets(availableDatasets);
      setDatasetLoadState(availableDatasets.length > 0 ? "ready" : "empty");
      const firstDataset = availableDatasets[0];
      setDraft((current) => {
        const dataset = pickBacktestDataset(availableDatasets, current.datasetVersion) ?? firstDataset;
        if (!dataset) return { ...current, datasetVersion: "", rangeFrom: "", rangeTo: "" };
        return {
          ...current,
          datasetVersion: dataset.dataset_version,
          rangeFrom: dataset.range_from.slice(0, 10),
          rangeTo: new Date(new Date(dataset.range_to).getTime() - 1).toISOString().slice(0, 10),
        };
      });
    }).catch(() => {
      if (!cancelled) {
        settled = true;
        setDatasets([]);
        setDatasetLoadState("error");
      }
    });
    return () => {
      cancelled = true;
      window.cancelAnimationFrame(loadingFrame);
      controller.abort();
    };
  }, [dataMode, effectiveTimeframe, market]);

  const issues = backtestIssues(effectiveDraft);
  const running = !uiCancelled && (experiment?.status === "queued" || experiment?.status === "running" || dataMode === "mock" && mockRunState === "running");
  const completed = !uiCancelled && experiment?.status === "completed" && result !== null;
  const visibleExperimentStatus = uiCancelled ? "cancelled" : experiment?.status;
  const isMock = dataMode === "mock" && !completed;
  const selectedChildren = useMemo(
    () => buildBacktestChildren(effectiveDraft.mode, effectiveDraft.strategyId, effectiveDraft.selectedStrategyIds, backtestStrategies),
    [backtestStrategies, effectiveDraft.mode, effectiveDraft.selectedStrategyIds, effectiveDraft.strategyId],
  );
  const noRegistry = backtestStrategies.length === 0;
  const noStrategies = selectedChildren.length === 0;

  const trades = useMemo(
    () => completed && result ? result.trades : isMock ? MOCK_TRADES : [],
    [completed, isMock, result],
  );
  const kpis = useMemo(() => deriveKpis(trades), [trades]);
  const shownDraft = submitted ?? effectiveDraft;

  useEffect(() => {
    if (!experiment) return;
    const frame = window.requestAnimationFrame(() => {
      setHistory((current) => {
        const next = { ...summaryToHistory(experiment), ...(uiCancelled ? { status: "cancelled" } : {}) };
        return [next, ...current.filter((record) => record.id !== experiment.id && !record.id.startsWith("draft-"))].slice(0, 20);
      });
    });
    return () => window.cancelAnimationFrame(frame);
  }, [experiment, uiCancelled]);

  function patch(next: Partial<BacktestDraft>) {
    setDraft((current) => ({ ...current, ...next }));
  }

  function submit() {
    if (noStrategies) return;
    setUiCancelled(false);
    setSubmitted(effectiveDraft);
    const selectedNames = selectedChildren.map((child) => backtestStrategies.find((strategy) => strategy.strategy_id === child.strategy_id)?.display_name ?? child.strategy_id);
    if (dataMode === "mock") {
      setMockRunState("running");
      window.setTimeout(() => {
        const now = new Date().toISOString();
        setMockRunState("completed");
        setHistory((current) => [{
          id: `mock-${Date.now()}`,
          status: "completed",
          createdAt: now,
          symbol: effectiveDraft.market.symbol,
          timeframe: effectiveDraft.timeframe,
          strategy: selectedNames.join(" + "),
          strategyVersion: selectedChildren.map((child) => child.strategy_version ?? "v1").join(" + "),
          datasetVersion: effectiveDraft.datasetVersion,
          rangeFrom: effectiveDraft.rangeFrom,
          rangeTo: effectiveDraft.rangeTo,
          parameters: Object.assign({}, ...selectedChildren.map((child) => child.parameters ?? {})),
          execution: draftToExecution(effectiveDraft) as unknown as Record<string, unknown>,
          metrics: null,
        }, ...current].slice(0, 20));
      }, 700);
      return;
    }
    const draftId = `draft-${Date.now()}`;
    setHistory((current) => [{
      id: draftId,
      status: "queued",
      createdAt: new Date().toISOString(),
      symbol: effectiveDraft.market.symbol,
      timeframe: effectiveDraft.timeframe,
      strategy: selectedNames.join(" + "),
      strategyVersion: selectedChildren.map((child) => child.strategy_version ?? "v1").join(" + "),
      datasetVersion: effectiveDraft.datasetVersion,
      rangeFrom: effectiveDraft.rangeFrom,
      rangeTo: effectiveDraft.rangeTo,
      parameters: Object.assign({}, ...selectedChildren.map((child) => child.parameters ?? {})),
      execution: draftToExecution(effectiveDraft) as unknown as Record<string, unknown>,
      metrics: null,
    }, ...current].slice(0, 20));
    void runBacktest(
      selectedChildren,
      draftToExecution(effectiveDraft),
      effectiveDraft.timeframe,
      { from: effectiveDraft.rangeFrom, to: effectiveDraft.rangeTo },
      effectiveDraft.market,
      effectiveDraft.datasetVersion,
    ).then((accepted) => {
      if (accepted) return;
      setHistory((current) => current.map((record) => record.id === draftId ? { ...record, status: "failed" } : record));
    });
  }

  function toggleComparison(id: string) {
    setComparisonIds((current) => current.includes(id) ? current.filter((item) => item !== id) : [...current, id]);
  }

  function cancelHistory(id: string) {
    setHistory((current) => current.map((record) => record.id === id ? { ...record, status: "cancelled" } : record));
    if (id === experiment?.id || id.startsWith("draft-")) setUiCancelled(true);
  }

  return (
    <section className={styles.screen} aria-label="Không gian backtest và kết quả giao dịch">
      <div className={styles.stack}>
        {issues.length > 0 ? <StatusMessage tone="syncing">{issues[0]}</StatusMessage> : null}
        {noRegistry ? <StatusMessage tone="syncing">Chưa có strategy nào trong registry để chạy backtest.</StatusMessage> : null}
        {!noRegistry && noStrategies ? <StatusMessage tone="syncing">Hãy chọn strategy hợp lệ để chạy backtest.</StatusMessage> : null}
        {dataMode === "mock" && mockRunState === "completed" ? <StatusMessage tone="live">Backtest mock đã hoàn tất — kết quả đang hiển thị từ dữ liệu tham chiếu.</StatusMessage> : null}
        {dataMode === "mock" && mockRunState === "running" ? <StatusMessage tone="syncing">Backtest mock đang chạy trên dataset đã chọn…</StatusMessage> : null}
        {dataMode !== "mock" && !user ? <StatusMessage tone="syncing">Đăng nhập ở menu tài khoản để bật nút Chạy backtest và xem dữ liệu kết quả.</StatusMessage> : null}
        {experiment && !completed ? (
          <StatusMessage tone={visibleExperimentStatus === "failed" ? "error" : "syncing"}>
            {statusText(visibleExperimentStatus ?? "")}
          </StatusMessage>
        ) : null}

        <BacktestFilters
          draft={effectiveDraft}
          pairs={marketPairs}
          timeframes={backtestTimeframes}
          strategies={backtestStrategies}
          datasets={datasets}
          datasetLoadState={datasetLoadState}
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
            runDisabled={!canRunBacktest(dataMode === "mock" || Boolean(user), running, noStrategies, issues)}
            runLabel={running ? "Đang chạy backtest…" : completed || (dataMode === "mock" && mockRunState === "completed") ? "Chạy lại backtest" : "Chạy backtest"}
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
        <ExperimentHistory
          records={history}
          selectedIds={comparisonIds}
          onToggle={toggleComparison}
          onCancel={cancelHistory}
        />
      </div>
    </section>
  );
}

function summaryToHistory(summary: NonNullable<ReturnType<typeof useWorkspace>["experiment"]>): ExperimentHistoryRecord {
  return {
    id: summary.id,
    status: summary.status,
    createdAt: summary.created_at,
    symbol: summary.symbol,
    timeframe: summary.timeframe,
    strategy: summary.strategy_id,
    strategyVersion: summary.strategy_version,
    datasetVersion: summary.dataset_version,
    rangeFrom: summary.range_from.slice(0, 10),
    rangeTo: summary.range_to.slice(0, 10),
    parameters: summary.candidate_definition,
    execution: summary.execution,
    metrics: summary.metrics,
  };
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
