# Crypto Strategy Lab

Monorepo cho đồ án **Crypto Strategy Lab**. `requirements.html` là nguồn yêu cầu chính; `blueprint/` là nguồn sự thật cho kiến trúc và contract. Code hiện tại vẫn có phần scaffold/wiring, còn blueprint mô tả target architecture và delivery roadmap.

Luồng tổng quát:

```text
Browser (Next.js) -> Go Strategy Service (public boundary + domain)
                                                   -> PostgreSQL / Binance / News
                                                   -> Go Backtest Worker qua job queue
                                                   -> Python AI inference (sentiment only)
```

## Install

### Cách khuyến nghị: Docker Compose

Yêu cầu:

- Docker Desktop có Docker Compose v2.
- PowerShell trên Windows hoặc shell tương đương.

Chuẩn bị biến môi trường:

```powershell
Copy-Item .env.example .env
```

### Chạy từng service khi phát triển

- Go 1.23+
- Python 3.12+
- Node.js 20+ và npm

Python dependencies:

```powershell
cd ai
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
```

Web dependencies:

```powershell
cd web
Copy-Item .env.example .env.local
npm install
```

## Run

### Full stack

```powershell
docker compose up --build
```

Endpoints kiểm tra:

- Frontend: <http://localhost:3000>
- Go API health của **scaffold hiện tại**: <http://localhost:8080/health>
- Python AI health của **scaffold hiện tại**: <http://localhost:8000/health>
- Python OpenAPI của **scaffold hiện tại**: <http://localhost:8000/docs>

`docker-compose.yml` là profile dev/smoke của scaffold nên còn publish Python port để
debug. Đây **không** phải production topology của blueprint. Target contract dùng
`GET /healthz` và `GET /readyz` ở Go; Python chỉ nghe internal network và không có port
host. Override production tối thiểu nằm ở [`docker-compose.prod.yml`](docker-compose.prod.yml);
health route target và migration/DB vẫn là phần implementation của Phase 0 trong
[`blueprint/design.md`](blueprint/design.md) §12.0.

Dừng stack:

```powershell
docker compose down
```

### Local development

Go API:

```powershell
cd server
go run ./cmd/api
```

Biến môi trường chính: `PORT`, `AI_SERVICE_URL`, `CORS_ORIGIN`.

Python AI:

```powershell
cd ai
python -m uvicorn app.main:app --reload --port 8000
```

Next.js:

```powershell
cd web
npm run dev
```

## Architecture

Đọc theo thứ tự:

1. [`requirements.html`](requirements.html) — requirement authority.
2. [`blueprint/README.md`](blueprint/README.md) — index, traceability và hướng dẫn đọc.
3. [`blueprint/design.md`](blueprint/design.md) — C4, HLA, DDL, read projection, domain ports, event flow, ADR và demo script.
4. [`blueprint/specs/`](blueprint/specs/) — contract, flow, lỗi, invariant và acceptance criteria theo từng module.

Các ranh giới chính:

- Web chỉ render; không parse payload Binance và không tính indicator/PnL/ranking.
- Go sở hữu public boundary và domain: auth, RBAC, ownership, rate limit, market normalization, indicators, strategy/plugin, composite, experiment, backtest, evaluation, ranking, news orchestration và migrations.
- Go worker chạy backtest bất đồng bộ qua `backtest_jobs`; không giữ HTTP request mở.
- Go sở hữu domain write path và versioned read views; API dùng cùng domain codebase.
- Binance và News Providers là network dependencies ở MVP; Python AI service chỉ là sentiment inference integration seam, có thể đổi sang adapter remote/GPU.

Giới hạn kiến trúc quan trọng:

- Public candle response: tối đa 1.000 nến.
- Dataset/backtest input: tối đa 20.000 nến/experiment.
- Search loop phải có stop condition; không có run vô hạn.
- Artifact provenance (dataset, strategy version, experiment, evaluation, leaderboard entry) là append-only.

## Demo

### Smoke demo của scaffold hiện tại (không phải target acceptance)

1. Chạy `docker compose up --build`.
2. Mở frontend tại <http://localhost:3000>.
3. Kiểm tra wiring AI của scaffold:

```powershell
Invoke-RestMethod http://localhost:8080/api/v1/ai/predict `
  -Method Post `
  -ContentType 'application/json' `
  -Body '{"text":"Bitcoin đang có xu hướng tích cực"}'
```

Response hiện tại dùng predictor stub (`stub-v0`); đây là smoke test cho wiring, chưa phải demo đầy đủ của target product.

Endpoint này đang được gọi không có auth vì scaffold chưa implement boundary đầy đủ.
Trong target product, cùng route thuộc Go API và anonymous request phải nhận `401`; demo
acceptance phải đăng nhập trước và gửi cookie/CSRF theo [`blueprint/specs/auth.md`](blueprint/specs/auth.md).

### Target product demo

Kịch bản demo đầy đủ gồm realtime chart, 4 timeframe độc lập, strategy/plugin picker, composite, search, backtest, evaluation, leaderboard, trade visualization, news và sentiment. Script 18 bước, mapping requirement và tiêu chí kiểm chứng nằm ở [`blueprint/design.md`](blueprint/design.md) §12.2.

## Tài liệu thiết kế

| Thư mục | Vai trò |
| --- | --- |
| [`blueprint/`](blueprint/README.md) | Nguồn sự thật kiến trúc: proposal, design, 14 specs, ADR và sơ đồ |
| [`plans/`](plans/README.md) | Bản nháp cũ đã archive, chỉ giữ để tra cứu lịch sử |
| [`requirements.html`](requirements.html) | Nguồn yêu cầu chính được chuẩn hoá từ đề bài |

## API contract mẫu của scaffold (không phải target contract)

```http
POST http://localhost:8080/api/v1/ai/predict
Content-Type: application/json

{"text":"Bitcoin đang có xu hướng tích cực"}
```

Response hiện tại:

```json
{
  "label": "neutral",
  "score": 0.5,
  "model": "stub-v0",
  "received_at": "2026-01-01T00:00:00Z"
}
```

Target contract của route này là `POST /api/v1/ai/predict` qua Go, yêu cầu auth; Python
không được gọi trực tiếp từ browser. Các route/health target chuẩn nằm trong
[`blueprint/design.md`](blueprint/design.md) §5.5, còn phần trên chỉ giúp chạy scaffold
hiện tại mà không nhầm nó với deliverable cuối cùng.
