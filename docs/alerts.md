# Runbook cho Hệ thống Giám sát & Cảnh báo (Day 13 Monitoring & LLMOps)

Mỗi alert phải dựa trên triệu chứng người dùng hoặc vi phạm SLO, tuân thủ nguyên tắc SRE chuẩn.

## Alert 1

- **Tên:** HighLatencyP95Symptom
- **Severity:** warning
- **Duration:** 3m
- **Kênh thông báo:** Slack (#alerts-llmops)
- **SLI/SLO liên quan:** Primary SLO `fast_successful_requests` (SLI: latency_ms <= 3000ms trên 99.5% request).
- **Điều kiện và thời gian duy trì:** Latency P95 > 3000ms duy trì liên tục trong 3 phút.
- **Ảnh hưởng tới người dùng:** Người dùng trải nghiệm phản hồi chậm, thời gian chờ sinh câu trả lời kéo dài bất thường.
- **Ba bước kiểm tra đầu tiên:**
  1. Kiểm tra panel *Latency* trên Dashboard để xác định thời điểm bắt đầu trễ và xem TTFT P95 có tăng đồng thời không.
  2. Lọc file `data/logs.jsonl` tìm các log line `response_sent` có `latency_ms > 3000`, trích xuất `correlation_id`.
  3. Mở Langfuse tìm trace tương ứng qua `correlation_id`, kiểm tra waterfall xem nghẽn ở span `retrieve` hay span `llm-generate`.
- **Mitigation tạm thời:**
  - Nếu span `retrieve` chậm: kiểm tra trạng thái vector store / RAG cache; nếu vector store quá tải, kích hoạt circuit breaker hoặc chuyển sang local fallback corpus.
  - Nếu span `llm-generate` chậm: kiểm tra token output có tăng vọt không; tạm thời giảm `max_tokens` hoặc điều chỉnh timeout.
- **Owner:** oncall-llmops

## Alert 2

- **Tên:** ElevatedErrorRateSymptom
- **Severity:** critical
- **Duration:** 2m
- **Kênh thông báo:** Slack (#alerts-llmops-critical)
- **SLI/SLO liên quan:** Guardrail `error_rate_pct_max: 2` (Error rate tối đa không quá 2%).
- **Điều kiện và thời gian duy trì:** Tỷ lệ lỗi `error_rate_pct > 2%` kéo dài trong 2 phút.
- **Ảnh hưởng tới người dùng:** Người dùng nhận lỗi HTTP 500 hoặc thông báo gián đoạn dịch vụ, suy giảm độ khả dụng của API.
- **Ba bước kiểm tra đầu tiên:**
  1. Mở panel *Errors* trên Dashboard để xem phân bổ `error_type` (ví dụ `RuntimeError`, `TimeoutError`, v.v.).
  2. Lọc `data/logs.jsonl` tìm các event `request_failed`, ghi nhận `error_type` và thông báo lỗi trong `payload.detail`.
  3. Lấy `correlation_id` của request lỗi mở trace trên Langfuse để xác định span ném ngoại lệ.
- **Mitigation tạm thời:**
  - Nếu lỗi do vector store (ví dụ sự cố `tool_fail` timeout): chuyển RAG sang chế độ fallback hoặc trả câu trả lời mặc định an toàn.
  - Nếu lỗi do phiên bản prompt mới (prompt candidate bị lỗi): thực hiện rollback ngay label `production` về version trước đó trên Langfuse.
- **Owner:** oncall-llmops

## Alert 3

- **Tên:** RetrievalSuccessDegradationSymptom
- **Severity:** warning
- **Duration:** 3m
- **Kênh thông báo:** Slack (#alerts-rag-team)
- **SLI/SLO liên quan:** Guardrail `retrieval_success_rate_pct_min: 90` (Tỷ lệ truy xuất tài liệu thành công tối thiểu 90%).
- **Điều kiện và thời gian duy trì:** Tỷ lệ truy xuất thành công `retrieval_success_rate_pct < 90%` trong 3 phút.
- **Ảnh hưởng tới người dùng:** Chatbot trả lời chung chung (fallback answers), suy giảm chất lượng câu trả lời vì thiếu tài liệu ngữ cảnh chính xác.
- **Ba bước kiểm tra đầu tiên:**
  1. Kiểm tra panel *Errors / Retrieval Success* trên Dashboard để xác nhận tỷ lệ truy xuất thành công.
  2. Truy vấn logs với `tool_name == "retrieval"` và `tool_success == false` trong `data/logs.jsonl`.
  3. Mở trace trên Langfuse xem span `retrieve`, kiểm tra query text và thông số `doc_count`.
- **Mitigation tạm thời:**
  - Khởi động lại service RAG/vector store connector hoặc flush cache.
  - Tạm thời nới lỏng semantic similarity threshold nếu vector search bị quá chặt chẽ.
- **Owner:** oncall-rag-team
