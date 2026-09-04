---
kind: configuration_system
name: Environment-Driven Settings via python-dotenv and a Flat Settings Class
category: configuration_system
scope:
    - '**'
source_files:
    - src/config.py
    - .env.example
    - src/main.py
---

## What system/approach is used

The application uses a minimal, flat configuration system built on `python-dotenv` and Python's `os.getenv`. There is no YAML/JSON/TOML config file format, no Pydantic settings model, and no centralized config server. All runtime values — secrets (API keys), feature toggles, service endpoints, and server tuning — are read from environment variables, with a local `.env` file auto-loaded at import time.

## Key files and packages

- `src/config.py` — the single source of truth for all configuration. Defines a `Settings` class whose attributes map one-to-one to environment variables, plus a module-level `settings` singleton and an `is_qwen_configured()` helper.
- `.env.example` — the canonical template of every supported environment variable, with comments explaining purpose, defaults, and where to obtain credentials.
- `src/main.py` — FastAPI entry point that consumes `config.settings` to initialize the app metadata (`app_name`, `app_version`, `qwen_model`) and to start uvicorn on `api_host` / `api_port`.
- `src/qwen_client.py`, `src/github_service.py`, `src/resume_service.py` — consume `config.settings` for per-service timeouts, tokens, and limits (e.g. `max_resume_mb`, `github_timeout_seconds`).

## Architecture and conventions

1. **Single load point.** On import, `config.py` computes `BASE_DIR = Path(__file__).resolve().parent.parent` (the project root) and calls `load_dotenv(BASE_DIR / ".env")`. This lets the app be launched either from the repo root or from `src/` and still find `.env`.
2. **Flat `Settings` class.** Every setting is a class attribute with a default obtained via `os.getenv("VAR", default_value)`. Types are enforced by casting inside the call: `int(...)`, `float(...)`, `bool(...)`.
3. **Secrets-only env vars.** Sensitive values (`DASHSCOPE_API_KEY`, `GITHUB_TOKEN`) have empty-string defaults; non-secret tuning knobs (`QWEN_MODEL`, `QWEN_TEMPERATURE`, `MAX_RESUME_MB`, `API_HOST`, `API_PORT`) carry sensible defaults so the app runs out-of-the-box.
4. **Module-level singleton.** `settings = Settings()` is imported wherever needed; there is no dependency injection for configuration.
5. **Capability probe.** `is_qwen_configured()` returns `True` when `dashscope_api_key` is non-empty, and `main.py` uses it in both the `/health` endpoint and the `/api/analyze` guard to return a 503 with instructions to copy `.env.example` to `.env`.
6. **`.env` is gitignored.** The `.env.example` header explicitly instructs users to copy it to `.env` and never commit real keys; `.gitignore` already excludes `.env`.
7. **Defaults mirror documentation.** Every variable in `.env.example` has a matching attribute in `Settings` with the same default value, keeping the example file and code in lockstep.

## Conventions and constraints

- **No hard-coded secrets.** The docstring in `config.py` states: "Never hard-code API keys in source code." All secrets must come from environment variables.
- **One `.env` per deployment.** The loader expects exactly one `.env` at the project root; there is no precedence chain (no `.env.local`, no per-environment overrides).
- **Variables are case-sensitive and uppercase.** All env var names follow UPPER_SNAKE_CASE (`DASHSCOPE_API_KEY`, `QWEN_BASE_URL`, `GITHUB_TOKEN`, `API_HOST`, `API_PORT`, etc.).
- **Type coercion happens at read time.** Missing numeric env vars raise `ValueError` during import because `int(os.getenv(...))` is called eagerly — misconfigured types will fail fast at startup rather than at request time.
- **Optional vs required distinction is semantic only.** There is no validation schema; `DASHSCOPE_API_KEY` defaults to `""` and is checked later by `is_qwen_configured()`. A missing key does not crash startup but causes the analyze endpoint to return HTTP 503.
- **Configuration is immutable at runtime.** Because `Settings` is a plain class instantiated once at import, changing `os.environ` after import has no effect on `settings` attributes.
- **Server binding defaults are development-oriented.** `API_HOST=127.0.0.1` and `API_PORT=8000` are intended for local dev; production deployments should override these via environment.