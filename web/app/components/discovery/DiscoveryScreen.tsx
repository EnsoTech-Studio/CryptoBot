"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import {
  MAX_COMBINED,
  createDraft,
  draftIssues,
  normalizeWeights,
  type DiscoveryDraft,
} from "../../../lib/discovery";
import { STRATEGIES_MOCK } from "../../../lib/discovery-mock";
import { api, type LeaderboardEntry } from "../../../lib/api";
import { useWorkspace } from "../../providers/workspace";
import { Field, Panel, Select, StatusMessage } from "../ui/Foundation";
import { BuilderActions, CombinedStrategyBuilder } from "./CombinedStrategyBuilder";
import { DiscoveryLeaderboard } from "./DiscoveryLeaderboard";
import { DiscoveryMethodSelector, DiscoveryProgress } from "./DiscoveryControls";
import { DiscoveryWorkflow } from "./DiscoveryWorkflow";
import { StrategyCatalog } from "./StrategyCatalog";
import { WeightedVotingPanel } from "./WeightedVotingPanel";
import styles from "./discovery.module.css";

export function DiscoveryScreen() {
  const {
    strategies,
    dataMode,
    selectedMarket,
    panels,
    discoveryArchive,
    discoveryArchiveState,
    loadProvenance,
    openExperiment,
    search,
    discoverySessions,
    discoverySessionsState,
    submittedDraft,
    startSearch,
    searchAction,
    selectDiscoverySession,
    runBacktest,
    focusIndex,
    availableTimeframes,
  } = useWorkspace();
  const router = useRouter();

  const timeframe = panels[0]?.timeframe ?? "5m";
  const [discoveryTimeframe, setDiscoveryTimeframe] = useState(timeframe);
  const [discoveryLeaderboard, setDiscoveryLeaderboard] = useState<LeaderboardEntry[]>([]);
  const [draft, setDraft] = useState<DiscoveryDraft>(() => {
    const base = createDraft(selectedMarket, timeframe);
    return {
      ...base,
      selectedStrategyIds: ["ma_cross", "rsi", "support_resistance"],
      weights: { ma_cross: 0.4, rsi: 0.3, support_resistance: 0.3 },
      method: "discovery",
    };
  });
  const availableStrategies = dataMode === "mock" ? STRATEGIES_MOCK : strategies;
  const registryIds = useMemo(
    () => new Set(availableStrategies.filter((item) => !item.is_composite).map((item) => item.strategy_id)),
    [availableStrategies],
  );
  const focusMarkers = panels[focusIndex]?.markers ?? [];

  /* The market and timeframe are owned by the Realtime screen, so the draft
     mirrors them rather than keeping its own stale copy. */
  const timeframeOptions = availableTimeframes.length > 0 ? availableTimeframes : [timeframe];
  const activeTimeframe = timeframeOptions.includes(discoveryTimeframe) ? discoveryTimeframe : timeframeOptions[0];
  const activeDraft: DiscoveryDraft = { ...draft, market: selectedMarket, timeframe: activeTimeframe };

  async function refreshDiscoveryLeaderboard() {
    if (dataMode === "mock") {
      setDiscoveryLeaderboard([]);
      return;
    }
    try {
      const payload = await api.leaderboard(selectedMarket, activeTimeframe);
      setDiscoveryLeaderboard(payload.entries ?? []);
    } catch {
      setDiscoveryLeaderboard([]);
    }
  }

  useEffect(() => {
    if (dataMode === "mock") return;
    let cancelled = false;
    void api.leaderboard(selectedMarket, activeTimeframe).then(
      (payload) => { if (!cancelled) setDiscoveryLeaderboard(payload.entries ?? []); },
      () => { if (!cancelled) setDiscoveryLeaderboard([]); },
    );
    return () => { cancelled = true; };
    // Search status changes are the completion boundary; polling otherwise stays local to the provider.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTimeframe, dataMode, selectedMarket.provider, selectedMarket.symbol, search?.search_run_id, search?.status]);
  const missingStrategies = activeDraft.selectedStrategyIds.filter((id) => !registryIds.has(id));
  const issues = [
    ...draftIssues(activeDraft),
    ...(missingStrategies.length > 0 ? ["Một hoặc nhiều strategy đã chọn không còn trong registry."] : []),
  ];
  const canSubmit = issues.length === 0;

  function toggleStrategy(strategyId: string) {
    setDraft((current) => {
      const selected = current.selectedStrategyIds.includes(strategyId);
      if (selected) {
        const nextIds = current.selectedStrategyIds.filter((id) => id !== strategyId);
        const nextWeights = { ...current.weights };
        delete nextWeights[strategyId];
        return { ...current, selectedStrategyIds: nextIds, weights: evenWeights(nextIds, nextWeights) };
      }
      if (current.selectedStrategyIds.length >= MAX_COMBINED) return current;
      const nextIds = [...current.selectedStrategyIds, strategyId];
      return { ...current, selectedStrategyIds: nextIds, weights: evenWeights(nextIds, current.weights) };
    });
  }

  function applyCombo(ids: string[]) {
    const available = ids.filter((id) => registryIds.has(id));
    setDraft((current) => ({ ...current, selectedStrategyIds: available, weights: evenWeights(available, {}) }));
  }

  function setWeight(strategyId: string, weight: number) {
    setDraft((current) => ({ ...current, weights: { ...current.weights, [strategyId]: weight } }));
  }

  function submittedChildren() {
    const weights = normalizeWeights(activeDraft.selectedStrategyIds, activeDraft.weights);
    return activeDraft.selectedStrategyIds.map((id) => ({ strategy_id: id, weight: weights[id] }));
  }

  async function viewLeaderboardExperiment(id: string) {
    if (await openExperiment(id)) router.push("/backtests");
  }

  async function backtestDiscoveryStrategy() {
    const accepted = await runBacktest(submittedChildren(), undefined, activeDraft.timeframe, undefined, activeDraft.market);
    if (accepted) router.push("/backtests");
  }

  return (
    <section className={styles.screen} aria-label="Không gian tạo và tìm kiếm strategy">
      {issues.length > 0 && draft.selectedStrategyIds.length > 0 ? (
        <StatusMessage tone="syncing">{issues[0]}</StatusMessage>
      ) : null}

      <div className={styles.toolbar}>
        <label className={styles.toolbarField}>
          <span>Khung thời gian Discovery</span>
          <select
            aria-label="Khung thời gian Discovery"
            value={activeTimeframe}
            onChange={(event) => setDiscoveryTimeframe(event.target.value)}
          >
            {timeframeOptions.map((option) => <option key={option} value={option}>{option}</option>)}
          </select>
        </label>
      </div>

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
            markers={focusMarkers}
            referenceMode={dataMode === "mock"}
            onWeight={setWeight}
            onToggle={toggleStrategy}
          />
          <BuilderActions
            canSubmit={canSubmit}
            onSave={() => void startSearch(activeDraft)}
            onBacktest={() => void backtestDiscoveryStrategy()}
          />
        </div>

        <div className={styles.rightColumn}>
          <DiscoveryWorkflow status={search?.status} />
          <DiscoveryLeaderboard
            entries={discoveryLeaderboard}
            archive={discoveryArchive}
            run={search}
            archiveState={discoveryArchiveState}
            referenceMode={dataMode === "mock"}
            onRefresh={() => void refreshDiscoveryLeaderboard()}
            onTrace={(id) => void loadProvenance(id)}
            onOpenExperiment={(id) => void viewLeaderboardExperiment(id)}
          />
          <Panel title="Discovery sessions" bodyClassName={styles.sessionHistory}>
            <Field label="Past sessions">
              <Select
                aria-label="Discovery sessions"
                value={search?.search_run_id ?? ""}
                disabled={discoverySessionsState === "loading" || discoverySessions.length === 0}
                onChange={(event) => { if (event.target.value) void selectDiscoverySession(event.target.value); }}
              >
                <option value="">Select saved Discovery session</option>
                {discoverySessions.map((session) => (
                  <option key={session.search_run_id} value={session.search_run_id}>
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
              disabled={search?.status === "running"}
              onChange={(method) => setDraft((current) => ({ ...current, method }))}
            />
            <DiscoveryProgress
              run={search}
              draft={activeDraft}
              submittedDraft={submittedDraft}
              referenceMode={dataMode === "mock"}
              onAction={(action) => void searchAction(action)}
              onStart={() => void startSearch(activeDraft)}
              canStart={canSubmit}
            />
          </div>
        </div>
      </div>
    </section>
  );
}

function sessionLabel(session: { search_run_id: string; status: string; candidates: { tested: number; generated: number }; updated_at: string }) {
  const when = new Date(session.updated_at).toLocaleString("vi-VN", { dateStyle: "short", timeStyle: "short" });
  return `${session.status} · ${session.candidates.tested}/${session.candidates.generated} candidates · ${when}`;
}

/* New rows start at an even split. Existing user-set weights survive because
   the reference shows 0.40/0.30/0.30 — an even split is only the starting point. */
function evenWeights(ids: string[], previous: Record<string, number>): Record<string, number> {
  if (ids.length === 0) return {};
  const even = Number((1 / ids.length).toFixed(2));
  return Object.fromEntries(ids.map((id) => [id, previous[id] ?? even]));
}
