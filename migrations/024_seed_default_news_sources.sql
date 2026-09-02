INSERT INTO news_sources(source_key, display_name, kind, allowed_origin, url_template, is_active)
VALUES
    ('coindesk', 'CoinDesk', 'rss', 'https://www.coindesk.com', 'https://www.coindesk.com/arc/outboundfeeds/rss', true),
    ('cointelegraph', 'Cointelegraph', 'rss', 'https://cointelegraph.com', 'https://cointelegraph.com/rss', true),
    ('cryptoslate', 'CryptoSlate', 'rss', 'https://cryptoslate.com', 'https://cryptoslate.com/feed/', true),
    ('decrypt', 'Decrypt', 'rss', 'https://decrypt.co', 'https://decrypt.co/feed', true)
ON CONFLICT (source_key) DO UPDATE SET
    display_name = EXCLUDED.display_name,
    kind = EXCLUDED.kind,
    allowed_origin = EXCLUDED.allowed_origin,
    url_template = EXCLUDED.url_template,
    is_active = EXCLUDED.is_active;
