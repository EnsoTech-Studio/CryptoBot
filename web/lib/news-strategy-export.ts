export const NEWS_SENTIMENT_STRATEGY = {
  strategy_id: "news_sentiment",
  version: "v1",
  parameters: {
    min_items: 3,
    buy_above: 0.7,
    sell_below: -0.7,
  },
} as const;

export function newsStrategyEnginePrompt() {
  return `Use the registered ${NEWS_SENTIMENT_STRATEGY.strategy_id} strategy (${NEWS_SENTIMENT_STRATEGY.version}) with ${JSON.stringify(NEWS_SENTIMENT_STRATEGY.parameters)}. It reads persisted, versioned NewsSentimentWindow data; do not replace it with an LLM result during a backtest.`;
}
