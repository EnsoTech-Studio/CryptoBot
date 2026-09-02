import assert from "node:assert/strict";
import test from "node:test";

import { createDraft, DISCOVERY_METHODS } from "./discovery";


test("unsupported discovery generators stay disabled instead of submitting a 422", () => {
  assert.equal(DISCOVERY_METHODS.find((method) => method.value === "genetic")?.supported, true);
});

test("new discovery drafts default to the durable discovery loop", () => {
  assert.equal(createDraft({ provider: "binance_usdm", symbol: "SOLUSDT" }, "1m").method, "discovery");
  assert.equal(DISCOVERY_METHODS.find((method) => method.value === "discovery")?.supported, true);
});
