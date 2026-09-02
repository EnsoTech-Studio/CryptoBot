# Speaker Notes — Strategy Engine, Discovery Loop & Backtest

Phạm vi: bắt đầu từ Slide 13, đi qua Strategy Engine, Discovery Loop và Async Backtest Pipeline.
Thời lượng gợi ý: 6–8 phút.

## Slide 13 — Component Specs: Strategy Engine, Backtest, Discovery

“Từ đây, em đi vào ba thành phần trung tâm của Crypto Strategy Lab: Strategy Engine, Backtest và Discovery.

Strategy Engine chịu trách nhiệm biến dữ liệu thị trường thành tín hiệu giao dịch. Backtest dùng lại chính runtime này để replay dữ liệu lịch sử và đo kết quả. Discovery đứng ở phía trên, tự sinh nhiều biến thể strategy, gửi từng biến thể xuống Backtest, sau đó đánh giá và xếp hạng.

Điểm quan trọng là ba thành phần này không chạy như một khối lớn. Mỗi thành phần có trách nhiệm riêng và giao tiếp qua các DTO có version cùng Outbox event. Nhờ vậy, thay đổi thuật toán tìm kiếm không làm thay đổi logic thực thi strategy; thay đổi cách tính metric cũng không làm hỏng API phía ngoài.”

“Trong phần tiếp theo, em tập trung trước vào Strategy Engine — nơi định nghĩa hợp đồng chung cho mọi strategy.”

## Slide 14 — UML Class Diagram: Strategy Plugin Model

“Trung tâm của Strategy Engine là contract `IStrategy`. Mỗi strategy chỉ cần triển khai `evaluate(context)` và trả về một trong ba tín hiệu: `BUY`, `SELL` hoặc `HOLD`.

`context` chứa những dữ liệu strategy được phép sử dụng, ví dụ candle history, indicator values, BBO và sentiment window. Strategy không tự đọc database hay tự gọi Binance. Cách giới hạn này giúp logic dễ kiểm thử và tránh phụ thuộc hạ tầng.

Trong phiên bản đầu, registry có năm strategy đơn: moving-average crossover, Bollinger Bands, RSI threshold, SMC structure và news sentiment. Mỗi strategy có metadata và parameter schema, nên UI có thể hiển thị, chọn và cấu hình mà không cần sửa Core.”

“Ngoài strategy đơn, hệ thống hỗ trợ composite strategy. Composite nhận từ hai đến năm strategy con, sau đó kết hợp tín hiệu bằng `majority` hoặc `weighted`. Với `weighted`, mỗi strategy có trọng số; hệ thống normalize trọng số trước khi tính tín hiệu cuối.”

“`StrategyRegistry` chịu trách nhiệm dynamic loading. Khi thêm một file strategy hợp lệ, registry phát hiện và đăng ký strategy mới. Đây là cách áp dụng Open–Closed Principle: mở rộng bằng plugin, không sửa một God Service trung tâm.”

## Slide 21 — Runtime Flow: Strategy Execution & Dynamic Registration

“Slide này mô tả lúc strategy thực sự chạy.

Đầu tiên, hệ thống tạo `StrategyContext` từ datafeed và sentiment window. Sau đó gọi `IStrategy.evaluate()`. Strategy trả về tín hiệu đơn; nếu là composite, `CompositeStrategy` aggregate các tín hiệu theo policy đã chọn.

Luồng thêm strategy có hai nguồn. Với strategy viết tay, developer đưa module Python vào registry, hệ thống kiểm tra metadata và dynamic load. Với strategy do AI tạo, LLM chỉ tạo bản nháp hoặc source code; trước khi chạy, code phải qua AST validation và sandbox. Những import, builtin hoặc thao tác nguy hiểm như `eval`, `subprocess`, `socket` đều bị chặn theo policy.

Invariant quan trọng nhất ở đây là runtime parity. Live execution và Backtest phải gọi cùng `StrategyRuntime`, cùng rule signal và cùng execution assumptions. Nếu hai môi trường dùng hai cách tính khác nhau, leaderboard sẽ không còn đáng tin.”

“Sau khi có signal, phần tiếp theo là mô phỏng việc khớp lệnh và đo hiệu quả. Đó là nhiệm vụ của Backtest Pipeline.”

## Slide 15 — UML Class Diagram: Search Algorithm & Discovery Loop

“Discovery Loop giải quyết vấn đề không gian tham số rất lớn. Thay vì người dùng thử từng cấu hình bằng tay, hệ thống dùng contract `ISearchAlgorithm` với method `sample(space, rng)` để sinh candidate.

Contract này cho phép thay thế thuật toán: `RandomSearch` phù hợp làm baseline, `GeneticAlgorithm` khai thác mutation và crossover, còn `BayesianOptimization` dùng kết quả trước đó để chọn vùng có tiềm năng. Strategy Engine không cần biết candidate được sinh bằng cách nào.”

“Điểm bảo vệ quan trọng nhất là chia dữ liệu thành ba phần.

Train gồm 30 ngày, dùng để search và tối ưu biến thể. Validation gồm 15 ngày, dùng làm gate kiểm tra khả năng tổng quát hóa. Chỉ candidate vượt gate mới được chạy trên Sealed Test 15 ngày. Sealed Test không được dùng để điều chỉnh tham số; kết quả ở đây mới được dùng làm benchmark công bằng cho Leaderboard.

Nếu dùng toàn bộ dữ liệu để chọn candidate, hệ thống dễ chọn một strategy chỉ nhớ quá khứ. Ba split này giảm data leakage và làm rõ lineage: candidate nào, config nào, dataset snapshot nào tạo ra kết quả nào.”

“Discovery cũng không được phép chiếm hết tài nguyên worker. `DiscoveryTrialReservation`, ví dụ `reserved_jobs=4`, giới hạn số trial đồng thời và giữ fair scheduling cho các request khác. UI nhận trạng thái bất đồng bộ, nên search hàng nghìn candidate không khóa giao diện.”

## Slide 22 — Runtime Flow: Async Backtest Pipeline

“Đây là luồng thực thi một experiment, bao gồm cả trial do Discovery tạo.

Bước một, API tạo experiment và ghi metadata cùng job event vào Outbox trong cùng một ACID transaction. Nếu transaction thất bại, không có job mồ côi.

Bước hai, worker claim job bằng optimistic locking với `FOR UPDATE SKIP LOCKED`. Worker gửi heartbeat trong lúc chạy. Nếu worker crash, lease hết hạn và worker khác có thể takeover; không cần giữ request HTTP mở trong suốt backtest.

Bước ba, engine replay immutable Candle và BBO theo thứ tự thời gian. Strategy nhận từng context và sinh signal. Execution simulator xử lý fill, fee và slippage, sau đó ghi trade facts. Dùng BBO giúp mô phỏng giá khớp sát hơn so với giả định luôn khớp tại candle close.

Bước bốn, hệ thống chạy lần lượt Train, Validation và Sealed Test theo policy của experiment. Sau cùng, evaluator tính Sharpe Ratio, Max Drawdown, Profit Factor và các metric liên quan. Trade logs, config hash, dataset snapshot và result hash được lưu để truy xuất nguồn gốc; kết quả phù hợp mới được đưa vào Top-K Leaderboard.

Vì job, trade facts và completion event có tính idempotent, retry không tạo duplicate execution. Đây là phần biến Backtest từ một phép tính cục bộ thành pipeline có thể scale và quan sát được.”

## Transition / Closing

“Tóm lại, Strategy Engine cung cấp runtime plugin có contract rõ ràng. Discovery Loop dùng runtime đó để tìm kiếm có kiểm soát, đồng thời bảo vệ khỏi overfitting bằng Train, Validation và Sealed Test. Backtest Pipeline thực thi bất đồng bộ trên dữ liệu immutable, mô phỏng execution thực tế và lưu đầy đủ provenance.

Ba quyết định này liên kết trực tiếp với ba quality attributes của hệ thống: modifiability, scalability và reproducibility.”

## Short version if time is limited

“Strategy Engine chuẩn hóa mọi strategy qua `IStrategy`, hỗ trợ plugin động và composite strategy. Discovery dùng `ISearchAlgorithm` để sinh candidate, đánh giá theo Train–Validation–Sealed Test nhằm giảm overfitting. Mỗi candidate chạy qua Backtest Worker, replay Candle+BBO bằng cùng `StrategyRuntime`, mô phỏng fee/slippage, tính metric và cập nhật leaderboard. Nhờ Outbox, lease, heartbeat và idempotency, toàn bộ luồng vừa bất đồng bộ vừa có thể retry và scale-out.”

## Likely questions

- **Vì sao cần cả Train, Validation và Sealed Test?**  
  Train để tối ưu, Validation để gate, Sealed Test để benchmark cuối cùng. Không dùng Sealed Test để chọn tham số.

- **Vì sao Backtest phải dùng cùng runtime với Live?**  
  Để tránh parity mismatch: strategy có kết quả tốt trên Backtest nhưng chạy khác khi live.

- **AI-generated strategy có chạy trực tiếp không?**  
  Không. Code phải qua AST validation, sandbox và các contract kiểm tra trước khi registry cho phép load.

- **Worker crash giữa chừng xử lý thế nào?**  
  Heartbeat và lease timeout cho phép worker khác takeover; idempotency key ngăn ghi kết quả trùng.
