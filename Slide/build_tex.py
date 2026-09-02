import re
import subprocess
import os

def build_latex():
    slide_dir = os.path.dirname(os.path.abspath(__file__))
    main_tex_path = os.path.join(slide_dir, 'main.tex')

    tex_code = r'''\documentclass[aspectratio=169,10pt]{beamer}

\usepackage[utf8]{inputenc}
\usepackage[vietnamese]{babel}
\usepackage{graphicx}
\usepackage{booktabs}
\usepackage{tabularx}
\usepackage{tikz}
\usepackage{amssymb}
\usepackage{pifont}
\usepackage{hyperref}

\usetheme{Madrid}
\usecolortheme{whale}

\definecolor{primary}{RGB}{30, 58, 138}
\definecolor{secondary}{RGB}{15, 118, 110}
\definecolor{accent}{RGB}{245, 158, 11}
\definecolor{darkslate}{RGB}{15, 23, 42}

\setbeamercolor{palette primary}{bg=primary,fg=white}
\setbeamercolor{palette secondary}{bg=secondary,fg=white}
\setbeamercolor{palette tertiary}{bg=darkslate,fg=white}
\setbeamercolor{structure}{fg=primary}
\setbeamercolor{titlelike}{parent=palette primary}
\setbeamercolor{block title}{bg=primary!15,fg=primary}
\setbeamercolor{block body}{bg=primary!5,fg=darkslate}

\setbeamertemplate{navigation symbols}{}
\setbeamertemplate{footline}{
  \leavevmode%
  \hbox{%
  \begin{beamercolorbox}[wd=.333333\paperwidth,ht=2.25ex,dp=1ex,left]{author in head/foot}%
    \usebeamerfont{author in head/foot}\hspace*{2ex}CryptoBot Architecture
  \end{beamercolorbox}%
  \begin{beamercolorbox}[wd=.333333\paperwidth,ht=2.25ex,dp=1ex,center]{title in head/foot}%
    \usebeamerfont{title in head/foot}HCMUS - KTPM
  \end{beamercolorbox}%
  \begin{beamercolorbox}[wd=.333333\paperwidth,ht=2.25ex,dp=1ex,right]{date in head/foot}%
    \usebeamerfont{date in head/foot}\insertframenumber{} / \inserttotalframenumber\hspace*{2ex}
  \end{beamercolorbox}}%
  \vskip0pt%
}

\title[CryptoBot Architecture]{\textbf{CRYPTO STRATEGY LAB (CryptoBot)}}
\subtitle{Báo Cáo Thiết Kế Kiến Trúc Phần Mềm (Software Architecture)}
\author[HCMUS - KTPM]{Nền tảng Research, Auto-Discovery \& Đánh giá Trading Strategy Tự động}
\institute[HCMUS]{Trường Đại học Khoa học Tự nhiên - ĐHQG-HCM \\ Bộ môn Kỹ thuật Phần mềm}
\date{\today}

\begin{document}

% Title Slide
\begin{frame}
  \titlepage
\end{frame}

% Slide 1: Business Domain
\begin{frame}{1. Miền Nghiệp Vụ \& Bối Cảnh (Business Domain)}
\begin{columns}[T]
\begin{column}{0.48\textwidth}
\begin{block}{\textbf{[Binance USDT-M Futures \& Algo-Trading]}}
\begin{itemize}
  \item \textbf{Perpetual Futures Market (USDT-M):} Leverage 2 chiều Long/Short 24/7; Order execution theo BBO realtime.
  \item \textbf{Đặc tính tài chính:} Funding Rate (8h), Fee Maker/Taker, Slippage \& Rủi ro Liquidation.
\end{itemize}
\end{block}
\end{column}
\begin{column}{0.48\textwidth}
\begin{block}{\textbf{[Đối Tượng Sử Dụng \& Nhu Cầu Cốt Lõi]}}
\begin{itemize}
  \item \textbf{Quant Researcher / Trader:} Ingest candle low-latency ($<200$ms) đa timeframe (1m, 5m, 1h, 1d); Backtest chính xác (Sharpe, Drawdown, Win Rate).
  \item \textbf{Autonomous AI Agents:} Crawl multi-source news, scoring sentiment; Generate strategy code \& scan hyperparameter space.
\end{itemize}
\end{block}
\end{column}
\end{columns}
\end{frame}

% Slide 2: Problem Statement
\begin{frame}{2. Bài Toán Thực Tế \& Thách Thức (Problem Statement)}
\begin{columns}[T]
\begin{column}{0.48\textwidth}
\begin{block}{\textbf{[Market Data \& Order Execution]}}
\begin{itemize}
  \item \textbf{Realtime Data Jitter \& Packet Drop:} WSS rớt kết nối làm mất nến $\rightarrow$ Auto-detect candle gap \& Gap Backfill tự động.
  \item \textbf{Lookahead Bias \& Parity Mismatch:} Giả lập thiếu slippage/phí $\rightarrow$ Deterministic Replay Engine mô phỏng sát thực tế.
\end{itemize}
\end{block}
\end{column}
\begin{column}{0.48\textwidth}
\begin{block}{\textbf{[Scalability \& Architecture]}}
\begin{itemize}
  \item \textbf{Combinatorial Explosion:} Quét hàng ngàn tham số gây block UI nếu chạy sync $\rightarrow$ Async Outbox Job Queue \& Worker Pool.
  \item \textbf{Tightly Coupled \& Vendor Lock-in:} Code gắn chặt vào 1 sàn $\rightarrow$ Strategy Plugin Architecture \& AST Sandbox.
\end{itemize}
\end{block}
\end{column}
\end{columns}
\end{frame}

% Slide 3: Quality Attributes Taxonomy
\begin{frame}{3. Bối Cảnh \& Hệ Thống Quality Attributes (ASRs Taxonomy)}
\resizebox{\textwidth}{!}{%
\begin{tabular}{lp{6.5cm}p{7.5cm}}
\toprule
\textbf{Thuộc tính (QA)} & \textbf{Trọng tâm Thiết kế} & \textbf{Tactic / Kỹ thuật Kiến trúc Áp dụng} \\
\midrule
\textbf{Modifiability} & Thêm mới Strategy, Search Algorithm, Market Provider không sửa Core & Strategy Plugin Architecture, Open-Closed Principle, Dynamic Registry \\
\textbf{Scalability} & Xử lý workload $>100,000$ backtests \& stream candle realtime & Scale-out Python Worker pool, Postgres Leased Job Queue, In-memory Broadcaster \\
\textbf{Realtime / Perf} & Latency cập nhật candle $<200$ms, high throughput Backtest & Go Edge Gateway, WebSocket Streaming, Deterministic Replay Engine \\
\textbf{Reliability} & Fault isolation (lỗi crawl/search không crash API); auto-reconnect sàn & Failure Isolation, Transactional Outbox, Lease Takeover \\
\textbf{Observability} & Monitor Worker health, tiến độ Search Loop \& telemetry metrics & Structured Logging, State Machine tracking, Run Metrics \\
\textbf{Reproducibility} & Kết quả Backtest \& Leaderboard đảm bảo tính Deterministic \& Immutable & Immutable Dataset snapshots, Run Config Hash, Seed Lock \\
\bottomrule
\end{tabular}}
\end{frame}

% Slide 4: ASR 1 & 2
\begin{frame}{4. Kịch Bản ASR Chi Tiết (Modifiability \& Scalability)}
\begin{columns}[T]
\begin{column}{0.48\textwidth}
\begin{block}{\textbf{[ASR-1: Modifiability (Thêm Strategy mới)]}}
\begin{itemize}
  \item \textbf{Source:} Quant Researcher / AI Agent.
  \item \textbf{Stimulus:} Thêm strategy class mới (\texttt{MACDStrategy}).
  \item \textbf{Artifact:} Strategy Subsystem \& UI Registry.
  \item \textbf{Response:} Auto-discovery, load metadata lên UI không cần compile lại Go Gateway hay sửa Core.
  \item \textbf{Measure:} Thao tác trên 1 file Python độc lập, 0 downtime.
\end{itemize}
\end{block}
\end{column}
\begin{column}{0.48\textwidth}
\begin{block}{\textbf{[ASR-2: Scalability (High Backtest Workload)]}}
\begin{itemize}
  \item \textbf{Source:} User trigger Auto Search Loop.
  \item \textbf{Stimulus:} 10,000 backtest jobs vào Job Queue đồng thời.
  \item \textbf{Artifact:} Job Queue \& Python Worker Pool.
  \item \textbf{Response:} Phân phối jobs qua Lease Heartbeat, worker scale-out, zero OOM / memory leak.
  \item \textbf{Measure:} Completion rate 100\%, 0 dropped job, stable CPU.
\end{itemize}
\end{block}
\end{column}
\end{columns}
\end{frame}

% Slide 5: ASR 3 & 4
\begin{frame}{5. Kịch Bản ASR Chi Tiết (Realtime \& Reliability)}
\begin{columns}[T]
\begin{column}{0.48\textwidth}
\begin{block}{\textbf{[ASR-3: Realtime \& Data Parity]}}
\begin{itemize}
  \item \textbf{Source:} Binance Exchange (WSS drop / network jitter).
  \item \textbf{Stimulus:} Mất kết nối mạng trong 30 giây.
  \item \textbf{Artifact:} Go Market Gateway \& Postgres Candle Storage.
  \item \textbf{Response:} Auto-reconnect, trigger REST Backfill bù missing candles, deduplicate bằng Open Time.
  \item \textbf{Measure:} Continuous candle stream, 0 duplicate, catch-up latency $<2$s.
\end{itemize}
\end{block}
\end{column}
\begin{column}{0.48\textwidth}
\begin{block}{\textbf{[ASR-4: Fault Tolerance (Worker Crash)]}}
\begin{itemize}
  \item \textbf{Source:} Python Worker process bị kill đột ngột (OOM).
  \item \textbf{Stimulus:} Job đang ở trạng thái RUNNING.
  \item \textbf{Artifact:} Job Queue \& Outbox Manager.
  \item \textbf{Response:} Lease Heartbeat timeout (30s), Worker khác auto-takeover và retry job.
  \item \textbf{Measure:} Job hoàn thành thành công, 0 stuck / orphaned job.
\end{itemize}
\end{block}
\end{column}
\end{columns}
\end{frame}

% Slide 6: Use Case Diagram
\begin{frame}{6. Tổng Quan Use Case Hệ Thống}
\begin{columns}[c]
\begin{column}{0.45\textwidth}
\begin{itemize}
  \item \textbf{Quant Trader:} Xem realtime candlestick chart đa timeframe, authoring strategy, chạy backtest, xem leaderboard.
  \item \textbf{AI Agent:} Crawl financial news, extract text, scoring sentiment, trigger Loop Discovery tìm strategy tối ưu.
  \item \textbf{System Worker:} Ingest candle định kỳ, process async Backtest Job Queue.
\end{itemize}
\end{column}
\begin{column}{0.53\textwidth}
\centering
\includegraphics[width=\linewidth,height=0.75\textheight,keepaspectratio]{../blueprint/assets/diagrams-png/34-use-case-overview.png}
\end{column}
\end{columns}
\end{frame}

% Slide 7: C4 L1
\begin{frame}{7. C4 Model (Level 1) - System Context Diagram}
\begin{columns}[c]
\begin{column}{0.45\textwidth}
\begin{itemize}
  \item \textbf{CryptoBot Core Platform:} Platform trung tâm cho market data ingestion, strategy research và portfolio ranking.
  \item \textbf{External Systems:}
  \begin{itemize}
    \item \textbf{Binance Exchange:} Historical REST \& WebSocket BBO price stream.
    \item \textbf{News / RSS Feeds:} Multi-source crypto news feeds.
    \item \textbf{LLM Providers (OpenAI/Groq):} LLM reasoning, sentiment analysis \& strategy self-repair.
  \end{itemize}
\end{itemize}
\end{column}
\begin{column}{0.53\textwidth}
\centering
\includegraphics[width=\linewidth,height=0.75\textheight,keepaspectratio]{../blueprint/assets/diagrams-png/01-c4-l1-system-context.png}
\end{column}
\end{columns}
\end{frame}

% Slide 8: C4 L2
\begin{frame}{8. C4 Model (Level 2) - Container Diagram}
\begin{columns}[c]
\begin{column}{0.45\textwidth}
\begin{itemize}
  \item \textbf{Next.js Dashboard:} Render-only UI cho chart, authoring, search, backtest, trade detail \& news.
  \item \textbf{Go Edge \& Market Gateway:} Public REST/WSS, Auth/Quota, Candle/BBO normalization \& realtime fan-out.
  \item \textbf{Python Research API:} Strategy/Agent runtime, experiment/search, news/sentiment orchestration \& queries.
  \item \textbf{Python Research Worker $\times$ N:} Leased backtest/agent jobs; immutable Candle+BBO; execution; facts/outbox.
  \item \textbf{PostgreSQL:} Source of truth: market, strategies, jobs/results, news/sentiment \& outbox.
  \item \textbf{Object Storage / Broker (optional):} Raw HTML by hash; replaceable queue/stream adapter.
\end{itemize}
\end{column}
\begin{column}{0.53\textwidth}
\centering
\includegraphics[width=\linewidth,height=0.75\textheight,keepaspectratio]{../blueprint/assets/diagrams-png/02-c4-l2-container.png}
\end{column}
\end{columns}
\end{frame}

% Slide 9: C4 L3 Python
\begin{frame}{9. C4 Model (Level 3) - Python Research Platform}
\begin{columns}[c]
\begin{column}{0.45\textwidth}
\begin{itemize}
  \item \textbf{Application services:} Research API, Experiment/Search/Ranking, News/Sentiment \& AgentOrchestrator.
  \item \textbf{Domain runtime:} StrategyRegistry + StrategyRuntime; Backtest Engine + Execution Simulator; news rules; agent state/artifacts.
  \item \textbf{Python-owned ports:} MarketDataPort, ModelGatewayPort, Artifact/Sandbox/Approval \& Repository/Job/Outbox ports.
  \item \textbf{Infrastructure adapters:} Go Market adapter, internal AI/LLM adapter, Sandbox Runner, SafeFetcher/Readability \& PostgreSQL repositories.
\end{itemize}
\end{column}
\begin{column}{0.53\textwidth}
\centering
\includegraphics[width=\linewidth,height=0.75\textheight,keepaspectratio]{../blueprint/assets/diagrams-png/03-c4-l3-python-strategy-platform.png}
\end{column}
\end{columns}
\end{frame}

% Slide 10: C4 L3 Go
\begin{frame}{10. C4 Model (Level 3) - Go Edge \& Market Gateway}
\begin{columns}[c]
\begin{column}{0.45\textwidth}
\begin{itemize}
  \item \textbf{REST API + Auth Guard:} Request validation/DTO mapping, JWT, RBAC \& quota.
  \item \textbf{Public WebSocket Hub:} Subscription fan-out theo panel key.
  \item \textbf{MarketProviderRegistry + BinanceAdapter:} Resolve provider, REST history \& WSS kline/BBO.
  \item \textbf{MarketNormalizer + MarketService:} Validate symbol/timeframe/decimal/timestamp/sequence; checkpoint, de-dup, persistence, reconnect \& backfill.
  \item \textbf{Python Research Client + Internal Event Ingress:} Signed commands, queries \& progress/result events.
\end{itemize}
\end{column}
\begin{column}{0.53\textwidth}
\centering
\includegraphics[width=\linewidth,height=0.75\textheight,keepaspectratio]{../blueprint/assets/diagrams-png/35-c4-l3-go-edge-market-gateway.png}
\end{column}
\end{columns}
\end{frame}

% Slide 11: Boundaries
\begin{frame}{11. Component Boundaries: 6 Module Cốt Lõi (Anti-God Service)}
\begin{columns}[T]
\begin{column}{0.48\textwidth}
\begin{block}{\textbf{[6 Bounded Contexts (High Cohesion)]}}
\begin{enumerate}
  \item \textbf{Market Realtime (Go Edge):} WSS candles/BBO, normalization, gap backfill.
  \item \textbf{Strategy Engine (Python):} Single/composite runtime qua Registry.
  \item \textbf{Backtest (Python Worker):} Candle+BBO replay, LONG/SHORT execution, trade facts.
  \item \textbf{Discovery / Search Loop (Python):} Candidates, jobs, validation, lineage, stop conditions.
  \item \textbf{News Crawler (Python):} RSS/HTML, SSRF guard, quality gate.
  \item \textbf{News Intelligence (Python + AI adapter):} Extraction, tagging, sentiment; AI chỉ inference.
\end{enumerate}
\end{block}
\end{column}
\begin{column}{0.48\textwidth}
\begin{block}{\textbf{[Trách Nhiệm Công Nghệ (Go vs Python)]}}
\resizebox{\linewidth}{!}{%
\begin{tabular}{lp{2.4cm}p{2.6cm}}
\toprule
\textbf{Tiêu chí} & \textbf{Go Edge \& Market} & \textbf{Python Platform} \\
\midrule
\textbf{Ownership} & Market Ingestion, Edge API, fan-out & Strategy, Backtest, Discovery, News/Agents/Ranking \\
\textbf{Strengths} & Goroutines non-blocking, Low RAM & Quantitative math, AST, ML \\
\textbf{Protocols} & Public REST/WSS, signed events & Internal HTTP, DTOs, Job/Outbox Ports \\
\textbf{Isolation} & Lỗi network không crash Worker & Crash strategy không làm sập API Gateway \\
\bottomrule
\end{tabular}}
\end{block}
\end{column}
\end{columns}
\end{frame}

% Slide 12: Module Specs
\begin{frame}{12. Đặc Tả Ranh Giới \& Phạm Vi 6 Module (Component Specs)}
\begin{columns}[T]
\begin{column}{0.48\textwidth}
\begin{block}{\textbf{[1. Market Realtime \& 2. Strategy Engine]}}
\begin{itemize}
  \item \textbf{Market Realtime:} Raw Binance WSS $\rightarrow$ Normalized \texttt{Candle} \& \texttt{BBO}; persist vào Postgres, broadcast \texttt{CandleClosed} qua SSE/WS; Invariant: continuous time-series, zero-duplicate.
  \item \textbf{Strategy Engine:} Pluggable qua \texttt{IStrategy}; Output là \texttt{Signal} (\texttt{BUY/SELL/HOLD}); 100\% execution parity Live/Backtest.
\end{itemize}
\end{block}
\end{column}
\begin{column}{0.48\textwidth}
\begin{block}{\textbf{[3. Backtest \& 4. Discovery]}}
\begin{itemize}
  \item \textbf{Backtest Subsystem:} Replay immutable \texttt{Candle+BBO} với cùng runtime; simulate execution \& emit trade facts qua Worker/Outbox.
  \item \textbf{Discovery Subsystem:} Generate candidates, orchestrate Search Loop qua Train/Validation/Sealed Test; enforce lineage \& stop conditions.
\end{itemize}
\end{block}
\vspace{0.3em}
\begin{block}{\textbf{[5. News Crawler \& 6. News Intelligence]}}
\begin{itemize}
  \item \textbf{News Crawler:} Fetch news từ \texttt{ApprovedSource} (RSS/HTML), SSRF protection, Quality Gate validation.
  \item \textbf{News Intelligence:} Orchestrate LLM/Agent extraction khi DOM thay đổi \& scoring sentiment [-1.0, 1.0] async (non-blocking crawl).
\end{itemize}
\end{block}
\end{column}
\end{columns}
\end{frame}

% Slide 13: UML Strategy
\begin{frame}{13. UML Class Diagram: Strategy Plugin Model}
\begin{columns}[c]
\begin{column}{0.45\textwidth}
\begin{itemize}
  \item \textbf{Contract \texttt{IStrategy}:} Method \texttt{evaluate(context) -> Signal} (\texttt{BUY}, \texttt{SELL}, \texttt{HOLD}).
  \item \textbf{5 Single Strategies:} \texttt{ma\_crossover}, \texttt{bollinger\_bands}, \texttt{rsi\_threshold}, \texttt{smc\_structure}, \texttt{news\_sentiment}.
  \item \textbf{Composite Strategy:} Combine 2-5 child strategies theo \texttt{CombinationPolicy} (majority/weighted).
  \item \textbf{Strategy Registry:} Dynamic loading file Python mới; loại bỏ God Service, loose coupling.
\end{itemize}
\end{column}
\begin{column}{0.53\textwidth}
\centering
\includegraphics[width=\linewidth,height=0.75\textheight,keepaspectratio]{../blueprint/assets/diagrams-png/36-uml-strategy-plugin-model.png}
\end{column}
\end{columns}
\end{frame}

% Slide 14: UML Search
\begin{frame}{14. UML Class Diagram: Search Algorithm \& Discovery Loop}
\begin{columns}[c]
\begin{column}{0.45\textwidth}
\begin{itemize}
  \item \textbf{Contract \texttt{ISearchAlgorithm}:} Method \texttt{sample(space, rng)} implement qua RandomSearch, GeneticAlgorithm, BayesianOptimization.
  \item \textbf{3-Split Dataset Partitioning (Chống Overfitting):}
  \begin{itemize}
    \item \textbf{Train (30d):} Search \& optimize strategy variants.
    \item \textbf{Validation (15d):} Generalization evaluation (Gate check).
    \item \textbf{Sealed Test (15d):} Out-of-sample benchmark cho Leaderboard.
  \end{itemize}
  \item \textbf{Job Throttling:} \texttt{DiscoveryTrialReservation} (reserved\_jobs=4).
\end{itemize}
\end{column}
\begin{column}{0.53\textwidth}
\centering
\includegraphics[width=\linewidth,height=0.75\textheight,keepaspectratio]{../blueprint/assets/diagrams-png/37-uml-search-algorithm-model.png}
\end{column}
\end{columns}
\end{frame}

% Slide 15: UML News
\begin{frame}{15. UML Class Diagram: Resilient News Crawler Model}
\begin{columns}[c]
\begin{column}{0.45\textwidth}
\begin{itemize}
  \item \textbf{Contract \texttt{NewsProvider}:} Implemented by \texttt{RssNewsProvider} \& \texttt{HtmlNewsProvider} (\texttt{ApprovedSource}).
  \item \textbf{SSRF Guard \& Quality Gate Pipeline:} Resolver \& Fetcher validate DNS, private IP blocking, safe redirect.
  \item \textbf{LLM Fallback Extraction:} Trigger \texttt{NewsExtractionHTTPAdapter} khi DOM thay đổi.
  \item \textbf{Decoupled Sentiment Scoring:} Async batch scoring, AI errors không block crawl pipeline.
\end{itemize}
\end{column}
\begin{column}{0.53\textwidth}
\centering
\includegraphics[width=\linewidth,height=0.75\textheight,keepaspectratio]{../blueprint/assets/diagrams-png/38-uml-news-crawler-model.png}
\end{column}
\end{columns}
\end{frame}

% Slide 16: High-Level Architecture
\begin{frame}{16. High-Level Architecture: Modular Monolith}
\begin{columns}[c]
\begin{column}{0.45\textwidth}
\begin{itemize}
  \item \textbf{Frontend (Next.js):} React SPA, Event Streaming (SSE/WS) cho realtime chart \& telemetry.
  \item \textbf{API Gateway (Go Edge):} CQRS, RBAC, Rate Limiting, Binance WSS Ingestion \& Broadcaster.
  \item \textbf{Backend Research (Python):} Strategy Plugin Architecture, Event-Driven Job Queue, Backtest Worker Pool.
  \item \textbf{Database:} PostgreSQL (ACID Outbox, Candles, Experiments, News) \& In-memory Ring Buffers.
\end{itemize}
\end{column}
\begin{column}{0.53\textwidth}
\centering
\includegraphics[width=\linewidth,height=0.75\textheight,keepaspectratio]{../blueprint/assets/diagrams-png/04-high-level-architecture.png}
\end{column}
\end{columns}
\end{frame}

% Slide 17: Design Patterns
\begin{frame}{17. Các Design \& Architectural Patterns Trọng Yếu}
\begin{columns}[c]
\begin{column}{0.45\textwidth}
\begin{itemize}
  \item \textbf{CQRS (Go API):} Tách biệt Command (tạo experiment) và Query (đọc candles, leaderboard), optimize latency.
  \item \textbf{Transactional Outbox:} Atomic consistency khi tạo Experiment và dispatch Job, eliminate dual-write risk.
  \item \textbf{Dual-Channel Market Engine with Parity:} Schema \& execution parity cho Realtime WSS và Historical Backfill.
  \item \textbf{Plugin Architecture:} Decouple hoàn toàn Core Engine khỏi strategy logic và search algorithms (Open-Closed Principle).
\end{itemize}
\end{column}
\begin{column}{0.53\textwidth}
\centering
\includegraphics[width=\linewidth,height=0.75\textheight,keepaspectratio]{../blueprint/assets/diagrams-png/07-outbox-retry-order.png}
\end{column}
\end{columns}
\end{frame}

% Slide 18: Multi-Agent
\begin{frame}{18. Nền Tảng Multi-Agent \& Vòng Lặp AI Tự Chủ}
\begin{columns}[c]
\begin{column}{0.45\textwidth}
\begin{itemize}
  \item \textbf{Strategy Designer Agent:} Nhận natural language prompt / URL $\rightarrow$ generate Draft spec (JSON).
  \item \textbf{Implementation Agent:} Transform JSON Draft thành Python code tuân thủ \texttt{IStrategy} protocol.
  \item \textbf{Self-Repair Loop (AST + Sandbox):} Static AST syntax validation \& isolated dry-run, feed traceback về LLM auto self-repair (tối đa 3 retry cycles).
  \item \textbf{Candidate Discovery \& Crawling Agent:} Automated hyperparameter sampling \& multi-source news crawling.
\end{itemize}
\end{column}
\begin{column}{0.53\textwidth}
\centering
\includegraphics[width=\linewidth,height=0.75\textheight,keepaspectratio]{../blueprint/assets/diagrams-png/25-agent-platform-components.png}
\end{column}
\end{columns}
\end{frame}

% Slide 19: Realtime Reconnect Flow
\begin{frame}{19. Runtime Flow: Realtime Ingestion \& Gap Backfill}
\begin{columns}[c]
\begin{column}{0.45\textwidth}
\begin{enumerate}
  \item \textbf{Chart Initialization:} Fetch 1,000 historical candles từ Postgres/Binance REST đa timeframe (1m, 5m, 1h, 1d).
  \item \textbf{WSS Stream Ingestion:} Ingest ticker \& update provisional candle theo realtime ticks.
  \item \textbf{Candle Close Event:} Persist candle vào Postgres và broadcast event \texttt{CandleClosed} qua SSE/WS.
  \item \textbf{Gap Backfill:} Khi WSS drop, auto-reconnect và trigger REST API backfill bù missing candles.
\end{enumerate}
\end{column}
\begin{column}{0.53\textwidth}
\centering
\includegraphics[width=\linewidth,height=0.75\textheight,keepaspectratio]{../blueprint/assets/diagrams-png/09-realtime-reconnect-backfill-flow.png}
\end{column}
\end{columns}
\end{frame}

% Slide 20: Strategy Flow
\begin{frame}{20. Runtime Flow: Strategy Execution \& Dynamic Registration}
\begin{columns}[c]
\begin{column}{0.45\textwidth}
\begin{itemize}
  \item \textbf{Run Strategy Flow:}
  \begin{itemize}
    \item Load \texttt{Datafeed} \& \texttt{Sentiment Window} vào \texttt{StrategyContext}.
    \item \texttt{IStrategy.evaluate()} emit trading signal \texttt{BUY} / \texttt{SELL} / \texttt{HOLD}.
    \item \texttt{CompositeStrategy} aggregate signals theo majority/weighted policy.
  \end{itemize}
  \item \textbf{Add Strategy Flow:} Handcrafted (drop Python file $\rightarrow$ auto-load) \& AI-Generated (LLM $\rightarrow$ AST Sandbox).
  \item \textbf{Runtime Parity:} 100\% deterministic parity giữa Live Trading và Backtest execution.
\end{itemize}
\end{column}
\begin{column}{0.53\textwidth}
\centering
\includegraphics[width=\linewidth,height=0.75\textheight,keepaspectratio]{../blueprint/assets/diagrams-png/10-strategy-flow.png}
\end{column}
\end{columns}
\end{frame}

% Slide 21: Search Pipeline Flow
\begin{frame}{21. Runtime Flow: Async Backtest Pipeline}
\begin{columns}[c]
\begin{column}{0.45\textwidth}
\begin{enumerate}
  \item \textbf{Create Experiment:} Persist metadata và job event vào Outbox trong cùng một ACID transaction.
  \item \textbf{Worker Lease Acquire:} Worker claim job qua Optimistic Lock (FOR UPDATE SKIP LOCKED) \& gửi heartbeat.
  \item \textbf{Multi-Split Execution:} Run backtest trên Train $\rightarrow$ Validation $\rightarrow$ Sealed Test.
  \item \textbf{Compute Metrics \& Leaderboard:} Calculate Sharpe Ratio, Max Drawdown, Profit Factor; persist Trade logs \& update Leaderboard.
\end{enumerate}
\end{column}
\begin{column}{0.53\textwidth}
\centering
\includegraphics[width=\linewidth,height=0.75\textheight,keepaspectratio]{../blueprint/assets/diagrams-png/11-search-backtest-pipeline.png}
\end{column}
\end{columns}
\end{frame}

% Slide 22: News Pipeline Flow
\begin{frame}{22. Runtime Flow: Resilient News Crawl \& LLM Fallback Pipeline}
\begin{columns}[c]
\begin{column}{0.45\textwidth}
\begin{enumerate}
  \item \textbf{SSRF Validation:} Whitelist check qua \texttt{ApprovedSource}, resolve DNS \& block internal/private IPs.
  \item \textbf{Standard Ingestion:} Fetch \& extract article content qua RSS/HTML Parser (Readability).
  \item \textbf{Quality Gate Check:} Trigger fallback nếu DOM thay đổi hoặc extraction rỗng.
  \item \textbf{LLM Fallback Extraction:} Dispatch raw HTML sang LLM Agent để parse structured content.
  \item \textbf{Async Sentiment Scoring:} Background worker scoring sentiment [-1.0, 1.0] và persist vào PostgreSQL.
\end{enumerate}
\end{column}
\begin{column}{0.53\textwidth}
\centering
\includegraphics[width=\linewidth,height=0.75\textheight,keepaspectratio]{../blueprint/assets/diagrams-png/13-news-html-llm-pipeline.png}
\end{column}
\end{columns}
\end{frame}

% Slide 23: Defense in Depth
\begin{frame}{23. Security Architecture: Defense-in-Depth}
\begin{columns}[c]
\begin{column}{0.45\textwidth}
\begin{itemize}
  \item \textbf{Authentication \& RBAC:} JWT authentication, role-based access control, tenant/user experiment isolation.
  \item \textbf{Crawler SSRF Prevention:} Block private IP ranges (127.0.0.1, 10.0.0.0/8, cloud metadata), domain whitelisting qua \texttt{ApprovedSource}.
  \item \textbf{AST Sandbox \& Safe Execution:} AST static analysis trên AI-generated code; ban dangerous builtins/modules (\texttt{eval}, \texttt{subprocess}, \texttt{socket}, \texttt{os.system}).
  \item \textbf{Tool Invocation Boundary:} Schema-validated DTOs, strict input boundaries cho AI Agents.
\end{itemize}
\end{column}
\begin{column}{0.53\textwidth}
\centering
\includegraphics[width=\linewidth,height=0.75\textheight,keepaspectratio]{../blueprint/assets/diagrams-png/14-defense-in-depth.png}
\end{column}
\end{columns}
\end{frame}

% Slide 24: Scalability
\begin{frame}{24. Scalability Architecture \& Benchmark}
\begin{columns}[c]
\begin{column}{0.45\textwidth}
\begin{itemize}
  \item \textbf{Stateless Horizontal Scale-Out:}
  \begin{itemize}
    \item Spin up N Python Worker instances độc lập dựa trên CPU load / queue backlog.
    \item Distribute jobs qua PostgreSQL B-Tree indexed Leased Job Queue.
  \end{itemize}
  \item \textbf{Load Testing \& Benchmarking (k6 / Locust):}
  \begin{itemize}
    \item Simulate 10,000 concurrent users dispatch Backtest jobs \& query candle data.
    \item Queue throughput đạt $> 1,500$ backtests/phút trên 4 workers.
    \item Candle \& Leaderboard API latency duy trì $\le 120$ms ($p95$).
  \end{itemize}
\end{itemize}
\end{column}
\begin{column}{0.53\textwidth}
\centering
\includegraphics[width=\linewidth,height=0.75\textheight,keepaspectratio]{../blueprint/assets/diagrams-png/15-job-queue-scale.png}
\end{column}
\end{columns}
\end{frame}

% Slide 25: Fault Tolerance
\begin{frame}{25. Fault Tolerance \& Self-Healing Architecture}
\begin{columns}[c]
\begin{column}{0.45\textwidth}
\begin{itemize}
  \item \textbf{Worker Lease Takeover \& Heartbeat:} Heartbeat 10s/lần. Nếu worker crash, lease timeout sau 30s, worker khác auto-takeover job.
  \item \textbf{Idempotency \& Retry:} Unique \texttt{idempotency\_key} constraint, eliminate duplicate execution risk.
  \item \textbf{Failure Isolation \& Reconnect:} Plugin failure isolation (lỗi 1 strategy không crash Worker); WSS auto-reconnect \& backfill.
  \item \textbf{Chaos Engineering Simulation:} Kill worker process / inject network drops để verify self-healing behavior.
\end{itemize}
\end{column}
\begin{column}{0.53\textwidth}
\centering
\includegraphics[width=\linewidth,height=0.75\textheight,keepaspectratio]{../blueprint/assets/diagrams-png/18-worker-lease-takeover.png}
\end{column}
\end{columns}
\end{frame}

% Slide 26: Deployment Topology
\begin{frame}{26. Deployment Topology \& MLOps Infrastructure}
\begin{columns}[c]
\begin{column}{0.45\textwidth}
\begin{itemize}
  \item \textbf{Full-Stack Containerization:} Isolated container services: Next.js Web Dashboard, Go Edge Gateway, Python Research API, Python Research Worker $\times$ N, Internal AI Inference Adapter, PostgreSQL.
  \item \textbf{Health Checks \& Liveness Probes:} \texttt{/healthz} và \texttt{/readyz} endpoints cho container auto-restart \& traffic routing.
  \item \textbf{MLOps \& Configuration:} Versioned system prompts và LLM API keys tách biệt qua environment variables (\texttt{.env}).
  \item \textbf{Kubernetes-Ready Architecture:} Hỗ trợ Deployment Replicas, Rolling Updates, HPA khi scale production.
\end{itemize}
\end{column}
\begin{column}{0.53\textwidth}
\centering
\includegraphics[width=\linewidth,height=0.75\textheight,keepaspectratio]{../blueprint/assets/diagrams-png/39-deployment-topology.png}
\end{column}
\end{columns}
\end{frame}

% Slide 27: Tradeoffs Matrix
\begin{frame}{27. Architectural Tradeoffs Matrix}
\resizebox{\textwidth}{!}{%
\begin{tabular}{lp{3.2cm}p{3cm}p{6cm}}
\toprule
\textbf{Lựa Chọn Thiết Kế} & \textbf{Phương Án Được Chọn} & \textbf{Phương Án Thay Thế} & \textbf{Lý Do \& Đánh Đổi Kiến Trúc (Rationale)} \\
\midrule
\textbf{System Architecture} & \textbf{Modular Monolith} & Microservices & Giảm overhead vận hành mạng/distributed latency; enforce module boundaries qua contracts. \\
\textbf{Candle \& Job Storage} & \textbf{PostgreSQL + B-Tree} & ClickHouse / InfluxDB & Giữ tính ACID cho Experiments \& Outbox; B-Tree indexing đủ đáp ứng hàng triệu candles. \\
\textbf{Job Queue \& Event Ingress} & \textbf{PostgreSQL Outbox \& Leases} & Kafka / RabbitMQ / Redis & Loại bỏ dual-write, ACID transactional guarantees, zero additional infrastructure dependencies. \\
\textbf{AI Code Execution} & \textbf{AST Analyzer + Sandbox} & Docker-in-Docker & Low latency initialization ($<10$ms), static syntax safety check, minimal container resource overhead. \\
\textbf{Sentiment Analysis Pipeline} & \textbf{Hybrid: Rule + LLM Batch} & Pure LLM Realtime & Optimize token cost \& API rate limits; non-blocking crawl pipeline, deep LLM scoring theo batch. \\
\bottomrule
\end{tabular}}
\end{frame}

% Slide 28: Replaceability
\begin{frame}{28. Replaceability \& Extensibility Architecture}
\begin{columns}[c]
\begin{column}{0.45\textwidth}
\begin{itemize}
  \item \textbf{Pluggable Market Data Providers:} \texttt{MarketProviderAdapter} interface cho phép switch từ Binance sang OKX, Bybit, Coinbase mà \textbf{không thay đổi} Core Frontend hay Strategy Engine.
  \item \textbf{Extensible Search Algorithms:} Sẵn sàng plug-in Reinforcement Learning (PPO) hoặc Custom Optimizers qua interface \texttt{ISearchAlgorithm}.
  \item \textbf{Extensible News Ingestion:} Dễ dàng add new sources (CryptoPanic, CoinDesk API) qua config \texttt{ApprovedSource}.
\end{itemize}
\end{column}
\begin{column}{0.53\textwidth}
\centering
\includegraphics[width=\linewidth,height=0.75\textheight,keepaspectratio]{../blueprint/assets/diagrams-png/20-market-provider-replaceability.png}
\end{column}
\end{columns}
\end{frame}

% Slide 29: Summary & QA
\begin{frame}{29. Architectural Summary \& Project Conclusion}
\begin{columns}[T]
\begin{column}{0.48\textwidth}
\begin{block}{\textbf{[Architectural Highlights \& Key Takeaways]}}
\begin{itemize}
  \item $\checkmark$ \textbf{ASR-Driven Architecture:} Bám sát 4 Architectural Drivers \& Quality Attributes taxonomy.
  \item $\checkmark$ \textbf{Clean Boundaries \& Anti-God Service:} Phân rã 6 bounded contexts, zero tight-coupling.
  \item $\checkmark$ \textbf{Multi-Agent \& Automation:} Self-repair loop (AST + Sandbox) \& anti-overfitting data partitioning (Train/Val/Test).
  \item $\checkmark$ \textbf{High Scalability \& Self-Healing:} Scale-out 100,000 backtests, Lease Takeover \& Idempotent execution.
\end{itemize}
\end{block}
\vspace{0.5em}
\centering
\textbf{[Q \& A]} \\
\textit{Cảm ơn Thầy và các bạn đã lắng nghe!}
\end{column}
\begin{column}{0.48\textwidth}
\begin{block}{\textbf{[Architecture Artifacts \& Verification]}}
\begin{itemize}
  \item \textbf{39 Blueprint Diagrams \& Specs:} C4 Model (L1-L3), UML Class, State Machines, Sequence Flows, Deployment Topology.
  \item \textbf{5 Interactive Working Dashboards:}
  \begin{enumerate}
    \item Realtime Market Chart \& Indicators
    \item Strategy Authoring \& Plugin Registry
    \item Async Backtest \& Trade Visualization
    \item Search Loop \& Top-K Leaderboard
    \item News Crawler \& Sentiment Intelligence
  \end{enumerate}
  \item \textbf{Automated Test Scenarios \& Benchmark Suite.}
\end{itemize}
\end{block}
\end{column}
\end{columns}
\end{frame}

\end{document}
'''

    with open(main_tex_path, 'w', encoding='utf-8') as f:
        f.write(tex_code)

    print(f'Wrote {main_tex_path} successfully!')

    # Compile with pdflatex
    res = subprocess.run(['pdflatex', '-interaction=nonstopmode', '-output-directory=' + slide_dir, main_tex_path], capture_output=True, text=True, errors='replace')
    if res.returncode == 0:
        print('SUCCESS: pdflatex compiled Slide/main.tex -> Slide/main.pdf (0 errors)!')
        return True
    else:
        print('LaTeX Compilation Output:\n' + res.stdout[-1500:])
        return False

if __name__ == '__main__':
    build_latex()
