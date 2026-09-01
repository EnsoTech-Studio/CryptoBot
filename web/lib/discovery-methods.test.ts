import assert from "node:assert/strict";
import test from "node:test";

import { DISCOVERY_METHODS } from "./discovery";


test("unsupported discovery generators stay disabled instead of submitting a 422", () => {
  assert.equal(DISCOVERY_METHODS.find((method) => method.value === "genetic")?.supported, false);
});
