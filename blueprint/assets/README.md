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

| # | Slug | Nội dung | Nguồn trong tài liệu | Góc nhìn kiến trúc bắt buộc |
| - | ---- | -------- | -------------------- | --------------------------- |
| 01 | `01-c4-l1-system-context` | C4 Level 1 — actor + hệ thống ngoài | `design.md` §2.1 | **System Context** |
| 02 | `02-c4-l2-container` | C4 Level 2 — container + công nghệ + giao thức | `design.md` §2.2 | **Container/Module decomposition** |
| 03 | `03-c4-l3-component-strategy-lab` | C4 Level 3 — component của Strategy Lab, 4 lớp | `design.md` §2.3 | **Component responsibilities** |
| 04 | `04-high-level-architecture` | HLA — cấu trúc + 6 luồng dữ liệu trong một hình | `design.md` §3 | **Container/HLA**, **Data Flow** |
| 05 | `05-candle-path-binance-to-pixel` | Đường đi của một nến từ Binance tới pixel | `design.md` §3.2 | **Data Flow**, **Realtime Flow** |
| 06 | `06-erd` | ERD — quan hệ giữa 24 bảng | `design.md` §4.3 | **ERD** |
| 07 | `07-outbox-scenarios` | Outbox: 4 kịch bản (thành công, handler fail, dispatcher chết, duplicate) | `design.md` §5.7.5 | **Data Flow** |
| 08 | `08-outbox-event-state` | State machine của một event trong outbox | `design.md` §5.7.6 | **Data Flow** |
| 09 | `09-realtime-reconnect-backfill-flow` | Realtime Flow — disconnect → reconnect → backfill | `design.md` §6.1 | **Realtime/Reconnect Flow** |
| 10 | `10-strategy-flow` | Strategy Flow — từ nến tới tín hiệu composite | `design.md` §6.2 | **Strategy Flow** |
| 11 | `11-search-backtest-flow` | Search/Backtest Flow — vòng lặp có kiểm soát, 2 worker song song | `design.md` §6.3 | **Search/Backtest Flow** |
| 12 | `12-search-run-state` | State machine của `search_runs` (pause/resume/cancel) | `design.md` §6.3 | **Search/Backtest Flow** |
| 13 | `13-news-sentiment-flow` | News → Sentiment Flow, cô lập hoàn toàn | `design.md` §6.4 | **Data Flow** |
| 14 | `14-defense-in-depth` | 4 lớp kiểm soát truy cập | `design.md` §7.4 | Access control |
| 15 | `15-job-queue-scale` | Job queue: 1 worker → N worker → broker, cùng contract | `design.md` §8.3 | **Search/Backtest Flow**, scalability |
| 16 | `16-experiment-create-transaction` | Tạo experiment: snapshot + job trong một transaction | `specs/experiment.md` §A | **Search/Backtest Flow** |
| 17 | `17-experiment-worker-execution` | Worker: claim → heartbeat → ghi kết quả, guard bằng `lease_token` | `specs/experiment.md` §D | **Search/Backtest Flow** |
| 18 | `18-experiment-lease-takeover` | Worker chết → lease hết hạn → take-over | `specs/experiment.md` §E | **Search/Backtest Flow** |
| 19 | `19-backtest-run-state` | State machine của `backtest_runs` | `specs/experiment.md` §F | **Search/Backtest Flow** |

Bảy góc nhìn bắt buộc ở `requirements.html` (System Context, Container/HLA, ERD, Data Flow, Realtime/Reconnect Flow, Strategy Flow, Search/Backtest Flow) đều có ít nhất một sơ đồ render sẵn — xem cột cuối.

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

**Mermaid trong `design.md` và `specs/*.md` là nguồn sự thật.** File `.mmd` ở đây được **trích ra** từ đó, không phải bản gốc song song. Quy trình khi sửa một sơ đồ:

1. Sửa mermaid trong `design.md` (hoặc spec tương ứng).
2. Trích lại `.mmd`.
3. Render lại `.svg` + `.png`.

Làm ngược lại — sửa `.mmd` rồi quên đồng bộ Markdown — sẽ tạo hai phiên bản của cùng một sơ đồ và không có cách nào biết cái nào đúng. `diagrams/index.json` ghi lại `(file nguồn, block index)` của từng slug để việc trích lại xác định được.

Lưu ý: `-b white` là cố ý. Không có nền, SVG nhúng vào PDF hoặc slide nền tối sẽ mất chữ đen.
