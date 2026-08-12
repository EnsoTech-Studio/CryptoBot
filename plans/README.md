# ⚠️ ARCHIVED — Không dùng thư mục này nữa

> **Thư mục `plans/` đã bị thay thế hoàn toàn bởi [`blueprint/`](../blueprint/README.md).**
>
> Đây là bản nháp kiến trúc **đầu tiên**, viết bằng tiếng Anh, **chưa được xác thực** với đề bài và code thật. Nó được giữ lại chỉ để tra cứu lịch sử quyết định. **Không sửa file nào trong đây**, và **không** dùng nó làm nguồn cho báo cáo hay khi implement.

## Dùng gì thay thế

| Cần gì | Đọc ở đâu |
| ------ | --------- |
| Vấn đề, mục tiêu định lượng, phạm vi, rủi ro, tiêu chí thành công | [`blueprint/proposal.md`](../blueprint/proposal.md) |
| Kiến trúc, C4, DDL, contract, luồng nghiệp vụ, ADR, 8 câu hỏi §40 | [`blueprint/design.md`](../blueprint/design.md) |
| Đặc tả chi tiết 14 tính năng | [`blueprint/specs/`](../blueprint/specs/) |
| Sơ đồ render sẵn (SVG + PNG) | [`blueprint/assets/`](../blueprint/assets/README.md) |
| Index + mapping yêu cầu đề bài → tài liệu | [`blueprint/README.md`](../blueprint/README.md) |

## Vì sao thay thế, không sửa tiếp

`plans/` đúng về hướng lớn nhưng để mở hoặc chưa xác thực nhiều quyết định mà `blueprint/` đã chốt kèm lý do và cách kiểm chứng:

| Vấn đề | `plans/` | `blueprint/` |
| ------ | -------- | ------------ |
| Job queue | "thêm queue khi workload cần" | `backtest_jobs` + `FOR UPDATE SKIP LOCKED` + `lease_token` + heartbeat, kèm điều kiện đo được để đổi sang broker (ADR-005, §8.3.1) |
| Backtest sync/async | "chạy inline nếu nhỏ, promote lên worker sau" | **Luôn** `202 + run_id`, không có fast path — hai code path là hai chỗ lệch nhau (ADR-006) |
| Event delivery | "in-process dispatcher, tách sau nếu cần" | In-process **không** giao được cross-process; worker là process riêng từ đầu → transactional outbox trên `domain_events` (§5.7) |
| Strategy versioning | "không ghi đè version" (quy ước) | `code_fingerprint` — sửa code quên bump version thì **fail startup** (ADR-009) |
| Dataset identity | `dataset_version` dạng string | Thêm `content_hash` — phát hiện Binance revise nến (§4.2) |
| Leaderboard | chưa quyết lưu trực tiếp hay tính từ evaluation | Append-only tham chiếu `evaluation_id`, có `market_dataset_id` và `score_policy_version` (ADR-012) |
| Chống look-ahead | fill policy + "indicator chỉ đọc nến ≤ t" | **3 tầng**: `candles[:t+1]`, `IndicatorView` causal, fill policy (§5.2.1) |
| Sandbox plugin | không nêu | 3 tầng `SIGALRM` → `SIGKILL` child → job lease, kèm mô hình tin cậy rõ ràng |
| Stop Loss / Take Profit | không nêu | Chốt là **MVP** với `intrabar_priority` tường minh (ADR-017) |
| Auth | OIDC Authorization Code + PKCE | JWT RS256 + refresh rotation tự quản — OIDC cần identity provider ngoài, ngoài phạm vi đồ án |
| Ngôn ngữ | tiếng Anh | tiếng Việt, khớp ngôn ngữ báo cáo |

## Nội dung gốc (để tra cứu)

Sáu file dưới đây là bản nháp ban đầu:

1. `01-requirements-and-scope.md` — yêu cầu, ranh giới MVP, acceptance criteria
2. `02-target-architecture.md` — C4-style context, container, module, extension seam
3. `03-domain-contracts.md` — ubiquitous language, interface, API shape, versioning
4. `04-runtime-flows.md` — realtime, backtest/search, news/sentiment, failure matrix
5. `05-data-and-operational-design.md` — persistence, deployment, reliability, security, observability
6. `06-decisions-and-roadmap.md` — 7 ADR, delivery phase, demo, traceability
7. `architecture-overview.html` — bản HTML gấp/mở được

Mọi yêu cầu ở đây truy về `Crypto Strategy Lab – Đồ án cuối kỳ.pdf`.
