"use client";

import { useState, type ReactNode } from "react";

import { DEFINITION_JSON, PARSED_BLOCKS } from "../../../lib/strategy-authoring";
import type { StrategySpec } from "../../../lib/api";
import { Panel } from "../ui/Foundation";
import { Icon } from "../ui/Icon";
import styles from "./strategy.module.css";

export function ParsedSummary({ spec }: { spec: StrategySpec | null }) {
  const blocks = spec ? blocksFromSpec(spec) : PARSED_BLOCKS;
  return (
    <Panel title="Strategy đã phân tích" className={styles.parsedPanel}>
      <div className={styles.parsedList}>
        {blocks.map((block) => (
          <div key={block.title} className={`${styles.parsedBlock} ${styles[`block${block.tone[0].toUpperCase()}${block.tone.slice(1)}`]}`}>
            <span className={styles.parsedTitle}>
              <Icon name={block.icon} aria-hidden="true" />
              {block.title}
            </span>
            <ul className={styles.parsedLines}>
              {block.lines.map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </Panel>
  );
}

/* Column 3. Copy is a real browser capability, so it works. */
export function DefinitionJson({ spec }: { spec: StrategySpec | null }) {
  const [copied, setCopied] = useState(false);
  const definition = spec ? JSON.stringify(spec, null, 2) : DEFINITION_JSON;

  async function copy() {
    try {
      await navigator.clipboard.writeText(definition);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1_600);
    } catch {
      setCopied(false);
    }
  }

  return (
    <Panel
      title="Định nghĩa strategy (JSON)"
      className={styles.jsonPanel}
      action={
        <button type="button" className={styles.copyButton} onClick={() => void copy()}>
          <Icon name={copied ? "check" : "copy"} aria-hidden="true" />
          {copied ? "Đã sao chép" : "Sao chép"}
        </button>
      }
    >
      <pre className={styles.jsonBlock}>{highlightJson(definition)}</pre>
    </Panel>
  );
}

function blocksFromSpec(spec: StrategySpec) {
  const indicatorLines = spec.indicators.map((indicator) => {
    const kind = String(indicator.kind ?? indicator.name ?? "indicator");
    const params = Object.entries(indicator)
      .filter(([key]) => key !== "kind" && key !== "name")
      .map(([key, value]) => `${key}=${String(value)}`)
      .join(", ");
    return params ? `${kind} (${params})` : kind;
  });
  const ruleLines = (key: string) => {
    const rules = spec.rules[key];
    return Array.isArray(rules) ? rules.map((rule) => typeof rule === "string" ? rule : JSON.stringify(rule)) : [JSON.stringify(rules)];
  };
  return [
    { icon: "target" as const, tone: "green" as const, title: "Điều kiện LONG", lines: ruleLines("long_entry") },
    { icon: "target" as const, tone: "red" as const, title: "Điều kiện SHORT", lines: ruleLines("short_entry") },
    { icon: "shield" as const, tone: "violet" as const, title: "Quản trị rủi ro", lines: ruleLines("exit") },
    { icon: "clock" as const, tone: "brand" as const, title: "Warm-up", lines: [`${spec.warmup_bars} candles`] },
    { icon: "coins" as const, tone: "brand" as const, title: "Chỉ báo", lines: indicatorLines },
  ];
}

function highlightJson(value: string): ReactNode[] {
  const nodes: ReactNode[] = [];
  const tokenPattern = /("(?:\\.|[^"\\])*")|(-?\d+(?:\.\d+)?)/g;
  let cursor = 0;
  let match: RegExpExecArray | null;

  while ((match = tokenPattern.exec(value))) {
    if (match.index > cursor) nodes.push(value.slice(cursor, match.index));
    const token = match[0];
    const isKey = token.startsWith('"') && value.slice(tokenPattern.lastIndex).trimStart().startsWith(":");
    nodes.push(
      <span key={`${match.index}-${token}`} className={isKey ? styles.jsonKey : token.startsWith('"') ? styles.jsonString : styles.jsonNumber}>
        {token}
      </span>,
    );
    cursor = tokenPattern.lastIndex;
  }

  if (cursor < value.length) nodes.push(value.slice(cursor));
  return nodes;
}
