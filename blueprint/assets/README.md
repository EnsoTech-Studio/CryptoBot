# Visual assets — sơ đồ render sẵn

Thư mục này chứa **toàn bộ sơ đồ của blueprint đã render sẵn**, để tài liệu đọc được offline và export PDF được mà sơ đồ vẫn hiển thị. Không có URL ảnh ngoài: mọi file đều là asset local, và các SVG chỉ tham chiếu fragment nội bộ (`url(#...)`) cùng namespace W3C — không fetch font hay ảnh từ internet.

## Cấu trúc

```
assets/
├── README.md                 # File này
├── mermaid-config.json       # Theme + font + useMaxWidth cho mermaid-cli
├── puppeteer-config.json     # Cờ Chromium cho môi trường container
├── diagrams/                 # Mermaid source (.mmd) + SVG vector
│   ├── 01-c4-l1-system-context.mmd
│   ├── 01-c4-l1-system-context.svg
│   └── ...
└── diagrams-png/             # PNG raster, scale 2× (cho Word/PowerPoint/PDF)
    ├── 01-c4-l1-system-context.png
    └── ...
```

Giữ cả ba định dạng có lý do: `.mmd` là **nguồn** (sửa ở đây rồi render lại, không sửa SVG bằng tay); `.svg` cho web và cho PDF vector (zoom không mờ); `.png` cho công cụ không đọc SVG (Word, Google Docs, một số renderer Markdown).

## Danh mục sơ đồ

39 sơ đồ đánh số thống nhất. Cột "Gốc" cho biết nguồn của file `.mmd`: **doc** = trích
từ mermaid nhúng trong tài liệu (Markdown là nguồn sự thật); **target** = sơ đồ kiến trúc
đích của bộ thống nhất (`.mmd` chính là nguồn sự thật cho tới khi mermaid tương ứng được
nhúng vào tài liệu narrative).

| # | Slug | Nội dung | Gốc | Nguồn trong tài liệu | Góc nhìn kiến trúc bắt buộc |
| - | ---- | -------- | --- | -------------------- | --------------------------- |
| 01 | `01-c4-l1-system-context` | C4 Level 1 — actor + hệ thống ngoài | target | `design.md` §2.1 | **System Context** |
| 02 | `02-c4-l2-container` | C4 Level 2 — Go edge, Python platform, worker, `ai` | target | `design.md` §2.2 | **Container/Module decomposition** |
| 03 | `03-c4-l3-python-strategy-platform` | C4 Level 3 — Python platform theo ports/adapters | target | `design.md` §2.3 | **Component responsibilities** |
| 04 | `04-high-level-architecture` | HLA — pipeline toàn hệ thống | target | `design.md` §3 | **Container/HLA**, **Data Flow** |
| 05 | `05-market-realtime-candle-bbo` | Candle + BBO từ exchange tới UI/Python; WSS reconnect/backfill | target | `design.md` §3.2, §6.1 | **Data Flow**, **Realtime Flow** |
| 06 | `06-erd` | ERD — quan hệ dữ liệu đích | target | `design.md` §4.3 | **ERD** |
| 07 | `07-outbox-retry-order` | Outbox: retry, duplicate, ordering | target | `design.md` §5.7.5 | **Data Flow** |
| 08 | `08-outbox-event-state` | State machine của một event trong outbox | target | `design.md` §5.7.6 | **Data Flow** |
| 09 | `09-realtime-reconnect-backfill-flow` | Realtime Flow — disconnect → reconnect → backfill | doc | `design.md` §6.1 | **Realtime/Reconnect Flow** |
| 10 | `10-strategy-flow` | Strategy Flow — từ nến tới tín hiệu composite | doc | `design.md` §6.2 | **Strategy Flow** |
| 11 | `11-search-backtest-pipeline` | Generator registry → worker → rank; bounded loop | target | `design.md` §6.3 | **Search/Backtest Flow** |
| 12 | `12-search-run-state` | State machine của `search_runs` (pause/resume/cancel/stop) | target | `design.md` §6.3 | **Search/Backtest Flow** |
| 13 | `13-news-html-llm-pipeline` | RSS/HTML → extract → LLM tag → sentiment (owner Python platform) | target | `design.md` §6.4 · `specs/news.md` | **Data Flow** |
| 14 | `14-defense-in-depth` | Security + AI/plugin guardrails (SSRF, sandbox, human approval) | target | `design.md` §7.4 | Access control |
| 15 | `15-job-queue-scale` | Job queue: 1 worker → N worker → broker, cùng contract | target | `design.md` §8.3 | **Search/Backtest Flow**, scalability |
| 16 | `16-experiment-create-transaction` | Tạo experiment: snapshot + job trong một transaction | target | `specs/experiment.md` | **Search/Backtest Flow** |
| 17 | `17-python-worker-execution` | Worker: claim → heartbeat → execute → commit (lease, BBO snapshot) | target | `specs/experiment.md` | **Search/Backtest Flow** |
| 18 | `18-worker-lease-takeover` | Worker chết → lease hết hạn → take-over | target | `specs/experiment.md` | **Search/Backtest Flow** |
| 19 | `19-backtest-run-state` | State machine của `backtest_runs` | target | `specs/experiment.md` | **Search/Backtest Flow** |
| 20 | `20-market-provider-replaceability` | Thêm Binance/OKX qua registry; frontend không đổi | target | `design.md` §11.3 | Modifiability |
| 21 | `21-ai-strategy-authoring` | Text/URL → StrategySpec an toàn (AI, version, approval) | target | `specs/strategy-authoring.md` | **Strategy Flow** |
| 22 | `22-strategy-runtime-parity` | Một runtime cho realtime/backtest — không hai nguồn chân lý | target | `design.md` §6.2 | **Strategy Flow** |
| 23 | `23-bbo-long-short-execution` | Mô phỏng LONG/SHORT bằng BBO (fee, spread, slippage, SL/TP) | target | `specs/backtest.md` | **Search/Backtest Flow** |
| 24 | `24-trade-result-provenance` | Trade detail và provenance chain đầy đủ | target | `specs/leaderboard.md` | **Search/Backtest Flow** |
| 25 | `25-agent-platform-components` | Agent Platform: control plane, 6 role, tool/service/state/approval | target | `specs/agent-architecture.md` | **Agent Architecture** |
| 26 | `26-agent-run-state-machine` | Durable authoring/repair/review/publish state machine | target | `specs/agent-architecture.md` | **Agent Architecture** |
| 27 | `27-strategy-designer-agent` | Designer Agent và typed tools | target | `specs/agent-architecture.md` | **Agent Architecture** |
| 28 | `28-strategy-implementation-agent` | Implementation Agent: compiler, policy, sandbox, review | target | `specs/agent-architecture.md` | **Agent Architecture** |
| 29 | `29-strategy-repair-agent` | Repair Agent: evidence, bounded patch và retest | target | `specs/agent-architecture.md` | **Agent Architecture** |
| 30 | `30-news-extraction-agent` | Adaptive news extraction fallback với sanitized HTML | target | `specs/news.md` | **Agent Architecture**, **Data Flow** |
| 31 | `31-candidate-discovery-agent` | Optional Candidate Discovery bounded by normal queue | target | `specs/agent-architecture.md` | **Agent Architecture**, **Search/Backtest Flow** |
| 32 | `32-market-insight-agent` | Optional read-only Market Insight flow | target | `specs/agent-architecture.md` | **Agent Architecture** |
| 33 | `33-tool-invocation-security-boundary` | Typed tool contract và least-privilege security boundary | target | `specs/agent-architecture.md` | **Agent Architecture**, access control |
| 34 | `34-use-case-overview` | Use Case tổng thể cho user, author, operator và plugin developer | target | `docs/note-update-require.txt` | **Use Case** |
| 35 | `35-c4-l3-go-edge-market-gateway` | C4 Level 3 — component bên trong Go Edge & Market Gateway | target | `design.md` §1.2–§3.2 | **Component responsibilities**, **Realtime Flow** |
| 36 | `36-uml-strategy-plugin-model` | UML class — Strategy interface, plugin, composite, registry và runtime | target | `specs/strategy-registry.md`, `specs/composite-strategy.md` | **UML/Class**, **Strategy Flow** |
| 37 | `37-uml-search-algorithm-model` | UML class — CandidateGenerator và các search algorithm thay thế được | target | `specs/search-loop.md` | **UML/Class**, **Search/Backtest Flow** |
| 38 | `38-uml-news-crawler-model` | UML class — crawler adapters, deterministic extractor và LLM fallback | target | `specs/news.md` | **UML/Class**, **Data Flow** |
| 39 | `39-deployment-topology` | Deployment — Docker Compose MVP, network boundary và scale path | target | `design.md` §1.3, §8, §12 | **Deployment**, scalability/reliability |

Ghi chú parity: 09 và 10 là sơ đồ gốc của tài liệu narrative (mermaid nhúng); target
tương ứng của chúng nằm ở 05 (candle+BBO realtime) và 22 (runtime parity) — đọc kèm nhau.
Mapping yêu cầu → sơ đồ → verification gate: `blueprint/traceability.md`.

Bảy góc nhìn bắt buộc ở `requirements.html` (System Context, Container/HLA, ERD, Data Flow, Realtime/Reconnect Flow, Strategy Flow, Search/Backtest Flow) đều có ít nhất một sơ đồ render sẵn — xem cột cuối. Nhóm Agent Architecture (25–33) và nhóm Use Case/C4-Go/UML/Deployment (34–39) bổ sung cho yêu cầu trong `docs/note-update-require.txt`; không thay thế các góc nhìn bắt buộc.

## Render lại

Yêu cầu: Node.js (đã có Chromium tải qua puppeteer lần đầu). Không cần cài global.

Trích lại `.mmd` từ Markdown (chỉ khi đã sửa mermaid trong `design.md` / `specs/`):

```bash
py scripts/extract_diagrams.py       # xem mục "Nguồn sự thật" bên dưới
```

Render một sơ đồ:

```bash
cd blueprint/assets
npx --yes @mermaid-js/mermaid-cli@11 \
  -i diagrams/04-high-level-architecture.mmd \
  -o diagrams/04-high-level-architecture.svg \
  -c mermaid-config.json -p puppeteer-config.json -b white
```

Render tất cả (SVG + PNG 2×):

```bash
cd blueprint/assets
for f in diagrams/*.mmd; do
  b=$(basename "$f" .mmd)
  npx --yes @mermaid-js/mermaid-cli@11 -i "$f" -o "diagrams/$b.svg" \
    -c mermaid-config.json -p puppeteer-config.json -b white
  npx --yes @mermaid-js/mermaid-cli@11 -i "$f" -o "diagrams-png/$b.png" \
    -c mermaid-config.json -p puppeteer-config.json -b white -s 2
done
```

## Nguồn sự thật

Bộ sơ đồ có **hai loại nguồn gốc** (ghi trong `diagrams/index.json`, cột `origin`):

- **`origin: doc`** (09, 10): mermaid trong `design.md` / `specs/*.md` là nguồn sự thật. File `.mmd` ở đây được **trích ra** từ đó. Quy trình khi sửa: (1) sửa mermaid trong `design.md`, (2) chạy `py scripts/extract_diagrams.py`, (3) render lại `.svg` + `.png`.
- **`origin: target`** (còn lại): sơ đồ kiến trúc **đích** của bộ thống nhất — mô tả contract, ownership và pipeline cần đạt, không phải bằng chứng code hiện tại. File `.mmd` là nguồn sự thật cho tới khi tài liệu narrative nhúng mermaid tương ứng; script extract **không** ghi đè lên chúng. SVG/PNG render từ `.mmd` tại thời điểm gộp bộ — sau khi sửa `.mmd`, render lại theo lệnh bên dưới.

Làm ngược lại — sửa `.mmd` rồi quên đồng bộ Markdown (với sơ đồ doc) — sẽ tạo hai phiên bản của cùng một sơ đồ và không có cách nào biết cái nào đúng. `diagrams/index.json` ghi lại origin của từng slug để việc trích lại xác định được.

Bằng chứng hoàn thành của các sơ đồ target phải đến từ test, benchmark, demo và
provenance record thật — sơ đồ không tự chứng minh implementation
(`blueprint/traceability.md`).

Lưu ý: `-b white` là cố ý. Không có nền, SVG nhúng vào PDF hoặc slide nền tối sẽ mất chữ đen.
