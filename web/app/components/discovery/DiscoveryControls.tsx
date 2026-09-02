"use client";

import { PROGRESS_MOCK } from "../../../lib/discovery-mock";
import { DISCOVERY_METHODS, shortLabel, type DiscoveryDraft, type DiscoveryMethod } from "../../../lib/discovery";
import type { SearchRun } from "../../../lib/api";
import { Button, Panel, PlannedNotice, ProgressBar } from "../ui/Foundation";
import { Icon } from "../ui/Icon";
import styles from "./discovery.module.css";

/* Column 3, bottom-left. Every enabled option maps directly to a backend
   generator; the discovery loop remains the archive-driven mode. */
export function DiscoveryMethodSelector({
  method,
  disabled,
  onChange,
}: {
  method: DiscoveryMethod;
  disabled: boolean;
  onChange: (method: DiscoveryMethod) => void;
}) {
  return (
    <Panel title="Phương pháp Discovery" info="Bộ sinh biến thể được backend hỗ trợ.">
      <div className={styles.methodList} role="radiogroup" aria-label="Phương pháp Discovery">
        {DISCOVERY_METHODS.map((option) => (
          <label key={option.value} className={styles.methodRow}>
            <span className={styles.methodIcon}>
              <Icon name={option.icon} aria-hidden="true" />
            </span>
            <span className={styles.methodCopy}>
              <strong>
                {option.label}
                {option.supported ? null : <em className={styles.unsupportedTag}>Chưa hỗ trợ</em>}
              </strong>
              <span>{option.description}</span>
            </span>
            <input
              type="radio"
              name="discovery-method"
              value={option.value}
              checked={option.supported && method === option.value}
              disabled={!option.supported || disabled}
              onChange={() => option.supported && onChange(option.value as DiscoveryMethod)}
            />
          </label>
        ))}
      </div>
      <p className={styles.progressLabel}>
        LLM agent dùng archive và research context; test data vẫn được niêm phong.
      </p>
    </Panel>
  );
}

/* Column 3, bottom-right. Every number belongs to the run that produced it:
   `submittedDraft` is the frozen draft from the start request, so editing the
   builder mid-run cannot relabel a live score with a different strategy set. */
export function DiscoveryProgress({
  run,
  draft,
  submittedDraft,
  referenceMode,
  onAction,
  onStart,
  canStart,
}: {
  run: SearchRun | null;
  draft: DiscoveryDraft;
  submittedDraft: DiscoveryDraft | null;
  referenceMode: boolean;
  onAction: (action: "pause" | "resume" | "cancel") => void;
  onStart: () => void;
  canStart: boolean;
}) {
  const live = run !== null;
  const showMock = referenceMode && !live;
  const tested = run?.candidates.tested ?? (showMock ? PROGRESS_MOCK.tested : 0);
  const generated = run?.candidates.generated ?? 0;
  const maxCandidates = submittedDraft?.maxCandidates ?? (showMock ? PROGRESS_MOCK.maxIterations : draft.maxCandidates);
  const iteration = live ? tested : showMock ? PROGRESS_MOCK.iteration : 0;
  const runStrategies = submittedDraft?.selectedStrategyIds ?? [];
  const runActive = run?.status === "queued" || run?.status === "running" || run?.status === "paused";

  return (
    <Panel title="Tiến trình Discovery" info="Số liệu lấy từ search run thật; mốc tối đa là stop condition đã gửi.">
      <div className={styles.progressBlock}>
        <span className={styles.progressLabel}>Iteration hiện tại</span>
        <span className={styles.iterationValue}>
          <strong>{iteration}</strong>
          <span>/ {maxCandidates}</span>
        </span>
        <ProgressBar value={iteration} max={maxCandidates} label="Tiến trình discovery" />
      </div>

      <div className={styles.progressBlock}>
        <span className={styles.progressLabel}>Đã kiểm tra</span>
        <span className={styles.progressStat}>
          {tested.toLocaleString("en-US")} candidates
        </span>
      </div>

      <div className={styles.progressBlock}>
        <span className={styles.progressLabel}>Best strategy so far</span>
        {live ? (
          run.best_score === null ? (
            <span className={styles.progressLabel}>Chưa có candidate nào hoàn tất.</span>
          ) : (
            <>
              <span className={styles.bestRow}>
                {runStrategies.map((id, index) => (
                  <span key={id} className={styles.bestRow}>
                    {index > 0 ? <b className={styles.partPlus}>+</b> : null}
                    <em className={styles.partBrand}>{shortLabel(id)}</em>
                  </span>
                ))}
              </span>
              <span className={styles.bestFoot}>
                <span>Score: <b>{run.best_score.toFixed(4)}</b></span>
                <span>Generated: {generated}</span>
                <span>Failed: {run.candidates.failed}</span>
              </span>
            </>
          )
        ) : showMock ? (
          <>
            <span className={styles.bestRow}>
              {PROGRESS_MOCK.best.parts.map((part, index) => (
                <span key={part} className={styles.bestRow}>
                  {index > 0 ? <b className={styles.partPlus}>+</b> : null}
                  <em className={styles.partBrand}>{part}</em>
                </span>
              ))}
            </span>
            <span className={styles.bestFoot}>
              <span>Profit: <b>+{PROGRESS_MOCK.best.profitUsdt.toLocaleString("en-US", { minimumFractionDigits: 2 })} USDT</b></span>
              <span>Winrate: {PROGRESS_MOCK.best.winratePct.toFixed(2)}%</span>
            </span>
          </>
        ) : <span className={styles.progressLabel}>Chưa có Discovery run.</span>}
      </div>

      {runActive ? (
        <div className={styles.runActions}>
          <Button variant="ghost" disabled={run.status !== "running" && run.status !== "queued"} onClick={() => onAction("pause")}>
            Tạm dừng
          </Button>
          <Button variant="ghost" disabled={run.status !== "paused"} onClick={() => onAction("resume")}>
            Tiếp tục
          </Button>
          <Button variant="danger" disabled={run.status === "completed" || run.status === "cancelled"} onClick={() => onAction("cancel")}>
            Huỷ
          </Button>
        </div>
      ) : (
        <div className={styles.progressMockActions}>
          {showMock ? (
            <PlannedNotice>Số liệu minh hoạ theo thiết kế. Bắt đầu một run để thay bằng dữ liệu thật.</PlannedNotice>
          ) : live ? (
            <span className={styles.progressLabel}>Run trước đã kết thúc. Có thể bắt đầu Discovery mới.</span>
          ) : null}
          <div className={styles.runActions}>
            <Button variant="primary" disabled={!canStart} onClick={onStart}>
              <Icon name="play" aria-hidden="true" />
              Bắt đầu Discovery
            </Button>
          </div>
        </div>
      )}
    </Panel>
  );
}
