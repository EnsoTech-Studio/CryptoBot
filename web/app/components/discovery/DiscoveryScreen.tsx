"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import {
  MAX_COMBINED,
  createDraft,
  draftIssues,
  normalizeWeights,
  type DiscoveryDraft,
} from "../../../lib/discovery";
import {
  DISCOVERY_BACKTEST_COMPOSITE_ID,
  type BacktestDraft,
} from "../../../lib/backtest";
import { STRATEGIES_MOCK } from "../../../lib/discovery-mock";
import {
  api,
  type LeaderboardEntry,
  type MarketDataset,
} from "../../../lib/api";
import { marketKey } from "../../../lib/market";
import {
  BACKTEST_HANDOFF_KEY,
  readStoredJson,
  removeStoredJson,
  writeStoredJson,
} from "../../../lib/settings-storage";
import { useWorkspace } from "../../providers/workspace";
import { Field, Panel, Select, StatusMessage } from "../ui/Foundation";
import {
  BuilderActions,
  CombinedStrategyBuilder,
} from "./CombinedStrategyBuilder";
import { DiscoveryLeaderboard } from "./DiscoveryLeaderboard";
import {
  DiscoveryMethodSelector,
  DiscoveryProgress,
} from "./DiscoveryControls";
import { StrategyCatalog } from "./StrategyCatalog";
import { WeightedVotingPanel } from "./WeightedVotingPanel";
import styles from "./discovery.module.css";

const DISCOVERY_SETTINGS_KEY = "crypto-lab-discovery-settings";

export function DiscoveryScreen() {
  const {
    strategies,
    dataMode,
    selectedMarket,
    panels,
    marketPairs,
    discoveryArchive,
    discoveryArchiveState,
    loadProvenance,
    openExperiment,
    search,
    discoverySessions,
    discoverySessionsState,
    submittedDraft,
    saveCompositeStrategy,
    startSearch,
    searchAction,
    selectDiscoverySession,
    runBacktest,
  } = useWorkspace();
  const router = useRouter();

  const timeframe = panels[0]?.timeframe ?? "5m";
  const [discoveryLeaderboard, setDiscoveryLeaderboard] = useState<
    LeaderboardEntry[]
  >([]);
  const [draft, setDraft] = useState<DiscoveryDraft>(() => {
    const base = createDraft(selectedMarket, timeframe);
    return {
      ...base,
      selectedStrategyIds: ["ma_cross", "rsi", "support_resistance"],
      weights: { ma_cross: 0.4, rsi: 0.3, support_resistance: 0.3 },
      method: "discovery",
    };
  });
  const [draftRestored, setDraftRestored] = useState(false);
  const [datasets, setDatasets] = useState<MarketDataset[]>([]);
  const [datasetState, setDatasetState] = useState<
    "loading" | "ready" | "empty" | "error"
  >("loading");
  const [activityLog, setActivityLog] = useState<string[]>([]);
  const autoSourceResolved = useRef(false);
  const availableStrategies =
    dataMode === "mock" ? STRATEGIES_MOCK : strategies;
  const registryIds = useMemo(
    () =>
      new Set(
        availableStrategies
          .filter((item) => !item.is_composite)
          .map((item) => item.strategy_id),
      ),
    [availableStrategies],
  );
  /* Discovery owns its source. Coupling it to the Realtime card could submit a
     provider/timeframe that has no complete BBO window. */
  const activeTimeframe = draft.timeframe;
  const activeDraft = draft;
  const sourceTimeframes = useMemo(
    () =>
      marketPairs
        .find((pair) => marketKey(pair) === marketKey(draft.market))
        ?.timeframes.filter(Boolean) ?? [],
    [draft.market, marketPairs],
  );
  const selectedDataset =
    datasets.find(
      (dataset) => dataset.dataset_version === draft.datasetVersion,
    ) ?? null;

  useEffect(() => {
    const frame = window.requestAnimationFrame(() => {
      const stored = readStoredJson<Partial<DiscoveryDraft>>(
        DISCOVERY_SETTINGS_KEY,
      );
      if (stored && isDiscoverySettings(stored)) {
        setDraft((current) => ({
          ...current,
          ...stored,
          selectedStrategyIds:
            stored.selectedStrategyIds ?? current.selectedStrategyIds,
          weights: stored.weights ?? current.weights,
        }));
      }
      setDraftRestored(true);
    });
    return () => window.cancelAnimationFrame(frame);
  }, []);

  useEffect(() => {
    if (!draftRestored) return;
    writeStoredJson(DISCOVERY_SETTINGS_KEY, draft);
  }, [draft, draftRestored]);

  useEffect(() => {
    if (!draftRestored) return;
    if (dataMode === "mock") {
      setDatasetState("ready");
      return;
    }
    let cancelled = false;
    const controller = new AbortController();
    setDatasetState("loading");
    setDatasets([]);
    void api
      .datasets(draft.market, draft.timeframe, controller.signal)
      .then(({ datasets: nextDatasets }) => {
        if (cancelled) return;
        setDatasets(nextDatasets);
        setDatasetState(nextDatasets.length > 0 ? "ready" : "empty");
        setDraft((current) => ({
          ...current,
          datasetVersion: nextDatasets.some(
            (dataset) => dataset.dataset_version === current.datasetVersion,
          )
            ? current.datasetVersion
            : (nextDatasets[0]?.dataset_version ?? ""),
        }));
      })
      .catch(() => {
        if (!cancelled) setDatasetState("error");
      });
    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [dataMode, draft.market, draft.timeframe, draftRestored]);

  useEffect(() => {
    if (
      !draftRestored ||
      dataMode === "mock" ||
      datasetState !== "empty" ||
      autoSourceResolved.current
    )
      return;
    autoSourceResolved.current = true;
    let cancelled = false;
    const findReadySource = async () => {
      const candidates = marketPairs.flatMap((pair) => {
        const timeframes = [...pair.timeframes].sort(
          (left, right) => Number(right === "5m") - Number(left === "5m"),
        );
        return timeframes.map((candidateTimeframe) => ({
          market: { provider: pair.provider, symbol: pair.symbol },
          timeframe: candidateTimeframe,
        }));
      });
      for (const candidate of candidates) {
        try {
          const response = await api.datasets(
            candidate.market,
            candidate.timeframe,
          );
          const dataset = response.datasets[0];
          if (!dataset || cancelled) continue;
          setDraft((current) => ({
            ...current,
            market: candidate.market,
            timeframe: candidate.timeframe,
            datasetVersion: dataset.dataset_version,
          }));
          setActivityLog((current) =>
            [
              `Tự chọn nguồn sẵn sàng: ${candidate.market.provider} · ${candidate.market.symbol} · ${candidate.timeframe}.`,
              ...current,
            ].slice(0, 8),
          );
          return;
        } catch {
          // Try the next configured source; the selector remains available.
        }
      }
      if (!cancelled)
        setActivityLog((current) =>
          [
            "Không tìm thấy snapshot sẵn sàng. Hãy chọn nguồn dữ liệu khác.",
            ...current,
          ].slice(0, 8),
        );
    };
    void findReadySource();
    return () => {
      cancelled = true;
    };
  }, [dataMode, datasetState, draftRestored, marketPairs]);

  useEffect(() => {
    if (!selectedDataset) return;
    setActivityLog((current) => {
      const message = `Nguồn Discovery sẵn sàng: ${selectedDataset.dataset_version} (${selectedDataset.candle_count.toLocaleString("en-US")} nến).`;
      return current[0] === message
        ? current
        : [message, ...current].slice(0, 8);
    });
  }, [selectedDataset]);

  useEffect(() => {
    if (!search) return;
    const message = `Discovery ${search.status}: ${search.candidates.tested}/${search.candidates.generated} candidates, lỗi ${search.candidates.failed}.`;
    setActivityLog((current) =>
      current[0] === message ? current : [message, ...current].slice(0, 8),
    );
  }, [
    search?.candidates.failed,
    search?.candidates.generated,
    search?.candidates.tested,
    search?.status,
  ]);

  async function refreshDiscoveryLeaderboard() {
    if (dataMode === "mock") {
      setDiscoveryLeaderboard([]);
      return;
    }
    try {
      const payload = await api.leaderboard(
        activeDraft.market,
        activeTimeframe,
      );
      setDiscoveryLeaderboard(payload.entries ?? []);
    } catch {
      setDiscoveryLeaderboard([]);
    }
  }

  useEffect(() => {
    if (dataMode === "mock") return;
    let cancelled = false;
    void api.leaderboard(activeDraft.market, activeTimeframe).then(
      (payload) => {
        if (!cancelled) setDiscoveryLeaderboard(payload.entries ?? []);
      },
      () => {
        if (!cancelled) setDiscoveryLeaderboard([]);
      },
    );
    return () => {
      cancelled = true;
    };
    // Search status changes are the completion boundary; polling otherwise stays local to the provider.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    activeDraft.market.provider,
    activeDraft.market.symbol,
    activeTimeframe,
    dataMode,
    search?.search_run_id,
    search?.status,
  ]);
  const missingStrategies = activeDraft.selectedStrategyIds.filter(
    (id) => !registryIds.has(id),
  );
  const issues = [
    ...draftIssues(activeDraft),
    ...(dataMode !== "mock" && (!selectedDataset || datasetState !== "ready")
      ? ["Chọn snapshot dữ liệu có BBO đầy đủ để chạy Discovery."]
      : []),
    ...(missingStrategies.length > 0
      ? ["Một hoặc nhiều strategy đã chọn không còn trong registry."]
      : []),
  ];
  const canSubmit = issues.length === 0;
  const searchActive = ["queued", "running", "paused"].includes(
    search?.status ?? "",
  );

  function toggleStrategy(strategyId: string) {
    setDraft((current) => {
      const selected = current.selectedStrategyIds.includes(strategyId);
      if (selected) {
        const nextIds = current.selectedStrategyIds.filter(
          (id) => id !== strategyId,
        );
        const nextWeights = { ...current.weights };
        delete nextWeights[strategyId];
        return {
          ...current,
          selectedStrategyIds: nextIds,
          weights: evenWeights(nextIds, nextWeights),
        };
      }
      if (current.selectedStrategyIds.length >= MAX_COMBINED) return current;
      const nextIds = [...current.selectedStrategyIds, strategyId];
      return {
        ...current,
        selectedStrategyIds: nextIds,
        weights: evenWeights(nextIds, current.weights),
      };
    });
  }

  function applyCombo(ids: string[]) {
    const available = ids.filter((id) => registryIds.has(id));
    setDraft((current) => ({
      ...current,
      selectedStrategyIds: available,
      weights: evenWeights(available, {}),
    }));
  }

  function setWeight(strategyId: string, weight: number) {
    setDraft((current) => ({
      ...current,
      weights: { ...current.weights, [strategyId]: weight },
    }));
  }

  function submittedChildren() {
    const weights = normalizeWeights(
      activeDraft.selectedStrategyIds,
      activeDraft.weights,
    );
    return activeDraft.selectedStrategyIds.map((id) => ({
      strategy_id: id,
      weight: weights[id],
    }));
  }

  async function viewLeaderboardExperiment(id: string) {
    if (await openExperiment(id)) router.push("/backtests");
  }

  async function backtestDiscoveryStrategy() {
    const weights = normalizeWeights(
      activeDraft.selectedStrategyIds,
      activeDraft.weights,
    );
    const handoff: Partial<BacktestDraft> = {
      market: activeDraft.market,
      timeframe: activeDraft.timeframe,
      mode: "composite",
      selectedStrategyIds: [...activeDraft.selectedStrategyIds],
      selectedStrategyWeights: weights,
      selectedCompositeId: DISCOVERY_BACKTEST_COMPOSITE_ID,
      datasetVersion: activeDraft.datasetVersion ?? "",
    };
    writeStoredJson(BACKTEST_HANDOFF_KEY, handoff);
    const accepted = await runBacktest(
      submittedChildren(),
      undefined,
      activeDraft.timeframe,
      undefined,
      activeDraft.market,
      activeDraft.datasetVersion,
    );
    if (accepted) {
      router.push("/backtests");
    } else {
      removeStoredJson(BACKTEST_HANDOFF_KEY);
    }
  }

  function startActiveSearch() {
    void startSearch(activeDraft);
  }

  return (
    <section
      className={styles.screen}
      aria-label="Không gian tạo và tìm kiếm strategy"
    >
      {issues.length > 0 && draft.selectedStrategyIds.length > 0 ? (
        <StatusMessage tone="syncing">{issues[0]}</StatusMessage>
      ) : null}

      <div className={styles.workspace}>
        <StrategyCatalog
          strategies={availableStrategies}
          referenceMode={dataMode === "mock"}
          selectedIds={activeDraft.selectedStrategyIds}
          registryIds={registryIds}
          onToggle={toggleStrategy}
        />

        <div className={styles.builderColumn}>
          <CombinedStrategyBuilder
            draft={activeDraft}
            strategies={availableStrategies}
            onRemove={toggleStrategy}
            onApplyCombo={applyCombo}
          />
          <WeightedVotingPanel
            draft={activeDraft}
            strategies={availableStrategies}
            onWeight={setWeight}
            onToggle={toggleStrategy}
          />
          <BuilderActions
            canSubmit={canSubmit}
            onSave={() => saveCompositeStrategy(activeDraft)}
            onBacktest={() => void backtestDiscoveryStrategy()}
            strategies={availableStrategies}
            selectedStrategyIds={activeDraft.selectedStrategyIds}
          />
        </div>

        <div className={styles.rightColumn}>
          <Panel
            title="Nguồn dữ liệu Discovery"
            info="Discovery và backtest dùng cùng snapshot đã chọn."
          >
            <div className={styles.sourceGrid}>
              <Field label="Thị trường">
                <Select
                  aria-label="Nguồn thị trường Discovery"
                  value={marketKey(activeDraft.market)}
                  disabled={
                    search?.status === "running" || marketPairs.length === 0
                  }
                  onChange={(event) => {
                    const pair = marketPairs.find(
                      (item) => marketKey(item) === event.target.value,
                    );
                    if (!pair) return;
                    setDraft((current) => ({
                      ...current,
                      market: { provider: pair.provider, symbol: pair.symbol },
                      timeframe: pair.timeframes.includes(current.timeframe)
                        ? current.timeframe
                        : (pair.timeframes[0] ?? "5m"),
                      datasetVersion: "",
                    }));
                  }}
                >
                  {marketPairs.map((pair) => (
                    <option key={marketKey(pair)} value={marketKey(pair)}>
                      {pair.symbol} · {pair.provider}
                    </option>
                  ))}
                </Select>
              </Field>
              <Field label="Khung thời gian">
                <Select
                  aria-label="Khung thời gian Discovery"
                  value={activeDraft.timeframe}
                  disabled={search?.status === "running"}
                  onChange={(event) =>
                    setDraft((current) => ({
                      ...current,
                      timeframe: event.target.value,
                      datasetVersion: "",
                    }))
                  }
                >
                  {sourceTimeframes.map((value) => (
                    <option key={value} value={value}>
                      {value}
                    </option>
                  ))}
                </Select>
              </Field>
              <Field label="Snapshot dữ liệu">
                <Select
                  aria-label="Snapshot dữ liệu Discovery"
                  value={activeDraft.datasetVersion ?? ""}
                  disabled={
                    search?.status === "running" || datasetState !== "ready"
                  }
                  onChange={(event) =>
                    setDraft((current) => ({
                      ...current,
                      datasetVersion: event.target.value,
                    }))
                  }
                >
                  <option value="">
                    {datasetState === "loading"
                      ? "Đang tải snapshot…"
                      : datasetState === "empty"
                        ? "Không có snapshot tương thích"
                        : "Chọn snapshot"}
                  </option>
                  {datasets.map((dataset) => (
                    <option key={dataset.id} value={dataset.dataset_version}>
                      {dataset.dataset_version} ·{" "}
                      {dataset.candle_count.toLocaleString("en-US")} nến
                    </option>
                  ))}
                </Select>
              </Field>
            </div>
            <p className={styles.sourceHint}>
              {selectedDataset
                ? `BBO và candle: ${selectedDataset.range_from.slice(0, 10)} → ${selectedDataset.range_to.slice(0, 10)}.`
                : "Chỉ snapshot có BBO hợp lệ mới được cho phép chạy."}
            </p>
          </Panel>
          <DiscoveryLeaderboard
            key={`${search?.search_run_id ?? "no-run"}:${activeDraft.market.provider}:${activeDraft.market.symbol}:${activeTimeframe}`}
            entries={discoveryLeaderboard}
            archive={discoveryArchive}
            run={search}
            archiveState={discoveryArchiveState}
            referenceMode={dataMode === "mock"}
            onRefresh={() => void refreshDiscoveryLeaderboard()}
            onTrace={(id) => void loadProvenance(id)}
            onOpenExperiment={(id) => void viewLeaderboardExperiment(id)}
          />
          <Panel
            title="Discovery sessions"
            bodyClassName={styles.sessionHistory}
          >
            <Field label="Past sessions">
              <Select
                aria-label="Discovery sessions"
                value={search?.search_run_id ?? ""}
                disabled={
                  discoverySessionsState === "loading" ||
                  discoverySessions.length === 0
                }
                onChange={(event) => {
                  if (event.target.value) {
                    void selectDiscoverySession(event.target.value);
                  }
                }}
              >
                <option value="">Select saved Discovery session</option>
                {discoverySessions.map((session) => (
                  <option
                    key={session.search_run_id}
                    value={session.search_run_id}
                  >
                    {sessionLabel(session)}
                  </option>
                ))}
              </Select>
            </Field>
            <p className={styles.sessionHint}>
              {discoverySessionsState === "unavailable"
                ? "Could not load saved sessions."
                : discoverySessions.length === 0
                  ? "No saved Discovery sessions yet."
                  : "Past sessions include archive, candidate status, and results."}
            </p>
          </Panel>
          <div className={styles.methodProgressRow}>
            <DiscoveryMethodSelector
              method={activeDraft.method}
disabled={searchActive}
              onChange={(method) =>
                setDraft((current) => ({ ...current, method }))
              }
            />
            <DiscoveryProgress
              run={search}
              draft={activeDraft}
              submittedDraft={submittedDraft}
              referenceMode={dataMode === "mock"}
              onAction={(action) => void searchAction(action)}
              onStart={startActiveSearch}
              canStart={canSubmit}
            />
          </div>
          {/* <Panel title="Nhật ký Discovery" info="Cập nhật từ snapshot và trạng thái run.">
            <ol className={styles.activityLog} aria-live="polite">
              {activityLog.length > 0 ? activityLog.map((entry, index) => <li key={`${entry}-${index}`}>{entry}</li>) : <li>Chưa có hoạt động Discovery.</li>}
            </ol>
          </Panel> */}
        </div>
      </div>
    </section>
  );
}

function sessionLabel(session: {
  search_run_id: string;
  status: string;
  candidates: { tested: number; generated: number };
  updated_at: string;
}) {
  const when = new Date(session.updated_at).toLocaleString("vi-VN", {
    dateStyle: "short",
    timeStyle: "short",
  });
  return `${session.status} · ${session.candidates.tested}/${session.candidates.generated} candidates · ${when}`;
}

/* New rows start at an even split. Existing user-set weights survive because
   the reference shows 0.40/0.30/0.30 — an even split is only the starting point. */
function evenWeights(
  ids: string[],
  previous: Record<string, number>,
): Record<string, number> {
  if (ids.length === 0) return {};
  const even = Number((1 / ids.length).toFixed(2));
  return Object.fromEntries(ids.map((id) => [id, previous[id] ?? even]));
}

function isDiscoverySettings(
  value: Partial<DiscoveryDraft>,
): value is Partial<DiscoveryDraft> & {
  selectedStrategyIds?: string[];
  weights?: Record<string, number>;
} {
  return (
    (value.selectedStrategyIds === undefined ||
      value.selectedStrategyIds.every((id) => typeof id === "string")) &&
    (value.weights === undefined ||
      (typeof value.weights === "object" &&
        value.weights !== null &&
        Object.values(value.weights).every(
          (weight) => typeof weight === "number",
        ))) &&
    (value.timeframe === undefined || typeof value.timeframe === "string")
  );
}
