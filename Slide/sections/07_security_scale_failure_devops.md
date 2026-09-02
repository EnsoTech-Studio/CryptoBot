## 24. Kiến Trúc An Ninh: Phòng Thủ Đa Tầng

<div class="columns">
<div>

### Các Lớp Bảo Vệ Hệ Thống (Defense-in-Depth)
* **Authentication & RBAC:** Xác thực JWT, phân quyền tài nguyên theo người dùng (cô lập dữ liệu thí nghiệm).
* **Crawler SSRF Prevention:** Chặn IP nội bộ (`127.0.0.1`, `10.0.0.0/8`, cloud metadata), chỉ duyệt domain trong `ApprovedSource`.
* **AST Sandbox & Safe Execution:** Phân tích AST mã AI sinh ra; nghiêm cấm lệnh nguy hiểm (`eval`, `subprocess`, socket).
* **Tool Invocation Boundary:** Giới hạn quyền hạn AI Agent qua DTO chặt chẽ.

</div>
<div>

![Defense in Depth](../../blueprint/assets/diagrams-png/14-defense-in-depth.png)

</div>
</div>

---

## 25. Khả Năng Mở Rộng (Scalability) & Benchmark

<div class="columns">
<div>

### Scale-Out & Chiến Lược Chịu Tải 100,000 Backtests
* **Mở Rộng Ngang Không Trạng Thái (Scale-Out):**
  * Nhân bản số lượng Python Worker độc lập tùy theo tải CPU.
  * Phân phối công việc qua hàng đợi PostgreSQL có chỉ mục B-Tree.
* **Kịch Bản Kiểm Thử Tải (k6 / Locust Benchmark):**
  * Mô phỏng 10,000 user gửi lệnh Backtest và truy vấn nến đồng thời.
  * Tốc độ xử lý hàng đợi đạt > 1,500 backtests/phút trên 4 worker.
  * Độ trễ API nến và leaderboard luôn duy trì ≤ 120ms (p95).

</div>
<div>

![Job Queue Scale](../../blueprint/assets/diagrams-png/15-job-queue-scale.png)

</div>
</div>

---

## 26. Xử Lý Sự Cố (Fault Tolerance) & Khôi Phục

<div class="columns">
<div>

### Cơ Chế Phục Hồi & Mô Phỏng Sự Cố
* **Chiếm Quyền Xử Lý (Worker Lease Takeover):**
  * Worker gửi heartbeat 10s/lần. Nếu worker crash, sau 30s hết hạn lease, worker khác tự động tiếp quản job.
* **Idempotency & Retry:**
  * Khóa duy nhất `idempotency_key`, loại bỏ rủi ro chạy trùng lặp.
* **Failure Isolation & Reconnect:**
  * Lỗi 1 plugin không làm sập Worker; WSS tự reconnect sàn.
* **Kịch Bản Test Mô Phỏng:** Chủ động tắt module worker/database để kiểm chứng khả năng tự phục hồi.

</div>
<div>

![Worker Lease Takeover](../../blueprint/assets/diagrams-png/18-worker-lease-takeover.png)

</div>
</div>

---

## 27. Triển Khai Thực Tế & MLOps

<div class="columns">
<div>

### Mô Hình Triển Khai Docker & Kubernetes Readiness
* **Container Hóa Toàn Diện (Docker Compose):**
  * Đóng gói độc lập: Next.js Web, Go Edge Gateway, Python Research API, Python Background Worker Pool (Backtest, Event, News, Agent), AI Service, PostgreSQL.
* **Health Checks Khi Triển Khai:**
  * `/healthz` và `/readyz` tự động khởi động lại container khi lỗi.
* **MLOps & Prompt Management:**
  * System prompt và API key LLM tách biệt qua biến môi trường `.env`.
* **Kubernetes Note:** Hỗ trợ replicas, scheduling, rolling update và HPA khi mở rộng quy mô lớn (MVP dùng Docker Compose).

</div>
<div>

![Deployment Topology](../../blueprint/assets/diagrams-png/39-deployment-topology.png)

</div>
</div>
