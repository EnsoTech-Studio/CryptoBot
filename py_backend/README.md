# CryptoBot — Strategy/Backtest Backend (Python)

FastAPI backend sở hữu **Strategy Engine, Backtest, Evaluation, Search, Composite,
Visualization-of-results và Leaderboard**. Tách riêng khỏi Go `server/` backend
(Market Data, News, Sentiment, Auth, Observability).

- Mirror cấu trúc `server/internal/domain/*` 1:1, đổi `decimal.Decimal` → `float`
  (float64) theo quyết định `[PD]` ở `blueprint/specs/python-research.md`.
- Domain logic hiện là skeleton (raise `NotImplementedError`), tương đương trạng
  thái `ErrNotImplemented` của Go skeleton.
- Port mặc định: `8001` (khác `ai` sentiment service trên `8000`).

Chạy local:

```bash
pip install -r requirements.txt -r requirements-dev.txt
uvicorn app.main:app --reload --port 8001
```
