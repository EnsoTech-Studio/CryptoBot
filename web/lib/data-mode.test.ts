import assert from "node:assert/strict";
import test from "node:test";

import { dataSourceLabel } from "./data-mode";

test("reference mode is visibly labeled as mock data", () => {
  assert.equal(dataSourceLabel("mock"), "Dữ liệu tham chiếu (mock)");
  assert.equal(dataSourceLabel("live"), "Nguồn dữ liệu: Exchange API + WebSocket");
});
