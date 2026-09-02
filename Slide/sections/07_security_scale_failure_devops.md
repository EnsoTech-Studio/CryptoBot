## 24. Security Architecture: Defense-in-Depth

<div class="columns">
<div>

### Multi-Layer Security Architecture (Defense-in-Depth)
* **Authentication & RBAC:** JWT authentication, role-based access control, tenant/user experiment isolation.
* **Crawler SSRF Prevention:** Block private IP ranges (`127.0.0.1`, `10.0.0.0/8`, cloud metadata), domain whitelisting qua `ApprovedSource`.
* **AST Sandbox & Safe Execution:** AST static analysis trên AI-generated code; ban dangerous builtins/modules (`eval`, `subprocess`, `socket`, `os.system`).
* **Tool Invocation Boundary:** Schema-validated DTOs, strict input boundaries cho AI Agents.

</div>
<div>

![Defense in Depth](../../blueprint/assets/diagrams-png/14-defense-in-depth.png)

</div>
</div>

---

## 25. Scalability Architecture & Benchmark

<div class="columns">
<div>

### Scale-Out Strategy & 100,000 Backtests Benchmark
* **Stateless Horizontal Scale-Out:**
  * Spin up N Python Worker instances độc lập dựa trên CPU load / queue backlog.
  * Distribute jobs qua PostgreSQL B-Tree indexed Leased Job Queue.
* **Load Testing & Benchmarking (k6 / Locust):**
  * Simulate 10,000 concurrent users dispatch Backtest jobs và query candle data.
  * Queue throughput đạt > 1,500 backtests/phút trên 4 workers.
  * Candle & Leaderboard API latency duy trì ≤ 120ms (p95).

</div>
<div>

![Job Queue Scale](../../blueprint/assets/diagrams-png/15-job-queue-scale.png)

</div>
</div>

---

## 26. Fault Tolerance & Self-Healing Architecture

<div class="columns">
<div>

### Resilient Recovery & Chaos Simulation
* **Worker Lease Takeover & Heartbeat:**
  * Worker gửi heartbeat 10s/lần. Nếu worker crash, lease timeout sau 30s, worker khác auto-takeover job.
* **Idempotency & Retry:**
  * Unique `idempotency_key` constraint, eliminate duplicate execution risk.
* **Failure Isolation & Reconnect:**
  * Plugin failure isolation (lỗi 1 strategy không crash Worker); WSS auto-reconnect & backfill.
* **Chaos Engineering Simulation:** Kill worker process / inject network drops để verify self-healing behavior.

</div>
<div>

![Worker Lease Takeover](../../blueprint/assets/diagrams-png/18-worker-lease-takeover.png)

</div>
</div>

---

## 27. Deployment Topology & MLOps Infrastructure

<div class="columns">
<div>

### Containerized Deployment (Docker Compose) & K8s Readiness
* **Full-Stack Containerization:**
  * Isolated container services: Next.js Web Dashboard, Go Edge Gateway, Python Research API, Python Research Worker × N, Internal AI Inference Adapter, PostgreSQL.
* **Health Checks & Liveness Probes:**
  * `/healthz` và `/readyz` endpoints cho container auto-restart & traffic routing.
* **MLOps & Configuration:**
  * Versioned system prompts và LLM API keys tách biệt qua environment variables (`.env`).
* **Kubernetes-Ready Architecture:** Hỗ trợ Deployment Replicas, Rolling Updates, Horizontal Pod Autoscaling (HPA) khi scale production.

</div>
<div>

![Deployment Topology](../../blueprint/assets/diagrams-png/39-deployment-topology.png)

</div>
</div>
