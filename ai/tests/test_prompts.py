from app.services.prompts import load_system_prompt


def test_llm_system_prompts_are_loaded_from_config_files() -> None:
    sentiment = load_system_prompt("news_sentiment")
    aggregate = load_system_prompt("news_aggregate_sentiment")
    strategy = load_system_prompt("news_strategy_analysis")

    assert "untrusted data" in sentiment
    assert "news digest" in aggregate
    assert "Quy trình suy luận AI" in strategy
