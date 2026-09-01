import assert from "node:assert/strict";
import test from "node:test";

import { strategyDraftReview } from "./strategy-authoring-review";


test("a missing draft is explicitly pending instead of valid", () => {
  const review = strategyDraftReview(null);

  assert.equal(review.label, "Chưa tạo draft");
  assert.equal(review.canApprove, false);
});


test("only a complete review package can be approved", () => {
  const review = strategyDraftReview({
    status: "REVIEW_REQUIRED",
    spec_hash: "spec",
    artifact_hash: "artifact",
    sandbox_report_hash: "sandbox",
  });

  assert.equal(review.label, "Sẵn sàng phê duyệt");
  assert.equal(review.canApprove, true);
});


test("a published draft is no longer an approval action", () => {
  const review = strategyDraftReview({
    status: "APPROVED",
    spec_hash: "spec",
    artifact_hash: "artifact",
    sandbox_report_hash: "sandbox",
  });

  assert.equal(review.label, "Đã lưu vào Strategy Library");
  assert.equal(review.canApprove, false);
});
