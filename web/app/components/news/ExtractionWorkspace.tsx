"use client";

import {
  EXTRACTION_METRICS,
  EXTRACTION_STAGES,
  FIELD_MAP_SAMPLE,
  RAW_HTML_SAMPLE,
  REPAIR_PROPOSAL,
  SELF_HEALING_STAGES,
  TEMPLATE_JSON_SAMPLE,
  TEMPLATE_VERSIONS,
} from "../../../lib/news-mock";
import { Button, Panel, StepFlow, Toggle } from "../ui/Foundation";
import { Icon } from "../ui/Icon";
import styles from "./news.module.css";

/* Centre region. The fixed data is the local fallback for the complete screen;
   the extraction API can replace it without changing this layout. */
export function ExtractionWorkspace() {
  return (
    <Panel
      title="LLM-assisted Extraction"
      action={
        <span className={styles.headBadge}>
          Template: {EXTRACTION_METRICS.templateVersion}
          <Icon name="check" aria-hidden="true" />
        </span>
      }
    >
      <StepFlow steps={EXTRACTION_STAGES} variant="numbered" />

      <div className={styles.stageCards}>
        <div className={styles.stageCard}>
          <pre className={styles.codeBlock}>{RAW_HTML_SAMPLE}</pre>
        </div>

        <div className={styles.stageCard}>
          <span className={styles.stageMeta}><span>Nhận diện vùng:</span></span>
          <div className={styles.fieldMap}>
            {FIELD_MAP_SAMPLE.map(([field, selector]) => (
              <div key={field} className={styles.fieldMapRow}>
                <b>{field}</b>
                <i aria-hidden="true">→</i>
                <code>{selector}</code>
              </div>
            ))}
          </div>
          <span className={styles.stageMeta}>
            <span>Độ tin cậy:</span>
            <b>{EXTRACTION_METRICS.confidence.toFixed(2)}</b>
          </span>
        </div>

        <div className={styles.stageCard}>
          <pre className={styles.codeBlock}>{TEMPLATE_JSON_SAMPLE}</pre>
          <span className={styles.stageMeta}>
            <span>Fields: {EXTRACTION_METRICS.fields}</span>
            <b>Score: {EXTRACTION_METRICS.score.toFixed(2)}</b>
          </span>
        </div>

        <div className={styles.stageCard}>
          <span className={styles.stageMeta}><span>Các phiên bản</span></span>
          <div className={styles.versionList}>
            {TEMPLATE_VERSIONS.map((version) => (
              <div key={version.version} className={`${styles.versionRow} ${version.current ? styles.versionCurrent : ""}`}>
                <span>
                  <b>{version.version}{version.current ? " (Hiện tại)" : ""}</b>
                  <span>{version.stamp}</span>
                </span>
                {version.current ? <Icon name="chevron-right" aria-hidden="true" /> : null}
              </div>
            ))}
          </div>
          <button type="button" className={styles.linkButton} disabled>Xem tất cả</button>
        </div>
      </div>

    </Panel>
  );
}

export function SelfHealingPanel({ enabled, onToggle }: { enabled: boolean; onToggle: (value: boolean) => void }) {
  return (
    <Panel
      title="Self-healing extraction"
      className={styles.healingPanel}
      action={<Toggle checked={enabled} label="Tự động bật self-healing" onChange={onToggle} />}
    >
      <StepFlow steps={SELF_HEALING_STAGES} variant="numbered" />

      <div className={styles.healingRow}>
        <div className={styles.stageCard}>
          <span className={styles.stageMeta}><span>Chỉ số hiện tại</span></span>
          <div className={styles.metricList}>
            <div className={styles.metricRow}><span>Fields rỗng:</span><b>{EXTRACTION_METRICS.emptyFieldsPct}%</b></div>
            <div className={styles.metricRow}><span>Sai định dạng:</span><b>{EXTRACTION_METRICS.malformedPct}%</b></div>
            <div className={styles.metricRow}><span>Độ tin cậy TB:</span><b>{EXTRACTION_METRICS.averageConfidence.toFixed(2)}</b></div>
            <div className={`${styles.metricRow} ${styles.metricAlert}`}><span>Tổng lỗi:</span><b>{EXTRACTION_METRICS.totalErrorPct}%</b></div>
          </div>
        </div>

        <div className={styles.decisionCell}>
          <span className={styles.flowArrow} aria-hidden="true"><Icon name="chevron-right" /></span>
          <span className={`${styles.branchLabel} ${styles.branchNo}`}>Không</span>
          <span className={styles.diamond}>Lỗi cao?</span>
          <span className={`${styles.flowArrow} ${styles.flowArrowOut}`} aria-hidden="true"><Icon name="chevron-right" /></span>
          <span className={`${styles.branchLabel} ${styles.branchYes}`}>
            Có
            <Icon name="arrow-down" aria-hidden="true" />
          </span>
        </div>

        <div className={styles.stageCard}>
          <span className={styles.stageMeta}><span>Đề xuất template mới</span></span>
          <div className={styles.metricList}>
            <div className={styles.metricRow}><span>{REPAIR_PROPOSAL.version}</span></div>
            <div className={styles.metricRow}>
              <span>Giảm lỗi dự kiến:</span>
              <b>{REPAIR_PROPOSAL.errorBefore}% → {REPAIR_PROPOSAL.errorAfter}%</b>
            </div>
            <div className={`${styles.metricRow} ${styles.metricGood}`}>
              <span>Độ tin cậy dự kiến:</span>
              <b>{REPAIR_PROPOSAL.expectedConfidence.toFixed(2)}</b>
            </div>
          </div>
          <Button variant="ghost" disabled>Xem diff</Button>
        </div>

        <div className={styles.stageCard}>
          <span className={styles.stageMeta}><span>Đã lưu thành công</span></span>
          <div className={styles.metricList}>
            <div className={`${styles.metricRow} ${styles.metricGood}`}><span /><b>{REPAIR_PROPOSAL.savedVersion}</b></div>
            <div className={styles.metricRow}><span>{REPAIR_PROPOSAL.savedAt}</span></div>
          </div>
          <Button variant="ghost" disabled>Áp dụng ngay</Button>
        </div>
      </div>

    </Panel>
  );
}
