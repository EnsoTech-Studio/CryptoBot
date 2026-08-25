-- Reproducible offline demo replay. This is a fixed fixture, not operational
-- market data and not a candle-price fill fallback: executable prices are the
-- explicit BBO rows below. It keeps a fresh stack immediately demonstrable
-- while live deployments accumulate their own BBO-complete replay windows.
DO $$
DECLARE
    dataset_id UUID;
    candle_hash CHAR(64);
    quote_hash CHAR(64);
BEGIN
    WITH generated AS (
        SELECT i,
               TIMESTAMPTZ '2026-01-01 00:00:00+00' + i * INTERVAL '5 minutes' AS open_time,
               round((2000 + 80*sin(2*pi()*i/24.0) + 25*sin(2*pi()*i/7.0))::numeric,8) AS open,
               round((2000 + 80*sin(2*pi()*(i+1)/24.0) + 25*sin(2*pi()*(i+1)/7.0))::numeric,8) AS close
        FROM generate_series(0,239) AS series(i)
    ), facts AS (
        SELECT open_time,open_time+INTERVAL '5 minutes' AS close_time,open,
               greatest(open,close)+3 AS high,least(open,close)-3 AS low,close,
               (100+i%20)::numeric AS volume,(200+i%40)::int AS trade_count
        FROM generated
    )
    SELECT encode(digest(jsonb_agg(to_jsonb(facts) ORDER BY open_time)::text,'sha256'),'hex')
    INTO candle_hash FROM facts;

    WITH generated AS (
        SELECT i,
               TIMESTAMPTZ '2026-01-01 00:00:00+00' + i * INTERVAL '5 minutes' AS open_time,
               round((2000 + 80*sin(2*pi()*(i+1)/24.0) + 25*sin(2*pi()*(i+1)/7.0))::numeric,8) AS close
        FROM generate_series(0,239) AS series(i)
    ), quotes AS (
        SELECT open_time+INTERVAL '1 minute' AS event_time,i*2+1 AS source_sequence,
               close-0.50 AS bid,50::numeric AS bid_qty,
               close+0.50 AS ask,50::numeric AS ask_qty,(i*2+1)::bigint AS update_id
        FROM generated
        UNION ALL
        SELECT open_time+INTERVAL '4 minutes 59 seconds',i*2+2,
               close-0.25,75::numeric,close+0.25,75::numeric,(i*2+2)::bigint
        FROM generated
    )
    SELECT encode(digest(jsonb_agg(to_jsonb(quotes) ORDER BY event_time,source_sequence)::text,'sha256'),'hex')
    INTO quote_hash FROM quotes;

    INSERT INTO market_datasets(
        dataset_version,provider,symbol,timeframe,range_from,range_to,
        revision_no,candle_count,content_hash,bbo_content_hash
    ) VALUES (
        'demo:binance_usdm:ETHUSDT:5m:20260101:v1','binance_usdm','ETHUSDT','5m',
        TIMESTAMPTZ '2026-01-01 00:00:00+00',TIMESTAMPTZ '2026-01-01 20:00:00+00',
        1,240,candle_hash,quote_hash
    )
    ON CONFLICT(dataset_version) DO NOTHING
    RETURNING id INTO dataset_id;

    IF dataset_id IS NULL THEN
        SELECT id INTO dataset_id FROM market_datasets
        WHERE dataset_version='demo:binance_usdm:ETHUSDT:5m:20260101:v1';
    END IF;

    WITH generated AS (
        SELECT i,
               TIMESTAMPTZ '2026-01-01 00:00:00+00' + i * INTERVAL '5 minutes' AS open_time,
               round((2000 + 80*sin(2*pi()*i/24.0) + 25*sin(2*pi()*i/7.0))::numeric,8) AS open,
               round((2000 + 80*sin(2*pi()*(i+1)/24.0) + 25*sin(2*pi()*(i+1)/7.0))::numeric,8) AS close
        FROM generate_series(0,239) AS series(i)
    )
    INSERT INTO market_dataset_candles(
        market_dataset_id,open_time,close_time,open,high,low,close,volume,trade_count
    )
    SELECT dataset_id,open_time,open_time+INTERVAL '5 minutes',open,
           greatest(open,close)+3,least(open,close)-3,close,
           (100+i%20)::numeric,(200+i%40)::int
    FROM generated
    ON CONFLICT(market_dataset_id,open_time) DO NOTHING;

    WITH generated AS (
        SELECT i,
               TIMESTAMPTZ '2026-01-01 00:00:00+00' + i * INTERVAL '5 minutes' AS open_time,
               round((2000 + 80*sin(2*pi()*(i+1)/24.0) + 25*sin(2*pi()*(i+1)/7.0))::numeric,8) AS close
        FROM generate_series(0,239) AS series(i)
    ), quotes AS (
        SELECT open_time+INTERVAL '1 minute' AS event_time,i*2+1 AS source_sequence,
               close-0.50 AS bid,50::numeric AS bid_qty,
               close+0.50 AS ask,50::numeric AS ask_qty,(i*2+1)::bigint AS update_id
        FROM generated
        UNION ALL
        SELECT open_time+INTERVAL '4 minutes 59 seconds',i*2+2,
               close-0.25,75::numeric,close+0.25,75::numeric,(i*2+2)::bigint
        FROM generated
    )
    INSERT INTO market_dataset_bbo(
        market_dataset_id,event_time,source_sequence,bid,bid_qty,ask,ask_qty,update_id
    )
    SELECT dataset_id,event_time,source_sequence,bid,bid_qty,ask,ask_qty,update_id
    FROM quotes
    ON CONFLICT(market_dataset_id,event_time,source_sequence) DO NOTHING;
END $$;

