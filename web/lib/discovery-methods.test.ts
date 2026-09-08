import assert from "node:assert/strict";
import test from "node:test";

import { createDraft, DISCOVERY_METHODS } from "./discovery";


test("all Discovery methods backed by generators remain selectable", () => {
  const enabled = DISCOVERY_METHODS.filter((method) => method.supported).map((method) => method.value);
  assert.deepEqual(enabled, ["grid", "discovery", "random_search", "domain_guided", "genetic"]);
});

test("new discovery drafts default to the durable discovery loop", () => {
  assert.equal(createDraft({ provider: "binance_usdm", symbol: "SOLUSDT" }, "1m").method, "discovery");
  assert.equal(DISCOVERY_METHODS.find((method) => method.value === "discovery")?.supported, true);
});
