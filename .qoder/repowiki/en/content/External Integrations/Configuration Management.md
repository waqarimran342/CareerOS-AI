# Configuration Management

<cite>
**Referenced Files in This Document**
- [config.py](file://src/config.py)
- [main.py](file://src/main.py)
- [qwen_client.py](file://src/qwen_client.py)
- [github_service.py](file://src/github_service.py)
- [resume_service.py](file://src/resume_service.py)
- [.env.example](file://.env.example)
- [.gitignore](file://.gitignore)
- [README.md](file://README.md)
</cite>

## Table of Contents
1. [Introduction](#introduction)
2. [Project Structure](#project-structure)
3. [Core Components](#core-components)
4. [Architecture Overview](#architecture-overview)
5. [Detailed Component Analysis](#detailed-component-analysis)
6. [Dependency Analysis](#dependency-analysis)
7. [Performance Considerations](#performance-considerations)
8. [Troubleshooting Guide](#troubleshooting-guide)
9. [Conclusion](#conclusion)
10. [Appendices](#appendices)

## Introduction
This document explains the centralized configuration management system for CareerOS AI. It focuses on how environment-based settings are loaded and consumed across the application using python-dotenv, with a focus on type-safe configuration loading, default values, environment variable mapping for external services (Qwen API keys, GitHub tokens, service endpoints), secure credential handling, naming conventions, validation mechanisms, .env structure, environment-specific examples, override behavior, hot-reloading considerations, debugging tools, adding new parameters, and troubleshooting common issues.

## Project Structure
The configuration is centralized in a single module that loads environment variables at import time and exposes a shared Settings instance used by all components. The FastAPI app reads from this central source to configure itself and validate runtime readiness.

```mermaid
graph TB
A[".env file<br/>loaded by dotenv"] --> B["Settings class<br/>reads env vars + defaults"]
B --> C["FastAPI app<br/>title/version/health"]
B --> D["QwenClient<br/>LLM calls"]
B --> E["GitHubService<br/>REST API calls"]
B --> F["ResumeService<br/>PDF parsing limits"]
```

**Diagram sources**
- [config.py:11-20](file://src/config.py#L11-L20)
- [config.py:23-73](file://src/config.py#L23-L73)
- [main.py:28-36](file://src/main.py#L28-L36)
- [qwen_client.py:70-95](file://src/qwen_client.py#L70-L95)
- [github_service.py:26-45](file://src/github_service.py#L26-L45)
- [resume_service.py:51-55](file://src/resume_service.py#L51-L55)

**Section sources**
- [config.py:11-20](file://src/config.py#L11-L20)
- [main.py:28-36](file://src/main.py#L28-L36)

## Core Components
- Settings class: A flat, typed container for all configuration values. Each attribute maps to an environment variable with sensible defaults. Types are enforced via Python’s type hints and explicit casting where needed.
- Shared instance: A single global settings object is created at import time and reused throughout the application.
- Environment loading: dotenv loads .env from the project root when config.py is imported, ensuring credentials are available before any other module runs.

Key responsibilities:
- Provide consistent access to configuration across modules.
- Centralize defaults and environment mappings.
- Expose helper functions to check configuration readiness (e.g., Qwen availability).

**Section sources**
- [config.py:23-73](file://src/config.py#L23-L73)
- [config.py:76-78](file://src/config.py#L76-L78)

## Architecture Overview
Configuration flows from environment files into a single source of truth, then propagates to services and the web server.

```mermaid
sequenceDiagram
participant Dev as "Developer"
participant Dotenv as "dotenv.load_dotenv"
participant Config as "Settings (config.py)"
participant App as "FastAPI (main.py)"
participant Qwen as "QwenClient"
participant GH as "GitHubService"
participant Resume as "ResumeService"
Dev->>Dotenv : Start app
Dotenv-->>Config : Load .env into process env
Config->>Config : Build Settings with defaults + env
App->>Config : Read app_name, version, model, etc.
App->>App : Configure FastAPI title/version
App->>Qwen : Create client (uses config.settings)
App->>GH : Fetch profile (uses config.settings)
App->>Resume : Extract text (uses config.settings)
```

**Diagram sources**
- [config.py:11-20](file://src/config.py#L11-L20)
- [config.py:23-73](file://src/config.py#L23-L73)
- [main.py:28-36](file://src/main.py#L28-L36)
- [qwen_client.py:70-95](file://src/qwen_client.py#L70-L95)
- [github_service.py:26-45](file://src/github_service.py#L26-L45)
- [resume_service.py:51-55](file://src/resume_service.py#L51-L55)

## Detailed Component Analysis

### Settings Class and Type-Safe Loading
- Purpose: Centralized, typed configuration with defaults and environment overrides.
- Behavior:
  - Loads .env from the project root on import.
  - Reads environment variables with fallback defaults.
  - Casts numeric types explicitly to ensure runtime safety.
  - Provides a helper to detect if Qwen is configured.

Environment variables mapped:
- Qwen / Alibaba Cloud Model Studio:
  - DASHSCOPE_API_KEY: Required API key string.
  - QWEN_BASE_URL: Base URL for OpenAI-compatible endpoint.
  - QWEN_MODEL: Model name (e.g., qwen-plus).
  - QWEN_TEMPERATURE: Sampling temperature (float).
  - QWEN_MAX_TOKENS: Maximum tokens per response (int).
  - QWEN_TIMEOUT: Timeout in seconds (int).
- GitHub:
  - GITHUB_TOKEN: Optional personal access token.
  - GITHUB_TIMEOUT: Timeout in seconds (int).
  - GITHUB_MAX_REPOS: Number of top repos to analyze (int).
- Upload limits:
  - MAX_RESUME_MB: Max resume size in MB (float).
  - MAX_RESUME_CHARS: Max resume text length (int).
- Server:
  - API_HOST: Host address (string).
  - API_PORT: Port number (int).

Validation and checks:
- is_qwen_configured(): Returns True if a non-empty API key is present.
- Runtime checks in main.py raise HTTP 503 when Qwen is not configured.

Type safety:
- Numeric fields use int() or float() casts to enforce types.
- String fields rely on os.getenv with empty-string defaults.

Security:
- Secrets are never hard-coded; they come from environment variables.
- .env is excluded from version control.

**Section sources**
- [config.py:11-20](file://src/config.py#L11-L20)
- [config.py:23-73](file://src/config.py#L23-L73)
- [config.py:76-78](file://src/config.py#L76-L78)
- [main.py:100-107](file://src/main.py#L100-L107)

### Qwen Client Integration
- Uses config.settings for API key, base URL, model, temperature, max tokens, and timeout.
- Raises a clear error if the API key is missing.
- Wraps LLM calls and handles JSON parsing robustly.

```mermaid
classDiagram
class QwenClient {
+api_key : str
+base_url : str
+model : str
+temperature : float
+max_tokens : int
+__init__(api_key, base_url, model)
+chat_json(agent_name, system_prompt, user_prompt, temperature, max_tokens) Dict
}
class Settings {
+dashscope_api_key : str
+qwen_base_url : str
+qwen_model : str
+qwen_temperature : float
+qwen_max_tokens : int
+qwen_timeout_seconds : int
}
QwenClient --> Settings : "reads config"
```

**Diagram sources**
- [qwen_client.py:70-95](file://src/qwen_client.py#L70-L95)
- [config.py:23-73](file://src/config.py#L23-L73)

**Section sources**
- [qwen_client.py:70-95](file://src/qwen_client.py#L70-L95)
- [qwen_client.py:120-157](file://src/qwen_client.py#L120-L157)

### GitHub Service Integration
- Reads optional GITHUB_TOKEN to add Authorization headers.
- Uses config.settings for timeouts and maximum repositories to analyze.
- Converts API errors into friendly exceptions with actionable messages.

```mermaid
flowchart TD
Start(["fetch_profile(username)"]) --> Validate["Validate username"]
Validate --> CallProfile["GET /users/{username}"]
CallProfile --> ProfileOK{"Status 200?"}
ProfileOK --> |No| ExplainProfile["Raise GitHubError with message"]
ProfileOK --> |Yes| CallRepos["GET /users/{username}/repos?per_page=100&sort=pushed"]
CallRepos --> ReposOK{"Status 200?"}
ReposOK --> |No| ExplainRepos["Raise GitHubError with message"]
ReposOK --> |Yes| Summarize["Build summary using config.settings.github_max_repos"]
Summarize --> End(["Return profile dict"])
```

**Diagram sources**
- [github_service.py:63-89](file://src/github_service.py#L63-L89)
- [github_service.py:92-147](file://src/github_service.py#L92-L147)
- [github_service.py:26-45](file://src/github_service.py#L26-L45)

**Section sources**
- [github_service.py:26-45](file://src/github_service.py#L26-L45)
- [github_service.py:63-89](file://src/github_service.py#L63-L89)
- [github_service.py:92-147](file://src/github_service.py#L92-L147)

### Resume Service Integration
- Enforces character limit for extracted resume text using config.settings.max_resume_chars.
- Truncates long resumes to control prompt size and cost.

**Section sources**
- [resume_service.py:51-55](file://src/resume_service.py#L51-L55)

### FastAPI Application Usage
- Sets app title and version from config.settings.
- Health endpoint reports current model and whether Qwen/GitHub are configured.
- Analyze endpoint validates inputs, enforces upload limits, checks Qwen configuration, and orchestrates analysis.

```mermaid
sequenceDiagram
participant Client as "Client"
participant API as "FastAPI (/api/analyze)"
participant CFG as "config.settings"
participant Resume as "ResumeService"
participant GH as "GitHubService"
participant Q as "QwenClient"
Client->>API : POST /api/analyze (resume, github_username, target_role, job_description)
API->>CFG : Read max_resume_mb, qwen_model, is_qwen_configured()
API->>API : Validate inputs & size
API->>Resume : extract_text_from_pdf(resume_bytes)
Resume-->>API : text (truncated if needed)
API->>GH : fetch_profile(github_username)
GH-->>API : profile summary
API->>Q : run_full_analysis(...)
Q-->>API : results
API-->>Client : success response
```

**Diagram sources**
- [main.py:58-147](file://src/main.py#L58-L147)
- [config.py:23-73](file://src/config.py#L23-L73)
- [resume_service.py:24-57](file://src/resume_service.py#L24-L57)
- [github_service.py:63-89](file://src/github_service.py#L63-L89)
- [qwen_client.py:70-95](file://src/qwen_client.py#L70-L95)

**Section sources**
- [main.py:28-36](file://src/main.py#L28-L36)
- [main.py:45-55](file://src/main.py#L45-L55)
- [main.py:58-147](file://src/main.py#L58-L147)

## Dependency Analysis
- All modules depend on the central config module for configuration.
- No circular dependencies observed; config has no imports beyond standard library and dotenv.
- External integrations (OpenAI SDK, requests, pypdf) are isolated within their respective modules and consume configuration through config.settings.

```mermaid
graph LR
CFG["config.Settings"] --> MAIN["main.py"]
CFG --> QWEN["qwen_client.py"]
CFG --> GH["github_service.py"]
CFG --> RES["resume_service.py"]
QWEN --> EXT1["openai SDK"]
GH --> EXT2["requests"]
RES --> EXT3["pypdf"]
```

**Diagram sources**
- [config.py:11-20](file://src/config.py#L11-L20)
- [main.py:17-21](file://src/main.py#L17-L21)
- [qwen_client.py:18-24](file://src/qwen_client.py#L18-L24)
- [github_service.py:12-17](file://src/github_service.py#L12-L17)
- [resume_service.py:9-14](file://src/resume_service.py#L9-L14)

**Section sources**
- [config.py:11-20](file://src/config.py#L11-L20)
- [main.py:17-21](file://src/main.py#L17-L21)

## Performance Considerations
- Timeouts:
  - QWEN_TIMEOUT controls LLM call timeouts to prevent hanging requests.
  - GITHUB_TIMEOUT controls REST API timeouts.
- Token limits:
  - QWEN_MAX_TOKENS caps response size to manage cost and latency.
- Input limits:
  - MAX_RESUME_MB prevents oversized uploads.
  - MAX_RESUME_CHARS truncates very long resumes to reduce processing time and cost.
- GitHub rate limiting:
  - Use GITHUB_TOKEN to increase rate limits from 60 to 5000 requests/hour.

[No sources needed since this section provides general guidance]

## Troubleshooting Guide
Common issues and resolutions:

- Missing Qwen API key:
  - Symptom: Health endpoint shows Qwen not configured; /api/analyze returns 503.
  - Resolution: Set DASHSCOPE_API_KEY in .env and restart the app.
  - Reference: [config.py:76-78](file://src/config.py#L76-L78), [main.py:100-107](file://src/main.py#L100-L107)

- Invalid or unreachable Qwen endpoint:
  - Symptom: QwenError with network/auth details.
  - Resolution: Verify QWEN_BASE_URL and network connectivity; adjust QWEN_TIMEOUT if needed.
  - Reference: [qwen_client.py:120-157](file://src/qwen_client.py#L120-L157)

- GitHub rate limit exceeded:
  - Symptom: GitHubError indicating rate limit reached.
  - Resolution: Add GITHUB_TOKEN to .env to raise limits; retry later.
  - Reference: [github_service.py:48-60](file://src/github_service.py#L48-L60)

- Invalid resume file:
  - Symptom: HTTP 400 with details about unsupported PDF or empty content.
  - Resolution: Ensure the uploaded file is a valid, text-based PDF; check MAX_RESUME_MB and MAX_RESUME_CHARS.
  - Reference: [resume_service.py:24-57](file://src/resume_service.py#L24-L57)

- Wrong types in environment variables:
  - Symptom: Runtime errors due to invalid numeric strings.
  - Resolution: Ensure numeric env vars are valid integers/floats; defaults are applied if missing.
  - Reference: [config.py:44-69](file://src/config.py#L44-L69)

- Hot-reloading note:
  - Uvicorn is started with reload=False in development entry point. If you need hot-reload during development, enable it in your uvicorn invocation; however, note that reloading will re-import config and re-read .env each time.
  - Reference: [main.py:150-159](file://src/main.py#L150-L159)

**Section sources**
- [config.py:76-78](file://src/config.py#L76-L78)
- [main.py:100-107](file://src/main.py#L100-L107)
- [qwen_client.py:120-157](file://src/qwen_client.py#L120-L157)
- [github_service.py:48-60](file://src/github_service.py#L48-L60)
- [resume_service.py:24-57](file://src/resume_service.py#L24-L57)
- [config.py:44-69](file://src/config.py#L44-L69)
- [main.py:150-159](file://src/main.py#L150-L159)

## Conclusion
The configuration system centralizes all environment-based settings behind a simple, typed Settings class. It ensures secure handling of secrets, provides sensible defaults, and offers clear diagnostics for misconfiguration. Services consume configuration consistently, enabling predictable behavior across development and production environments.

[No sources needed since this section summarizes without analyzing specific files]

## Appendices

### .env File Structure and Examples
- Location: Project root .env file is automatically loaded by config.py.
- Template: See .env.example for all supported variables and comments.
- Security: .env is ignored by Git to prevent accidental commits of secrets.

Environment variable reference:
- DASHSCOPE_API_KEY: Required. Your Alibaba Cloud Model Studio API key.
- QWEN_BASE_URL: International or mainland-China endpoint URL.
- QWEN_MODEL: Model name (qwen-turbo, qwen-plus, qwen-max).
- QWEN_TEMPERATURE: Float sampling parameter.
- QWEN_MAX_TOKENS: Integer token cap.
- QWEN_TIMEOUT: Integer seconds for LLM calls.
- GITHUB_TOKEN: Optional token to increase rate limits.
- GITHUB_TIMEOUT: Integer seconds for GitHub API calls.
- GITHUB_MAX_REPOS: Integer count of top repos to analyze.
- MAX_RESUME_MB: Float MB limit for uploads.
- MAX_RESUME_CHARS: Integer character limit for resume text.
- API_HOST: String host for the server.
- API_PORT: Integer port for the server.

Example configurations:
- Development:
  - Use local defaults for API_HOST and API_PORT.
  - Set DASHSCOPE_API_KEY and optionally GITHUB_TOKEN.
  - Keep QWEN_MODEL set to qwen-plus for balanced performance.
- Production:
  - Pin QWEN_BASE_URL to the appropriate regional endpoint.
  - Adjust QWEN_TIMEOUT and GITHUB_TIMEOUT based on network conditions.
  - Tune MAX_RESUME_MB and MAX_RESUME_CHARS to match capacity.
  - Ensure GITHUB_TOKEN is set to avoid rate limiting.

**Section sources**
- [config.py:11-20](file://src/config.py#L11-L20)
- [.env.example:10-50](file://.env.example#L10-L50)
- [.gitignore:1-2](file://.gitignore#L1-L2)

### Adding New Configuration Parameters
Steps:
1. Define a new attribute in Settings with a type hint and default value.
2. Map it to an environment variable using os.getenv with a sensible default.
3. Optionally add a helper function to validate presence or format.
4. Update .env.example to document the new variable.
5. Use config.settings.<new_attr> in relevant modules.

Guidelines:
- Prefer explicit casting for numeric types to enforce validity.
- Keep names uppercase and descriptive (e.g., NEW_SERVICE_TIMEOUT_SECONDS).
- Group related variables with comments for clarity.

**Section sources**
- [config.py:23-73](file://src/config.py#L23-L73)
- [.env.example:10-50](file://.env.example#L10-L50)

### Creating Environment-Specific Settings
Approaches:
- Use different .env files per environment (e.g., .env.development, .env.production) and load the appropriate one based on an environment flag.
- Or keep a single .env and switch values per deployment context.

Current behavior:
- The app loads a single .env from the project root at startup.

Recommendation:
- For multi-environment deployments, consider loading a specific .env file based on an environment variable (e.g., APP_ENV) and updating config.py accordingly.

**Section sources**
- [config.py:16-20](file://src/config.py#L16-L20)

### Implementing Configuration Validation Rules
Options:
- Extend Settings with validation methods to check ranges, formats, or required combinations.
- Raise explicit errors early if critical settings are missing or invalid.
- Use helper functions like is_qwen_configured() to expose readiness checks.

Examples:
- Validate numeric ranges (e.g., QWEN_TEMPERATURE between 0 and 2).
- Ensure required keys are present before starting the server.

**Section sources**
- [config.py:76-78](file://src/config.py#L76-L78)

### Debugging Tools for Configuration Issues
- Health endpoint:
  - GET /health reports app name, version, model, and whether Qwen/GitHub are configured.
- Error messages:
  - QwenError and GitHubError provide actionable details for misconfiguration.
- Logging:
  - Add logging around configuration reads to capture actual values during startup.

**Section sources**
- [main.py:45-55](file://src/main.py#L45-L55)
- [qwen_client.py:120-157](file://src/qwen_client.py#L120-L157)
- [github_service.py:48-60](file://src/github_service.py#L48-L60)

### Secure Credential Handling Practices
- Never hard-code secrets in source code.
- Store secrets in .env and ensure .env is listed in .gitignore.
- Use minimal permissions for tokens (e.g., GitHub token only needs public data access).
- Rotate secrets regularly and restrict access to production .env files.

**Section sources**
- [config.py:1-9](file://src/config.py#L1-L9)
- [.gitignore:1-2](file://.gitignore#L1-L2)
- [.env.example:10-8](file://.env.example#L10-L8)

### Environment Variable Naming Conventions
- Use uppercase, snake_case names.
- Prefix groupings logically (e.g., QWEN_*, GITHUB_*, MAX_*).
- Include units or scope in names when helpful (e.g., _TIMEOUT, _MB, _CHARS).

**Section sources**
- [.env.example:10-50](file://.env.example#L10-L50)
- [config.py:23-73](file://src/config.py#L23-L73)

### Hot-Reloading Capabilities
- Current setup starts uvicorn with reload=False.
- To enable hot-reloading during development, start uvicorn with reload=True; note that reloading re-imports modules and re-reads .env.

**Section sources**
- [main.py:150-159](file://src/main.py#L150-L159)