-- Public OKX USDT perpetual swap markets supported by the OKX realtime adapter.
INSERT INTO market_pairs(symbol,base,quote,provider,is_active) VALUES
    ('BTCUSDT','BTC','USDT','okx_swap',TRUE),
    ('ETHUSDT','ETH','USDT','okx_swap',TRUE),
    ('SOLUSDT','SOL','USDT','okx_swap',TRUE)
ON CONFLICT(provider,symbol) DO UPDATE SET
    base=EXCLUDED.base,
    quote=EXCLUDED.quote,
    is_active=EXCLUDED.is_active;
