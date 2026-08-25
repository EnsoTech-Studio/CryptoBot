-- Stable market reference records. Operational candles, BBO and news remain
-- runtime data and are intentionally not seeded by migrations.
INSERT INTO market_pairs(symbol,base,quote,provider,is_active) VALUES
    ('BTCUSDT','BTC','USDT','binance_usdm',TRUE),
    ('ETHUSDT','ETH','USDT','binance_usdm',TRUE),
    ('SOLUSDT','SOL','USDT','binance_usdm',TRUE)
ON CONFLICT(provider,symbol) DO UPDATE SET
    base=EXCLUDED.base,
    quote=EXCLUDED.quote,
    is_active=EXCLUDED.is_active;

