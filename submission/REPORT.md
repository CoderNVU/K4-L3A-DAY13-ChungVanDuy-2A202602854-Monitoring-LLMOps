# Báo cáo cá nhân — K4-L3A Day 13 Monitoring & LLMOps

> Mỗi học viên hoàn thiện một file duy nhất này. Khi dẫn evidence, dùng đường dẫn tương đối, ví dụ `evidence/07-trace-waterfall.png`.

## 1. Thông tin học viên

- **Họ và tên:** Chung Văn Duy
- **MSSV:** 2A202602854
- **Lớp:** K4-L3A
- **Repository URL:** https://github.com/CoderNVU/K4-L3A-DAY13-ChungVanDuy-2A202602854-Monitoring-LLMOps.git
- **Commit SHA cuối:** `949d5fb429abcad99984d7622a87c4b2b41d4a35`
- **Challenge ID:** `day13-k4-l3a-monitoring-llmops-v1`
- **Tên project Langfuse cá nhân:** `day13-k4-l3a-2A202602854`

## 2. Evidence index

Điền đúng đường dẫn tới evidence thực tế. Có thể đổi tên hoặc dùng nhiều ảnh nếu cần.

| Evidence | Đường dẫn |
|---|---|
| Pytest cuối | `evidence/01-pytest.png` |
| Log validator | `evidence/02-log-validator.png` |
| Dashboard validator | `evidence/03-dashboard-validator.png` |
| Structured log | `evidence/04-structured-log.png` |
| PII redaction | `evidence/05-pii-redaction.png` |
| Trace list | `evidence/06-trace-list.png` |
| Trace waterfall | `evidence/07-trace-waterfall.png` |
| Trace metadata | `evidence/08-trace-metadata.png` |
| Prompt versions | `evidence/09-prompt-versions.png` |
| Prompt rollback | `evidence/10-prompt-rollback.png` |
| Dashboard runtime | `evidence/11-dashboard-overview.png` |
| Incident metric | `evidence/12-incident-metric.png` |
| Incident log | `evidence/13-incident-log.png` |
| Incident trace | `evidence/14-incident-trace.png` |

## 3. Kết quả kỹ thuật

| Nội dung | Baseline | Kết quả cuối | Nhận xét |
|---|---|---|---|
| `validate_logs.py` | 30/100 | 100/100 | Đạt điểm tuyệt đối sau khi bind correlation_id, contextvars và scrub PII đệ quy |
| `validate_dashboard.py` | 6/6 panel hợp lệ | 6/6 panel hợp lệ | Đạt 100% hợp đồng dashboard 6 panel theo config/dashboard.yaml |
| `pytest` | 22 passed | 24 passed | 100% tests vượt qua (bao gồm 2 test mới cho CCCD và thẻ) |
| Số traces hợp lệ | 10 | 15+ | Bao gồm root observation, child retriever và child generation |
| Số PII leak | 0 | 0 | 0 PII leak trên toàn bộ sample queries chứa email, phone, thẻ |
| Latency P95 / TTFT P95 | 678.0 ms / 59.0 ms | 665.0 ms / 50.0 ms | Đo từ /metrics và dashboard runtime sau khi tối ưu |
| Retrieval success rate | 100% | 100% | 10/10 request thành công, không có lỗi |

## 4. Logging và PII

- **Cách tạo/nhận và truyền correlation ID:**
  - Middleware `CorrelationIdMiddleware` (`app/middleware.py`) kiểm tra header `x-request-id` trong request đến. Nếu có thì sử dụng, nếu không có hoặc rỗng thì tự động sinh mới với định dạng `req-<8-hex>` thông qua `f"req-{uuid.uuid4().hex[:8]}"`.
  - ID này được gán vào structlog contextvars thông qua `bind_contextvars(correlation_id=correlation_id)` và lưu vào `request.state.correlation_id` để router sử dụng.
  - Sau khi xử lý request, middleware gán lại `x-request-id` và `x-response-time-ms` vào HTTP response headers gửi về cho client.
  - Đầu mỗi request, middleware gọi `clear_contextvars()` để xóa sạch ngữ cảnh của request trước đó, tránh hiện tượng context contamination (rò rỉ context) giữa các request đồng thời.
- **Các metadata được ghi vào structured log:**
  - Tại sự kiện `request_received` và xuyên suốt request: `ts` (ISO 8601 UTC timestamp), `level` (info/error), `service` ("api"), `event`, `correlation_id`, `env` ("dev"), `user_id_hash` (SHA-256 rút gọn 12 ký tự của user_id), `session_id`, `feature`, `model` ("claude-sonnet-4-5").
  - Tại sự kiện `response_sent`: bổ sung `latency_ms`, `ttft_ms`, `tokens_in`, `tokens_out`, `cost_usd`, `quality_score`, `tool_name` ("retrieval"), `tool_success` (true) và tóm tắt an toàn câu trả lời `payload.answer_preview`.
  - Tại sự kiện `request_failed`: bổ sung `error_type`, `tool_name`, `tool_success` (false) và `payload.detail`.
- **Cách bảo đảm PII được scrub trước khi ghi:**
  - Xây dựng bộ quét PII tại `app/pii.py` với các biểu thức chính quy bao phủ: Email (`[\w\.-]+@[\w\.-]+\.\w+`), Số điện thoại Việt Nam các định dạng (`(?<!\d)(?:\+84|0)(?:[ .-]?\d){9}(?!\d)`), CCCD 12 số (`\b\d{12}\b`), Thẻ tín dụng/thanh toán 16 số (`\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b`).
  - Trong `app/logging_config.py`, cài đặt hàm `_scrub_value` và processor `scrub_event` duyệt đệ quy toàn bộ cấu trúc của `event_dict` (bao gồm chuỗi, dict, list lồng nhau).
  - Đăng ký `scrub_event` vào chuỗi processors của `structlog` nằm ngay **trước** `JsonlFileProcessor` và `JSONRenderer`. Nhờ đó, mọi trường dữ liệu trước khi được format thành JSON và ghi xuống đĩa `data/logs.jsonl` hoặc hiển thị console đều đã được làm sạch 100%.
- **Cách kiểm chứng kết quả:**
  - Chạy `python scripts/load_test.py` để gửi các query mẫu chứa email, số điện thoại, thẻ tín dụng.
  - Chạy `python scripts/validate_logs.py` kiểm tra toàn bộ file log: kết quả đạt **100/100 điểm** (0 missing required fields, 0 missing enrichment, 10 unique correlation IDs, 0 PII leak).
  - Chạy `python -m pytest -q tests/test_pii.py`: vượt qua toàn bộ các bài kiểm thử che PII cho cả 4 loại dữ liệu nhạy cảm.

## 5. Tracing và prompt versioning

- **Cách xác nhận traces do chính tôi tạo trong project cá nhân:**
  - Khóa API trong file `.env` (`LANGFUSE_PUBLIC_KEY` và `LANGFUSE_SECRET_KEY`) được tạo trực tiếp từ project cá nhân mang tên `day13-k4-l3a-2A202602854` trên Langfuse Cloud (JP Region: `https://jp.cloud.langfuse.com`).
  - Toàn bộ các request khi thực thi đều gắn trace name `"day13-agent-request"`, tags `["lab", feature, model]`, environment `"dev"` và user_id đã băm bảo mật. Traces hiển thị trực tiếp trên giao diện của project cá nhân này, không dùng chung project/key của người khác.
- **Cấu trúc root/retrieval/generation observations:**
  - **Root Observation:** `@observe(name="lab-agent-run", as_type="agent")` bao quát toàn bộ hàm `run()` của `LabAgent`, chứa metadata chung (doc_count, correlation_id, prompt version).
  - **Child 1 (Retrieval):** Bọc quanh hàm `retrieve(message)` bằng `langfuse_client.start_as_current_observation(name="retrieve", as_type="retriever")` kèm metadata `query_preview`.
  - **Child 2 (Generation):** Bọc quanh hàm `FakeLLM.generate()` bằng `langfuse_client.start_as_current_observation(name="llm-generate", as_type="generation")`, liên kết `prompt=prompt.managed_prompt`, cập nhật thông tin `model`, `usage_details` (input, output, total tokens) và `cost_details` (chi phí USD ước lượng).
  - Cấu trúc cha-con tạo thành một Trace Waterfall phân lớp hoàn chỉnh, cho phép cô lập chính xác thời gian và trạng thái của từng mắt xích.
- **Cách nối trace với log:**
  - Trong `app/agent.py`, context manager `propagate_attributes` truyền `correlation_id` vào trace metadata (`metadata={"correlation_id": correlation_id}`).
  - Nhờ vậy, mỗi dòng log trong `data/logs.jsonl` đều sở hữu trường `correlation_id` (ví dụ `req-bd51bf37`) khớp chính xác 1-1 với metadata `correlation_id` của trace tương ứng trên Langfuse, cho phép điều tra xuyên suốt từ Log sang Trace.
- **Prompt name:** `day13-chat`
- **Version/label baseline:** Version 1, labels: `["baseline", "production"]` (template chuẩn 3 biến `feature`, `docs`, `message`).
- **Version/label candidate:** Version 2, labels: `["candidate"]` (bổ sung chỉ dẫn câu trả lời ngắn gọn và trực diện).
- **Trace ID của mỗi version:**
  - Version 1 (baseline / production): `req-prompt-v1-baseline` (hoặc trace ID trên Langfuse waterfall).
  - Version 2 (candidate): `req-prompt-v2-candidate` (hoặc trace ID trên Langfuse waterfall).
- **Cách promote và rollback `production`:**
  - **Promote:** Khi kiểm thử prompt Version 2 đạt chất lượng tốt, gán nhãn `production` cho Version 2 bằng API SDK `client.update_prompt(name="day13-chat", version=2, new_labels=["candidate", "production"])` hoặc thao tác trên UI Langfuse.
  - **Rollback:** Khi phát hiện Version 2 gây suy giảm chất lượng hoặc lỗi, thực hiện rollback tức thì bằng cách gán lại nhãn `production` cho Version 1 `client.update_prompt(name="day13-chat", version=1, new_labels=["baseline", "production"])`. Ứng dụng tự động tải lại Version 1 trong vòng 60s cache TTL mà không cần sửa code hay redeploy API.

## 6. Dashboard, SLO và alerts

- **Dashboard và sáu panel:**
  - Dashboard runtime được tích hợp trực tiếp tại endpoint `/dashboard` (`http://127.0.0.1:8000/dashboard`), đọc trực tiếp từ `data/logs.jsonl`, hiển thị chuẩn xác 6 panel theo hợp đồng `config/dashboard.yaml`:
    1. *Latency percentiles and TTFT:* Hiển thị P50, P95, P99 và TTFT P95 (đơn vị: ms), kèm threshold line `latency_p95 <= 3000ms`.
    2. *Request traffic:* Hiển thị tổng số request và tốc độ request/phút (đơn vị: requests_per_minute), kèm threshold line `rate_per_minute >= 1`.
    3. *Error rate and retrieval success:* Hiển thị tỷ lệ lỗi (%), tỷ lệ truy xuất thành công (%) và danh sách phân bổ `error_type` (đơn vị: percent), kèm threshold line `error_rate_pct <= 2%`.
    4. *Cost over time:* Hiển thị tổng chi phí tích lũy và chi phí trung bình/request (đơn vị: USD), kèm threshold line `total <= $2.5`.
    5. *Input and output tokens:* Hiển thị tổng Tokens In, Tokens Out và tổng token (đơn vị: tokens), kèm threshold line `total <= 50,000`.
    6. *Quality proxy:* Hiển thị điểm chất lượng trung bình theo heuristic proxy (đơn vị: score 0-1), kèm threshold line `mean >= 0.75`.
  - Cửa sổ đo mặc định: 60 phút, tự động làm mới mỗi 30 giây.
- **SLO và lý do chọn:**
  - Định nghĩa tại `config/slo.yaml`: Primary SLO `fast_successful_requests` với mục tiêu 99.5% request đạt trạng thái thành công (`event == "response_sent"`) và có độ trễ `latency_ms <= 3000ms` trên cửa sổ 28 ngày.
  - *Lý do chọn:* Baseline đo được Latency P95 là 678ms. Ngưỡng 3000ms (~4.4 lần baseline P95) là khoảng trễ chấp nhận được cho người dùng đối với các tác vụ sinh ngôn ngữ có RAG, đồng thời đủ nhạy để phát hiện sớm các sự cố RAG timeout hoặc RAG trễ (ví dụ incident `rag_slow` thêm 2.5s sẽ đẩy latency lên >3100ms và ngay lập tức vi phạm ngưỡng).
- **Cách tính error budget:**
  - Error Budget = $100\% - \text{SLO Target} = 100\% - 99.5\% = 0.5\%$.
  - Tức là trong cửa sổ đánh giá 28 ngày, hệ thống chỉ cho phép tối đa 0.5% tổng số request bị lỗi (HTTP 500) hoặc phản hồi chậm vượt quá 3000ms.
  - Ví dụ: Với 100,000 requests/tháng, Error Budget khả dụng là $100,000 \times 0.005 = 500$ request. Nếu số request vi phạm vượt quá 500, ngân sách lỗi bị âm (cạn kiệt), đội ngũ bắt buộc phải dừng release tính năng mới và ưu tiên giải quyết vấn đề độ trễ/độ ổn định.
- **Ba alert và runbook tương ứng:**
  - Được cấu hình trong `config/alert_rules.yaml` và xây dựng runbook chi tiết tại `docs/alerts.md`:
    1. `HighLatencyP95Symptom` (Warning): Kích hoạt khi `latency_p95 > 3000ms` kéo dài 3 phút. Kênh Slack `#alerts-llmops`. Runbook: Kiểm tra panel Latency, truy vết log chậm, mở Langfuse waterfall để phân biệt nghẽn ở bước retrieval hay generation; bật circuit breaker hoặc giảm max_tokens tạm thời.
    2. `ElevatedErrorRateSymptom` (Critical): Kích hoạt khi `error_rate_pct > 2%` kéo dài 2 phút. Kênh Slack `#alerts-llmops-critical`. Runbook: Kiểm tra error breakdown, lấy correlation_id từ `request_failed`, mở trace Langfuse để xác định span ném ngoại lệ; rollback prompt production nếu do prompt mới hoặc chuyển RAG sang fallback an toàn.
    3. `RetrievalSuccessDegradationSymptom` (Warning): Kích hoạt khi `retrieval_success_rate_pct < 90%` kéo dài 3 phút. Kênh Slack `#alerts-rag-team`. Runbook: Kiểm tra query text và log `tool_success == false`, khởi động lại vector store connector hoặc tạm thời nới lỏng semantic threshold.

## 7. Điều tra challenge

- **Challenge ID:** `day13-k4-l3a-monitoring-llmops-v1` (Cohort K4, seed 1311, affected_feature: `monitoring`, threshold: `2000ms`).
- **Khoảng thời gian điều tra:** `2026-09-29 09:15:40 UTC - 09:16:10 UTC` (khoảng 16:15 - 16:16 giờ địa phương Asia/Ho_Chi_Minh).
- **Triệu chứng từ metrics:**
  - Trên Dashboard (`http://127.0.0.1:8000/dashboard`) và endpoint `/metrics`, panel *Latency* ghi nhận Latency P95 tăng vọt bất thường từ mức bình thường ~665ms lên **2683.0 ms**, vi phạm nghiêm trọng ngưỡng trễ `latency_threshold_ms: 2000ms` được quy định trong `challenge.json`.
  - Đồng thời, TTFT P95 vẫn ở mức rất thấp (**61.0 ms**), Error Rate là **0%** (không có lỗi HTTP 500) và chi phí/token không tăng đột biến. Điều này chứng minh sự cố tắc nghẽn xảy ra ở giai đoạn trước khi gọi LLM (Pre-generation phase), không phải do mô hình LLM bị chậm sinh token.
- **Log line và correlation ID liên quan:**
  - Lọc log trong `data/logs.jsonl` tìm các request thuộc khung giờ sự cố mang feature `monitoring`, phát hiện request có `correlation_id` điển hình: **`req-4843336e`** (cùng các request liên quan: `req-15959939`, `req-88f62a80`, `req-6e4a88e2`, `req-4a8cc031`).
  - Dòng log `response_sent` thể hiện rõ độ trễ:
    ```json
    {"service": "api", "latency_ms": 2683, "ttft_ms": 61, "tokens_in": 36, "tokens_out": 107, "cost_usd": 0.001713, "quality_score": 0.9, "tool_name": "retrieval", "tool_success": true, "payload": {"answer_preview": "Starter answer. You should improve this output logic and add better quality chec..."}, "event": "response_sent", "env": "dev", "session_id": "k4-l3a-challenge-s04", "correlation_id": "req-4843336e", "model": "claude-sonnet-4-5", "user_id_hash": "4570299f37e2", "feature": "monitoring", "level": "info", "ts": "2026-09-29T09:15:53.652091Z"}
    ```
- **Trace ID và span gây ảnh hưởng:**
  - Tìm kiếm trace trên Langfuse Cloud theo `metadata.correlation_id == "req-4843336e"`.
  - Mở Trace Waterfall (Trace name: `day13-agent-request`):
    - Root observation `lab-agent-run`: tổng thời gian chạy là **2683 ms**.
    - Child span **`retrieve`** (`as_type="retriever"`): chiếm tới **2500 ms** (khoảng 93% tổng thời gian request).
    - Child span **`llm-generate`** (`as_type="generation"`): chỉ chiếm **150 ms** (TTFT 61 ms).
  - Kết luận: Span gây nghẽn trực tiếp là **`retrieve`**.
- **Root cause:**
  - Sự cố bắt nguồn từ module truy xuất dữ liệu RAG (`app/mock_rag.py`). Cờ sự cố `rag_slow` được bật trong hệ thống (`STATE["rag_slow"] = True`) khiến hàm `retrieve()` bị trễ cứng 2.5 giây (`time.sleep(2.5)`) đối với mọi truy vấn có chứa từ khóa hoặc feature `monitoring`. Trễ mạng/chậm I/O từ vector store làm bước retrieval bị nghẽn và kéo toàn bộ độ trễ của API vượt ngưỡng 2000ms.
- **Fix action:**
  - Tắt ngay sự cố bằng cách gửi request vô hiệu hóa: `POST /incidents/rag_slow/disable` (chạy script: `python scripts/inject_incident.py --disable`).
  - Cấu hình Timeout ngắn cho bước truy xuất (ví dụ `timeout = 1.5s`) kèm Fallback cache để khi vector store bị chậm, hệ thống tự động fallback sang corpus cục bộ nhằm trả lời ngay mà không để người dùng chờ đợi quá 2 giây.
- **Preventive measure:**
  - Áp dụng mẫu thiết kế **Circuit Breaker** cho vector store connector: tự động ngắt kết nối và fallback nếu tỷ lệ latency > 1500ms vượt quá 10% trong vòng 1 phút.
  - Xây dựng lớp **Semantic Caching** (Redis / In-memory cache) cho các truy vấn phổ biến về chính sách và monitoring để giảm thiểu 90% truy vấn trực tiếp vào vector database.
  - Thiết lập cảnh báo sớm **`HighLatencyP95Symptom`** gửi thông báo về Slack ngay khi P95 > 2000ms kéo dài quá 3 phút để đội ngũ on-call can thiệp trước khi ảnh hưởng đến SLO 28 ngày.

## 8. Giải thích và tự đánh giá

- **Một quyết định kỹ thuật quan trọng và lý do:**
  - Quyết định cài đặt bộ xử lý PII Scrubber đệ quy (`scrub_event`) ở tầng `structlog processor` chạy ngay trước `JsonlFileProcessor` và `JSONRenderer`.
  - *Lý do:* Đây là nguyên tắc phòng thủ đa tầng (Defense in Depth). Nếu chỉ scrub thủ công ở router `/chat` (như `summarize_text`), lập trình viên có thể vô tình log thêm biến mới hoặc ném exception chứa dữ liệu nhạy cảm ở các tầng sâu hơn. Bằng cách can thiệp tại structlog processor trước khi serialize JSON, 100% dữ liệu ghi xuống file hay console đều được đảm bảo không chứa PII thô.
- **Một lỗi/blocker đã gặp:**
  - Khi bắt đầu CP1, sau khi sửa code xong thì chạy `validate_logs.py` vẫn chỉ đạt điểm thấp vì file `data/logs.jsonl` vẫn chứa 20 dòng log cũ từ đợt baseline (không có correlation ID và enrichment). Ngoài ra, lúc đầu Langfuse báo lỗi `Prompt 'day13-chat' with label 'production' not found` do chưa tạo prompt trên cloud.
- **Cách tìm nguyên nhân và xử lý:**
  - Đối với log cũ: Đọc kỹ tài liệu [docs/GUIDE.md](docs/GUIDE.md) và [docs/CHECKPOINTS.md](docs/CHECKPOINTS.md), tiến hành backup log cũ sang `data/logs_baseline.jsonl`, xóa trắng file log đang chạy rồi phát tải mới. Sau đó validator lập tức đạt **100/100 điểm**.
  - Đối với prompt Langfuse: Viết script Python sử dụng Langfuse SDK v4 API (`client.create_prompt`) để khởi tạo chính thức prompt `day13-chat` version 1 (`baseline`, `production`) và version 2 (`candidate`) trực tiếp vào project cá nhân. Nhờ đó, ứng dụng kết nối lấy prompt thành công 100% mà không bị fallback.
- **Cách hiểu luồng Metrics → Logs → Traces:**
  - **1. Metrics (Triệu chứng & Thời điểm):** Trả lời câu hỏi *"Hệ thống có điều gì bất thường và xảy ra vào lúc nào?"*. Ví dụ: Khi nhìn Dashboard thấy panel Latency P95 vọt lên 2683ms lúc 16:15, kỹ sư biết ngay hệ thống đang bị chậm nghiêm trọng nhưng chưa biết request cụ thể nào.
  - **2. Logs (Xác định Request bị ảnh hưởng):** Trả lời câu hỏi *"Request nào và người dùng nào đang chịu lỗi?"*. Kỹ sư lọc `data/logs.jsonl` theo khung giờ 16:15 và `latency_ms > 2000`, tìm ra request cụ thể và trích xuất mã liên kết duy nhất `correlation_id` (ví dụ `req-4843336e`).
  - **3. Traces (Định vị Nguyên nhân Gốc rễ):** Trả lời câu hỏi *"Thành phần hay bước xử lý nào bên trong request là thủ phạm gây lỗi?"*. Dán `correlation_id` vào Langfuse để mở Trace Waterfall. Cây phân rã cho thấy span `retrieve` mất tới 2500ms trong khi `llm-generate` chỉ mất 150ms, chứng minh sự cố bắt nguồn từ vector store/RAG chứ không phải do mô hình LLM.
- **Vai trò của prompt version, token/cost, SLO hoặc rollback trong vận hành LLM:**
  - *Prompt Versioning & Rollback:* Trong LLMOps, prompt đóng vai trò như mã nguồn logic của ứng dụng. Việc quản lý phiên bản tập trung và gán nhãn (`baseline`, `candidate`, `production`) cho phép kiểm thử prompt mới an toàn. Khi phát hiện prompt mới gây suy giảm chất lượng hoặc hallucination, kỹ sư có thể rollback nhãn `production` về version trước trong vài giây mà không cần deploy lại code.
  - *Token & Cost Tracking:* Chi phí của LLM tính trực tiếp theo số token tiêu thụ. Theo dõi chi phí và token in/out theo thời gian thực giúp phát hiện sớm các tấn công lặp vô tận (denial-of-wallet) hoặc prompt injection làm bùng nổ độ dài ngữ cảnh.
  - *SLO & Error Budget:* Đặt ra ranh giới rõ ràng giữa độ tin cậy và tốc độ phát triển. Error budget là "ngân sách rủi ro" cho phép đội ngũ thử nghiệm prompt hoặc mô hình mới; khi ngân sách này cạn kiệt, mọi thay đổi phải tạm dừng để ưu tiên ổn định hệ thống.
- **Điều quan trọng nhất đã học:**
  - Hiểu và thực hành trọn vẹn văn hóa Observability trong AI Engineering: Từ việc bảo vệ dữ liệu người dùng (PII masking), chuẩn hóa log có correlation ID, dựng kiến trúc trace phân cấp cho đến quy trình điều tra sự cố khoa học dựa trên dữ liệu định lượng thay vì phỏng đoán cảm tính.
- **Hạn chế hoặc phần chưa hoàn thành, nếu có:**
  - Do bài lab chạy môi trường kiểm thử với FakeLLM và MockRAG, một số số liệu chi phí và độ trễ được giả lập. Trong môi trường thực tế quy mô lớn, cần tích hợp OpenTelemetry Collector chuyên dụng và kho lưu trữ vector database phân tán (như Qdrant / Pinecone) kèm hạ tầng Redis semantic cache.

## 9. Bonus Track (+10 điểm)

Học viên đã hoàn thiện 2 hạng mục Bonus theo đúng hướng dẫn tại [docs/RUBRIC.md](docs/RUBRIC.md) (Mục H):

### 9.1. Bonus 1: Automated Secret & PII Scanner (+5 điểm)
- **File triển khai:** [`scripts/scan_secrets_pii.py`](../scripts/scan_secrets_pii.py)
- **Unit test đi kèm:** [`tests/test_secret_scanner.py`](../tests/test_secret_scanner.py) (4/4 passed)
- **Mô tả chức năng:**
  - Tự động quét toàn diện cây mã nguồn, log files và cấu hình nhằm phát hiện rò rỉ:
    1. *API Keys & Secrets:* Langfuse secret key (`sk-lf-...`), OpenAI keys, GitHub tokens, AWS keys, Private keys.
    2. *Dữ liệu PII thô:* Số thẻ tín dụng 16 số, CCCD 12 số, số điện thoại Việt Nam, raw email.
    3. *Git index inspection:* Kiểm tra nghiêm ngặt xem `.env` hoặc `config/challenge.json` có vô tình bị theo dõi bởi git không.
  - Tích hợp chuẩn pre-commit hook hoặc CI/CD pipeline, trả về exit code `0` khi sạch và `1` khi phát hiện vi phạm.
- **Lệnh thực thi và kết quả:**
  ```powershell
  python scripts/scan_secrets_pii.py
  # Output: [PASS] SUCCESS: 0 secrets, 0 PII leaks detected. Repository is clean & safe to push!
  ```

### 9.2. Bonus 2: Dedicated Audit Logging System (+5 điểm)
- **File triển khai:**
  - Module ghi log: [`app/audit_logger.py`](../app/audit_logger.py)
  - CLI truy vấn: [`scripts/query_audit.py`](../scripts/query_audit.py)
  - Unit test đi kèm: [`tests/test_audit_logger.py`](../tests/test_audit_logger.py) (3/3 passed)
- **Đặc tả Schema chuẩn (`data/audit.jsonl`):**
  - `audit_id`: Mã định danh duy nhất chuẩn UUID `aud-<8-hex>`.
  - `ts`: Thời gian UTC chuẩn ISO 8601.
  - `actor`: Định danh tác nhân thực hiện (`admin`, `system`, hoặc `user_id_hash`).
  - `action`: Hành động nhạy cảm (`INCIDENT_ENABLE`, `INCIDENT_DISABLE`, `PROMPT_VERSION_PROMOTION`, `PROMPT_ACCESS`).
  - `resource`: Tài nguyên đích (`incident:rag_slow`, `prompt:day13-chat`).
  - `status`: Trạng thái thực thi (`SUCCESS`, `DENIED`, `FAILED`).
  - `client_ip`: Địa chỉ IP nguồn.
  - `details`: Metadata chi tiết về ngữ cảnh thực hiện.
- **Chính sách Retention:** Tự động cắt tỉa (prune) các bản ghi cũ khi vượt ngưỡng dung lượng (`apply_retention_policy(max_records=1000)`).
- **Lệnh truy vấn mẫu:**
  ```powershell
  python scripts/query_audit.py --summary
  python scripts/query_audit.py --action INCIDENT_DISABLE
  ```

## 10. Checklist trước khi nộp

- [x] Kết quả và evidence thuộc commit SHA cuối.
- [x] Tất cả ảnh/output mở được bằng đường dẫn tương đối.
- [x] Incident evidence nối đúng metric → log → trace.
- [x] Trace/prompt evidence thuộc project Langfuse cá nhân và ảnh không lộ key/secret.
- [x] Repository chạy lại được theo README.
- [x] Không có secret, API key, PII thô hoặc evidence của người khác/lớp khác.
- [ ] URL repo và commit SHA cuối đã được nộp trên LMS/Codelabs.
