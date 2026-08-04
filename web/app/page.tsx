"use client";

import { useState, type FormEvent } from "react";

import { predictText, type Prediction } from "../lib/api";

const examples = [
  "Bitcoin đang có xu hướng tích cực trong ngắn hạn",
  "Thị trường biến động mạnh, cần quản trị rủi ro",
];

export default function Home() {
  const [text, setText] = useState(examples[0]);
  const [result, setResult] = useState<Prediction | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setResult(null);
    setIsLoading(true);

    try {
      setResult(await predictText(text));
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Đã xảy ra lỗi không xác định.",
      );
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <main className="shell">
      <nav className="topbar">
        <div className="brand-mark" aria-label="CryptoBot">
          <span className="brand-dot" />
          CRYPTOBOT
        </div>
        <span className="service-pill">
          <span className="status-dot" />
          AI workspace
        </span>
      </nav>

      <section className="hero-grid">
        <div className="hero-copy">
          <p className="eyebrow">GO API / PYTHON AI / NEXT.JS</p>
          <h1>Biến tín hiệu thị trường thành quyết định rõ ràng.</h1>
          <p className="hero-description">
            Gửi một đoạn nhận định thị trường qua gateway Go và nhận kết quả từ
            inference service Python trong vài giây.
          </p>
          <div className="stack-row" aria-label="Technology stack">
            <span>01 · Gateway</span>
            <span>02 · Inference</span>
            <span>03 · Interface</span>
          </div>
        </div>

        <div className="signal-card">
          <div className="card-heading">
            <span>LIVE SIGNAL</span>
            <span className="card-index">/ 001</span>
          </div>
          <div className="signal-line">
            <span className="signal-value">{result ? result.label : "neutral"}</span>
            <span className="signal-score">
              {result ? `${Math.round(result.score * 100)}%` : "50%"}
            </span>
          </div>
          <div className="meter" aria-hidden="true">
            <span style={{ width: `${result ? result.score * 100 : 50}%` }} />
          </div>
          <p className="signal-caption">
            {result ? `Model: ${result.model}` : "Đang chờ tín hiệu đầu tiên"}
          </p>
        </div>
      </section>

      <section className="workspace-grid">
        <div className="panel panel-input">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">INPUT / 01</p>
              <h2>Market context</h2>
            </div>
            <span className="panel-code">POST /predict</span>
          </div>

          <form onSubmit={handleSubmit}>
            <label htmlFor="market-text">Nội dung cần phân tích</label>
            <textarea
              id="market-text"
              value={text}
              onChange={(event) => setText(event.target.value)}
              placeholder="Nhập nhận định, tin tức hoặc tín hiệu thị trường..."
              maxLength={10_000}
              required
            />
            <div className="form-footer">
              <span>{text.length.toLocaleString("vi-VN")} / 10.000 ký tự</span>
              <button type="submit" disabled={isLoading || !text.trim()}>
                {isLoading ? "ĐANG PHÂN TÍCH..." : "PHÂN TÍCH TÍN HIỆU →"}
              </button>
            </div>
          </form>

          <div className="examples">
            <span>Gợi ý nhanh</span>
            {examples.map((example) => (
              <button key={example} type="button" onClick={() => setText(example)}>
                {example}
              </button>
            ))}
          </div>
        </div>

        <div className="panel panel-output">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">OUTPUT / 02</p>
              <h2>Inference result</h2>
            </div>
            <span className="panel-code">JSON</span>
          </div>

          {error ? (
            <div className="empty-state error-state">
              <span className="empty-icon">!</span>
              <strong>Không nhận được kết quả</strong>
              <p>{error}</p>
            </div>
          ) : result ? (
            <div className="result-state">
              <div className="result-label-row">
                <span className="result-label">{result.label}</span>
                <span className="result-score">{(result.score * 100).toFixed(0)}%</span>
              </div>
              <div className="result-meta">
                <span>MODEL</span>
                <strong>{result.model}</strong>
                <span>RECEIVED</span>
                <strong>{new Date(result.received_at).toLocaleTimeString("vi-VN")}</strong>
              </div>
              <pre>{JSON.stringify(result, null, 2)}</pre>
            </div>
          ) : (
            <div className="empty-state">
              <span className="empty-icon">↗</span>
              <strong>Kết quả sẽ xuất hiện ở đây</strong>
              <p>Nhập nội dung ở khung bên trái để bắt đầu một lần phân tích.</p>
            </div>
          )}
        </div>
      </section>

      <footer>
        <span>CRYPTOBOT PLATFORM · v0.1.0</span>
        <span>Built for extensible inference</span>
      </footer>
    </main>
  );
}
