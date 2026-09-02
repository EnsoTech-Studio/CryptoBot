# Đặc tả: Python News Collection và Adaptive Extraction

Trạng thái: Python canonical; deterministic RSS/HTML + direct typed LLM fallback implemented; agent-tool fallback là P1 target gap
Owner: Python `research`  
Nguồn: `[SRC]` news Collect -> Store -> Analyze và `[SRC-ADD]` resilient HTML extraction

## Mô tả

News Pipeline thu thập từ approved RSS/HTML sources, lưu document/item có provenance,
gắn coin tag và chuyển validated content sang Sentiment orchestration. Khi website đổi HTML,
current `HtmlNewsProvider` parser chạy trước; quality failure gọi trực tiếp typed
`NewsExtractionHTTPAdapter` trên document đã sanitize. Agent/tool orchestration là P1 target.

```text
Approved Source
  -> provider HTTPS guards
  -> RSS normalize hoặc HTML parser trong provider
  -> Content Quality Gate
       -> pass: normalize
       -> fail: direct typed AI extraction on sanitized text (current)
  -> schema + quality validation
  -> content/model/prompt/schema hash cache
  -> deterministic coin tagging + optional structured model tagging
  -> sentiment via internal AI adapter
```

Go không sở hữu crawler/parser/news worker/domain tables. Browser query news qua Go public
edge; Go proxy authorized query tới Python và không parse article.

## Source contract

`ApprovedSource` là server/operator configuration, không phải URL tùy ý từ browser:

```json
{
  "id": "01J_SOURCE",
  "source_key": "coindesk",
  "kind": "rss",
  "allowed_origin": "https://www.coindesk.com",
  "url_template": "https://www.coindesk.com/arc/outboundfeeds/rss/",
  "is_active": true
}
```

Source update chỉ ADMIN/operator; config change audited và versioned.

## Current implementation alignment

`app/news_worker.py` constructs `NewsService` with a provider map:
`{"rss": RssNewsProvider(), "url": HtmlNewsProvider()}`. There is no
`NewsSourceRegistry`, `SafeFetcher`, `ReadabilityExtractor`, `ContentQualityGate`,
`NewsTagger` or `NewsExtractionAgent` class in the current runtime. HTTPS/origin/
DNS/redirect/size/type guards are provider/module functions; HTML parsing is
`HtmlNewsProvider._ArticleParser`; quality failure is `HtmlQualityGateFailed`.

After that exception, `NewsService._fallback_item()` calls the typed
`NewsExtractionHTTPAdapter` directly with sanitized document text, validates title/body
evidence, and persists the extraction cache. The five-tool agent fallback described
below remains a P1 target.

The sections below describe the target P1 extension contract. They must not be read as
the current class/module topology unless the current-alignment section says so.

## Safe Fetcher target contract

Network chỉ nằm trong deterministic infrastructure fetcher. Mỗi request/redirect:

1. Parse URL và require HTTPS.
2. Match exact configured origin/path policy.
3. Resolve DNS; reject loopback/private/link-local/multicast/reserved/cloud metadata IP.
4. Connect tới resolved allowed IP, giữ Host/SNI đúng origin.
5. Revalidate redirect target từ bước 1; không forward credential/cookie.
6. Enforce method GET, timeout, max redirects, max bytes, content type và decompressed-size limit.
7. Normalize encoding, remove script/style/iframe/form/event handlers và unsafe URL.
8. Persist sanitized document, final URL, response metadata và SHA-256 content hash.

Agent/model không nhận URL/browser/fetch tool. Nó chỉ nhận `document_id` và sanitized content
qua typed read tool.

## Document và item contract

```json
{
  "document_id": "01J_DOC",
  "source_id": "coindesk",
  "requested_url": "https://www.coindesk.com/article",
  "final_url": "https://www.coindesk.com/article",
  "fetched_at": "2026-08-27T02:00:00Z",
  "content_type": "text/html",
  "content_hash": "sha256:...",
  "sanitizer_version": "sanitize/v1",
  "status": "sanitized"
}
```

```json
{
  "news_item_id": "01J_NEWS",
  "source_id": "coindesk",
  "canonical_url": "https://www.coindesk.com/article",
  "title": "Bitcoin market update",
  "body_text": "Validated normalized content",
  "author": "Reporter",
  "published_at": "2026-08-27T01:30:00Z",
  "related_coins": ["BTC"],
  "document_content_hash": "sha256:...",
  "extraction": {
    "method": "readability",
    "schema_version": "news-item/v1",
    "extractor_version": "readability/v1",
    "model_version": null,
    "prompt_version": null,
    "quality_score": 0.92
  }
}
```

LLM fallback dùng `method = llm_fallback` và bắt buộc model/prompt/tool-policy/output hashes.

## Deterministic extraction

RSS/API parser dùng schema/field mapping theo provider adapter. HTML dùng generic Readability
extractor, structured metadata (`article`, JSON-LD/OpenGraph) và text normalization; không
selector tree cứng cho từng website ở domain core.

Content Quality Gate deterministic đánh giá:

- Title/body required và length bounds.
- Text/markup ratio.
- Duplicate/navigation/boilerplate ratio.
- Language/encoding validity.
- Published time confidence/bounds.
- Article-content markers.
- Known error/paywall/challenge page signature.

Threshold và feature version persist. Gate pass đi thẳng normalize/cache; không gọi model.

## NewsExtractionAgent fallback

Chỉ orchestrator được tạo fallback run sau quality fail evidence. Allowed tools:

- `document.get_sanitized_html`
- `document.get_extraction_errors`
- `news.get_item_schema`
- `news.validate_extraction`
- `news.save_extraction`

Agent trả structured fields + source spans/evidence reference. `news.validate_extraction` kiểm:

- Output JSON Schema.
- Title/body/published time bounds.
- Trường trích xuất có evidence trong sanitized content.
- Không thêm facts không xuất hiện trong source.
- Canonical URL vẫn là Safe Fetcher result, agent không tự sửa origin.
- Quality score sau extraction đạt threshold.

Invalid fallback persist failure; không bịa item để pipeline tiếp tục.

## Cache và de-dup

### Document cache key

`(source_id, final_url, content_hash, sanitizer_version)`.

### Extraction cache key

```text
sha256(
  document_content_hash
  + extraction_method
  + extractor_or_model_version
  + prompt_version
  + schema_version
  + quality_policy_version
)
```

### News item de-dup

Ưu tiên canonical URL + published identity; fallback title/body normalized hash trong bounded
time window. Duplicate collection không overwrite validated item/provenance; link collection
attempt tới existing item.

## Tagging

Deterministic alias/symbol rules chạy trước (`Bitcoin`, `BTC`, `$BTC`). Optional structured
model tagging chỉ nhận validated item text, output coin IDs từ allowed catalog và có
model/prompt/schema provenance. Unknown coin không tự thêm market pair.

Tagging và extraction là hai task khác: extraction agent không suy luận sentiment/trade signal.

## Sentiment hand-off

Chỉ validated `news_item_id`/content hash được đưa vào Sentiment orchestration. AI Adapter trả
structured inference; Python validate/persist. Model unavailable để sentiment null/unavailable;
không fake `NEUTRAL`. Chi tiết ở `sentiment.md`.

## Luồng chính

1. Python scheduler claim source job với bounded concurrency/rate policy.
2. Provider thực hiện HTTPS/origin/DNS/redirect/size/type guards và chuẩn hóa payload.
3. `RssNewsProvider` hoặc `HtmlNewsProvider` parse deterministic.
4. HTML quality failure -> direct typed `NewsExtractionHTTPAdapter` trên text đã sanitize.
5. Extraction result cache/persist idempotently.
6. Coin tagger chạy deterministic; sentiment worker xử lý asynchronously.
7. Persist item + `news.collected` outbox atomically.
8. Go query/fan-out persisted summary; chart/backtest technical không phụ thuộc news success.

Agent/tool fallback năm tool vẫn là target P1; không phải bước runtime hiện tại.

## Persistence

Python-owned:

- `news_sources`: approved config/version/status.
- `news_fetch_attempts`: request/final URL, DNS/IP evidence, status/error/latency.
- `news_documents`: sanitized object/hash/metadata.
- `news_extraction_attempts`: method/version/quality/features/model/prompt/result/evidence.
- `news_items`: validated normalized fields/content hash.
- `news_item_tags`: coin/tagger version/provenance.
- `news_sentiments`: separate immutable model result.
- Python outbox/event consumption state.

Raw/sanitized large HTML lưu content-addressed object store hoặc compressed DB artifact theo
retention policy; API/event không trả raw HTML cho browser.

## Kịch bản lỗi

| Tình huống | Phản ứng |
|---|---|
| DNS/private IP/redirect SSRF | Block fetch và audit; không gọi agent |
| Response quá lớn/wrong type | Abort bounded stream, persist failure |
| Malformed RSS/API | Adapter parse fail isolated |
| HTML tree đổi | Readability + Quality Gate; conditional LLM fallback |
| Challenge/paywall page | Quality fail; fallback chỉ lưu nếu evidence/quality valid |
| Prompt injection trong article | Content là data; không đổi tool/policy |
| Agent hallucinate field | Validation/evidence fail; không save item |
| Model timeout/down | Persist unavailable; deterministic sources khác vẫn chạy |
| Duplicate content | Return/reuse existing extraction/item idempotently |
| DB unavailable | Không emit collected event trước commit |
| One source repeatedly fails | Circuit/backoff per source; sources khác không bị dừng |

## Security và resource limits

- No browser-supplied arbitrary source URL.
- HTTPS allowlist + re-resolve/revalidate mọi redirect.
- No cookie/auth forwarding.
- Bounded bytes/decompression/time/concurrency.
- Sanitize trước persistence/agent/model.
- Agent no HTTP/shell/SQL/filesystem/secret.
- Raw content không render unsanitized trên UI.
- Prompt/source/model output size bounded và auditable.

## Observability

Metrics:

- `news_fetch_total{source,status}`
- `news_fetch_latency_seconds{source}`
- `news_extraction_total{method,status}`
- `news_quality_gate_total{decision,policy_version}`
- `news_llm_fallback_total{model,status}`
- `news_extraction_cache_total{result}`
- `news_pipeline_lag_seconds{stage}`

Không label URL/document/item ID. Correlation fields nằm log/trace/evidence.

## Tiêu chí chấp nhận

- [ ] AC-01: Private/loopback/link-local/metadata IP bị chặn trước connection.
- [ ] AC-02: Redirect được DNS/IP/origin revalidate từng hop.
- [ ] AC-03: Size/type/decompression/time limits có fixture.
- [ ] AC-04: Sanitizer loại executable/unsafe HTML trước agent/UI.
- [ ] AC-05: Readability path pass không gọi LLM.
- [ ] AC-06: HTML tree drift fixture làm quality fail và kích hoạt fallback.
- [ ] AC-07: NewsExtractionAgent chỉ có 5 tools, không có URL fetch.
- [ ] AC-08: Hallucinated field/source span fail validation.
- [ ] AC-09: Cache key đổi khi content/model/prompt/schema/policy version đổi.
- [ ] AC-10: Duplicate fetch/extraction không tạo duplicate item/event.
- [ ] AC-11: Model down để extraction/sentiment unavailable rõ ràng, không fake content/NEUTRAL.
- [ ] AC-12: News source failure không ảnh hưởng chart hoặc technical backtest.
- [ ] AC-13: Architecture test chứng minh Go không sở hữu news parser/worker/tables.
- [ ] AC-14: Audit truy được source -> fetch -> document -> extraction -> tag -> sentiment.

## Implementation status

Python news service seam đã tồn tại, nhưng complete Safe HTML Fetcher, deterministic quality
gate, NewsExtractionAgent/tool handlers và content/model/prompt cache cần code/test evidence
trước khi requirement adaptive extraction được đánh dấu `Implemented` hoặc `Verified`.
