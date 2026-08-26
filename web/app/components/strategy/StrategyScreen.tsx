"use client";

import { useState } from "react";

import { SAMPLE_PROMPT, SAMPLE_URL, SAVE_FORM } from "../../../lib/strategy-authoring";
import { useWorkspace } from "../../providers/workspace";
import { AuthoringInputs } from "./AuthoringInputs";
import { DefinitionJson, ParsedSummary } from "./ParsedSummary";
import { RecentImports } from "./RecentImports";
import { SaveLibraryPanel, ValidationPanel } from "./ValidationPanel";
import styles from "./strategy.module.css";

export function StrategyScreen() {
  const { strategies } = useWorkspace();

  const [prompt, setPrompt] = useState(SAMPLE_PROMPT);
  const [url, setUrl] = useState(SAMPLE_URL);
  const [name, setName] = useState(SAVE_FORM.name);
  const [version, setVersion] = useState(SAVE_FORM.version);
  const [source, setSource] = useState<string>(SAVE_FORM.source);
  const [tags, setTags] = useState<string[]>(SAVE_FORM.tags);

  return (
    <section className={styles.screen} aria-label="Không gian tạo strategy từ prompt hoặc URL">
      <div className={styles.stack}>
        <div className={styles.authoringRow}>
          <div className={styles.inputColumn}>
            <AuthoringInputs prompt={prompt} url={url} onPrompt={setPrompt} onUrl={setUrl} />
          </div>

          <ParsedSummary />
          <DefinitionJson />

          <div className={styles.railColumn}>
            <ValidationPanel strategies={strategies} />
            <SaveLibraryPanel
              name={name}
              version={version}
              source={source}
              tags={tags}
              onName={setName}
              onVersion={setVersion}
              onSource={setSource}
              onRemoveTag={(tag) => setTags((current) => current.filter((item) => item !== tag))}
            />
          </div>
        </div>

        <RecentImports />
      </div>
    </section>
  );
}
