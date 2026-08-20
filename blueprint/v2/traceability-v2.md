# Target V2 — Requirement Traceability and Verification Gates

Tài liệu này nối yêu cầu cập nhật của giảng viên với sơ đồ V2 và bằng chứng cần
có trước khi nhóm được phép nói implementation đã hoàn thành. Sơ đồ chỉ là
design evidence; không thay thế test/demo/benchmark.

| # | Requirement/invariant | Diagram V2 | Evidence bắt buộc sau implementation |
|---|---|---|---|
| 1 | Thêm strategy không sửa core branching | 03, 07, 08 | Architecture test cấm `if/switch` theo strategy ID; add-one-plugin/spec diff |
| 2 | Nhập text/URL thành strategy an toàn | 01, 07, 22 | Invalid/prompt-injection/SSRF tests; preview + explicit approval audit |
| 3 | Đổi search generator không ảnh hưởng execution | 03, 09 | Contract tests chạy cùng candidate qua ≥2 generator; core diff = 0 |
| 4 | Thêm provider không đổi frontend/domain | 05, 06 | Binance/OKX adapter contract tests trả cùng CandleV2/BBOEventV2 |
| 5 | Realtime WSS reconnect/backfill không mất dữ liệu | 05, 06 | Disconnect test; checkpoint/backfill; zero missing/duplicate closed candles |
| 6 | LONG và SHORT được mô phỏng đúng | 10, 18, 21 | Hand-calculated fixtures cho open/close/reverse LONG và SHORT |
| 7 | Trade output đủ trường và cost breakdown | 10, 11, 12 | API/schema/UI tests cho pair/time/side/notional/SL/TP/fee/spread/slippage/PnL |
| 8 | BBO quyết định fill; fallback tường minh | 05, 10, 12, 17, 18 | BBO replay fixtures; BUY=ask/SELL=bid; no-look-ahead; fallback provenance |
| 9 | RSS/HTML extract + LLM tags được lưu và tái sử dụng | 13, 22 | Content-hash cache test; model/prompt version; model-down leaves null sentiment |
| 10 | 100k/retry/dedup/order/provenance được chứng minh | 11, 14–19 | Load benchmark, crash/takeover, duplicate delivery, sequence gap, rerun hash test |

## Cross-diagram invariants

1. Browser chỉ giao tiếp với Go Edge; Python không mở public browser API.
2. Go không thực thi strategy; Python StrategyRuntime là nguồn semantics duy nhất.
3. Realtime và backtest resolve cùng exact StrategySpec/version/fingerprint.
4. Backtest chỉ đọc immutable Candle/BBO snapshot, không đọc operational cache.
5. Mọi fill BUY dùng ask, SELL dùng bid; candle fallback phải có cờ provenance.
6. Candidate, experiment snapshot, job và outbox event được tạo atomically.
7. Job/event delivery là at-least-once; logical side effect phải idempotent.
8. Event ordering chỉ được hứa theo aggregate sequence, không hứa global order.
9. LLM output không phải executable code; chỉ declarative DSL đã validate/approve.
10. Target scale chỉ được công bố khi benchmark/metric chứng minh.

