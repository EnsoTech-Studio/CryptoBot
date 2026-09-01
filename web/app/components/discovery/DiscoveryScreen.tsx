"use client";

import { useMemo, useState } from "react";

import {
  MAX_COMBINED,
  createDraft,
  draftIssues,
  normalizeWeights,
  type DiscoveryDraft,
} from "../../../lib/discovery";
import { STRATEGIES_MOCK } from "../../../lib/discovery-mock";
import { useWorkspace } from "../../providers/workspace";
import { StatusMessage } from "../ui/Foundation";
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
    leaderboard,
    refreshStaticData,
    loadProvenance,
    search,
    submittedDraft,
    startSearch,
    searchAction,
    runBacktest,
    focusIndex,
  } = useWorkspace();

  const timeframe = panels[0]?.timeframe ?? "5m";
  const [draft, setDraft] = useState<DiscoveryDraft>(() => {
    const base = createDraft(selectedMarket, timeframe);
    return {
      ...base,
      selectedStrategyIds: ["ma_cross", "rsi", "support_resistance"],
      weights: { ma_cross: 0.4, rsi: 0.3, support_resistance: 0.3 },
      method: "random_search",
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
  const activeDraft: DiscoveryDraft = { ...draft, market: selectedMarket, timeframe };
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

  return (
    <section className={styles.screen} aria-label="Không gian tạo và tìm kiếm strategy">
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
            markers={focusMarkers}
            referenceMode={dataMode === "mock"}
            onWeight={setWeight}
            onToggle={toggleStrategy}
          />
          <BuilderActions
            canSubmit={canSubmit}
            onSave={() => void startSearch(activeDraft)}
            onBacktest={() => void runBacktest(submittedChildren())}
          />
        </div>

        <div className={styles.rightColumn}>
          <DiscoveryWorkflow status={search?.status} />
          <DiscoveryLeaderboard
            entries={leaderboard}
            referenceMode={dataMode === "mock"}
            onRefresh={() => void refreshStaticData()}
            onTrace={(id) => void loadProvenance(id)}
          />
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

/* New rows start at an even split. Existing user-set weights survive because
   the reference shows 0.40/0.30/0.30 — an even split is only the starting point. */
function evenWeights(ids: string[], previous: Record<string, number>): Record<string, number> {
  if (ids.length === 0) return {};
  const even = Number((1 / ids.length).toFixed(2));
  return Object.fromEntries(ids.map((id) => [id, previous[id] ?? even]));
}
