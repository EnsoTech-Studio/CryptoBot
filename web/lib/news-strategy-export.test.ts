import assert from "node:assert/strict";
import test from "node:test";

import { NEWS_SENTIMENT_STRATEGY, newsStrategyEnginePrompt } from "./news-strategy-export";


test("news strategy export is ready to copy into the Strategy Engine", () => {
  assert.equal(NEWS_SENTIMENT_STRATEGY.strategy_id, "news_sentiment");
  assert.match(newsStrategyEnginePrompt(), /news_sentiment/);
  assert.match(newsStrategyEnginePrompt(), /min_items/);
});
