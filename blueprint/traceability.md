# Requirement Traceability and Verification Gates

Tài liệu này nối yêu cầu đích của blueprint với sơ đồ trong `assets/diagrams/`
(24 hình, đánh số thống nhất) và bằng chứng cần có trước khi nhóm được phép nói
implementation đã hoàn thành. Sơ đồ chỉ là design evidence; không thay thế
test/demo/benchmark. Bất biến xuyên sơ đồ nằm ở `design.md` §12.4.

| # | Requirement/invariant | Diagram | Evidence bắt buộc sau implementation |
|---|---|---|---|
| 1 | Thêm strategy không sửa core branching | 03, 21, 22 | Architecture test cấm `if/switch` theo strategy ID; add-one-plugin/spec diff |
| 2 | Nhập text/URL thành strategy an toàn | 01, 21, 14 | Invalid/prompt-injection/SSRF tests; preview + explicit approval audit |
| 3 | Đổi search generator không ảnh hưởng execution | 03, 11 | Contract tests chạy cùng candidate qua ≥2 generator; core diff = 0 |
| 4 | Thêm provider không đổi frontend/domain | 05, 20 | Binance/OKX adapter contract tests trả cùng Candle/BBO chuẩn hoá |
| 5 | Realtime WSS reconnect/backfill không mất dữ liệu | 05, 20 | Disconnect test; checkpoint/backfill; zero missing/duplicate closed candles |
| 6 | LONG và SHORT được mô phỏng đúng | 23, 17, 19 | Hand-calculated fixtures cho open/close/reverse LONG và SHORT |
| 7 | Trade output đủ trường và cost breakdown | 23, 24, 06 | API/schema/UI tests cho pair/time/side/notional/SL/TP/fee/spread/slippage/PnL |
| 8 | BBO quyết định fill; fallback tường minh | 05, 23, 06, 16, 17 | BBO replay fixtures; BUY=ask/SELL=bid; no-look-ahead; fallback provenance |
| 9 | RSS/HTML extract + LLM tags được lưu và tái sử dụng | 13, 14 | Content-hash cache test; model/prompt version; model-down leaves null sentiment |
| 10 | 100k/retry/dedup/order/provenance được chứng minh | 24, 07, 08, 15–19 | Load benchmark, crash/takeover, duplicate delivery, sequence gap, rerun hash test |

Số hiệu sơ đồ ở cột "Diagram" là slug trong `assets/diagrams/` — ví dụ `23` tương
ứng `23-bbo-long-short-execution`. Bản đồ "yêu cầu → spec chi tiết" của đề bài gốc
nằm ở `design.md` §12.3; các gap-derived epic tương ứng nằm trong `jira-backlog.md`.
