# Speaker Notes — Crypto Strategy Lab

Kịch bản đầy đủ cho Slide/main.md.

- Ngôn ngữ: tiếng Việt, giữ nguyên tên class, interface và công nghệ trong deck.
- Phạm vi: toàn bộ deck, gồm title slide và 30 slide nội dung.
- Thời lượng gợi ý: 15–20 phút.
- Cách dùng: đọc phần “Lời nói”, dùng phần “Chuyển” để nối sang slide kế tiếp.

## Slide 1 — CRYPTO STRATEGY LAB

### Lời nói

“Em xin chào Thầy và các bạn. Nhóm em trình bày đề tài Crypto Strategy Lab, hay CryptoBot. Đây là nền tảng phục vụ research strategy giao dịch crypto, tự động tìm kiếm biến thể strategy và đánh giá bằng backtest có kiểm soát.

Phần trình bày tập trung vào kiến trúc phần mềm: hệ thống tách market data, strategy runtime, backtest, discovery, news intelligence và các agent AI như thế nào; đồng thời bảo đảm khả năng mở rộng, độ tin cậy và tính tái lập của kết quả.”

### Chuyển

“Trước tiên, em giới thiệu bối cảnh nghiệp vụ mà hệ thống cần phục vụ.”

## Slide 2 — Miền nghiệp vụ & bối cảnh

### Lời nói

“CryptoBot tập trung vào thị trường Binance USDT-M Futures. Đây là thị trường perpetual, cho phép giao dịch Long và Short liên tục. Giá và trạng thái thị trường được nhận qua WebSocket; việc mô phỏng khớp lệnh cần quan tâm đến BBO, tức Best Bid và Best Offer.

Đây không phải bài toán chỉ lấy giá đóng cửa rồi tính lợi nhuận. Funding rate, trading fee, slippage, leverage và liquidation đều có thể làm kết quả thay đổi đáng kể. Vì vậy, người dùng chính là quant researcher hoặc algorithmic trader, cần dữ liệu đa timeframe, backtest đáng tin cậy và các metric như Sharpe Ratio, Max Drawdown, Profit Factor và Win Rate.

Ngoài researcher, hệ thống còn hỗ trợ Autonomous AI Agents để crawl news, chấm sentiment, tạo strategy và tìm kiếm hyperparameter.”

### Chuyển

“Những đặc thù này dẫn đến một số vấn đề kiến trúc cụ thể.”

## Slide 3 — Bài toán thực tế & thách thức

### Lời nói

“Thách thức đầu tiên nằm ở market data. WebSocket có thể jitter hoặc mất kết nối, làm thiếu candle và khiến tín hiệu entry hoặc exit bị sai. Hệ thống cần phát hiện gap và bù dữ liệu từ REST.

Thách thức thứ hai là lookahead bias và parity mismatch. Nếu backtest nhìn thấy dữ liệu tương lai, hoặc bỏ qua phí và slippage, kết quả sẽ đẹp hơn thực tế. Khi chạy live, strategy có thể thua lỗ dù backtest rất tốt.

Thách thức thứ ba là combinatorial explosion. Khi có nhiều indicator và nhiều tham số, hàng nghìn tổ hợp cần được chạy. Chạy đồng bộ trong request sẽ khóa UI và làm API không ổn định. Cuối cùng, nếu strategy bị gắn chặt vào một exchange hoặc một service lớn, việc mở rộng sẽ khó. Vì vậy, cần plugin architecture, sandbox và job queue bất đồng bộ.”

### Chuyển

“Từ các vấn đề đó, nhóm xác định bốn architectural drivers.”

## Slide 4 — Bối cảnh & 4 Architectural Drivers

### Lời nói

“Driver thứ nhất là realtime market ingestion: nhận dữ liệu liên tục, latency thấp và có gap repair. Driver thứ hai là modifiability: có thể thêm strategy viết tay hoặc do AI tạo mà không sửa Core.

Driver thứ ba là khả năng scale cho search workload lớn. Auto-discovery phải chạy nền, không block giao diện. Driver thứ tư là unstructured news intelligence: nguồn tin có thể dùng RSS hoặc HTML, DOM có thể thay đổi, nên pipeline cần quality gate và LLM fallback.

Bốn driver này được ánh xạ vào bốn quyết định: dual-channel ingestion, strategy plugin với AST sandbox, event-driven job queue với leased worker, và multi-agent với LLM fallback.”

### Chuyển

“Các quyết định này được đánh giá qua nhóm quality attributes sau.”

## Slide 5 — Quality Attributes Taxonomy

### Lời nói

“Bảng này cho thấy mục tiêu chất lượng và tactic tương ứng.

Modifiability được bảo vệ bằng plugin architecture, dynamic registry và Open-Closed Principle. Scalability đến từ Python worker pool, leased job queue và broadcaster trong memory. Realtime performance được hỗ trợ bởi Go Edge, WebSocket và deterministic replay.

Reliability dùng fault isolation, transactional outbox và lease takeover. Observability được thể hiện qua structured logging, state machine và run metrics. Cuối cùng, reproducibility dựa trên immutable dataset snapshot, run config hash và seed lock.

Điểm nhóm muốn nhấn mạnh là mỗi quality attribute đều gắn với một cơ chế cụ thể; không chỉ là yêu cầu mô tả trên giấy.”

### Chuyển

“Tiếp theo, em minh họa hai kịch bản quan trọng nhất: thêm strategy và xử lý workload backtest lớn.”

## Slide 6 — ASR-1 Modifiability & ASR-2 Scalability

### Lời nói

“Với ASR-1, nguồn stimulus có thể là quant researcher hoặc AI Agent thêm một class mới, ví dụ MACDStrategy. Hệ thống auto-discover module, kiểm tra contract, rồi đưa metadata lên UI. Mục tiêu là thêm một file Python độc lập, không cần compile lại Go Gateway và không gây downtime.

Với ASR-2, user kích hoạt Auto Search Loop, tạo ra hàng nghìn backtest jobs. Job Queue phân phối chúng cho nhiều Python Worker bằng lease và heartbeat. Worker có thể scale-out theo queue backlog hoặc CPU load. Measure quan trọng là không dropped job, không OOM và completion rate đạt yêu cầu.

Hai kịch bản này giải thích vì sao strategy phải độc lập, còn backtest phải là job bất đồng bộ.”

### Chuyển

“Ngoài modifiability và scalability, hệ thống còn phải giữ data parity và tự phục hồi khi có lỗi.”

## Slide 7 — ASR-3 Realtime & ASR-4 Fault Tolerance

### Lời nói

“Ở ASR-3, giả sử Binance WebSocket mất kết nối trong khoảng thời gian ngắn. Go Market Gateway sẽ reconnect, xác định khoảng thời gian bị thiếu, gọi REST Backfill và deduplicate theo Open Time. Kết quả cần là chuỗi candle liên tục, không duplicate.

Ở ASR-4, giả sử Python Worker bị kill khi job đang ở trạng thái RUNNING. Heartbeat ngừng cập nhật; sau lease timeout, worker khác takeover và retry job. Cơ chế idempotency bảo đảm retry không tạo trade hoặc result trùng.

Đây là hai tình huống production thực tế, nên kiến trúc phải xử lý như behavior mặc định thay vì coi là lỗi hiếm.”

### Chuyển

“Từ quality attributes, ta chuyển sang góc nhìn người dùng và các actor tương tác với hệ thống.”

## Slide 8 — Tổng quan Use Case

### Lời nói

“Actor chính là Quant Researcher hoặc Trader. Người dùng xem candlestick realtime, chọn strategy đơn hoặc composite, chạy backtest và phân tích equity curve cùng các metric rủi ro.

Người dùng cũng có thể nhập natural-language prompt hoặc URL để AI tạo strategy, sau đó đưa strategy vào quy trình validation và authoring. Autonomous AI Agent đảm nhiệm các tác vụ như crawl news, scoring sentiment và trigger Auto Search Loop. System Worker xử lý ingestion định kỳ và các backtest jobs trong background.

Use-case diagram cho thấy hệ thống không chỉ là một charting application. Đây là research platform kết nối người dùng, agent, exchange và worker.”

### Chuyển

“Sau use case, C4 Level 1 cho thấy ranh giới hệ thống và các hệ thống bên ngoài.”

## Slide 9 — C4 Level 1: System Context

### Lời nói

“Ở context level, CryptoBot Core Platform nằm ở trung tâm. Binance cung cấp historical candle qua REST và realtime kline, BBO qua WebSocket. News sources và RSS feeds cung cấp dữ liệu tin tức. LLM Providers như OpenAI hoặc Groq cung cấp reasoning, sentiment analysis và hỗ trợ self-repair strategy.

Điểm quan trọng của context diagram là external dependency được nhận diện rõ. Core Platform không coi Binance, news source hay LLM là một phần nội bộ. Mỗi kết nối sau này sẽ đi qua adapter hoặc port, để có thể kiểm soát lỗi, quota và thay thế provider.”

### Chuyển

“Đi sâu thêm một mức, ta xem các container chính và trách nhiệm của từng container.”

## Slide 10 — C4 Level 2: Container Architecture

### Lời nói

“Next.js Dashboard là lớp hiển thị: chart, authoring, search, backtest, trade detail và news. Go Edge là public boundary, chịu trách nhiệm REST, WebSocket, authentication, quota và market normalization.

Python Research API sở hữu domain logic cho strategy, experiment, search, ranking, news và agent orchestration. Python Research Worker chạy các job nặng như backtest và agent task. PostgreSQL là source of truth cho market data, strategies, jobs, results, news và outbox.

Object Storage hoặc Broker là adapter tùy chọn. Thiết kế này giúp UI không gọi trực tiếp Binance hoặc worker, đồng thời cô lập workload tính toán khỏi public API.”

### Chuyển

“Tiếp theo, em zoom vào Python Research Platform, nơi chứa strategy, backtest và discovery.”

## Slide 11 — C4 Level 3: Python Research Platform

### Lời nói

“Python platform được chia thành application services, domain runtime, ports và infrastructure adapters.

Application services điều phối Research API, Experiment/Search/Ranking, News/Sentiment và AgentOrchestrator. Domain runtime chứa StrategyRegistry, StrategyRuntime, Backtest Engine và Execution Simulator. Các domain component này không nên phụ thuộc trực tiếp vào database hoặc provider.

Thay vào đó, platform định nghĩa các port như MarketDataPort, ModelGatewayPort, Artifact/Sandbox/Approval và Repository/Job/Outbox. Adapter bên ngoài nối các port này với Go Market Gateway, AI adapter, sandbox runner, safe fetcher và PostgreSQL. Nhờ vậy, quantitative logic có thể test độc lập.”

### Chuyển

“Market data là phần có yêu cầu realtime và concurrency cao, nên được tách sang Go Edge.”

## Slide 12 — C4 Level 3: Go Edge & Market Gateway

### Lời nói

“Go Edge là public boundary của hệ thống. REST API xử lý validation, DTO mapping, JWT, RBAC và quota. Public WebSocket Hub fan-out dữ liệu đến đúng các panel đang subscribe.

MarketProviderRegistry và BinanceAdapter che giấu chi tiết provider. MarketNormalizer và MarketService kiểm tra symbol, timeframe, decimal, timestamp và sequence; đồng thời xử lý checkpoint, deduplication, persistence, reconnect và backfill.

Python Research Client giao tiếp qua các signed command, query và progress/result event. Lựa chọn này giữ network-heavy work ở Go, còn strategy và quantitative computation ở Python. Nếu mạng Binance lỗi, worker research vẫn không bị crash theo.”

### Chuyển

“Hai container này được chia thành sáu bounded context để tránh hình thành một God Service.”

## Slide 13 — Component Boundaries: 6 Core Modules

### Lời nói

“Sáu bounded context gồm Market Realtime, Strategy Engine, Backtest, Discovery, News Crawler và News Intelligence.

Market Realtime xử lý WSS, candle và gap backfill. Strategy Engine chạy strategy đơn hoặc composite. Backtest replay Candle và BBO, mô phỏng execution và tạo trade facts. Discovery sinh candidate, chạy Search Loop, validation và stop conditions. News Crawler lấy RSS hoặc HTML và bảo vệ SSRF. News Intelligence xử lý extraction và sentiment bất đồng bộ.

Các module có cohesion cao, còn coupling thấp. Giao tiếp qua versioned DTOs và Outbox events. Ví dụ, Discovery không cần biết chi tiết cách worker fill lệnh; nó chỉ gửi experiment config và nhận result facts.”

### Chuyển

“Slide kế tiếp đặc tả sâu hơn cách Strategy Engine và Backtest phối hợp với nhau.”

## Slide 14 — Component Specs: Strategy Engine, Backtest, Discovery

### Lời nói

“Strategy Engine cung cấp runtime pluggable qua IStrategy, gồm registry, indicators và single/composite runtime. Invariant quan trọng là execution parity giữa Live và Backtest.

Backtest là event-driven subsystem. Nó replay immutable Candle và BBO bằng cùng StrategyRuntime, mô phỏng execution rồi phát trade và evaluation facts qua Worker hoặc Outbox. Discovery đứng ở tầng orchestration: generate candidates, gửi backtest jobs qua Train, Validation và Sealed Test, đồng thời giữ lineage và stop conditions.

Ba module này có thể phát triển độc lập nhưng vẫn dùng chung contract. Đó là nền tảng cho phần UML và runtime flow tiếp theo.”

### Chuyển

“Trước hết, em đi sâu vào plugin model của Strategy Engine.”

## Slide 15 — UML Class Diagram: Strategy Plugin Model

### Lời nói

“Trung tâm của Strategy Engine là contract IStrategy. Mỗi strategy triển khai evaluate(context) và trả về BUY, SELL hoặc HOLD.

Context chứa datafeed, indicator values, BBO và sentiment window cần thiết. Strategy không tự đọc database hoặc gọi Binance. Năm strategy đơn trong phiên bản đầu là ma_crossover, bollinger_bands, rsi_threshold, smc_structure và news_sentiment.

Composite Strategy nhận từ hai đến năm strategy con, rồi kết hợp tín hiệu bằng majority hoặc weighted. StrategyRegistry dynamic-load strategy mới từ Python module. Cấu trúc này loại bỏ God Service và cho phép UI đọc metadata, parameter schema từ registry.”

### Chuyển

“Strategy Engine quyết định cách một candidate chạy. Discovery quyết định candidate nào được tạo và candidate nào được giữ lại.”

## Slide 16 — UML Class Diagram: Search Algorithm & Discovery Loop

### Lời nói

“Discovery dùng contract ISearchAlgorithm với method sample(space, rng). Nhờ contract này, hệ thống có thể thay Random Search bằng Genetic Algorithm hoặc Bayesian Optimization mà không sửa Strategy Engine.

Vòng lặp phải chống overfitting. Train dùng để search và tối ưu biến thể. Validation kiểm tra khả năng generalization và đóng vai trò gate. Sealed Test là dữ liệu out-of-sample để benchmark và cập nhật Leaderboard; không dùng nó để tiếp tục chỉnh tham số.

Mỗi candidate cần lưu lineage: strategy version, parameter config, dataset snapshot, seed và result hash. DiscoveryTrialReservation giới hạn số trial chạy đồng thời, bảo vệ worker khỏi bị search workload chiếm hết tài nguyên và giữ fair scheduling.”

### Chuyển

“Cùng mô hình contract và quality gate này cũng được áp dụng cho news crawler, nhưng crawler cần thêm lớp an toàn khi xử lý URL.”

## Slide 17 — UML Class Diagram: Resilient News Crawler

### Lời nói

“News ingestion dùng NewsProvider protocol. RssNewsProvider và HtmlNewsProvider chỉ được phép đọc các ApprovedSource.

Trước khi fetch, Resolver và Fetcher kiểm tra DNS, block private IP và kiểm soát redirect để giảm SSRF risk. Sau khi lấy HTML, Quality Gate kiểm tra nội dung có đủ và đúng cấu trúc không. Nếu DOM thay đổi hoặc extraction rỗng, NewsExtractionHTTPAdapter gọi LLM fallback để trích xuất structured content.

Sentiment scoring chạy theo batch bất đồng bộ. Nếu AI provider lỗi, crawl pipeline vẫn hoàn thành và có thể retry scoring sau. Vì vậy, news intelligence không trở thành điểm nghẽn của toàn hệ thống.”

### Chuyển

“Ba bounded context chính đã rõ. Bây giờ ghép chúng vào high-level architecture.”

## Slide 18 — High-Level Architecture: Modular Monolith

### Lời nói

“Kiến trúc tổng thể chọn Modular Monolith ở cấp domain, kết hợp process separation cho Go Edge, Python API và Worker.

Frontend là Next.js SPA, nhận realtime chart và telemetry qua SSE hoặc WebSocket. Go API Gateway xử lý CQRS, RBAC, rate limiting và Binance ingestion. Python Backend sở hữu strategy plugin, job queue và backtest worker pool. PostgreSQL giữ dữ liệu ACID; Go Edge dùng ring buffer cho dữ liệu cần fan-out nhanh. Agent và LLM kết nối qua adapter riêng.

Mục tiêu không phải tách mọi class thành microservice. Mục tiêu là giữ bounded context rõ, giảm distributed overhead và chỉ tách process ở nơi có yêu cầu concurrency hoặc isolation.”

### Chuyển

“Các ranh giới này được giữ vững bằng một số design pattern chính.”

## Slide 19 — Design & Architectural Patterns

### Lời nói

“Pattern thứ nhất là CQRS ở Go API: command như tạo experiment tách khỏi query như đọc candle hoặc leaderboard. Điều này giúp tối ưu từng loại workload.

Pattern thứ hai là dual-channel market engine. Realtime WSS và historical REST backfill dùng schema và normalization parity, nên dữ liệu live và dữ liệu replay có cùng ý nghĩa.

Pattern thứ ba là Transactional Outbox. Khi tạo experiment, metadata và job event được ghi trong cùng transaction. Outbox dispatcher phát event sau khi commit, tránh tình trạng database đã tạo experiment nhưng queue chưa nhận job.

Pattern cuối là Plugin Architecture, tách Core Engine khỏi strategy logic và search algorithm. Đây là cơ chế trực tiếp phục vụ modifiability.”

### Chuyển

“Ngoài các component deterministic, hệ thống còn có lớp AI hỗ trợ authoring và self-repair.”

## Slide 20 — Multi-Agent & Autonomous AI Loop

### Lời nói

“Strategy Designer Agent nhận prompt tự nhiên hoặc URL và tạo Draft spec dạng JSON. Implementation Agent chuyển draft thành Python code tuân thủ IStrategy.

Code không được chạy trực tiếp. AST validator kiểm tra syntax và cấu trúc; Sandbox chạy dry-run cô lập. Nếu có traceback, lỗi được đưa lại cho LLM để self-repair, với số vòng retry giới hạn. Giới hạn retry giúp tránh loop vô hạn và kiểm soát chi phí.

Candidate Discovery Agent tự động sample hyperparameters, còn Crawling Agent xử lý nhiều nguồn tin. AI ở đây đóng vai trò trợ lý có ranh giới: mọi output vẫn đi qua contract, validation, approval và sandbox.”

### Chuyển

“Sau khi nói về cấu trúc, em chuyển sang runtime flow, bắt đầu từ nguồn dữ liệu realtime.”

## Slide 21 — Runtime Flow: Realtime Ingestion & Gap Backfill

### Lời nói

“Khi mở chart, hệ thống lấy một vùng historical candles từ PostgreSQL hoặc Binance REST theo symbol và timeframe. Sau đó WebSocket stream các tick và cập nhật provisional candle.

Khi candle đóng, hệ thống persist candle và broadcast CandleClosed qua SSE hoặc WebSocket broadcaster. Các subscriber như chart hoặc downstream processor nhận cùng event.

Nếu WSS bị drop, gateway reconnect và xác định khoảng gap dựa trên checkpoint cuối cùng. REST backfill bù candle thiếu, rồi deduplicate theo Open Time trước khi persist. Cách này giữ continuous time-series và bảo đảm Strategy Runtime không nhận dữ liệu bị đứt hoặc trùng.”

### Chuyển

“Khi datafeed đã sẵn sàng, Strategy Runtime mới bắt đầu sinh signal.”

## Slide 22 — Runtime Flow: Strategy Execution & Dynamic Registration

### Lời nói

“Hệ thống đưa datafeed và sentiment window vào StrategyContext, sau đó gọi IStrategy.evaluate(). Strategy trả về BUY, SELL hoặc HOLD. Với composite, CompositeStrategy aggregate tín hiệu theo majority hoặc weighted policy.

Strategy viết tay được dynamic-load từ registry sau khi kiểm tra contract. Strategy AI-generated đi qua AST validator và sandbox trước khi được phép đăng ký. Các builtin hoặc module nguy hiểm như eval, subprocess, socket bị policy chặn.

Invariant ở đây là runtime parity: Live và Backtest dùng cùng rule signal và cùng StrategyRuntime. Có parity thì kết quả research mới có giá trị khi đưa vào execution thực tế.”

### Chuyển

“Từ signal, engine cần mô phỏng fill, fee và slippage. Phần đó nằm trong Backtest Pipeline.”

## Slide 23 — Runtime Flow: Async Backtest Pipeline

### Lời nói

“Một experiment bắt đầu bằng việc API ghi experiment metadata và job event vào Outbox trong cùng ACID transaction.

Worker claim job bằng optimistic locking với FOR UPDATE SKIP LOCKED, sau đó gửi heartbeat. Nếu worker crash, lease timeout cho phép worker khác takeover. Request của người dùng không phải giữ mở trong toàn bộ thời gian tính toán.

Engine replay immutable Candle và BBO theo thứ tự thời gian. Mỗi thời điểm, strategy nhận context và sinh signal; Execution Simulator xử lý fill, fee và slippage rồi ghi trade facts. Dùng BBO giúp execution simulator mô phỏng giá khớp thực tế hơn giả định luôn fill ở candle close.

Discovery chạy candidate qua Train, Validation và Sealed Test theo policy. Evaluator tính Sharpe Ratio, Max Drawdown, Profit Factor và các metric khác. Trade logs, config hash, dataset snapshot và result hash được lưu; candidate đạt điều kiện mới được đưa vào Top-K Leaderboard.

Outbox, lease và idempotency giúp retry an toàn, không tạo duplicate execution.”

### Chuyển

“Market, strategy và backtest đều có recovery path. News pipeline cũng cần behavior tương tự khi website thay đổi.”

## Slide 24 — Runtime Flow: Resilient News Crawl & LLM Fallback

### Lời nói

“Bước đầu là SSRF validation: kiểm tra URL thuộc ApprovedSource, resolve DNS và block private hoặc internal IP. Sau đó crawler fetch nội dung qua RSS hoặc HTML parser.

Quality Gate kiểm tra DOM và chất lượng text. Nếu extraction thành công, article đi tiếp theo pipeline chuẩn. Nếu DOM thay đổi hoặc text rỗng, raw HTML được gửi đến LLM Agent để parse structured content.

Cuối cùng, sentiment scoring chạy ở background worker và lưu điểm trong khoảng từ -1.0 đến 1.0 vào PostgreSQL. Nhờ tách extraction và scoring, lỗi AI không làm dừng crawl; hệ thống có thể retry phần scoring độc lập.”

### Chuyển

“Các agent và source bên ngoài làm tăng tính linh hoạt nhưng cũng mở rộng attack surface. Vì vậy, hệ thống dùng defense-in-depth.”

## Slide 25 — Security Architecture: Defense-in-Depth

### Lời nói

“Lớp đầu tiên là authentication và RBAC: JWT, role và tenant hoặc user isolation cho experiment.

Lớp thứ hai bảo vệ crawler khỏi SSRF bằng domain whitelist, DNS validation và block các dải private IP, loopback và cloud metadata endpoint.

Lớp thứ ba bảo vệ việc chạy code AI. AST static analysis loại bỏ syntax hoặc import nguy hiểm; sandbox giới hạn runtime. Những thao tác như eval, subprocess, socket và os.system không được phép.

Lớp cuối là tool invocation boundary. Agent chỉ gọi tool qua DTO có schema, validation và input boundary rõ. Nếu một lớp bị bypass, các lớp còn lại vẫn giảm blast radius.”

### Chuyển

“Sau security, em trình bày cách hệ thống scale khi số lượng backtest tăng mạnh.”

## Slide 26 — Scalability Architecture & Benchmark

### Lời nói

“API và worker được thiết kế stateless ở mức process, nên có thể tăng số Python Worker theo CPU load hoặc queue backlog. PostgreSQL job queue dùng index để worker tìm job chưa claim hiệu quả.

Theo benchmark của project, bốn worker đạt throughput trên 1.500 backtests mỗi phút trong workload thử nghiệm. Candle và Leaderboard API giữ latency khoảng tối đa 120 milliseconds ở p95 trong kịch bản benchmark. Hệ thống cũng hướng tới workload 100.000 backtests bằng cách scale-out worker thay vì tăng kích thước một process duy nhất.

Con số benchmark là kết quả trong môi trường thử nghiệm, không phải cam kết cho mọi production environment. Giá trị kiến trúc nằm ở việc workload có thể phân phối và đo lường được.”

### Chuyển

“Scale giúp xử lý nhiều job; fault tolerance bảo đảm job không bị mất khi một worker gặp lỗi.”

## Slide 27 — Fault Tolerance & Self-Healing

### Lời nói

“Worker gửi heartbeat định kỳ. Nếu process bị kill, lease timeout sau khoảng thời gian cấu hình và worker khác takeover. Unique idempotency_key ngăn việc cùng một job ghi kết quả hai lần.

Strategy plugin cũng được cô lập. Lỗi của một plugin không được làm sập toàn bộ worker. Với market stream, gateway reconnect và backfill khi có network drop.

Nhóm kiểm tra các behavior này bằng chaos simulation: kill worker, inject network drop và quan sát state transition. Mục tiêu không phải che giấu lỗi, mà là đưa lỗi về trạng thái có thể retry, takeover hoặc báo failure rõ ràng.”

### Chuyển

“Các cơ chế này được triển khai trong topology containerized và có đường nâng cấp lên Kubernetes.”

## Slide 28 — Deployment Topology & MLOps

### Lời nói

“Toàn bộ stack được containerize: Next.js Dashboard, Go Edge Gateway, Python Research API, Python Research Worker, AI adapter và PostgreSQL.

Mỗi service có health check và liveness hoặc readiness endpoint như /healthz và /readyz. Container orchestrator có thể restart service không healthy và chỉ route traffic đến instance sẵn sàng.

System prompt được version hóa; API key và cấu hình nhạy cảm nằm trong environment variables, không hard-code vào source. Topology hiện chạy được với Docker Compose và sẵn sàng chuyển sang Kubernetes với replicas, rolling updates và HPA khi production cần scale lớn hơn.”

### Chuyển

“Không có kiến trúc nào tối ưu tuyệt đối. Slide sau trình bày các lựa chọn và đánh đổi chính.”

## Slide 29 — Architectural Tradeoffs Matrix

### Lời nói

“Nhóm chọn Modular Monolith thay vì Microservices vì giảm network overhead và distributed latency, trong khi module boundaries vẫn được enforce bằng contract.

PostgreSQL với B-Tree được chọn cho candle và job storage vì project cần ACID cho experiment và Outbox. ClickHouse hoặc InfluxDB có thể mạnh hơn cho analytics chuyên biệt, nhưng thêm hạ tầng và làm phức tạp transaction boundary.

PostgreSQL Outbox và Lease được chọn thay Kafka, RabbitMQ hoặc Redis để giữ transactional guarantee và không thêm dependency vận hành. AI code execution dùng AST Analyzer và Sandbox vì khởi tạo nhẹ hơn Docker-in-Docker. Sentiment dùng hybrid rule và LLM batch để cân bằng chất lượng, token cost và rate limit.

Mỗi lựa chọn ưu tiên nhu cầu hiện tại của đồ án; khi scale hoặc workload thay đổi, adapter boundary cho phép thay thế có kiểm soát.”

### Chuyển

“Các adapter đó tạo nền tảng cho replaceability và mở rộng trong tương lai.”

## Slide 30 — Replaceability & Extensibility

### Lời nói

“MarketProviderAdapter cho phép chuyển từ Binance sang OKX, Bybit hoặc Coinbase mà không thay đổi Core Frontend hay Strategy Engine. Provider mới chỉ cần đáp ứng interface và mapping dữ liệu chuẩn.

Search có thể mở rộng thêm Reinforcement Learning như PPO hoặc custom optimizer qua ISearchAlgorithm. News ingestion cũng có thể thêm CryptoPanic hoặc CoinDesk API bằng ApprovedSource và provider adapter.

Điểm chung là mở rộng ở boundary, không sửa domain runtime. Điều này giảm regression risk và giúp hệ thống thích nghi khi exchange, thuật toán hoặc nguồn tin thay đổi.”

### Chuyển

“Cuối cùng, em tổng kết các quyết định kiến trúc và kết quả mà hệ thống hướng tới.”

## Slide 31 — Architectural Summary & Project Conclusion

### Lời nói

“CryptoBot bắt đầu từ bốn architectural drivers: realtime ingestion, modifiability, search scalability và news intelligence. Từ đó, nhóm xây dựng sáu bounded context với boundary rõ và tránh God Service.

Strategy Plugin Architecture hỗ trợ strategy đơn, composite và AI-assisted authoring. Discovery Loop có Train, Validation và Sealed Test để giảm overfitting. Backtest dùng immutable data, cùng Strategy Runtime, execution simulation và provenance đầy đủ. Worker lease, Outbox, idempotency và reconnect tạo khả năng self-healing; worker pool giúp scale-out workload lớn.

Về artifact, project có C4, UML, state machine, sequence flow, deployment topology, các dashboard tương tác và automated test hoặc benchmark suite để kiểm chứng.

Đó là phần trình bày của nhóm em. Em cảm ơn Thầy và các bạn đã lắng nghe. Nhóm em sẵn sàng nhận câu hỏi.”

## Câu trả lời nhanh cho Q&A

### Vì sao không dùng Microservices ngay từ đầu?

“Modular Monolith giảm overhead vận hành và distributed latency trong phạm vi đồ án. Boundary vẫn rõ qua module, DTO và port. Khi cần scale độc lập, các process như Go Edge, Python API và Worker đã được tách sẵn.”

### Vì sao cần cùng Strategy Runtime cho Live và Backtest?

“Để tránh parity mismatch. Nếu Live và Backtest có hai cách tính signal, leaderboard có thể chọn nhầm strategy. Dùng chung runtime giúp kết quả research phản ánh gần đúng execution.”

### Vì sao cần Sealed Test?

“Train dùng để tối ưu, Validation dùng để gate, Sealed Test dùng để benchmark out-of-sample. Nếu dùng Sealed Test để chỉnh tham số, test set không còn độc lập.”

### Worker crash giữa backtest xử lý thế nào?

“Heartbeat dừng, lease hết hạn, worker khác takeover và retry. Idempotency key cùng unique constraint ngăn duplicate result hoặc trade facts.”

### AI-generated code có được chạy trực tiếp không?

“Không. Code qua AST validation, sandbox dry-run và policy check trước khi registry cho phép load. Traceback có thể quay lại LLM cho self-repair, nhưng retry bị giới hạn.”

### Vì sao dùng BBO thay vì chỉ candle close?

“Candle close không mô tả chính xác giá bid hoặc ask lúc khớp. BBO giúp execution simulator mô phỏng limit fill, fee và slippage sát hơn.”

### Làm sao tránh Discovery chiếm hết worker?

“DiscoveryTrialReservation giới hạn số trial đồng thời, có fair scheduling và giữ quota cho request hoặc job khác.”

