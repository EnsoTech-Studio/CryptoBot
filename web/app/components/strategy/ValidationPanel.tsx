"use client";

import { SAVE_FORM, SOURCE_OPTIONS } from "../../../lib/strategy-authoring";
import type { StrategyDraft } from "../../../lib/api";
import { Button, Chip, Field, Panel, Select, TextInput } from "../ui/Foundation";
import { Icon } from "../ui/Icon";
import styles from "./strategy.module.css";

const DEFAULT_STRATEGY_MODEL = "gpt-4o-mini";
const DEFAULT_MODEL_VERSION = "openai-gpt-4o-mini";

export function ValidationPanel({ draft }: { draft: StrategyDraft | null }) {
  const model = draft?.model ?? DEFAULT_STRATEGY_MODEL;
  const modelVersion = draft?.model_version ?? DEFAULT_MODEL_VERSION;
  const trace = draft?.agent_reasoning?.trim() || fallbackReasoning(draft);

  return (
    <Panel title="Quy trình suy luận AI">
      <div className={styles.reasoningHeader}>
        <span>
          <strong>OpenAI model</strong>
          <code>{model}</code>
        </span>
        <span>
          <strong>Version</strong>
          <code>{modelVersion}</code>
        </span>
      </div>

      <pre className={styles.reasoningTrace}>{trace}</pre>

      <div className={styles.reasoningFooter} data-state={draft?.status ?? "idle"}>
        <Icon
          name={draft?.status === "REVIEW_REQUIRED" || draft?.status === "APPROVED" ? "check-circle" : "activity"}
          aria-hidden="true"
        />
        <span>{draft ? statusLabel(draft.status) : "Chưa có draft đang chạy."}</span>
      </div>
    </Panel>
  );
}

export function SaveLibraryPanel({
  name,
  version,
  source,
  tags,
  onName,
  onVersion,
  onSource,
  onRemoveTag,
  canSave,
  saving,
  cancelling,
  status,
  draft,
  onSave,
  onCancel,
}: {
  name: string;
  version: string;
  source: string;
  tags: string[];
  onName: (value: string) => void;
  onVersion: (value: string) => void;
  onSource: (value: string) => void;
  onRemoveTag: (tag: string) => void;
  canSave: boolean;
  saving: boolean;
  cancelling: boolean;
  status: string | null;
  draft: StrategyDraft | null;
  onSave: () => void;
  onCancel: () => void;
}) {
  const deploymentOnly = draft?.mode === "custom_python";
  return (
    <Panel title={deploymentOnly ? "Review custom artifact" : "Lưu vào Strategy Library"}>
      <div className={styles.saveForm}>
        <Field label="Name">
          <TextInput value={name} onChange={(event) => onName(event.target.value)} />
        </Field>

        <Field label="Version">
          <TextInput value={version} onChange={(event) => onVersion(event.target.value)} />
        </Field>

        <Field label="Tags">
          <span className={styles.tagField}>
            {tags.map((tag) => (
              <Chip key={tag} label={tag} tone="neutral" className={styles.tagChip} onRemove={() => onRemoveTag(tag)} />
            ))}
            <Icon name="chevron-down" aria-hidden="true" />
          </span>
        </Field>

        <Field label="Source">
          <Select value={source} onChange={(event) => onSource(event.target.value)}>
            {SOURCE_OPTIONS.map((option) => (
              <option key={option} value={option}>{option}</option>
            ))}
          </Select>
        </Field>

        <Button
          variant="primary"
          className={styles.saveButton}
          type="button"
          disabled={!canSave || saving}
          onClick={onSave}
        >
          <Icon name="save" aria-hidden="true" />
          {saving ? "Đang xác nhận..." : status === "APPROVED" ? (deploymentOnly ? "Chờ build/deploy" : "Đã lưu Strategy") : (deploymentOnly ? "Approve để build/deploy" : "Lưu Strategy")}
        </Button>
        {status && !["REVIEW_REQUIRED", "APPROVED", "REJECTED", "FAILED", "CANCELLED"].includes(status) ? (
          <Button variant="secondary" type="button" disabled={cancelling} onClick={onCancel}>
            {cancelling ? "Đang hủy..." : "Hủy tạo draft"}
          </Button>
        ) : null}
        {status ? <span className={styles.saveStatus}>{statusMessage(status, deploymentOnly)}</span> : null}
        {draft?.spec_hash && draft.artifact_hash && draft.sandbox_report_hash ? (
          <span className={styles.saveEvidence} aria-label="Fingerprint package đang review">
            <code title={draft.spec_hash}>Spec {shortFingerprint(draft.spec_hash)}</code>
            <code title={draft.artifact_hash}>Artifact {shortFingerprint(draft.artifact_hash)}</code>
            <code title={draft.sandbox_report_hash}>Preflight {shortFingerprint(draft.sandbox_report_hash)}</code>
          </span>
        ) : null}
      </div>
    </Panel>
  );
}

export { SAVE_FORM };

function fallbackReasoning(draft: StrategyDraft | null) {
  if (!draft) {
    return [
      `Model: ${DEFAULT_STRATEGY_MODEL} (${DEFAULT_MODEL_VERSION})`,
      "- Waiting for a strategy prompt or approved URL.",
    ].join("\n");
  }
  return [
    `Model: ${draft.model ?? DEFAULT_STRATEGY_MODEL} (${draft.model_version ?? DEFAULT_MODEL_VERSION})`,
    `- Current draft state: ${draft.status}.`,
    draft.strategy_spec
      ? "- StrategySpec is available for review."
      : "- The authoring worker is still preparing the StrategySpec.",
  ].join("\n");
}

function statusLabel(status: string) {
  switch (status) {
    case "DRAFT_CREATED":
    case "SOURCE_READY":
    case "SPEC_GENERATING":
    case "SPEC_VALIDATING":
    case "CODE_GENERATING":
    case "POLICY_CHECKING":
    case "SANDBOX_TESTING":
    case "REPAIRING":
      return "Model/pipeline đang xử lý draft.";
    case "REVIEW_REQUIRED":
      return "Reasoning và review package đã sẵn sàng.";
    case "APPROVED":
      return "Strategy đã được lưu.";
    case "FAILED":
      return "Draft bị lỗi trong quá trình tạo.";
    case "CANCELLED":
      return "Draft đã hủy.";
    default:
      return status;
  }
}

function statusMessage(status: string, deploymentOnly: boolean) {
  if (status === "REVIEW_REQUIRED") return "Đang chờ xác nhận fingerprint.";
  if (status === "APPROVED") {
    return deploymentOnly
      ? "Đã approve; artefact chờ pipeline build/deploy, không hot-load."
      : "Đã approve và lưu vào thư viện.";
  }
  return status;
}

function shortFingerprint(value: string) {
  return `${value.slice(0, 10)}...${value.slice(-6)}`;
}
