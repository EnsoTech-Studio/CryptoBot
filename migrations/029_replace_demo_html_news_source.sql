UPDATE news_sources
SET is_active = false
WHERE source_key = 'bitcoinmagazine-html';

INSERT INTO news_sources(source_key, display_name, kind, allowed_origin, url_template, is_active)
VALUES
    (
        'crypto-news-html',
        'Crypto.news HTML Article',
        'html',
        'https://crypto.news',
        'https://crypto.news/fairshake-enters-us-elections-with-122m-war-chest/',
        true
    )
ON CONFLICT (source_key) DO UPDATE SET
    display_name = EXCLUDED.display_name,
    kind = EXCLUDED.kind,
    allowed_origin = EXCLUDED.allowed_origin,
    url_template = EXCLUDED.url_template,
    is_active = EXCLUDED.is_active;
