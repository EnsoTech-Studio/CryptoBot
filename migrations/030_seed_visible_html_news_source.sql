UPDATE news_sources
SET is_active = false
WHERE source_key = 'crypto-news-html';

INSERT INTO news_sources(source_key, display_name, kind, allowed_origin, url_template, is_active)
VALUES
    (
        'utoday-html',
        'U.Today HTML Article',
        'html',
        'https://u.today',
        'https://u.today/price-analysis/dogecoin-doge-hyperliquid-hype-shiba-inu-shib-and-bitcoin-btc-price-analysis-for-september-2',
        true
    )
ON CONFLICT (source_key) DO UPDATE SET
    display_name = EXCLUDED.display_name,
    kind = EXCLUDED.kind,
    allowed_origin = EXCLUDED.allowed_origin,
    url_template = EXCLUDED.url_template,
    is_active = EXCLUDED.is_active;
