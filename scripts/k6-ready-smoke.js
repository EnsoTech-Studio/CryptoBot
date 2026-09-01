import http from "k6/http";
import { check } from "k6";

// Public, side-effect-free load smoke. It is deliberately not a claim about
// backtest throughput; experiments require authenticated immutable input.
export const options = {
  scenarios: {
    readiness: {
      executor: "constant-vus",
      vus: Number(__ENV.VUS || 10),
      duration: __ENV.DURATION || "60s",
    },
  },
  thresholds: {
    http_req_failed: ["rate<0.01"],
    http_req_duration: ["p(95)<1000"],
  },
};

const apiBaseUrl = (__ENV.API_BASE_URL || "http://127.0.0.1:8080").replace(/\/$/, "");

export default function () {
  const response = http.get(`${apiBaseUrl}/ready`);
  check(response, { "ready returns 200": (value) => value.status === 200 });
}
