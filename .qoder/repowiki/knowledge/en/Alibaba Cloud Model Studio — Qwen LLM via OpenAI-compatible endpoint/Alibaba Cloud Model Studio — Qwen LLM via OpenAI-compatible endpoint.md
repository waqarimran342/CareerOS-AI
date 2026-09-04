---
kind: external_dependency
name: Alibaba Cloud Model Studio — Qwen LLM via OpenAI-compatible endpoint
slug: alibaba-cloud-model-studio-qwen
category: external_dependency
category_hints:
    - vendor_identity
    - sdk_real_api
    - client_constraint
scope:
    - '**'
---

### Identity & role
- The LLM provider is Alibaba Cloud Model Studio exposing Qwen models through an OpenAI-compatible HTTP API; all five agents call it via the `openai` SDK.
- Configured through `DASHSCOPE_API_KEY` plus a base URL (`QWEN_BASE_URL`) that defaults to the international endpoint `https://dashscope-intl.aliyuncs.com/compatible-mode/v1`; mainland-China accounts must switch to `https://dashscope.aliyuncs.com/compatible-mode/v1`.
- Default model is `qwen-plus`; `qwen-turbo` and `qwen-max` are also supported.

### Integration shape
- `src/qwen_client.py` wraps the `openai` SDK against the DashScope base URL; prompts are strict-JSON with markdown-fence stripping and one self-repair retry before surfacing a `QwenError`.
- All agent calls go through this wrapper — never call the OpenAI SDK directly elsewhere in the codebase.

### Client constraint
- Endpoint selection is region-bound: international vs mainland-China endpoints are mutually exclusive per account type; using the wrong base URL will cause authentication or routing failures even with a valid key.