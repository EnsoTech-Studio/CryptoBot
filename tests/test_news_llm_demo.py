from uuid import uuid4

import pytest

from app.domain.news import ApprovedSource
from app.infrastructure.news.html import HtmlQualityGateFailed
from scripts.news_llm_demo import DEMO_ARTICLES, parse_demo_html


def test_demo_html_intentionally_uses_the_llm_fallback_path() -> None:
    source = ApprovedSource(
        id=uuid4(),
        source_key="demo-news-positive",
        display_name="Demo Positive",
        kind="url",
        allowed_origin="https://demo.cryptobot.local",
        url_template="https://demo.cryptobot.local/positive",
        is_active=False,
    )

    with pytest.raises(HtmlQualityGateFailed):
        parse_demo_html(source, DEMO_ARTICLES[0])
