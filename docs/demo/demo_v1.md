# Scenario

## 1. MACDStrategy

Chứng minh tính mở rộng ở tầng code.
Demo: sửa/thêm rất ít code -> khởi động lại service -> web tự nhận chức năng mới.

### Chuẩn bị file và tích hợp

File để trình diễn/paste đã đặt tại [macd.py](macd.py). Trong source thật, file
đích là `app/domain/strategy/plugins/macd.py`.

Chỉ cần hai thay đổi ở package plugin:

1. Copy `docs/demo/macd.py` vào `app/domain/strategy/plugins/macd.py`.
2. Trong `app/domain/strategy/plugins/catalog.py`, thêm import và một dòng
   đăng ký vào `register_all`:

```python
from .macd import MACDStrategy

# trong hàm register_all(registry)
registry.register(MACDStrategy)
```

Không sửa `worker.py`, backtest engine, evaluator, HTTP handler hoặc React UI.
Catalog API đọc definitions từ registry nên sau khi backend khởi động lại, web
tự nhận `macd@v1`.

> Lưu ý: repository hiện tại đã có `macd.py` và dòng `registry.register(MACDStrategy)`.
> Khi bảo vệ, dùng bản trong `docs/demo/` để minh hoạ phần code được thêm; không
> copy đè vào source đang chạy nếu MACD đã tồn tại.

Trên web, demo kết quả tích hợp:

1. Mở trang Strategy hoặc Discovery.
1. Cho thấy MACD xuất hiện trong strategy catalog.
1. Chọn MACD, hoặc ghép MACD + RSI.
1. Chạy Backtest / Discovery.
1. Mở kết quả, chỉ chart overlay, Buy/Sell, Metrics và Trades.

Sau đó chuyển sang code để chứng minh kiến trúc:

- Mở [macd.py](D:\University\Projects\Individual projects\CryptoBot\app\domain\strategy\plugins\macd.py) — implementation strategy.
- Mở [registry.py](D:\University\Projects\Individual projects\CryptoBot\app\domain\strategy\registry.py) — cơ chế đăng ký/resolve plugin.
- Chỉ rõ không cần sửa worker.py, backtest engine, evaluator hay React UI; chúng nhận strategy qua cùng contract/registry.
  Câu nói demo ngắn:
  “MACD được thêm như một strategy plugin và đăng ký vào registry. Sau khi restart backend, frontend lấy catalog từ API nên MACD tự xuất hiện. Backtester chỉ xử lý contract chung, nên không cần sửa luồng chạy backtest hay leaderboard.”

## 2. Thêm Market Data Provider mới

Dùng OKX đang có sẵn như một minh chứng provider thứ hai, thay vì phải tạo provider giả trong lúc bảo vệ.
Trên web:

1. Mở Realtime.
1. Mở danh sách market/provider.
1. Chọn cặp dữ liệu từ OKX (ví dụ swap pair mà danh sách trả về).
1. Chọn timeframe, kiểm tra chart cập nhật/realtime.
1. Chuyển sang Backtest hoặc Discovery, chọn dataset/provider đó nếu đã có dataset phù hợp.
1. Nhấn mạnh strategy và UI vẫn hoạt động như với Binance.
   Sau đó mở code theo thứ tự:

- [market.go](D:\University\Projects\Individual projects\CryptoBot\server\internal\ports\market.go): interface/port chung.
- [registry.go](D:\University\Projects\Individual projects\CryptoBot\server\internal\infrastructure\market\registry.go): đăng ký và resolve provider.
- [okx.go](D:\University\Projects\Individual projects\CryptoBot\server\internal\infrastructure\market\okx.go): implementation của provider mới.
  Câu nói demo ngắn:
  “Frontend không gọi Binance hoặc OKX trực tiếp; nó chỉ gọi API market chung. Khi thêm OKX, tôi chỉ implement provider port và đăng ký nó. Vì schema đã được normalize thành candle/BBO chung, strategy engine và UI không đổi.”
