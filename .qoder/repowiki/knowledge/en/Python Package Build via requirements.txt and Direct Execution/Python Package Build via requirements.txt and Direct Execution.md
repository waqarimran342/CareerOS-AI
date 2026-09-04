---
kind: build_system
name: Python Package Build via requirements.txt and Direct Execution
category: build_system
scope:
    - '**'
source_files:
    - requirements.txt
    - .env.example
    - src/main.py
    - tests/test_pipeline.py
---

This repository uses a minimal, flat Python build system with no dedicated build tooling (no Makefile, Dockerfile, setup.py/pyproject.toml, or CI pipeline files present in the repository).

**What is used:**
- **Dependency management**: `requirements.txt` at the repository root declares all runtime dependencies (`fastapi`, `uvicorn[standard]`, `openai`, `python-dotenv`, `requests`, `pypdf`, `python-multipart`, `pydantic`). There is no lock file (e.g. `requirements.lock`, `poetry.lock`) and no dependency resolver configuration.
- **Environment isolation**: The README instructs users to create a local virtual environment via `python -m venv venv` and activate it before installing dependencies. A `.venv/` directory exists at the repo root, indicating per-repo virtual environments are the intended pattern.
- **Application entry point**: The service is started by directly invoking the Python script `python src/main.py`. No wrapper scripts, shell launchers, or process managers are included.
- **Configuration**: Runtime configuration is loaded from an `.env` file (copied from `.env.example`) using `python-dotenv`; no build-time config generation occurs.
- **Testing**: Tests are run directly with `pytest tests/ -v` (and optional coverage flags). There is no test harness script; pytest is expected to be installed as part of the dev workflow.
- **Frontend**: The web UI is a single static HTML file served by FastAPI under `src/static/index.html` — the README explicitly states "no build step" for the frontend.
- **Deployment**: The README describes deployment as "Any Python host (e.g. Alibaba Cloud ECS)" with no containerization, packaging, or release artifacts checked into the repo.

**Key files:**
- `requirements.txt` — sole dependency manifest
- `.env.example` — template for environment variables
- `src/main.py` — application entry point
- `tests/test_pipeline.py` — unit tests executed via pytest

**Architecture and conventions:**
- The project treats itself as a runnable Python package rather than a compiled artifact; there is no versioned wheel, sdist, or image produced by the repository itself.
- Versioning is not managed through any build metadata (no `__version__` in a module, no `setup.cfg`/`pyproject.toml`); version information appears only in documentation.
- The absence of CI configuration (no `.github/workflows/`, no `Jenkinsfile`, no `Dockerfile`) means builds, tests, and releases are performed ad hoc on developer machines.

**Conventions and constraints observed:**
- Dependencies are pinned implicitly by name only in `requirements.txt` (no `==` pins visible), so reproducible installs rely on pip's default resolution.
- Virtual environments are created per-repo under the workspace root (`venv/` or `.venv/`) rather than system-wide installs.
- Environment secrets are loaded from `.env` via `python-dotenv`; the template `.env.example` documents required keys (`DASHSCOPE_API_KEY`, `GITHUB_TOKEN`).
- Testing is invoked with pytest against the `tests/` directory; coverage targets are documented in the README (80%+ target) but not enforced by any automation.