"use client";

import { SAVE_FORM, SOURCE_OPTIONS, VALIDATION_CHECKS } from "../../../lib/strategy-authoring";
import { strategyDraftReview } from "../../../lib/strategy-authoring-review";
import type { Strategy, StrategyDraft } from "../../../lib/api";
import { Button, Chip, Field, Panel, Select, TextInput } from "../ui/Foundation";
import { Icon } from "../ui/Icon";
import styles from "./strategy.module.css";

const CHECK_ICON_CLASS = ["", styles.checkIconScale, styles.checkIconChart];

/* Column 4, upper. "Chỉ báo hỗ trợ" is the one check that can be answered
   truthfully today: the registry list tells us which indicators exist. */
export function ValidationPanel({ strategies, draft }: { strategies: Strategy[]; draft: StrategyDraft | null }) {
  const supported = strategies.filter((item) => !item.is_composite).length;
  const review = strategyDraftReview(draft);
  const passed = review.canApprove || draft?.status === "APPROVED";

  return (
    <Panel title="Kiểm tra & Validation">
      <div className={styles.checkList}>
        {VALIDATION_CHECKS.map((check, index) => (
          <div key={check.title} className={styles.checkRow}>
            <span className={`${styles.checkIcon} ${CHECK_ICON_CLASS[index] ?? ""}`}>
              <Icon name={check.icon} aria-hidden="true" />
            </span>
            <span className={styles.checkCopy}>
              <strong>{check.title}</strong>
              <span>
                {check.title === "Chỉ báo hỗ trợ" && supported > 0
                  ? `${supported} chỉ báo trong registry`
                  : check.detail}
              </span>
            </span>
            <span className={styles.checkMark} data-state={passed ? "passed" : "pending"}>
              {passed ? <Icon name="check-circle" aria-hidden="true" /> : <span aria-hidden="true">—</span>}
              <span className="sr-only">{passed ? "Đạt" : "Chưa kiểm tra"}</span>
            </span>
          </div>
        ))}
      </div>

      <div className={styles.statusRow} data-state={passed ? "passed" : "pending"}>
        <span>
          <strong>{review.label}</strong>
          <span>{review.detail}</span>
        </span>
        {passed ? <Icon name="check-circle" aria-hidden="true" /> : <span className={styles.pendingMark} aria-hidden="true">…</span>}
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
          {saving ? "Đang xác nhận…" : status === "APPROVED" ? (deploymentOnly ? "Chờ build/deploy" : "Đã lưu Strategy") : (deploymentOnly ? "Approve để build/deploy" : "Lưu Strategy")}
        </Button>
        {status && !["REVIEW_REQUIRED", "APPROVED", "REJECTED", "FAILED", "CANCELLED"].includes(status) ? (
          <Button variant="secondary" type="button" disabled={cancelling} onClick={onCancel}>
            {cancelling ? "Đang hủy…" : "Hủy tạo draft"}
          </Button>
        ) : null}
        {status ? <span className={styles.saveStatus}>{status === "REVIEW_REQUIRED" ? "Đang chờ xác nhận fingerprint." : status === "APPROVED" ? (deploymentOnly ? "Đã approve; artefact chờ pipeline build/deploy, không hot-load." : "Đã approve và lưu vào thư viện.") : status}</span> : null}
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

function shortFingerprint(value: string) {
  return `${value.slice(0, 10)}…${value.slice(-6)}`;
}
