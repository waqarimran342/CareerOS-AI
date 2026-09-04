---
kind: error_handling
name: Domain-Specific Exception Types with FastAPI HTTPException Translation
category: error_handling
scope:
    - '**'
source_files:
    - src/main.py
    - src/github_service.py
    - src/qwen_client.py
    - src/resume_service.py
---

## Error Handling Approach

CareerOS AI uses a layered exception strategy: each service layer defines its own domain-specific `Exception` subclass, and the FastAPI entry point (`src/main.py`) catches those exceptions to translate them into appropriate HTTP responses. There is no centralized error-handling middleware; instead, translation happens inline in the request handler.

### Domain-Specific Exceptions

- **`GitHubError`** (`src/github_service.py`): Raised for GitHub API failures — missing user (404), rate limiting (403 with zero remaining), invalid username, or any other non-200 response. A helper `_explain(response, username)` maps HTTP status codes to human-readable messages before raising.
- **`QwenError`** (`src/qwen_client.py`): Raised when the Qwen/Alibaba Cloud LLM call fails (auth errors, rate limits, timeouts via `openai.OpenAIError`) or when the model returns invalid JSON after two retry attempts. The constructor also raises it if `DASHSCOPE_API_KEY` is missing.
- **`ResumeError(ValueError)`** (`src/resume_service.py`): Subclasses `ValueError` to signal user-input problems — unreadable PDF, empty pages, scanned/image-only resumes, or excessive length truncation. Its docstring explicitly states that the API layer turns these into HTTP 400s.

### Handler-Level Translation in `main.py`

The `/api/analyze` endpoint wraps each external call in a `try/except` block:

| Layer | Exception Caught | HTTP Status | Rationale |
|---|---|---|---|
| Input validation | `HTTPException(400)` directly | 400 Bad Request | Missing/invalid form fields, wrong file type, oversized upload |
| Resume parsing | `ResumeError` | 400 Bad Request | User-supplied bad input |
| GitHub fetch | `GitHubError` | 502 Bad Gateway | External third-party failure |
| Agent pipeline / Qwen calls | `QwenError` | 502 Bad Gateway | External LLM provider failure |

Configuration errors (missing `DASHSCOPE_API_KEY`) are detected early and raise `HTTPException(503 Service Unavailable)`.

### Retry and Recovery Logic

- **LLM JSON repair**: `QwenClient.chat_json` retries once by re-sending the raw broken output back to Qwen with a prompt asking for valid JSON only. After two failed attempts it raises `QwenError` with the truncated raw output for diagnostics.
- **No global exception handler**: There is no FastAPI `exception_handler` decorator registered; all error-to-HTTP mapping is explicit per call site.

### Conventions Observed

1. **Service layers never return bare Python exceptions to callers** — they wrap underlying library errors in their own domain exception types so the caller can distinguish failure modes.
2. **User-facing vs. system failures are distinguished by HTTP status**: 4xx for client/input errors, 502 for downstream service failures, 503 for misconfiguration.
3. **Error messages are human-readable strings**, not structured objects; the message is passed through `detail=str(exc)` to the HTTP response.
4. **Validation errors are raised as `HTTPException` at the boundary** rather than propagated upward, keeping the handler self-contained.
5. **No `raise ... from` chaining is used** except inside `QwenClient`, where `OpenAIError` is chained onto `QwenError` via `from exc` to preserve the original traceback.