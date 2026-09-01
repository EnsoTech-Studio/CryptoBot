import assert from "node:assert/strict";
import test from "node:test";

import { recentImportRows } from "./strategy-authoring";


test("authored drafts render truthfully in the recent imports table", () => {
  const rows = recentImportRows([
    {
      source_type: "approved_url",
      status: "APPROVED",
      name_hint: "ignored when the spec has a display name",
      current_revision: 2,
      created_at: "2026-08-31T10:30:00.000Z",
      strategy_spec: {
        strategy_id: "generated.rsi-bb",
        display_name: "RSI Bollinger Reversal",
        indicators: [{ kind: "rsi" }, { kind: "bollinger" }],
      },
    },
  ]);

  assert.equal(rows.length, 1);
  assert.equal(rows[0].name, "RSI Bollinger Reversal");
  assert.equal(rows[0].source, "WEB_IMPORT");
  assert.equal(rows[0].status, "approved");
  assert.equal(rows[0].strategyId, "generated.rsi-bb");
  assert.deepEqual(rows[0].tags, ["RSI", "BB"]);
});


test("reference fixtures stay opt-in instead of leaking into live data", () => {
  assert.equal(recentImportRows([]).length, 0);
  assert.equal(recentImportRows([], true).length, 2);
});
