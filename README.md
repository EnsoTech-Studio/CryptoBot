# CryptoBot platform

Monorepo khởi đầu cho một hệ thống gồm:

- `server/`: Go HTTP API, chịu trách nhiệm làm gateway và business API.
- `ai/`: Python FastAPI service, nơi đặt model/inference.
- `web/`: Next.js App Router frontend.

Luồng request mẫu:

```text
Browser (Next.js) -> Go API :8080 -> Python AI :8000
```

## Tài liệu thiết kế

| Thư mục | Trạng thái | Nội dung |
| ------- | ---------- | -------- |
| **[`blueprint/`](blueprint/README.md)** | ✅ **Nguồn sự thật** | Tài liệu thiết kế kiến trúc đầy đủ: proposal, design (13 section, 17 ADR), 14 spec tính năng, sơ đồ render sẵn |
| `plans/` | ⚠️ Archived | Bản nháp đầu tiên, đã bị `blueprint/` thay thế. Giữ để tra cứu lịch sử — [xem những gì đã đổi](plans/README.md) |
| `requirements.html` | Tham chiếu | Đề bài đã chuyển sang HTML, dùng để truy vết yêu cầu |

Bắt đầu đọc ở [`blueprint/README.md`](blueprint/README.md) — nó có index và mapping từ từng yêu cầu đề bài tới tài liệu tương ứng.

## Chạy bằng Docker Compose

```powershell
Copy-Item .env.example .env
docker compose up --build
```

Sau khi khởi động:

- Frontend: <http://localhost:3000>
- Go API health: <http://localhost:8080/health>
- Python AI health: <http://localhost:8000/health>
- Swagger/OpenAPI của AI: <http://localhost:8000/docs>

Dừng stack:

```powershell
docker compose down
```

## Chạy từng service khi phát triển

### Go API

Yêu cầu Go 1.23+:

```powershell
cd server
go run ./cmd/api
```

Biến môi trường chính: `PORT`, `AI_SERVICE_URL`, `CORS_ORIGIN`.

### Python AI

Yêu cầu Python 3.12+:

```powershell
cd ai
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
python -m uvicorn app.main:app --reload --port 8000
```

### Next.js

```powershell
cd web
Copy-Item .env.example .env.local
npm install
npm run dev
```

## API contract mẫu

```http
POST http://localhost:8080/api/v1/ai/predict
Content-Type: application/json

{"text":"Bitcoin đang có xu hướng tích cực"}
```

Response hiện tại là predictor stub để kiểm tra wiring:

```json
{
  "label": "neutral",
  "score": 0.5,
  "model": "stub-v0",
  "received_at": "2026-01-01T00:00:00Z"
}
```

Thay logic trong `ai/app/services/predictor.py` bằng model thật mà không cần thay đổi contract của frontend.
