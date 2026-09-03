ALTER TABLE news_sources DROP CONSTRAINT IF EXISTS news_sources_kind_check;
ALTER TABLE news_sources
    ADD CONSTRAINT news_sources_kind_check CHECK (kind IN ('rss','url','html'));

INSERT INTO news_sources(source_key, display_name, kind, allowed_origin, url_template, is_active)
VALUES
    (
        'bitcoinmagazine-html',
        'Bitcoin Magazine HTML',
        'html',
        'https://bitcoinmagazine.com',
        'https://bitcoinmagazine.com/articles',
        true
    )
ON CONFLICT (source_key) DO UPDATE SET
    display_name = EXCLUDED.display_name,
    kind = EXCLUDED.kind,
    allowed_origin = EXCLUDED.allowed_origin,
    url_template = EXCLUDED.url_template,
    is_active = EXCLUDED.is_active;
