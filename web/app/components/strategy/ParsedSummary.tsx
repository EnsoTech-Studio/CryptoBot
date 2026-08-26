"use client";

import { useState, type ReactNode } from "react";

import { DEFINITION_JSON, PARSED_BLOCKS } from "../../../lib/strategy-authoring";
import { Panel } from "../ui/Foundation";
import { Icon } from "../ui/Icon";
import styles from "./strategy.module.css";

/* Column 2. Illustrative parse of the sample prompt; a real analyze endpoint
   would replace these blocks wholesale. */
export function ParsedSummary() {
  return (
    <Panel title="Strategy đã phân tích" className={styles.parsedPanel}>
      <div className={styles.parsedList}>
        {PARSED_BLOCKS.map((block) => (
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
export function DefinitionJson() {
  const [copied, setCopied] = useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(DEFINITION_JSON);
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
      <pre className={styles.jsonBlock}>{highlightJson(DEFINITION_JSON)}</pre>
    </Panel>
  );
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
