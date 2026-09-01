"use client";

import { useState } from "react";

import { api, type StrategyDraft } from "../../../lib/api";
import { SAMPLE_PROMPT, SAMPLE_URL, SAVE_FORM } from "../../../lib/strategy-authoring";
import { strategyDraftReview } from "../../../lib/strategy-authoring-review";
import { useWorkspace } from "../../providers/workspace";
import { AuthoringInputs } from "./AuthoringInputs";
import { DefinitionJson, ParsedSummary } from "./ParsedSummary";
import { RecentImports } from "./RecentImports";
import { SaveLibraryPanel, ValidationPanel } from "./ValidationPanel";
import styles from "./strategy.module.css";

export function StrategyScreen() {
  const { strategies, strategyDrafts, dataMode, user, refreshStaticData, runBacktest } = useWorkspace();

  const [prompt, setPrompt] = useState(SAMPLE_PROMPT);
  const [url, setUrl] = useState(SAMPLE_URL);
  const [name, setName] = useState(SAVE_FORM.name);
  const [version, setVersion] = useState(SAVE_FORM.version);
  const [source, setSource] = useState<string>(SAVE_FORM.source);
  const [tags, setTags] = useState<string[]>(SAVE_FORM.tags);
  const [draft, setDraft] = useState<StrategyDraft | null>(null);
  const [busy, setBusy] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const review = strategyDraftReview(draft);

  async function createDraft(source: { type: "text"; text: string } | { type: "approved_url"; url: string }) {
    if (!user) {
      setError("Hãy đăng nhập trước khi tạo strategy draft.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const next = await api.createStrategyDraft(source, name);
      setDraft(next);
      if (next.strategy_spec) {
        setName(next.strategy_spec.display_name);
        setSource(source.type === "text" ? "USER_PROMPT" : "WEB_IMPORT");
      }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Không thể tạo strategy draft.");
    } finally {
      setBusy(false);
    }
  }

  async function approveDraft() {
    if (!draft || draft.status !== "REVIEW_REQUIRED") return;
    setSaving(true);
    setError(null);
    try {
      const next = await api.approveStrategyDraft(draft);
      setDraft(next);
      await refreshStaticData();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Không thể lưu strategy.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className={styles.screen} aria-label="Không gian tạo strategy từ prompt hoặc URL">
      <div className={styles.stack}>
        <div className={styles.authoringRow}>
          <div className={styles.inputColumn}>
            <AuthoringInputs
              prompt={prompt}
              url={url}
              onPrompt={setPrompt}
              onUrl={setUrl}
              busy={busy}
              onAnalyze={() => void createDraft({ type: "text", text: prompt })}
              onExtract={() => void createDraft({ type: "approved_url", url })}
            />
          </div>

          <ParsedSummary spec={draft?.strategy_spec ?? null} />
          <DefinitionJson spec={draft?.strategy_spec ?? null} />

          <div className={styles.railColumn}>
            <ValidationPanel strategies={strategies} draft={draft} />
            <SaveLibraryPanel
              name={name}
              version={version}
              source={source}
              tags={tags}
              onName={setName}
              onVersion={setVersion}
              onSource={setSource}
              onRemoveTag={(tag) => setTags((current) => current.filter((item) => item !== tag))}
              draft={draft}
              canSave={Boolean(user && review.canApprove)}
              saving={saving}
              status={draft?.status ?? null}
              onSave={() => void approveDraft()}
            />
          </div>
        </div>

        <RecentImports
          drafts={strategyDrafts}
          referenceMode={dataMode === "mock"}
          onRun={(strategyId) => void runBacktest([{ strategy_id: strategyId, weight: 1 }])}
        />
        {error ? <p className={styles.authoringError} role="alert">{error}</p> : null}
      </div>
    </section>
  );
}
