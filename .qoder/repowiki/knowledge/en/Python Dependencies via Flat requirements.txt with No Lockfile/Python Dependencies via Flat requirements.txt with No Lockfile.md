---
kind: dependency_management
name: Python Dependencies via Flat requirements.txt with No Lockfile
category: dependency_management
scope:
    - '**'
source_files:
    - requirements.txt
    - README.md
    - .gitignore
---

## Dependency Management Approach

This repository uses a minimal Python dependency management setup based on `pip` and a single flat `requirements.txt` file at the project root.

### What is used
- **Package manager**: `pip` (invoked via `python -m venv` + `pip install -r requirements.txt`, as documented in README.md Quick Start).
- **Manifest**: `requirements.txt` lists runtime dependencies only — no dev/test-only packages, no extras beyond what is needed for the FastAPI server.
- **Virtual environment**: `.venv/` exists but is empty; the README instructs users to create their own `venv` locally. The virtual environment directory itself is not committed.
- **No lockfile**: There is no `requirements.lock`, `Pipfile.lock`, `poetry.lock`, `uv.lock`, or equivalent. Versions are not pinned.
- **No vendoring**: No `vendor/` directory or vendored third-party source code.
- **No private registry / index configuration**: No `setup.cfg`, `pyproject.toml`, `pip.conf`, or environment variables configuring alternate package indexes.

### Key files
- `requirements.txt` — the sole declaration of third-party packages: `fastapi`, `uvicorn[standard]`, `openai`, `python-dotenv`, `requests`, `pypdf`, `python-multipart`, `pydantic`.
- `README.md` — documents installation via `python -m venv venv` then `pip install -r requirements.txt`; also describes the tech stack (FastAPI + Uvicorn, Qwen via OpenAI-compatible API, PyPDF, GitHub REST API).
- `.gitignore` — excludes generated/installed artifacts so that only the manifest is versioned.

### Architecture and conventions observed
- **Flat list, no grouping**: All dependencies are listed top-level without comments or sections (e.g., no `[web]`, `[dev]`, `[test]` groups).
- **Loose version specifiers**: Packages are declared without version pins (e.g., `fastapi` rather than `fastapi==0.x.y`), meaning `pip` resolves the latest compatible version at install time.
- **Single optional extra**: Only `uvicorn[standard]` uses an optional feature group (`[standard]`) to pull in its recommended extras.
- **Runtime-only scope**: The manifest contains only runtime libraries; test tooling (`pytest`) is referenced in the README's testing section but is not listed in `requirements.txt`, implying it is expected to be installed separately by developers.
- **Environment-driven configuration**: Secrets and external service endpoints (Qwen/DashScope API key, GitHub token) are loaded via `python-dotenv` from a `.env` file (copied from `.env.example`); this keeps credentials out of the dependency graph entirely.

### Constraints and rules enforced by the repo
- **Install command is fixed**: The README prescribes `pip install -r requirements.txt` as the canonical way to install dependencies; no alternative toolchain (Poetry, Pipenv, uv, conda) is documented or configured.
- **Only `requirements.txt` is version-controlled**: The `.venv/` directory is ignored, so contributors must recreate their environments from the manifest — there is no shared lock to guarantee identical installs across machines.
- **No CI/build step pins versions**: There is no CI configuration visible in the tree that would pin or audit versions, so upgrades happen ad hoc when someone edits `requirements.txt`.

### Implications
- Reproducibility relies on each developer's local pip resolver and cache; two developers installing today may receive different transitive dependency versions.
- Adding a new dependency requires editing `requirements.txt` directly; there is no automated tooling (no `pip-tools`, `pip-compile`, Poetry, etc.) to generate or update a lockfile.
- Test-only dependencies are not captured in the manifest, which can cause test failures for contributors who do not already have `pytest` installed.