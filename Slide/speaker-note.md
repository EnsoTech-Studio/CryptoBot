# Speaker Note - Crypto Strategy Lab (CryptoBot)

Nguồn đối chiếu: `Slide/standalone.html` hiện tại, gồm 31 slide.

Gợi ý nhịp trình bày: bản đầy đủ khoảng 20-25 phút. Nếu cần nói nhanh, ưu tiên giữ các ý chính về ASR, boundary 6 module, Strategy Plugin, Discovery/Backtest, News Intelligence, Security, Benchmark và Tradeoffs.

## Slide 1/31 - Trang mở đầu

Em xin chào Thầy và các bạn. Hôm nay em trình bày đề tài Crypto Strategy Lab, hay CryptoBot. Đây là một nền tảng hỗ trợ research, tự động discovery và đánh giá trading strategy cho thị trường crypto futures.

Điểm em muốn nhấn mạnh ngay từ đầu là bài này không chỉ tập trung vào việc có một bot giao dịch, mà tập trung vào kiến trúc phần mềm phía sau: làm sao lấy dữ liệu thị trường realtime, chạy backtest đáng tin cậy, tự động tìm kiếm strategy, phân tích tin tức bằng AI, và vẫn giữ hệ thống có thể mở rộng, thay thế, quan sát và phục hồi khi lỗi.

Trong phần trình bày, em sẽ đi từ bối cảnh nghiệp vụ, các yêu cầu kiến trúc quan trọng, sau đó vào C4 model, module boundary, runtime flow và cuối cùng là benchmark cùng tradeoff.

## Slide 2/31 - 1. Miền Nghiệp Vụ & Bối Cảnh

Miền nghiệp vụ của hệ thống là Binance USDT-M Futures và algorithmic trading. Đây là thị trường perpetual futures, giao dịch 24/7, cho phép long và short, có leverage, funding rate, fee, slippage và rủi ro liquidation. Vì vậy strategy không thể chỉ nhìn giá đóng cửa đơn giản, mà phải quan tâm đến điều kiện khớp lệnh, phí và biến động realtime.

Người dùng chính là quant researcher hoặc algorithmic trader. Họ cần xem dữ liệu candle nhiều timeframe, backtest strategy và đo các metric như Sharpe Ratio, Max Drawdown, Profit Factor và Win Rate.

Ngoài người dùng trực tiếp, hệ thống còn có autonomous AI agent. Agent này có thể crawl tin tức tài chính, phân tích sentiment, sinh strategy code, debug và thử nhiều bộ hyperparameter. Đây là lý do kiến trúc phải hỗ trợ cả data pipeline lẫn AI workflow.

## Slide 3/31 - 2. Bài Toán Thực Tế & Thách Thức

Bài toán thực tế có hai nhóm thách thức lớn. Nhóm đầu tiên là market data và order execution. Dữ liệu realtime qua WebSocket có thể bị jitter hoặc mất gói. Nếu mất một candle mà hệ thống không phát hiện, tín hiệu entry hoặc exit có thể bị sai. Vì vậy hệ thống cần cơ chế tự phát hiện gap và backfill dữ liệu bằng REST.

Thách thức tiếp theo là lookahead bias và parity mismatch. Nếu backtest vô tình nhìn trước dữ liệu tương lai, hoặc giả lập khớp lệnh quá lý tưởng, strategy có thể trông rất tốt trên lịch sử nhưng chạy live lại thua lỗ. Do đó engine phải replay dữ liệu deterministic và mô phỏng fee, slippage, BBO limit fill sát thực tế hơn.

Nhóm thứ hai là scalability và architecture. Việc quét hàng ngàn tham số không thể chạy đồng bộ trên UI. Đồng thời hệ thống không nên bị khóa vào một sàn, một model AI, hoặc một kiểu strategy duy nhất. Vì vậy cần job queue, worker pool và plugin architecture.

## Slide 4/31 - 3. Bối Cảnh & 4 Nhóm Architectural Drivers

Từ các thách thức đó, em rút ra bốn nhóm architectural drivers.

Driver thứ nhất là realtime market ingestion: dữ liệu thay đổi liên tục và hệ thống phải vừa stream realtime vừa tự bù gap. Driver thứ hai là high modifiability: người dùng hoặc AI có thể thêm strategy mới mà không sửa core. Driver thứ ba là massive search scalability: auto-discovery phải chạy hàng ngàn candidate mà không block UI. Driver thứ tư là unstructured news intelligence: tin tức đến từ nhiều nguồn, HTML có thể thay đổi, nên crawler và sentiment pipeline phải linh hoạt.

Mỗi driver dẫn đến một quyết định kiến trúc tương ứng. Realtime dùng dual-channel ingestion gồm WSS và REST backfill. Modifiability dùng Strategy Plugin và AST sandbox. Scalability dùng event-driven job queue với leased worker. News intelligence dùng multi-agent và LLM fallback để trích xuất, tổng hợp và chấm điểm sentiment.

## Slide 5/31 - 4. Hệ Thống Quality Attributes

Slide này gom các yêu cầu thành quality attributes. Với Modifiability, trọng tâm là thêm strategy, search algorithm hoặc market provider mà không sửa core. Kỹ thuật áp dụng là plugin architecture, dynamic registry và Open-Closed Principle.

Với Scalability, hệ thống phải xử lý workload backtest lớn và stream candle realtime. Ở đây em dùng Python worker pool scale-out và PostgreSQL leased job queue. Với Realtime và Performance, phần edge gateway viết bằng Go để tận dụng concurrency, WebSocket streaming và in-memory broadcaster.

Reliability tập trung vào fault isolation, transactional outbox và lease takeover. Observability cho phép theo dõi worker health, search loop progress và metric. Cuối cùng Reproducibility đảm bảo kết quả backtest có thể lặp lại bằng immutable dataset snapshot, run config hash và seed lock. Đây là phần giúp leaderboard không chỉ đẹp trên UI mà còn đáng tin về mặt nghiên cứu.

## Slide 6/31 - 5. Kịch Bản ASR Chi Tiết: Modifiability & Scalability

Ở slide này, em cụ thể hóa quality attributes thành kịch bản ASR.

ASR-1 là Modifiability. Tác nhân có thể là quant researcher hoặc AI agent. Khi họ thêm một strategy mới, ví dụ MACDStrategy, hệ thống phải tự phát hiện, load metadata lên UI và không cần compile lại Go Gateway hay sửa core. Thước đo là chỉ thao tác trên một file Python độc lập và không downtime.

ASR-2 là Scalability. Khi người dùng trigger Auto Search Loop, hệ thống có thể đẩy 10,000 backtest jobs vào queue cùng lúc. Worker pool nhận việc qua lease heartbeat, chia tải ra nhiều process và tránh OOM hoặc memory leak. Thước đo mong muốn là completion rate 100%, không dropped job và CPU ổn định.

Hai ASR này cho thấy kiến trúc không chỉ đúng về chức năng, mà còn có tiêu chí đo được.

## Slide 7/31 - 6. Kịch Bản ASR Chi Tiết: Realtime & Reliability

ASR-3 tập trung vào realtime và data parity. Nếu Binance WebSocket bị drop hoặc mạng bị mất trong 30 giây, Go Market Gateway phải tự reconnect, gọi REST backfill để bù candle thiếu và deduplicate bằng open time. Kết quả mong muốn là stream candle liên tục, không duplicate và catch-up dưới 2 giây.

ASR-4 tập trung vào fault tolerance. Nếu Python worker bị kill đột ngột khi job đang chạy, job không được kẹt vĩnh viễn ở trạng thái RUNNING. Cơ chế heartbeat và lease timeout sau 30 giây cho phép worker khác takeover và retry. Thước đo là job hoàn thành, không stuck job và không orphan job.

Hai kịch bản này là nền cho self-healing: lỗi mạng hoặc lỗi process không được làm hỏng tính toàn vẹn của pipeline.

## Slide 8/31 - 7. Tổng Quan Use Case Hệ Thống

Slide use case cho thấy ba nhóm actor chính.

Nhóm thứ nhất là quant researcher hoặc trader. Họ xem realtime candlestick chart, thử single strategy hoặc composite strategy, chạy backtest, phân tích equity curve, drawdown, win rate và có thể nhập prompt hoặc URL để AI hỗ trợ tạo strategy.

Nhóm thứ hai là autonomous AI agent. Agent có nhiệm vụ crawl financial news, extract nội dung, chấm sentiment và có thể trigger auto search loop để tìm candidate tốt hơn.

Nhóm thứ ba là system worker. Đây là phần chạy nền, ingest candle định kỳ và xử lý async backtest job queue.

Điểm chính của use case là UI không tự làm mọi thứ. UI điều phối trải nghiệm, còn các tác vụ nặng được chuyển xuống worker và event pipeline.

## Slide 9/31 - 8. C4 Model Level 1: System Context

Ở C4 Level 1, hệ thống trung tâm là CryptoBot Core Platform. Nó nằm giữa người dùng, sàn giao dịch, nguồn tin tức và LLM provider.

Phía Binance cung cấp historical candle qua REST và stream giá realtime qua WebSocket. Phía news source hoặc RSS feed cung cấp dữ liệu phi cấu trúc về thị trường crypto. Phía LLM provider như OpenAI hoặc Groq hỗ trợ reasoning, sentiment analysis và self-repair strategy.

Ranh giới hệ thống ở đây rất quan trọng. CryptoBot không kiểm soát Binance, không kiểm soát cấu trúc HTML của nguồn tin và cũng không kiểm soát độ ổn định của LLM provider. Vì vậy kiến trúc phải coi các hệ thống bên ngoài là unreliable dependency và đặt adapter, retry, fallback, validation ở boundary.

## Slide 10/31 - 9. C4 Model Level 2: Container Diagram

Ở C4 Level 2, hệ thống được chia thành các container chính.

Next.js Dashboard là lớp giao diện, chủ yếu render chart, authoring, search, backtest, trade detail và news. Go Edge & Market Gateway là lớp public REST và WebSocket, chịu trách nhiệm auth, quota, normalize candle/BBO và fan-out realtime.

Python Research API xử lý strategy runtime, agent runtime, experiment, search, news và sentiment orchestration. Python Research Worker scale theo N instance để xử lý job nặng như backtest và agent task. PostgreSQL là source of truth cho market data, strategies, jobs, results, news và outbox.

Ngoài ra có object storage hoặc broker tùy chọn. Điểm thiết kế là phần core vẫn chạy được với PostgreSQL trước, nhưng boundary đủ rõ để sau này thay queue hoặc storage nếu workload tăng.

## Slide 11/31 - 10. C4 Model Level 3: Python Research Platform

Slide này zoom vào Python Research Platform. Em chia nó thành application services, domain runtime, ports và infrastructure adapters.

Application services gồm Research API, Experiment/Search/Ranking, News/Sentiment và AgentOrchestrator. Đây là nơi nhận request nghiệp vụ và điều phối use case.

Domain runtime gồm StrategyRegistry, StrategyRuntime, Backtest Engine, Execution Simulator, news rules và agent state. Đây là phần quan trọng nhất vì chứa logic nghiệp vụ và cần được giữ độc lập khỏi database hoặc HTTP.

Ports định nghĩa các hợp đồng như MarketDataPort, ModelGatewayPort, Artifact/Sandbox/Approval và Repository/Job/Outbox. Infrastructure adapters hiện thực các port đó: adapter sang Go Market, adapter sang LLM nội bộ, Sandbox Runner, SafeFetcher/Readability và PostgreSQL repositories.

Thiết kế này giúp domain không bị khóa vào framework hay vendor cụ thể.

## Slide 12/31 - 11. C4 Model Level 3: Go Edge & Market Gateway

Slide này zoom vào Go Edge & Market Gateway. Đây là lớp gần thị trường và gần người dùng nhất.

REST API xử lý validation, DTO mapping, JWT, RBAC và quota. Public WebSocket Hub nhận subscription từ dashboard và fan-out dữ liệu theo panel key. MarketProviderRegistry kết nối với BinanceAdapter để lấy historical data và realtime stream.

MarketNormalizer và MarketService chuẩn hóa symbol, timeframe, decimal, timestamp và sequence. Đồng thời nó checkpoint, de-dup, persist, reconnect và backfill khi có gap. Phần Python Research Client và Internal Event Ingress tạo cầu nối sang Python thông qua signed command, query và progress/result event.

Lý do dùng Go ở lớp này là vì workload I/O concurrency cao, nhiều connection WebSocket và yêu cầu latency thấp.

## Slide 13/31 - 12. Component Boundaries: 6 Module Cốt Lõi

Để tránh God Service, hệ thống được chia thành 6 bounded context có trách nhiệm rõ.

Market Realtime ở Go Edge xử lý WSS candles, BBO và gap backfill. Strategy Engine ở Python xử lý single và composite runtime. Backtest ở Python Worker replay Candle+BBO và tạo execution facts. Discovery sinh candidate, điều phối search loop, validation và stop condition. News Crawler lấy RSS/HTML qua SSRF guard và quality gate. News Intelligence dùng Python và AI adapter để extraction, tổng hợp và scoring sentiment.

Go và Python được chọn theo thế mạnh. Go sở hữu market ingestion, API edge và fan-out. Python sở hữu quant math, AST, AI/ML, strategy, backtest, discovery và news intelligence.

Các module giao tiếp qua DTO versioned và outbox events, nhờ vậy mỗi phần có thể thay đổi tương đối độc lập.

## Slide 14/31 - 13. Đặc Tả Ranh Giới & Phạm Vi 6 Module

Slide này mô tả rõ input, output và invariant của từng nhóm module.

Market Realtime nhận raw Binance WSS, tạo normalized Candle và BBO, persist vào PostgreSQL và broadcast CandleClosed qua SSE hoặc WebSocket. Invariant là time-series liên tục và không duplicate candle.

Strategy Engine nhận data đã chuẩn hóa và chạy qua IStrategy. Nó hỗ trợ strategy viết tay, strategy do AI sinh và composite strategy. Invariant là live trading và backtest phải dùng cùng runtime để đảm bảo parity.

Backtest replay dữ liệu immutable và ghi trade/evaluation facts. Discovery sinh candidate, chạy Train, Validation và Sealed Test. News Crawler fetch dữ liệu từ ApprovedSource, qua SSRF protection và Quality Gate. News Intelligence xử lý extraction khi DOM thay đổi và chấm sentiment từ -1.0 đến 1.0 theo async pipeline.

## Slide 15/31 - 14. UML Class Diagram: Strategy Plugin Model

Trung tâm của Strategy Engine là contract IStrategy. Mỗi strategy chỉ cần implement evaluate(context) và trả về BUY, SELL hoặc HOLD.

Context chứa những dữ liệu strategy được phép dùng, ví dụ candle history, indicator values, BBO và sentiment window. Strategy không tự đọc database hoặc gọi trực tiếp Binance. Điều này giúp code strategy dễ test và không phụ thuộc hạ tầng.

Phiên bản hiện tại có năm strategy đơn: ma_crossover, bollinger_bands, rsi_threshold, smc_structure và news_sentiment. Mỗi strategy có metadata và parameter schema để UI có thể hiển thị và cấu hình động.

Ngoài strategy đơn, CompositeStrategy kết hợp từ 2 đến 5 strategy con theo majority hoặc weighted policy. StrategyRegistry chịu trách nhiệm dynamic loading. Khi thêm file Python hợp lệ, registry có thể phát hiện và đăng ký strategy mới mà không sửa core.

## Slide 16/31 - 15. UML Class Diagram: Search Algorithm & Discovery Loop

Discovery Loop giải quyết bài toán không gian tham số rất lớn. Thay vì người dùng thử từng config thủ công, hệ thống dùng contract ISearchAlgorithm với method sample(space, rng) để sinh candidate.

Nhờ contract này, hệ thống có thể thay thuật toán tìm kiếm. RandomSearch dùng làm baseline, GeneticAlgorithm dùng mutation và crossover, BayesianOptimization tận dụng kết quả trước để chọn vùng tham số có tiềm năng. Strategy Engine không cần biết candidate được sinh bằng thuật toán nào.

Để chống overfitting, dữ liệu được chia thành Train, Validation và Sealed Test. Train dùng để search, Validation dùng làm gate kiểm tra generalization, còn Sealed Test là benchmark cuối cùng cho leaderboard. Candidate không được dùng kết quả Sealed Test để điều chỉnh tham số.

DiscoveryTrialReservation, ví dụ reserved_jobs=4, giúp search loop không chiếm toàn bộ worker pool và vẫn giữ fair scheduling cho tác vụ khác.

## Slide 17/31 - 16. UML Class Diagram: Resilient News Crawler Model

News Crawler được thiết kế theo provider contract. NewsProvider có thể được hiện thực bởi RssNewsProvider hoặc HtmlNewsProvider, và mỗi nguồn phải đi qua ApprovedSource.

Trước khi fetch, hệ thống dùng Resolver và Fetcher để validate DNS, chặn private IP, chặn redirect nguy hiểm và giảm rủi ro SSRF. Sau khi lấy nội dung, Quality Gate kiểm tra dữ liệu trích xuất có đủ chất lượng hay không.

Nếu DOM thay đổi hoặc parser thường không lấy được nội dung, pipeline có thể chuyển sang LLM fallback thông qua NewsExtractionHTTPAdapter. Tuy nhiên sentiment scoring được tách async, nên nếu AI lỗi hoặc rate limit, crawl pipeline không bị block hoàn toàn.

Điểm chính là nguồn news có thể thêm bớt bằng cấu hình/provider, còn LLM model cũng có thể thay qua adapter thay vì sửa domain logic.

## Slide 18/31 - 17. High-Level Architecture: Modular Monolith

Ở high-level architecture, em chọn hướng modular monolith. Nghĩa là hệ thống vẫn triển khai tương đối gọn, nhưng bên trong có module boundary rõ ràng.

Frontend là Next.js, dùng React SPA và event streaming để hiển thị chart, telemetry và trạng thái job realtime. Go API Gateway xử lý CQRS, RBAC, rate limiting, Binance WSS ingestion và broadcaster. Python backend tập trung vào strategy plugin architecture, event-driven job queue và backtest worker pool.

PostgreSQL là source of truth cho candles, experiments, strategies, jobs, results và news. Go API có thêm in-memory ring buffer để fan-out realtime hiệu quả hơn.

Lựa chọn modular monolith giúp giảm overhead vận hành so với microservices, nhưng vẫn giữ codebase đủ tách bạch để sau này tách service nếu cần.

## Slide 19/31 - 18. Các Design & Architectural Patterns Trọng Yếu

Có bốn pattern chính trong hệ thống.

Thứ nhất là CQRS ở Go API: command như tạo experiment được tách khỏi query như đọc candles hay leaderboard. Điều này giúp tối ưu latency và ownership rõ hơn.

Thứ hai là dual-channel market engine with parity. Cùng schema và cùng normalization được dùng cho WSS realtime và REST historical backfill, tránh việc dữ liệu live và dữ liệu backtest lệch nhau.

Thứ ba là Transactional Outbox. Khi tạo experiment, metadata và job event được ghi trong cùng một transaction, tránh dual-write risk, tức là tránh trường hợp database đã ghi nhưng queue chưa nhận job hoặc ngược lại.

Thứ tư là Plugin Architecture. Core engine không phụ thuộc trực tiếp vào logic của từng strategy hoặc search algorithm, giúp hệ thống dễ mở rộng theo Open-Closed Principle.

## Slide 20/31 - 19. Nền Tảng Multi-Agent & Vòng Lặp AI Tự Chủ

Phần multi-agent gồm nhiều vai trò. Strategy Designer Agent nhận natural language prompt hoặc URL và tạo draft spec dạng JSON. Implementation Agent chuyển draft đó thành Python code tuân thủ IStrategy protocol.

Sau khi có code, hệ thống không chạy ngay. Code phải đi qua self-repair loop gồm AST validation và sandbox dry-run. Nếu có lỗi syntax hoặc runtime traceback, thông tin lỗi được gửi lại LLM để sửa tối đa một số vòng nhất định, ví dụ 3 retry cycles.

Ngoài ra còn có Candidate Discovery và Crawling Agent để tự động sinh hyperparameter và crawl tin tức nhiều nguồn.

Ý tưởng chính là AI được dùng như một thành phần hỗ trợ tự động hóa, nhưng vẫn bị ràng buộc bởi contract, sandbox, validation và approval boundary. Nhờ vậy hệ thống tận dụng AI mà không giao toàn quyền cho AI.

## Slide 21/31 - 20. Runtime Flow: Realtime Ingestion & Gap Backfill

Luồng realtime ingestion bắt đầu khi chart khởi tạo. Hệ thống fetch khoảng 1,000 historical candles từ PostgreSQL hoặc Binance REST theo timeframe như 1m, 5m, 1h và 1d.

Sau đó WSS stream bắt đầu nhận ticker và cập nhật provisional candle theo realtime tick. Khi candle đóng, hệ thống persist candle vào PostgreSQL và broadcast event CandleClosed qua SSE hoặc WebSocket broadcaster.

Nếu WebSocket bị drop, gateway tự reconnect và trigger REST backfill để bù các candle bị thiếu. Vì candle được deduplicate bằng open time, hệ thống tránh ghi trùng khi dữ liệu vừa đến từ stream vừa đến từ backfill.

Điểm quan trọng là realtime flow không chỉ phục vụ chart. Nó còn tạo nền dữ liệu sạch cho strategy execution và backtest sau này.

## Slide 22/31 - 21. Runtime Flow: Strategy Execution & Dynamic Registration

Khi strategy chạy, hệ thống tạo StrategyContext từ datafeed và sentiment window. Sau đó gọi IStrategy.evaluate để sinh signal BUY, SELL hoặc HOLD. Nếu là composite strategy, CompositeStrategy aggregate tín hiệu theo majority hoặc weighted policy.

Luồng thêm strategy có hai nguồn. Với strategy viết tay, developer thêm Python file vào registry, hệ thống kiểm tra metadata và dynamic load. Với strategy do AI sinh, LLM tạo code nhưng code phải đi qua AST validator và sandbox trước khi được đăng ký.

Điểm em muốn nhấn mạnh là runtime parity. Live Trading và Backtest phải gọi cùng StrategyRuntime, cùng rule signal và cùng assumption execution. Nếu backtest và live chạy hai logic khác nhau, kết quả leaderboard sẽ không còn đáng tin.

Nhờ thiết kế này, hệ thống có thể thêm strategy nhanh, nhưng vẫn kiểm soát được an toàn và tính nhất quán.

## Slide 23/31 - 22. Runtime Flow: Async Backtest Pipeline

Backtest pipeline bắt đầu bằng việc tạo experiment. API ghi experiment metadata và job event vào Outbox trong cùng một ACID transaction. Nếu transaction fail, không có job mồ côi.

Worker claim job bằng FOR UPDATE SKIP LOCKED và duy trì heartbeat trong lúc chạy. Nếu worker crash, lease hết hạn và worker khác có thể takeover.

Engine sau đó replay immutable Candle và BBO theo thứ tự thời gian. Strategy nhận từng context và sinh signal. Execution simulator xử lý fill, fee và slippage, rồi ghi trade facts.

Pipeline chạy theo Train 30 ngày, Validation 15 ngày và Sealed Test 15 ngày. Sau cùng evaluator tính Sharpe Ratio, Max Drawdown, Profit Factor, persist trade logs và cập nhật Top-K Leaderboard.

Vì job, facts và completion event có idempotency, retry không tạo duplicate result. Đây là điểm biến backtest từ một phép tính cục bộ thành một pipeline async có thể scale.

## Slide 24/31 - 23. Runtime Flow: Resilient News Crawl & LLM Fallback Pipeline

Luồng news crawl bắt đầu bằng SSRF validation. Nguồn phải nằm trong ApprovedSource, DNS được resolve an toàn và các private IP hoặc cloud metadata endpoint bị chặn.

Sau đó hệ thống fetch nội dung và thử extraction bằng RSS hoặc HTML parser như Readability. Nếu Quality Gate phát hiện DOM thay đổi, text rỗng hoặc nội dung không đủ chất lượng, pipeline sẽ trigger LLM fallback để parse raw HTML thành structured content.

Sau khi có article content, sentiment scoring chạy async ở background. Điểm sentiment được chuẩn hóa trong khoảng -1.0 đến 1.0 và persist vào PostgreSQL.

Thiết kế này cho phép crawler dùng dữ liệu thật từ website/RSS, thêm bớt nguồn dễ hơn, và LLM chỉ là adapter có thể thay provider hoặc model khi cần. Nếu LLM lỗi, hệ thống vẫn có thể lưu article và retry phần analysis sau.

## Slide 25/31 - 24. Security Architecture: Defense-in-Depth

Security được thiết kế theo defense-in-depth, tức là nhiều lớp bảo vệ chồng lên nhau.

Lớp đầu là authentication và RBAC. Người dùng đăng nhập bằng JWT, role quyết định quyền truy cập, và experiment được cô lập theo tenant hoặc user ownership.

Lớp thứ hai là crawler SSRF prevention. Vì hệ thống cho phép crawl URL bên ngoài, nó phải chặn private IP range như 127.0.0.1, 10.0.0.0/8, cloud metadata và chỉ cho phép domain trong ApprovedSource.

Lớp thứ ba là AST sandbox cho AI-generated code. Những builtin hoặc module nguy hiểm như eval, subprocess, socket hoặc os.system bị chặn trước khi chạy.

Lớp cuối là tool invocation boundary. AI agent chỉ giao tiếp qua DTO/schema được validate, giảm rủi ro input tùy ý gây lỗi hoặc vượt quyền.

## Slide 26/31 - 25. Scalability Architecture & Benchmark

Về scalability, hệ thống dùng stateless horizontal scale-out cho Python Worker. Khi queue backlog tăng, có thể tăng số worker độc lập. Công việc được chia qua PostgreSQL B-Tree indexed leased job queue.

Benchmark trên slide là mốc đo thực tế ngày 2026-09-03 trong phạm vi isolated PostgreSQL benchmark. Với 100,000 jobs, 4 workers và mỗi job 50 candles, hệ thống hoàn tất 100%, không failed và không cancelled.

Tổng thời gian là khoảng 1,519.209 giây, tức khoảng 25 phút 19 giây. Throughput đạt 65.824 jobs mỗi giây, khoảng 3,949 jobs mỗi phút. Queue-to-persisted-result latency theo cách ghi trên slide là p50 khoảng 746.604 ms, tương đương 12 phút 27 giây, và p95 khoảng 1.438.430 ms, gần 23 phút 58 giây.

Benchmark cũng ghi 4,700,000 signals và 15,000,000 equity points. Phạm vi đo là PostgreSQL queue đến Python worker, deterministic engine và persisted facts, chưa bao gồm Go/API/event evaluation. Các mốc 8 và 16 workers chưa đo nên không suy diễn.

## Slide 27/31 - 26. Fault Tolerance & Self-Healing Architecture

Fault tolerance tập trung vào bốn cơ chế.

Cơ chế đầu tiên là worker lease takeover và heartbeat. Worker gửi heartbeat mỗi 10 giây. Nếu worker crash, lease timeout sau 30 giây và worker khác tự nhận lại job.

Cơ chế thứ hai là idempotency và retry. Unique idempotency_key giúp retry không tạo duplicate execution hoặc duplicate result.

Cơ chế thứ ba là failure isolation. Nếu một strategy plugin lỗi, lỗi đó được cô lập ở job hoặc strategy instance, không làm crash toàn bộ API. Nếu WSS mất kết nối, gateway reconnect và backfill.

Cơ chế thứ tư là chaos simulation. Hệ thống có thể được kiểm tra bằng cách kill worker process hoặc inject network drop để xác minh hành vi tự phục hồi.

Như vậy self-healing không phải chỉ là retry đơn giản, mà là sự kết hợp giữa lease, heartbeat, idempotency và isolation.

## Slide 28/31 - 27. Deployment Topology & MLOps Infrastructure

Deployment topology hiện tại dựa trên Docker Compose nhưng có hướng sẵn sàng cho Kubernetes.

Các service chính gồm Next.js Web Dashboard, Go Edge Gateway, Python Research API, Python Research Worker theo N instance, Internal AI Inference Adapter và PostgreSQL. Mỗi service có boundary riêng, nên có thể scale phần worker mà không cần scale toàn bộ hệ thống.

Health check dùng các endpoint như /healthz và /readyz để container auto-restart và routing traffic an toàn hơn.

Về MLOps và cấu hình, system prompt, LLM API key và các thông số môi trường được tách qua .env. Điều này giúp đổi model hoặc provider mà không sửa code nghiệp vụ.

Khi lên production, kiến trúc có thể chuyển sang Kubernetes với Deployment replicas, rolling update và Horizontal Pod Autoscaling nếu workload tăng.

## Slide 29/31 - 28. Architectural Tradeoffs Matrix

Slide này tổng hợp các tradeoff lớn.

Với system architecture, em chọn modular monolith thay vì microservices để giảm overhead vận hành, giảm distributed latency và vẫn enforce boundary qua contract.

Với candle và job storage, em chọn PostgreSQL + B-Tree thay vì ClickHouse hoặc InfluxDB. Lý do là hệ thống cần ACID cho experiment và outbox, trong khi B-Tree index vẫn đủ cho quy mô hiện tại.

Với job queue và event ingress, em chọn PostgreSQL Outbox & Leases thay vì Kafka, RabbitMQ hoặc Redis. Lợi ích là tránh dual-write và không thêm infrastructure dependency.

Với AI code execution, em chọn AST Analyzer + Sandbox thay vì Docker-in-Docker để giảm latency và overhead. Với sentiment analysis, em chọn hybrid rule + LLM batch thay vì pure LLM realtime để giảm token cost và tránh block crawler.

## Slide 30/31 - 29. Replaceability & Extensibility Architecture

Replaceability là một mục tiêu quan trọng vì hệ thống crypto rất dễ thay đổi vendor và nguồn dữ liệu.

Ở market data, MarketProviderAdapter cho phép thay Binance bằng OKX, Bybit hoặc Coinbase mà không cần thay đổi core frontend hay strategy engine. Phần thay đổi nằm ở adapter, còn normalized Candle/BBO contract giữ nguyên.

Ở discovery, ISearchAlgorithm cho phép thêm thuật toán mới như PPO hoặc custom optimizer. Search loop chỉ cần gọi contract sample và không phụ thuộc thuật toán cụ thể.

Ở news ingestion, có thể thêm nguồn như CryptoPanic hoặc CoinDesk API thông qua ApprovedSource hoặc provider mới. Phần sentiment cũng được tách qua ModelGatewayPort, nên có thể thay OpenAI, Groq hoặc local model mà không chạm vào crawler domain.

Điểm chính là kiến trúc ưu tiên interface ổn định, còn vendor cụ thể nằm ở adapter.

## Slide 31/31 - 30. Architectural Summary & Project Conclusion

Để kết luận, CryptoBot được thiết kế theo hướng ASR-driven architecture. Bốn driver chính là realtime ingestion, modifiability, massive search scalability và unstructured news intelligence.

Hệ thống tránh God Service bằng cách chia thành 6 bounded context: Market Realtime, Strategy Engine, Backtest, Discovery, News Crawler và News Intelligence. Các phần giao tiếp qua contract, DTO versioned và outbox event.

Phần AI được dùng để hỗ trợ strategy generation, self-repair, crawling và sentiment analysis, nhưng vẫn nằm trong boundary có kiểm soát như AST validation, sandbox, prompt versioning và schema validation.

Về scalability và reliability, hệ thống hỗ trợ worker scale-out, leased job queue, heartbeat, idempotency và gap backfill. Benchmark 100,000 backtests cho thấy pipeline có thể xử lý workload lớn trong phạm vi đã đo.

Cuối cùng, artifact của dự án gồm 39 blueprint diagrams/specs, 5 dashboard tương tác, automated test scenarios và benchmark suite. Em xin cảm ơn Thầy và các bạn đã lắng nghe. Em sẵn sàng trả lời câu hỏi.

## Bản Rút Gọn Khi Thiếu Thời Gian

CryptoBot là nền tảng research và đánh giá trading strategy cho crypto futures. Kiến trúc được dẫn dắt bởi bốn ASR: realtime market ingestion, modifiability, massive search scalability và news intelligence.

Hệ thống chia thành Next.js Dashboard, Go Edge Gateway, Python Research API/Worker và PostgreSQL. Go xử lý realtime market, API edge và fan-out. Python xử lý strategy, backtest, discovery, news và AI agent.

Core được tách thành 6 module để tránh God Service. Strategy dùng IStrategy plugin contract, Discovery dùng ISearchAlgorithm và backtest chạy async qua Outbox, leased worker, heartbeat và idempotency. News pipeline crawl dữ liệu thật từ ApprovedSource, qua SSRF guard, Quality Gate và LLM sentiment scoring.

Kết quả là hệ thống dễ thêm strategy, dễ thay market/news/LLM provider, có thể scale worker, tự phục hồi khi worker hoặc WebSocket lỗi, và có benchmark 100,000 backtests để chứng minh năng lực xử lý.

## Câu Hỏi Dự Phòng

**Vì sao chọn Modular Monolith thay vì Microservices?**

Vì giai đoạn hiện tại cần giảm overhead vận hành và latency phân tán. Module boundary vẫn được enforce bằng contract và adapter, nên sau này có thể tách service khi workload đủ lớn.

**Vì sao không dùng Kafka ngay từ đầu?**

PostgreSQL Outbox & Leases đã đáp ứng nhu cầu hiện tại, giữ ACID với experiment/job và giảm dependency hạ tầng. Kafka có thể thêm sau nếu cần event throughput rất lớn.

**Làm sao tránh overfitting trong Discovery?**

Dữ liệu được chia Train, Validation và Sealed Test. Train dùng để search, Validation để gate, Sealed Test chỉ dùng benchmark cuối cùng và không dùng để điều chỉnh tham số.

**AI-generated strategy có được chạy trực tiếp không?**

Không. Code phải qua AST validation, sandbox dry-run và contract check trước khi registry cho phép load.

**Nếu worker crash giữa chừng thì sao?**

Heartbeat và lease timeout cho phép worker khác takeover job. Idempotency key giúp retry không ghi trùng kết quả.

**Nếu nguồn tin đổi HTML thì crawler xử lý thế nào?**

Parser thường chạy trước. Nếu Quality Gate fail, pipeline chuyển sang LLM fallback extraction. Sentiment scoring chạy async nên lỗi LLM không làm block toàn bộ crawler.
