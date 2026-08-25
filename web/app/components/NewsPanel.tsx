"use client";

import { compactDateTime } from "../../lib/format";
import { useWorkspace } from "../providers/workspace";
import { EmptyState, Skeleton, Unavailable } from "./States";

export function NewsPanel() {
  const { news, newsState, coverage, prediction, predictionText, setPredictionText, testSentiment, user } = useWorkspace();

  return (
    <section id="news" className="surface news-panel">
      <div className="surface-head">
        <div>
          <p className="eyebrow">News intelligence</p>
          <h2>Market signal desk</h2>
          <p className="surface-subtitle">
            Coverage {coverage ? `${coverage.items_analyzed}/${coverage.items_total}` : "0/0"} · source-linked sentiment.
          </p>
        </div>
      </div>

      <div className="sentiment-test">
        <label htmlFor="sentiment-copy">Analyze a market note</label>
        <textarea id="sentiment-copy" value={predictionText} onChange={(event) => setPredictionText(event.target.value)} />
        <div className="sentiment-actions">
          <button className="primary-action" onClick={() => void testSentiment()} disabled={!user}>Analyze</button>
          {prediction ? (
            <span className={`sentiment ${prediction.label.toLowerCase()}`}>{prediction.label} · {Math.round(prediction.score * 100)}%</span>
          ) : (
            <span className="analysis-hint">AI service ready</span>
          )}
        </div>
      </div>

      {newsState === "loading" ? (
        <div className="news-list"><Skeleton lines={5} /></div>
      ) : newsState === "unavailable" ? (
        <Unavailable title="News feed unavailable">
          The collector did not respond. Charts and backtests are unaffected — this panel simply has no source to show.
        </Unavailable>
      ) : news.length === 0 ? (
        <EmptyState title="Feed quiet">Collected market stories will appear here with sentiment and source metadata.</EmptyState>
      ) : (
        <div className="news-list">
          {news.map((item, index) => (
            <article key={item.id} className={index === 0 ? "featured-news" : ""}>
              <div className="news-meta">
                <span className={`sentiment ${(item.sentiment?.label ?? "unavailable").toLowerCase()}`}>
                  {item.sentiment?.label ?? "unavailable"}
                </span>
                <span>{compactDateTime(item.published_at)}</span>
              </div>
              <h3><a href={item.url} target="_blank" rel="noreferrer">{item.title}</a></h3>
              <p>{item.source.display_name}{item.related_coins?.length ? ` · ${item.related_coins.join(" / ")}` : ""}</p>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
