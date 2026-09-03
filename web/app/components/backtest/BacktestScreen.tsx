"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import { api, apiUrl, type MarketDataset } from "../../../lib/api";
import { MOCK_DATASETS, MOCK_TRADES } from "../../../lib/backtest-mock";
import { STRATEGIES_MOCK } from "../../../lib/discovery-mock";
import { marketKey } from "../../../lib/market";
import { BACKTEST_HANDOFF_KEY, readStoredJson, removeStoredJson, writeStoredJson } from "../../../lib/settings-storage";
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

const EXPERIMENT_HISTORY_KEY = "crypto-lab-experiment-history";
const BACKTEST_SETTINGS_KEY = "crypto-lab-backtest-settings";

type DatasetLoadState = "loading" | "ready" | "empty" | "error";

export function BacktestScreen() {
  const { user } = useWorkspace();
  /* Login changes the owner boundary. Remounting keeps account-scoped draft,
     ledger, and comparison state from ever leaking across accounts. */
  return <BacktestContent key={user?.id ?? "anonymous"} />;
}

function BacktestContent() {
  const {
    marketPairs,
    availableTimeframes,
    selectedMarket,
    strategies,
    experiment,
    result,
    openExperiment,
    runBacktest,
    savedCompositeStrategies,
    user,
    dataMode,
  } = useWorkspace();
  const userId = user?.id;

  const [draft, setDraft] = useState<BacktestDraft>(() =>
    createBacktestDraft(selectedMarket, "5m"),
  );
  const [draftRestored, setDraftRestored] = useState(false);
  /* Frozen at submit time so the chart title and ledger keep describing the run
     that produced the numbers, even while the user edits the strip again. */
  const [submitted, setSubmitted] = useState<BacktestDraft | null>(null);
  const [datasets, setDatasets] = useState<MarketDataset[]>([]);
  const [datasetLoadState, setDatasetLoadState] = useState<DatasetLoadState>("loading");
  const [selectedTradeSequence, setSelectedTradeSequence] = useState<number | null>(null);
  const [history, setHistory] = useState<ExperimentHistoryRecord[]>(() => user ? readExperimentHistory(user.id) : []);
  const [comparisonIds, setComparisonIds] = useState<string[]>([]);
  const [uiCancelled, setUiCancelled] = useState(false);
  const [mockRunState, setMockRunState] = useState<"idle" | "running" | "completed">("idle");
  const [submitPending, setSubmitPending] = useState(false);
  const submitLock = useRef(false);
  const submitOriginExperimentId = useRef<string | null>(null);
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
    const frame = window.requestAnimationFrame(() => {
      const handoff = readStoredJson<Partial<BacktestDraft>>(BACKTEST_HANDOFF_KEY);
      const stored = handoff && isBacktestSettings(handoff)
        ? handoff
        : readStoredJson<Partial<BacktestDraft>>(BACKTEST_SETTINGS_KEY);
      if (stored && isBacktestSettings(stored)) {
        setDraft((current) => ({
          ...current,
          ...stored,
          market: stored.market ?? current.market,
          selectedStrategyIds: stored.selectedStrategyIds ?? current.selectedStrategyIds,
        }));
      }
      if (handoff) removeStoredJson(BACKTEST_HANDOFF_KEY);
      setDraftRestored(true);
    });
    return () => window.cancelAnimationFrame(frame);
  }, []);

  useEffect(() => {
    if (!draftRestored) return;
    writeStoredJson(BACKTEST_SETTINGS_KEY, draft);
  }, [draft, draftRestored]);

  useEffect(() => {
    if (!draftRestored) return;
    if (dataMode === "mock") {
      const dataset = MOCK_DATASETS[0];
      const frame = window.requestAnimationFrame(() => {
        if (!dataset) return;
        setDatasets(MOCK_DATASETS);
        setDatasetLoadState("ready");
        setDraft((current) => ({
          ...current,
          ...(current.datasetVersion === dataset.dataset_version ? {} : {
            datasetVersion: dataset.dataset_version,
            rangeFrom: dataset.range_from.slice(0, 10),
            rangeTo: new Date(new Date(dataset.range_to).getTime() - 1).toISOString().slice(0, 10),
          }),
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
          ...(current.datasetVersion === dataset.dataset_version ? {} : {
            rangeFrom: dataset.range_from.slice(0, 10),
            rangeTo: new Date(new Date(dataset.range_to).getTime() - 1).toISOString().slice(0, 10),
          }),
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
  }, [dataMode, draftRestored, effectiveTimeframe, market]);

  const issues = backtestIssues(effectiveDraft);
  const running = !uiCancelled && (submitPending || experiment?.status === "queued" || experiment?.status === "running" || dataMode === "mock" && mockRunState === "running");
  const completed = !uiCancelled && experiment?.status === "completed" && result !== null;
  const visibleExperimentStatus = uiCancelled ? "cancelled" : experiment?.status;
  const isMock = dataMode === "mock" && !completed;
  const selectedChildren = useMemo(
    () => {
      const saved = savedCompositeStrategies.find((item) => item.id === effectiveDraft.selectedCompositeId);
      if (effectiveDraft.mode === "composite" && saved) {
        return saved.children.filter((child) => backtestStrategies.some((strategy) => strategy.strategy_id === child.strategy_id));
      }
      return buildBacktestChildren(
        effectiveDraft.mode,
        effectiveDraft.strategyId,
        effectiveDraft.selectedStrategyIds,
        backtestStrategies,
        effectiveDraft.selectedStrategyWeights,
      );
    },
    [backtestStrategies, effectiveDraft.mode, effectiveDraft.selectedCompositeId, effectiveDraft.selectedStrategyIds, effectiveDraft.selectedStrategyWeights, effectiveDraft.strategyId, savedCompositeStrategies],
  );
  const noRegistry = backtestStrategies.length === 0;
  const noStrategies = selectedChildren.length === 0;

  const trades = useMemo(
    () => completed && result ? result.trades : isMock ? MOCK_TRADES : [],
    [completed, isMock, result],
  );
  const kpis = useMemo(() => deriveKpis(trades), [trades]);
  const shownDraft = submitted ?? effectiveDraft;

  /* Lock synchronously on the first click. React state alone is not enough:
     two clicks in the same event loop can both observe the old false value
     before the disabled prop re-renders. Release once the newly accepted run
     replaces the previous experiment, or immediately when submission fails. */
  useEffect(() => {
    if (!submitPending || !experiment || experiment.id === submitOriginExperimentId.current) return;
    submitLock.current = false;
    submitOriginExperimentId.current = null;
    setSubmitPending(false);
  }, [experiment, submitPending]);

  /* The API exposes individual experiments but no owner-scoped collection.
     Keep the rendered experiment ledger per signed-in user so it survives
     sign-out, reload, and a later login on this browser. */
  useEffect(() => {
    if (!user) return;
    try {
      window.localStorage.setItem(experimentHistoryStorageKey(user.id), JSON.stringify(history));
    } catch {
      // Private-mode storage failures must not block a backtest.
    }
  }, [history, user]);

  useEffect(() => {
    if (!userId || dataMode === "mock") return;
    let cancelled = false;
    const timer = window.setTimeout(() => {
      void api.experiments().then(({ experiments }) => {
        if (!cancelled) setHistory(experiments.map(summaryToHistory));
      }).catch(() => undefined);
    }, 0);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [dataMode, userId]);

  useEffect(() => {
    if (!experiment) return;
    const frame = window.requestAnimationFrame(() => {
      setHistory((current) => {
        const next = { ...summaryToHistory(experiment), ...(uiCancelled ? { status: "cancelled" } : {}) };
        return [next, ...current.filter((record) => record.id !== experiment.id && !record.id.startsWith("draft-"))];
      });
    });
    return () => window.cancelAnimationFrame(frame);
  }, [experiment, uiCancelled]);

  function patch(next: Partial<BacktestDraft>) {
    setDraft((current) => ({ ...current, ...next }));
  }

  function submit() {
    if (submitLock.current || noStrategies) return;
    submitLock.current = true;
    submitOriginExperimentId.current = experiment?.id ?? null;
    setSubmitPending(true);
    setUiCancelled(false);
    setSubmitted(effectiveDraft);
    const selectedNames = selectedChildren.map((child) => backtestStrategies.find((strategy) => strategy.strategy_id === child.strategy_id)?.display_name ?? child.strategy_id);
    const saved = savedCompositeStrategies.find((item) => item.id === effectiveDraft.selectedCompositeId);
    const execution = {
      ...draftToExecution(effectiveDraft),
      ...(saved ? { policy: saved.policy, threshold: saved.threshold } : {}),
    };
    const candidateDefinition = buildCandidateDefinition(selectedChildren, execution);
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
          parameters: candidateDefinition,
          execution: execution as unknown as Record<string, unknown>,
          metrics: null,
        }, ...current]);
        submitLock.current = false;
        submitOriginExperimentId.current = null;
        setSubmitPending(false);
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
      parameters: candidateDefinition,
      execution: execution as unknown as Record<string, unknown>,
      metrics: null,
    }, ...current]);
    void runBacktest(
      selectedChildren,
      execution,
      effectiveDraft.timeframe,
      { from: effectiveDraft.rangeFrom, to: effectiveDraft.rangeTo },
      effectiveDraft.market,
      effectiveDraft.datasetVersion,
    ).then((accepted) => {
      if (accepted) return;
      submitLock.current = false;
      submitOriginExperimentId.current = null;
      setSubmitPending(false);
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
          savedComposites={savedCompositeStrategies}
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
          onVisualize={(id) => void openExperiment(id)}
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
    parameters: summary.strategy_definition ?? summary.candidate_definition,
    execution: summary.execution,
    metrics: summary.metrics,
  };
}

function isBacktestSettings(value: Partial<BacktestDraft>): value is Partial<BacktestDraft> & {
  market?: BacktestDraft["market"];
  selectedStrategyIds?: string[];
} {
  return (value.market === undefined || (
    typeof value.market === "object" && value.market !== null
    && typeof value.market.provider === "string"
    && typeof value.market.symbol === "string"
  ))
    && (value.selectedStrategyIds === undefined || value.selectedStrategyIds.every((id) => typeof id === "string"))
    && (value.selectedStrategyWeights === undefined || (
      typeof value.selectedStrategyWeights === "object"
      && value.selectedStrategyWeights !== null
      && Object.values(value.selectedStrategyWeights).every((weight) => typeof weight === "number" && Number.isFinite(weight))
    ))
    && (value.selectedCompositeId === undefined || typeof value.selectedCompositeId === "string");
}

function buildCandidateDefinition(
  children: Array<{
    strategy_id: string;
    strategy_version?: string;
    parameters?: Record<string, unknown>;
    weight: number;
  }>,
  execution: ReturnType<typeof draftToExecution>,
): Record<string, unknown> {
  const definitions = children.map((child) => ({
    strategy_id: child.strategy_id,
    version: child.strategy_version ?? "v1",
    parameters: child.parameters ?? {},
    weight: child.weight,
  }));
  const single = definitions[0];
  if (definitions.length === 1 && single) {
    return {
      strategy_id: single.strategy_id,
      version: single.version,
      parameters: single.parameters,
    };
  }
  return {
    strategy_id: "composite",
    version: "v1",
    children: definitions,
    policy: {
      name: execution.policy,
      threshold: execution.threshold,
      encoding: { BUY: 1, HOLD: 0, SELL: -1 },
    },
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

function experimentHistoryStorageKey(ownerId: string) {
  return `${EXPERIMENT_HISTORY_KEY}:${ownerId}`;
}

function readExperimentHistory(ownerId: string): ExperimentHistoryRecord[] {
  try {
    const value: unknown = JSON.parse(window.localStorage.getItem(experimentHistoryStorageKey(ownerId)) ?? "[]");
    if (!Array.isArray(value)) return [];
    return value.filter(isExperimentHistoryRecord);
  } catch {
    return [];
  }
}

function isExperimentHistoryRecord(value: unknown): value is ExperimentHistoryRecord {
  if (!value || typeof value !== "object") return false;
  const record = value as Partial<ExperimentHistoryRecord>;
  return typeof record.id === "string"
    && typeof record.status === "string"
    && typeof record.createdAt === "string"
    && typeof record.symbol === "string"
    && typeof record.timeframe === "string"
    && typeof record.strategy === "string"
    && typeof record.strategyVersion === "string"
    && typeof record.datasetVersion === "string"
    && typeof record.rangeFrom === "string"
    && typeof record.rangeTo === "string"
    && typeof record.parameters === "object"
    && record.parameters !== null
    && typeof record.execution === "object"
    && record.execution !== null;
}
