"use client";

import { SAVE_FORM, SOURCE_OPTIONS, VALIDATION_CHECKS } from "../../../lib/strategy-authoring";
import type { Strategy } from "../../../lib/api";
import { Button, Chip, Field, Panel, Select, TextInput } from "../ui/Foundation";
import { Icon } from "../ui/Icon";
import styles from "./strategy.module.css";

const CHECK_ICON_CLASS = ["", styles.checkIconScale, styles.checkIconChart];

/* Column 4, upper. "Chỉ báo hỗ trợ" is the one check that can be answered
   truthfully today: the registry list tells us which indicators exist. */
export function ValidationPanel({ strategies }: { strategies: Strategy[] }) {
  const supported = strategies.filter((item) => !item.is_composite).length;

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
            <span className={styles.checkMark}>
              <Icon name="check-circle" aria-hidden="true" />
              <span className="sr-only">Đạt</span>
            </span>
          </div>
        ))}
      </div>

      <div className={styles.statusRow}>
        <span>
          <strong>Trạng thái</strong>
          <span>Hợp lệ để lưu vào thư viện</span>
        </span>
        <Icon name="check-circle" aria-hidden="true" />
      </div>

    </Panel>
  );
}

/* Column 4, lower. Save is a local mock until the authored-strategy endpoint
   is available. */
export function SaveLibraryPanel({
  name,
  version,
  source,
  tags,
  onName,
  onVersion,
  onSource,
  onRemoveTag,
}: {
  name: string;
  version: string;
  source: string;
  tags: string[];
  onName: (value: string) => void;
  onVersion: (value: string) => void;
  onSource: (value: string) => void;
  onRemoveTag: (tag: string) => void;
}) {
  return (
    <Panel title="Lưu vào Strategy Library">
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
        >
          <Icon name="save" aria-hidden="true" />
          Lưu Strategy
        </Button>
      </div>
    </Panel>
  );
}

export { SAVE_FORM };
